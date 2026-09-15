"""Tests for the Supabase connector-plane sink.

All network I/O is faked through the Transport protocol; these tests verify
idempotency, ordering, retry, verification, and secret hygiene.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Optional

import pytest

from apk.connectors.base import SyncError
from apk.connectors.supabase import (
    SupabaseConnector,
    build_rows_by_table,
    correction_row,
    user_model_node_rows,
)

SECRET = "s3cr3t-service-key-do-not-leak"


class FakeTransport:
    """Scriptable in-memory PostgREST stand-in."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.tables: dict[str, dict[str, dict]] = {}
        self.fail_next: list[int] = []  # HTTP codes to return for next N writes

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str],
        body: Optional[str] = None,
    ) -> tuple[int, str]:
        self.calls.append({"method": method, "path": path,
                           "headers": dict(headers), "body": body})
        table, _, query = path.lstrip("/").partition("?")
        store = self.tables.setdefault(table, {})
        if method == "POST":
            if self.fail_next:
                return self.fail_next.pop(0), '{"message":"boom"}'
            for row in json.loads(body or "[]"):
                store[row["id"]] = row
            return 201, ""
        if method == "GET":
            wanted = None
            if "id=in.(" in query:
                inside = query.split("id=in.(", 1)[1].rstrip(")")
                wanted = {i.strip('"') for i in inside.split(",")}
            rows = [r for rid, r in store.items() if wanted is None or rid in wanted]
            if "select=id,content_hash" in query:
                rows = [{"id": r["id"], "content_hash": r.get("content_hash")} for r in rows]
            elif "select=id" in query:
                rows = [{"id": r["id"]} for r in rows]
            return 200, json.dumps(rows)
        raise AssertionError(f"unexpected method {method}")


@pytest.fixture()
def rows_by_table(tmp_data_dir: Path):
    return build_rows_by_table(tmp_data_dir)


def test_build_rows_covers_all_mapped_tables(rows_by_table) -> None:
    assert set(rows_by_table) == {
        "preferences",
        "behavior_patterns",
        "policy_rules",
        "corrections",
        "regression_cases",
        "user_model_nodes",
    }
    # 6 preferences, 2 successful + 5 failed strategies, 5 authority rules,
    # 11 correction revisions, 5 regression cases, 12 user-model sections.
    assert len(rows_by_table["preferences"]) == 6
    assert len(rows_by_table["behavior_patterns"]) == 7
    assert len(rows_by_table["policy_rules"]) == 5
    assert len(rows_by_table["corrections"]) == 11
    assert len(rows_by_table["regression_cases"]) == 5
    assert len(rows_by_table["user_model_nodes"]) == 12


def test_correction_row_preserves_chain_provenance() -> None:
    rec = {
        "id": "corr_x", "type": "behavior_correction", "pattern": "p",
        "scope": "global", "status": "active",
        "desired_behavior": "d", "undesired_behavior": "u",
        "confidence": 1.0, "recurrence_count": 2,
        "promotion_level": "strong_preference",
        "first_seen": "t0", "last_seen": "t1",
        "source_refs": ["b", "a"], "supersedes": ["corr_prev"],
        "superseded_by": [], "related_patterns": [],
    }
    row = correction_row(rec)
    assert row["supersedes"] == ["corr_prev"]
    assert row["source_refs"] == ["b", "a"]  # ledger order preserved, not resorted
    assert row["content_hash"]


def test_user_model_nodes_flatten_sections() -> None:
    rows = user_model_node_rows({"identity": {"role": "architect"}, "prohibitions": ["x"]})
    assert {r["id"] for r in rows} == {"user_model/identity", "user_model/prohibitions"}
    assert all(r["content_hash"] for r in rows)


def test_plan_is_network_free(rows_by_table) -> None:
    transport = FakeTransport()
    connector = SupabaseConnector(
        "https://example.supabase.co", SECRET, transport=transport)
    report = connector.plan(rows_by_table)
    assert report.ok and report.dry_run
    assert transport.calls == [], "plan() must not touch the network"
    assert report.upserted == sum(len(r) for r in rows_by_table.values())


