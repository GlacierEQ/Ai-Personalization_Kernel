# Ai-Personalization_Kernel

**An executable personalization-to-behavior binding layer.**

> The user model is always active. Deeper retrieval is selective; personalization itself is not optional.

[![CI](https://github.com/GlacierEQ/Ai-Personalization_Kernel/actions/workflows/ci.yml/badge.svg)](https://github.com/GlacierEQ/Ai-Personalization_Kernel/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

---

## What this is

Ai-Personalization_Kernel is a small, dependency-free Python kernel that makes durable user
state part of the **decision policy** that determines what an assistant does next — instead of
leaving personalization as optional, retrievable-but-ignorable context.

It is the executable counterpart to the [master control-plane specification](./docs/ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md)
and its companion documents:

- [`docs/ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md`](./docs/ACCOUNT_PERSONALIZATION_CONTROL_PLANE.md) — governing architecture and 18 global invariants
- [`docs/USER_AUTHORITY_MODEL.md`](./docs/USER_AUTHORITY_MODEL.md) — directional vs. factual authority
- [`docs/PERSONALIZATION_RETRIEVAL_POLICY.md`](./docs/PERSONALIZATION_RETRIEVAL_POLICY.md) — the 9-tier retrieval cascade
- [`docs/CORRECTION_PROMOTION_POLICY.md`](./docs/CORRECTION_PROMOTION_POLICY.md) — correction records and the promotion ladder
- [`docs/PERSONALIZATION_REGRESSION_SUITE.md`](./docs/PERSONALIZATION_REGRESSION_SUITE.md) — experience replay and telemetry metrics

## The core problem: instruction displacement

A system can possess explicit user preferences, synthesized cross-chat memories, current
instructions, project state, and a full correction history — and still choose a generic action
path that ignores all of it. That defect is **personalization-to-behavior binding failure**, also
called **instruction displacement**:

> User-specific state is present or retrievable, but generic model priors, local heuristics, or
> routing decisions displace it as the actual objective controlling behavior.

The fix is not "store more memory." It is to make durable user state a first-class input to
**action selection**, with real, auditable, numeric enforcement — not a hope that a summary in a
system prompt gets read.

## Architecture

```text
CURRENT USER MESSAGE
        |
        v
ALWAYS-ACTIVE USER MODEL
        |
        +--> identity / expertise / roles
        +--> durable preferences
        +--> explicit prohibitions
        +--> epistemic preferences
        +--> authority relationships
        +--> active goals / projects
        +--> correction history
        +--> prior successful strategies
        +--> prior failed strategies
        +--> continuity state
        |
        v
CONTEXT / STATE ROUTER
        |
        +--> recent exact conversation
        +--> relevant historical chats
        +--> native ChatGPT memory
        +--> files / library
        +--> project state
        +--> connected apps
        +--> external memory mesh
        +--> live provider state
        |
        v
POLICY STATE ASSEMBLER
        |
        v
ACTION POLICY
        |
        +--> retrieve
        +--> inspect
        +--> continue
        +--> execute
        +--> verify
        +--> answer
        |
        v
OUTCOME + USER REACTION + RECEIPTS
        |
        v
CORRECTION / REWARD CLASSIFIER
        |
        +--> update structured user model
        +--> update correction ledger
        +--> promote repeated rules
        +--> update regression corpus
        +--> preserve source/provenance
        |
        v
NEXT TURN
```

Each box in this diagram maps to a real, tested module in `src/apk/` — see the module map below.

## Quickstart

```bash
git clone https://github.com/GlacierEQ/Ai-Personalization_Kernel.git
cd Ai-Personalization_Kernel
pip install -e .[dev]

# Validate all bundled seed data against its JSON Schema
python scripts/validate_schemas.py

# Run the 12-step boot contract against the bundled demo user model + corrections
apk boot --demo

# Replay the regression corpus against the current policy (CI hard gate)
apk replay --cases data/regression_cases.jsonl

# Verify seed data is generator-canonical (drift gate)
python scripts/generate_seed_data.py --check

# Dry-run a Supabase sync (zero network); real sync writes + verifies by readback
apk sync supabase --url https://<project>.supabase.co --dry-run

# Run the full test suite
pytest -q
```

## Module map

| Module | Responsibility |
| --- | --- |
| `apk.types` | `MemoryObject` — the 24-type typed memory envelope, validated, content-hashed |
| `apk.store` | `JsonlStore` — append-only ledger; atomic writes; provenance-preserving dedup |
| `apk.user_model` | `UserModel` — mandatory always-active compact model loader |
| `apk.authority` | `AuthorityResolver` — per-claim-type factual authority + conflict resolution |
| `apk.router` | `RetrievalRouter` — 9-tier retrieval cascade, trigger-gated deep retrieval, anti-recursion guard |
| `apk.policy` | `PolicyEngine` — candidate action scoring; the binding enforcement layer |
| `apk.corrections` | `CorrectionLedger` / `PromotionEngine` — recurrence detection + 5-stage promotion ladder |
| `apk.supersession` | `SupersessionResolver` — supersede/resolve/reopen with provenance-preserving invariants |
| `apk.reward` | `RewardModel` — the section-10 reward/penalty scoring table with recurrence scaling |
| `apk.replay` | `ExperienceReplay` — regression corpus replay, the CI hard gate against regressions |
| `apk.drift` | `DriftDetector` — diff two policy/user-model states with content hashes |
| `apk.boot` | `BootContract` — the 12-step boot sequence orchestrator, producing an auditable `BootReceipt` |
| `apk.cli` | `apk` console script: `validate`, `replay`, `boot`, `metrics` |

| `apk.connectors` | Connector plane: `SyncSink` contract (plan / sync / verify), sink-agnostic |
| `apk.connectors.supabase` | Idempotent, verified Supabase write-through (PostgREST, stdlib-only) |
## Enforcement philosophy

This repository explicitly rejects "smallest usable" placeholder implementations. Every module
listed above is:

1. **Functional**, not a stub — `PolicyEngine.score_action` actually computes a different number
   when a correction, preference, or displacement condition applies; it does not return a fixed
   sentinel.
2. **Numerically auditable** — every scored action carries a full breakdown of every adjustment
   applied to it (`ScoredAction.adjustments`), so *why* an action ranked where it did is always
   inspectable, not just the final number.
3. **Tested against regression cases** — `tests/test_policy_binding.py` is the enforcement suite:
   it proves that corrections demote their undesired behavior (scaling with recurrence and
   promotion level), that invariant-level corrections hard-block their target action, that known
   preferences boost aligned actions, and that instruction displacement (answering before
   retrieving known-relevant context) is structurally impossible to rank first.
4. **CI-gated** — `apk replay --cases data/regression_cases.jsonl` is a hard merge gate. A policy
   change that reintroduces a previously corrected failure fails the build, full stop.

If a future contribution touches `policy.py`, `corrections.py`, or `authority.py` without adding
or updating a regression case, that is a defect in the contribution, not an acceptable shortcut.

## The 18 global invariants

1. Personalization is always active.
2. Deep retrieval is selective; the user model is not.
3. The user does not need to prove relevance before context is considered.
4. Repeated corrections change policy state.
5. A correction that recurs across domains is presumptively systemic.
6. User intent is not overwritten by web search.
7. Firsthand user observation is not silently replaced by third-party summaries.
8. Source factual authority is not project-direction authority.
9. Historical context should be reconciled, not blindly replayed.
10. Resolved issues must not be reopened merely because an older memory says unresolved.
11. Supersession preserves provenance.
12. Recover before recreating.
13. Continue before reconstructing.
14. Compound before replacing.
15. Context first, hard work second, answer last.
16. Regression failures become training/evaluation cases.
17. The system learns successful strategies as well as prohibitions.
18. Generic assistant habits are subordinate to explicit non-conflicting user direction.

## Data layout

```text
schemas/    JSON Schema (2020-12) for every persisted record shape
data/       Seed ledger: user_model.json, corrections.jsonl, preferences.jsonl,
            successful_strategies.jsonl, failed_strategies.jsonl,
            authority_rules.jsonl, regression_cases.jsonl, policy_weights.json
src/apk/    The kernel itself
tests/      pytest suite, including the enforcement suite
scripts/    validate_schemas.py — CI schema gate;
            generate_seed_data.py — single source of truth for data/ (CI drift gate)
supabase/   migrations/0001_control_plane.sql — canonical section-14 schema (idempotent)
```

All seed data uses a generic example "software architect" operator persona — no real personal
data is bundled with this repository.

## Connector plane & Supabase

The JSONL ledger is canonical; external stores are verified projections. The connector plane
(`apk.connectors`, contract in [`docs/CONNECTOR_PLANE.md`](./docs/CONNECTOR_PLANE.md)) is the seam
an orchestrator such as `backend-ops` drives:

- **`plan()`** — pure dry-run, zero network I/O;
- **`sync()`** — idempotent upsert (primary key + `content_hash` skip), supersession-chain ordered;
- **`verify()`** — mandatory live readback; a sync that is not read back is not complete.

The Supabase sink ([`docs/SUPABASE_CONNECTOR.md`](./docs/SUPABASE_CONNECTOR.md)) is stdlib-only,
retries 429/5xx with backoff, scrubs secrets from every report and error, and accepts keys via
environment variable only. The migration creates the 13 section-14 tables in a dedicated `apk`
schema with RLS locked by default.

## Seed data provenance

`data/` is generated, never hand-edited. `scripts/generate_seed_data.py` builds every record —
including correction supersession chains with deterministic ids matching
`CorrectionLedger.record` — and CI fails if committed data drifts from generator output
(`apk seed --check`).

## Roadmap (spec section 19)

- **Phase A — Normalize**: ingest existing preferences/corrections, type them, preserve source
  refs, deduplicate by meaning without destroying provenance, mark active/superseded/resolved.
  *(shipped in `apk.types` / `apk.store`)*
- **Phase B — Activate**: compact always-active `user_model`, retrieval router, encoded global
  invariants, encoded authority matrix. *(shipped in `apk.user_model` / `apk.router` /
  `apk.authority`)*
- **Phase C — Learn**: convert repeated corrections into policy rules, count recurrence, promote
  rules, store successful strategies. *(shipped in `apk.corrections` / `apk.policy`)*
- **Phase D — Test**: regression corpus from historical failures, replay current policy, detect
  recurrence. *(shipped in `apk.replay`)*
- **Phase E — Compound**: connect an external canonical ledger, semantic indexes,
  Files/Library source artifacts, provider state, cross-platform portability. *(Supabase
  write-through shipped in `apk.connectors.supabase` + `supabase/migrations/`; semantic indexes
  and cross-platform adapters remain future sinks on the connector plane)*

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE). Copyright GlacierEQ.
