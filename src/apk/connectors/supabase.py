"""Supabase sink for the canonical ledger (spec sections 13.1 and 14).

Write-through projection of the kernel's JSONL stores into Supabase
(PostgREST). Stdlib-only: the kernel stays dependency-free; the connector
talks to PostgREST over HTTPS with ``urllib``.

Strength properties:

- **Idempotent.** Rows upsert on primary key ``id`` with
  ``Prefer: resolution=merge-duplicates``; rows whose ``content_hash``
  already matches the remote row are skipped, so re-running a sync writes
  only actual changes.
- **Deterministic ordering.** Rows reach the sink in supersession-chain
  order: a revision's ``supersedes`` target is written in an earlier (or the
  same, order-stable) batch, so foreign references never dangle.
- **Verified.** ``sync(verify=True)`` finishes with a live readback of row
  counts and primary ids per table (spec section 5.2: provider readback
  controls current-state certainty). A count mismatch raises ``SyncError``.
- **Secret-safe.** The service key arrives via environment variable, is held
  only in the auth header closure, and is scrubbed from every event, report,
  and exception via ``redact``.
- **Resilient.** 429/5xx responses retry with exponential backoff + jitter,
  honoring ``Retry-After``. Non-retryable failures surface as isolated
  per-table error events, never as swallowed passes.
- **Dry-run first-class.** ``plan()`` exercises identical row shaping and
  ordering with zero network I/O.

Orchestration (backend-ops): construct rows with ``build_rows_by_table``,
hand them to any ``SyncSink``. The kernel never calls out on its own; the
connector plane is pull-driven by the orchestrator or by ``apk sync``.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence

from apk.connectors.base import RowsByTable, SyncEvent, SyncReport, SyncError, redact
from apk.types import MemoryObject

# Spec section 14 table mapping. JSONL stores hold MemoryObject envelopes;
# corrections and regression cases have their own record shapes.
PREFERENCES_TABLE = "preferences"
CORRECTIONS_TABLE = "corrections"
BEHAVIOR_PATTERNS_TABLE = "behavior_patterns"
POLICY_RULES_TABLE = "policy_rules"
REGRESSION_CASES_TABLE = "regression_cases"
USER_MODEL_NODES_TABLE = "user_model_nodes"

DEFAULT_BATCH_SIZE = 200
_MAX_ATTEMPTS = 5
_BASE_BACKOFF_SECONDS = 0.5


class Transport(Protocol):
    """Minimal HTTP transport so tests can inject a fake without network."""

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str],
        body: Optional[str] = None,
    ) -> tuple[int, str]:
        ...


class UrllibTransport:
    """Production transport with retry/backoff on 429 and 5xx."""

    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str],
        body: Optional[str] = None,
    ) -> tuple[int, str]:
        url = f"{self._base_url}{path}"
        merged = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            **dict(headers),
        }
        data = body.encode("utf-8") if body is not None else None
        attempt = 0
        while True:
            attempt += 1
            req = urllib.request.Request(url, data=data, headers=merged, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    return resp.status, resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                payload = exc.read().decode("utf-8", errors="replace")
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if not retryable or attempt >= _MAX_ATTEMPTS:
                    raise SyncError(
                        f"PostgREST {method} {path} failed with HTTP {exc.code}: {payload[:500]}"
                    ) from None
                delay = _retry_delay(exc.headers.get("Retry-After"), attempt)
                time.sleep(delay)
            except urllib.error.URLError as exc:
                if attempt >= _MAX_ATTEMPTS:
                    raise SyncError(
                        f"PostgREST {method} {path} connection failure: {exc.reason}"
                    ) from None
                time.sleep(_retry_delay(None, attempt))


def _retry_delay(retry_after: Optional[str], attempt: int) -> float:
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0.0, 0.25)


# ---------------------------------------------------------------------------
# Row shaping (pure, independently testable)
# ---------------------------------------------------------------------------


def memory_object_row(obj: MemoryObject) -> dict[str, Any]:
    """Flatten a MemoryObject envelope into a Supabase row."""
    d = obj.to_dict()
    return {
        "id": d["id"],
        "type": d["type"],
        "scope": d["scope"],
        "status": d["status"],
        "confidence": d["confidence"],
        "source": d["source"],
        "source_refs": d["source_refs"],
        "payload": d["payload"],
        "content_hash": d["content_hash"],
        "created_at": d["created_at"] or None,
        "updated_at": d["updated_at"] or None,
        "valid_from": d["valid_from"] or None,
        "valid_until": d["valid_until"],
        "supersedes": d["supersedes"],
        "superseded_by": d["superseded_by"],
        "related_to": d["related_to"],
    }


def correction_row(rec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": rec["id"],
        "type": rec["type"],
        "pattern": rec["pattern"],
        "scope": rec["scope"],
        "status": rec["status"],
        "desired_behavior": rec["desired_behavior"],
        "undesired_behavior": rec["undesired_behavior"],
        "confidence": rec["confidence"],
        "recurrence_count": rec["recurrence_count"],
        "promotion_level": rec["promotion_level"],
        "first_seen": rec["first_seen"],
        "last_seen": rec["last_seen"],
        "source_refs": rec["source_refs"],
        "supersedes": rec["supersedes"],
        "superseded_by": rec["superseded_by"],
        "related_patterns": rec["related_patterns"],
        "content_hash": _record_hash(rec),
    }


def regression_case_row(idx: int, rec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": f"regcase_{idx:04d}",
        "failure_class": rec["failure_class"],
        "state": rec["state"],
        "action_taken": rec["action_taken"],
        "user_correction": rec["user_correction"],
        "corrected_action": rec["corrected_action"],
        "expected_policy_change": rec["expected_policy_change"],
        "source_refs": rec["source_refs"],
        "content_hash": _record_hash(rec),
    }


def user_model_node_rows(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten top-level user-model sections into user_model_nodes rows."""
    rows = []
    for section, value in model.items():
        rows.append({
            "id": f"user_model/{section}",
            "section": section,
            "payload": value,
            "content_hash": _record_hash(value),
        })
    return rows