def test_sync_upserts_then_verifies(rows_by_table) -> None:
    transport = FakeTransport()
    connector = SupabaseConnector(
        "https://example.supabase.co", SECRET, transport=transport)
    report = connector.sync(rows_by_table)
    assert report.ok
    posts = [c for c in transport.calls if c["method"] == "POST"]
    assert posts, "sync must write"
    for call in posts:
        assert "resolution=merge-duplicates" in call["headers"]["Prefer"]
        assert call["headers"]["Content-Profile"] == "apk"
    verifies = [e for e in report.events if e.action == "verify"]
    assert len(verifies) == 6
    # Remote state matches intended rows after sync.
    for table, rows in rows_by_table.items():
        assert set(transport.tables[table]) == {r["id"] for r in rows}


def test_sync_is_idempotent_on_second_run(rows_by_table) -> None:
    transport = FakeTransport()
    connector = SupabaseConnector(
        "https://example.supabase.co", SECRET, transport=transport)
    connector.sync(rows_by_table)
    calls_before = len(transport.calls)
    report = connector.sync(rows_by_table)
    posts_after = [c for c in transport.calls[calls_before:] if c["method"] == "POST"]
    assert posts_after == [], "identical second sync must issue zero writes"
    assert report.skipped == sum(len(r) for r in rows_by_table.values())


def test_sync_writes_only_changed_rows(rows_by_table) -> None:
    transport = FakeTransport()
    connector = SupabaseConnector(
        "https://example.supabase.co", SECRET, transport=transport)
    connector.sync(rows_by_table)
    changed = dict(rows_by_table["preferences"][0])
    changed["payload"] = {**changed["payload"], "description": "revised"}
    changed["content_hash"] = "different-hash"
    rows_by_table["preferences"] = [changed] + rows_by_table["preferences"][1:]
    report = connector.sync(rows_by_table)
    pref_posts = [
        c for c in transport.calls
        if c["method"] == "POST" and c["path"].startswith("/preferences")
    ]
    written = json.loads(pref_posts[-1]["body"])
    assert len(written) == 1 and written[0]["id"] == changed["id"]
    assert report.ok


def test_transport_failure_aborts_sync_cleanly(rows_by_table) -> None:
    transport = FakeTransport()
    transport.fail_next = [500]
    connector = SupabaseConnector(
        "https://example.supabase.co", SECRET, transport=transport)
    # UrllibTransport owns retry/backoff; the sink must surface a terminal
    # transport failure as a clean SyncError, not a partial-success report.
    def failing(method, path, *, headers, body=None):
        return 500, '{"message":"boom"}'

    transport.request = failing  # type: ignore[assignment]
    with pytest.raises(SyncError):
        connector.sync(rows_by_table)


def test_verify_detects_missing_rows(rows_by_table) -> None:
    transport = FakeTransport()
    connector = SupabaseConnector(
        "https://example.supabase.co", SECRET, transport=transport)
    connector.sync(rows_by_table)
    victim = rows_by_table["preferences"][0]["id"]
    del transport.tables["preferences"][victim]
    with pytest.raises(SyncError) as excinfo:
        connector.verify(rows_by_table)
    assert "verify failed" in str(excinfo.value)


def test_secret_never_leaks_into_errors(rows_by_table) -> None:
    class LeakyTransport:
        def request(self, method, path, *, headers, body=None):
            raise SyncError(f"auth failed for key {SECRET}")

    connector = SupabaseConnector(
        "https://example.supabase.co", SECRET, transport=LeakyTransport())
    with pytest.raises(SyncError) as excinfo:
        connector.sync(rows_by_table)
    assert SECRET not in str(excinfo.value)
    assert "<redacted>" in str(excinfo.value)


def test_missing_env_key_is_an_error() -> None:
    with pytest.raises(SyncError):
        SupabaseConnector.from_env("https://example.supabase.co", "APK_NO_SUCH_ENV")


def test_empty_constructor_args_rejected() -> None:
    with pytest.raises(SyncError):
        SupabaseConnector("", SECRET, transport=FakeTransport())
    with pytest.raises(SyncError):
        SupabaseConnector("https://example.supabase.co", "", transport=FakeTransport())
