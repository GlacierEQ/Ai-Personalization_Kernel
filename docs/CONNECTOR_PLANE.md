# Connector Plane

**Status:** active contract
**Spec anchors:** master spec sections 13 (External Memory Mesh) and 18.12 (cross-store write-through)

## Principle

The kernel's JSONL ledger under `data/` is the **only canonical truth**. Every external store is a
**projection**: a write-through sink that may serve reads, dashboards, or semantic recall, but never
overrides the ledger.

```text
JSONL ledger (canonical, append-only, provenance-hashed)
        |
        |  build_rows_by_table()      <- pure shaping, no I/O
        v
   SyncSink.plan()   -> dry-run report, zero network
   SyncSink.sync()   -> idempotent write-through
   SyncSink.verify() -> live provider readback (required for completion)
        |
        +--> Supabase (canonical SQL projection)      [implemented]
        +--> vector recall / Mem0                     [future sink]
        +--> Notion / Airtable dashboards             [future sink]
```

## The SyncSink contract

Every sink implements three operations (see `src/apk/connectors/base.py`):

1. **`plan(rows)`** — pure. Same row shaping and ordering as a real sync, no network. Dry-run is a
   first-class path, not a flag that skips checks.
2. **`sync(rows)`** — idempotent write-through. Primary-key upsert; `content_hash` match means skip,
   not rewrite. Re-running a sync over unchanged data issues **zero writes**.
3. **`verify(rows)`** — live readback. Per spec section 5.2, provider readback controls current-state
   certainty: a sync that has not been read back is not complete.

### Non-negotiable sink rules

- **Secrets by environment only.** Keys arrive via env vars (`--key-env`), never literals, and are
  scrubbed from every event, report, and exception (`redact`).
- **Ordering.** Rows are emitted in supersession-chain order so a row's `supersedes` target already
  exists when it lands.
- **Isolated failure.** A per-table failure is an error event and aborts loudly; nothing is
  swallowed, nothing half-reports success.
- **No silent truth claims.** Sinks never claim state they have not read back.

## Role of backend-ops

`backend-ops` is the **orchestrator**: it pulls rows from the kernel, drives sinks through the
contract above, schedules recurring syncs, and records `policy_events` / `eval_runs` back into the
ledger. The kernel stays dependency-free and never calls out on its own; the connector plane is
pull-driven.

An orchestrator integration looks like:

```python
from apk.connectors import SupabaseConnector, build_rows_by_table

rows = build_rows_by_table("data/")
sink = SupabaseConnector.from_env(url, "SUPABASE_SERVICE_ROLE_KEY")
report = sink.sync(rows)          # plan() first for dry-run; sync() verifies by default
assert report.ok, report.to_dict()
```

## Implemented sinks

| Sink | Module | Status |
| --- | --- | --- |
| Supabase (PostgREST) | `apk.connectors.supabase` | Implemented — see [SUPABASE_CONNECTOR.md](./SUPABASE_CONNECTOR.md) |
