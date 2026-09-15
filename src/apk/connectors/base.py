"""Connector-plane primitives (spec section 13 / section 18.12).

The kernel owns the canonical JSONL ledger. Sinks (Supabase, future Mem0 /
Notion / vector indexes) are *projections* of that ledger, never independent
sources of truth. ``backend-ops`` (or any orchestrator) drives sinks through
the ``SyncSink`` protocol; every sink must implement:

- ``plan(rows_by_table)`` — a pure, network-free description of what a sync
  would do (dry-run is a first-class path, not a flag that skips checks);
- ``sync(rows_by_table)`` — idempotent write-through keyed on primary id +
  ``content_hash`` (rewriting identical bytes is a no-op, not a write);
- ``verify(rows_by_table)`` — live provider readback. A sync that has not
  been verified by readback is not complete (spec section 5.2).

Hidden-harm guards required of every sink:

- secrets enter via environment variables, never constructor literals, and
  must never appear in events, reports, logs, or exception messages;
- per-record failures are isolated and reported, never silently swallowed;
- ordering is explicit: records are written in supersession-chain order so a
  row's ``supersedes`` target already exists when the row lands.
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Sequence

# A table name mapped to the rows destined for it. Rows are plain dicts whose
# first key is the primary id; all shaping happens before the sink is called.
RowsByTable = Mapping[str, Sequence[dict[str, Any]]]


@dataclass(frozen=True)
class SyncEvent:
    """One auditable unit of a sync run."""

    table: str
    action: str  # "upsert" | "skip" | "verify" | "error"
    detail: str
    rows_affected: int = 0


@dataclass
class SyncReport:
    """Result of a sync run. ``ok`` is False if any event is an error."""

    sink: str
    dry_run: bool
    events: list[SyncEvent] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def finish(self) -> "SyncReport":
        self.finished_at = time.time()
        return self

    @property
    def ok(self) -> bool:
        return not any(e.action == "error" for e in self.events)

    @property
    def upserted(self) -> int:
        return sum(e.rows_affected for e in self.events if e.action == "upsert")

    @property
    def skipped(self) -> int:
        return sum(e.rows_affected for e in self.events if e.action == "skip")

    @property
    def errors(self) -> list[SyncEvent]:
        return [e for e in self.events if e.action == "error"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sink": self.sink,
            "dry_run": self.dry_run,
            "ok": self.ok,
            "upserted": self.upserted,
            "skipped": self.skipped,
            "error_count": len(self.errors),
            "duration_seconds": (
                round((self.finished_at or time.time()) - self.started_at, 3)
            ),
            "events": [dataclasses.asdict(e) for e in self.events],
        }


class SyncError(RuntimeError):
    """Raised when a sync cannot proceed or verification fails."""


class SyncSink(Protocol):
    """Contract every connector-plane sink must satisfy."""

    name: str

    def plan(self, rows_by_table: RowsByTable) -> SyncReport:
        """Pure dry-run: describe intended writes without any side effects."""
        ...

    def sync(self, rows_by_table: RowsByTable) -> SyncReport:
        """Idempotent write-through. Must be safe to run repeatedly."""
        ...

    def verify(self, rows_by_table: RowsByTable) -> SyncReport:
        """Live readback: confirm the provider state matches intended rows."""
        ...


def redact(text: str, secrets: Sequence[Optional[str]]) -> str:
    """Remove any occurrence of a secret from a string before surfacing it."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return text