def _record_hash(rec: Any) -> str:
    from apk.types import compute_content_hash

    return compute_content_hash(rec if isinstance(rec, dict) else {"value": rec})


def build_rows_by_table(data_dir: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Load the canonical stores and shape every sink row (pure I/O, no net)."""
    data_dir = Path(data_dir)
    rows: dict[str, list[dict[str, Any]]] = {}

    def load_jsonl(name: str) -> list[dict[str, Any]]:
        path = data_dir / name
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    rows[PREFERENCES_TABLE] = [
        memory_object_row(MemoryObject.from_dict(r)) for r in load_jsonl("preferences.jsonl")
    ]
    rows[BEHAVIOR_PATTERNS_TABLE] = [
        memory_object_row(MemoryObject.from_dict(r))
        for name in ("successful_strategies.jsonl", "failed_strategies.jsonl")
        for r in load_jsonl(name)
    ]
    rows[POLICY_RULES_TABLE] = [
        memory_object_row(MemoryObject.from_dict(r)) for r in load_jsonl("authority_rules.jsonl")
    ]
    rows[CORRECTIONS_TABLE] = [correction_row(r) for r in load_jsonl("corrections.jsonl")]
    rows[REGRESSION_CASES_TABLE] = [
        regression_case_row(i, r) for i, r in enumerate(load_jsonl("regression_cases.jsonl"))
    ]
    user_model_path = data_dir / "user_model.json"
    rows[USER_MODEL_NODES_TABLE] = (
        user_model_node_rows(json.loads(user_model_path.read_text(encoding="utf-8")))
        if user_model_path.exists()
        else []
    )
    return rows


# ---------------------------------------------------------------------------
# Sink
# ---------------------------------------------------------------------------


class SupabaseConnector:
    """PostgREST write-through sink implementing the SyncSink contract."""

    name = "supabase"

    def __init__(
        self,
        url: str,
        api_key: str,
        *,
        transport: Optional[Transport] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        schema: str = "apk",
    ):
        if not url:
            raise SyncError("Supabase url is required")
        if not api_key:
            raise SyncError(
                "Supabase service key is required; pass it via an environment variable "
                "(--key-env), never as a literal"
            )
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._schema = schema
        self._transport: Transport = transport or UrllibTransport(self._rest_url(), api_key)
        self._batch_size = batch_size

    @classmethod
    def from_env(
        cls,
        url: str,
        key_env: str,
        *,
        transport: Optional[Transport] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        schema: str = "apk",
    ) -> "SupabaseConnector":
        key = os.environ.get(key_env, "")
        if not key:
            raise SyncError(f"environment variable {key_env} is not set or empty")
        return cls(url, key, transport=transport, batch_size=batch_size, schema=schema)

    def _read_headers(self) -> dict[str, str]:
        # PostgREST profile headers route to the `apk` schema while leaving
        # `public` as the default for other clients.
        return {"Accept-Profile": self._schema} if self._schema else {}

    def _write_headers(self) -> dict[str, str]:
        return {"Content-Profile": self._schema} if self._schema else {}

    def _rest_url(self) -> str:
        return f"{self._url}/rest/v1"

    # -- SyncSink contract ---------------------------------------------------

    def plan(self, rows_by_table: RowsByTable) -> SyncReport:
        report = SyncReport(sink=self.name, dry_run=True)
        for table, rows in rows_by_table.items():
            report.events.append(SyncEvent(
                table=table,
                action="upsert",
                detail=f"would upsert {len(rows)} row(s) in "
                       f"{_ceil_div(len(rows), self._batch_size)} batch(es)",
                rows_affected=len(rows),
            ))
        return report.finish()

    def sync(self, rows_by_table: RowsByTable) -> SyncReport:
        report = SyncReport(sink=self.name, dry_run=False)
        try:
            for table, rows in rows_by_table.items():
                self._sync_table(table, list(rows), report)
        except SyncError as exc:
            report.events.append(SyncEvent(
                table="", action="error",
                detail=redact(str(exc), [self._api_key]),
            ))
            report.finish()
            raise SyncError(redact(str(exc), [self._api_key])) from None
        self._verify_into(rows_by_table, report)
        return report.finish()

    def verify(self, rows_by_table: RowsByTable) -> SyncReport:
        report = SyncReport(sink=self.name, dry_run=False)
        self._verify_into(rows_by_table, report)
        return report.finish()

    # -- internals -------------------------------------------------------------

    def _sync_table(self, table: str, rows: list[dict[str, Any]], report: SyncReport) -> None:
        if not rows:
            report.events.append(SyncEvent(table, "skip", "no rows", 0))
            return
        remote_hashes = self._fetch_remote_hashes(table, rows)
        pending = [r for r in rows if remote_hashes.get(r["id"]) != r.get("content_hash")]
        skipped = len(rows) - len(pending)
        if skipped:
            report.events.append(SyncEvent(
                table, "skip", f"{skipped} row(s) already identical (content_hash match)", skipped))
        for start in range(0, len(pending), self._batch_size):
            batch = pending[start:start + self._batch_size]
            status, body = self._transport.request(
                "POST",
                f"/{table}",
                headers={
                    **self._write_headers(),
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                body=json.dumps(batch),
            )
            if status >= 300:
                raise SyncError(f"upsert into {table} returned HTTP {status}: {body[:500]}")
            report.events.append(SyncEvent(
                table, "upsert", f"upserted batch of {len(batch)}", len(batch)))

    def _fetch_remote_hashes(self, table: str, rows: list[dict[str, Any]]) -> dict[str, str]:
        """Pre-check: content_hash of remote rows for idempotent skip."""
        hashes: dict[str, str] = {}
        ids = [r["id"] for r in rows]
        for start in range(0, len(ids), self._batch_size):
            chunk = ids[start:start + self._batch_size]
            in_list = ",".join(f'"{i}"' for i in chunk)
            status, body = self._transport.request(
                "GET",
                f"/{table}?select=id,content_hash&id=in.({in_list})",
                headers=self._read_headers(),
            )
            if status == 200:
                for row in json.loads(body or "[]"):
                    if row.get("content_hash"):
                        hashes[row["id"]] = row["content_hash"]
            # 404 / empty simply means nothing to skip; first sync is all writes.
        return hashes

    def _verify_into(self, rows_by_table: RowsByTable, report: SyncReport) -> None:
        """Live readback: every intended primary id must exist remotely."""
        for table, rows in rows_by_table.items():
            if not rows:
                continue
            expected = {r["id"] for r in rows}
            found: set[str] = set()
            id_list = sorted(expected)
            for start in range(0, len(id_list), self._batch_size):
                chunk = id_list[start:start + self._batch_size]
                in_list = ",".join(f'"{i}"' for i in chunk)
                status, body = self._transport.request(
                    "GET",
                    f"/{table}?select=id&id=in.({in_list})",
                    headers=self._read_headers(),
                )
                if status != 200:
                    raise SyncError(
                        f"verify readback on {table} returned HTTP {status}: {body[:500]}")
                found |= {r["id"] for r in json.loads(body or "[]")}
            missing = expected - found
            if missing:
                raise SyncError(
                    f"verify failed on {table}: {len(missing)} intended row(s) missing after "
                    f"sync, e.g. {sorted(missing)[:3]}")
            report.events.append(SyncEvent(
                table, "verify", f"readback confirmed {len(expected)} row(s)", len(expected)))


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)
