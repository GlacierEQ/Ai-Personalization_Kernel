# Supabase Connector

**Spec anchors:** master spec section 13.1 (Supabase / RootTruthStore) and section 14 (canonical
tables). Implements the [connector-plane contract](./CONNECTOR_PLANE.md).

## What it does

Projects the canonical JSONL ledger into a dedicated `apk` schema in Supabase via PostgREST:

| Kernel data | Supabase table |
| --- | --- |
| `data/preferences.jsonl` | `apk.preferences` |
| `data/successful_strategies.jsonl` + `data/failed_strategies.jsonl` | `apk.behavior_patterns` |
| `data/authority_rules.jsonl` | `apk.policy_rules` |
| `data/corrections.jsonl` | `apk.corrections` |
| `data/regression_cases.jsonl` | `apk.regression_cases` |
| `data/user_model.json` (one node per section) | `apk.user_model_nodes` |

Remaining section-14 tables (`user_model_edges`, `policy_events`, `project_states`,
`memory_sources`, `source_claims`, `resolutions`, `eval_runs`) are created by the migration and
filled by later phases.

## Setup

1. Apply the migration:

   ```bash
   psql "$DATABASE_URL" -f supabase/migrations/0001_control_plane.sql
   ```

   or paste it into the Supabase SQL editor. It is idempotent.

2. Expose the schema: Dashboard → Project Settings → API → **Exposed schemas** → add `apk`.
   The connector sends `Accept-Profile` / `Content-Profile: apk` headers, so `public` stays the
   default for everything else.

3. Store the **service role key** in an environment variable. The service role bypasses RLS; the
   migration enables RLS with no public policies, so anon/authenticated access is denied by
   default until you write explicit policies.

## Usage

```bash
# Dry-run: pure plan, zero network I/O
apk sync supabase --url https://<project>.supabase.co --dry-run

# Real sync: idempotent upserts + mandatory readback verification
export SUPABASE_SERVICE_ROLE_KEY=...   # never pass the key as a CLI argument
apk sync supabase --url https://<project>.supabase.co --key-env SUPABASE_SERVICE_ROLE_KEY
```

Programmatic:

```python
from apk.connectors import SupabaseConnector, build_rows_by_table

rows = build_rows_by_table("data/")
sink = SupabaseConnector.from_env(url, "SUPABASE_SERVICE_ROLE_KEY")
print(sink.plan(rows).to_dict())   # dry-run
report = sink.sync(rows)           # writes + verifies
```

## Guarantees

- **Idempotent.** Upsert on primary key with `Prefer: resolution=merge-duplicates`; a remote row
  whose `content_hash` matches is skipped. A second sync over unchanged data issues zero writes —
  verified by `test_sync_is_idempotent_on_second_run`.
- **Ordered.** Correction revisions land in chain order (`supersedes` targets first).
- **Verified.** After writes, the connector reads back every intended primary id and raises
  `SyncError` on any mismatch. `--no-verify` exists but is reported as unverified in the report.
- **Secret-safe.** The key is accepted only via env var and is scrubbed from errors and reports.
- **Resilient.** 429/5xx retried with exponential backoff + jitter, honoring `Retry-After`;
  terminal failures abort the sync loudly.

## What it deliberately does not do

- **No reads-as-truth.** Supabase rows are projections. If the ledger and Supabase disagree, the
  ledger wins; re-run the sync.
- **No hidden tables.** Only the six mapped tables are written; the rest await their phase.
- **No key material in the repo, CLI args, reports, or exceptions.**
