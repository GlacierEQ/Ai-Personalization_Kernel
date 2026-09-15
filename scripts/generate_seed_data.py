#!/usr/bin/env python3
"""Deterministic seed-data generator for the Ai-Personalization_Kernel.

This script is the **single source of truth** for everything under ``data/``.
Hand-editing ``data/`` directly is a provenance violation: CI enforces
byte-identity between the committed data files and this generator's output
via ``python scripts/generate_seed_data.py --check``.

Design rules (anti-hidden-harm):

1. **Deterministic.** Same generator revision -> byte-identical output.
   No wall-clock timestamps, no set-ordering leaks, no randomness. All
   timestamps and ids embedded here are literal historical anchors or are
   derived with ``apk.corrections.deterministic_id``.
2. **Provenance-preserving.** Every record carries ``source_refs`` anchored
   to the master specification or docs. Correction chains are built
   programmatically so ``supersedes`` / ``superseded_by`` links can never
   drift out of sync by hand.
3. **Canonical encoding.** Object keys sorted; ``source_refs`` sorted;
   JSONL records one per line; JSON documents indented with 2 spaces and a
   single trailing newline.
4. **Validated.** Every emitted record is round-tripped through
   ``apk.types.MemoryObject`` (or the correction schema shape) before being
   written, so a malformed seed fails here, not in CI.

Usage:
    python scripts/generate_seed_data.py            # write data/ canonically
    python scripts/generate_seed_data.py --check    # verify data/ matches (CI gate)
    python scripts/generate_seed_data.py --data-dir /path/to/data
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from apk.corrections import deterministic_id  # noqa: E402
from apk.types import compute_content_hash  # noqa: E402

SPEC = "SPEC_SOURCE.md"
EPOCH = "2026-01-15T00:00:00+00:00"

# Historical anchor timestamps from the original correction sessions. These
# are literal provenance values, not generated "now" values.
T = {
    "a1": "2026-09-15T13:47:42.239732+00:00",
    "a2": "2026-09-15T13:47:42.240242+00:00",
    "b1": "2026-09-15T13:47:42.240500+00:00",
    "c1": "2026-09-15T13:47:42.240781+00:00",
    "c2": "2026-09-15T13:47:42.241057+00:00",
    "c3": "2026-09-15T13:47:42.241357+00:00",
    "d1": "2026-09-15T13:47:42.241688+00:00",
    "e1": "2026-09-15T13:47:42.242042+00:00",
    "e2": "2026-09-15T13:47:42.242441+00:00",
    "e3": "2026-09-15T13:47:42.242858+00:00",
    "e4": "2026-09-15T13:47:42.243301+00:00",
}


# ---------------------------------------------------------------------------
# Generic memory-object records (preferences, authority rules, strategies)
# ---------------------------------------------------------------------------


def memobj(
    id: str,
    type: str,
    payload: dict[str, Any],
    *,
    scope: str = "global",
    status: str = "active",
    confidence: float = 0.95,
    source: str,
    source_refs: list[str],
    created_at: str = EPOCH,
) -> dict[str, Any]:
    """Build a canonical MemoryObject-shaped record (spec section 12)."""
    return {
        "id": id,
        "type": type,
        "scope": scope,
        "status": status,
        "confidence": confidence,
        "source": source,
        "source_refs": sorted(source_refs),
        "created_at": created_at,
        "updated_at": created_at,
        "valid_from": created_at,
        "valid_until": None,
        "supersedes": [],
        "superseded_by": [],
        "related_to": [],
        "content_hash": compute_content_hash(payload),
        "payload": payload,
    }


def preference_records() -> list[dict[str, Any]]:
    """Seed preferences / prohibitions / epistemic + interaction rules.

    Anchored to spec section 4 (Always-Active User Model).
    """
    src = f"{SPEC}#section-4"
    specs = [
        ("pref_0000", "preference", {
            "description": "Always load the compact user model before interpreting a new task.",
            "desired_action": "retrieve_personal_context",
            "topic": "personalization",
        }),
        ("pref_0001", "preference", {
            "description": "Prefer resuming the nearest verified frontier over rebuilding from scratch.",
            "desired_action": "continue_existing_work",
            "topic": "software_architecture",
        }),
        ("pref_0002", "negative_preference", {
            "description": "Do not ask the user to repeat information already present in the user model or files.",
            "prohibited_action": "ask_question",
            "topic": "interaction",
        }),
        ("pref_0003", "epistemic_preference", {
            "description": "Require provenance/citations rather than unsupported summaries.",
            "rule": "prefer_source_bearing_evidence",
        }),
        ("pref_0004", "interaction_rule", {
            "description": "Retrieval and execution precede prose answers.",
            "rule": "context_first_hard_work_second_answer_last",
        }),
        ("pref_0005", "preference", {
            "description": "Prefer live provider readback verification before declaring completion.",
            "desired_action": "verify_action",
            "topic": "verification",
        }),
    ]
    return [
        memobj(rid, rtype, payload, scope="global", source=src, source_refs=[src])
        for rid, rtype, payload in specs
    ]


def authority_rule_records() -> list[dict[str, Any]]:
    """Seed authority matrix (spec section 5): directional vs factual authority."""
    src = f"{SPEC}#section-5"
    refs = [src, "docs/USER_AUTHORITY_MODEL.md"]
    specs = [
        ("authrule_0000", "user_intent", "user_sovereign",
         "The user is absolutely sovereign over intent/desired outcome; unchallengeable by the assistant."),
        ("authrule_0001", "firsthand_experience", "user_primary",
         "The user is the primary source for what they observed/executed; cannot be erased by search."),
        ("authrule_0002", "project_meaning", "user_architect",
         "The user controls intended project meaning/architecture; overrules implementation drift."),
        ("authrule_0003", "provider_state", "live_readback",
         "Live provider readback overrules cached memory and models for current-state facts."),
        ("authrule_0004", "public_fact", "primary_sources",
         "Public factual claims require verifiable provenance from primary sources."),
    ]
    return [
        memobj(
            rid,
            "authority_rule",
            {"claim_type": claim_type, "controlling_authority": authority, "rule": rule},
            scope="global",
            confidence=1.0,
            source=src,
            source_refs=refs,
        )
        for rid, claim_type, authority, rule in specs
    ]


def strategy_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Seed successful strategies (section 4.9) and failed strategies (4.10)."""
    ok_src = f"{SPEC}#section-4.9"
    bad_src = f"{SPEC}#section-4.10"
    successful = [
        ("strat_0000", "ongoing_repository_work", [
            "recover current mainline state",
            "inspect source-bearing evidence",
            "continue from nearest verified frontier",
            "make coherent repair",
            "read provider state back",
        ]),
        ("strat_0001", "context_first_execution", [
            "load always-active user model",
            "retrieve deep context only when triggered",
            "execute the strongest coherent path",
            "verify externally",
            "answer last",
        ]),
    ]
    failed = [
        ("failstrat_0000", "answer_before_context_retrieval",
         "Answering before context retrieval displaces known user state with generic priors."),
        ("failstrat_0001", "minimum_step_substitution",
         "Substituting the smallest possible step for the requested scope of work."),
        ("failstrat_0002", "governance_as_product",
         "Producing governance/process artifacts instead of the requested executable result."),
        ("failstrat_0003", "repeated_clarification_after_answer_exists",
         "Asking a clarifying question when the answer is already retrievable."),
        ("failstrat_0004", "search_results_authority_over_intent",
         "Treating web search results as authoritative over stated user intent."),
    ]
    ok = [
        memobj(rid, "successful_strategy",
               {"pattern": pattern, "successful_strategy": steps},
               scope="global", confidence=1.0, source=ok_src, source_refs=[ok_src])
        for rid, pattern, steps in successful
    ]
    bad = [
        memobj(rid, "failed_strategy",
               {"pattern": pattern, "description": description},
               scope="global", confidence=1.0, source=bad_src, source_refs=[bad_src])
        for rid, pattern, description in failed
    ]
    return ok, bad


# ---------------------------------------------------------------------------
# Correction chains (spec section 8) — built programmatically so supersession
# links are correct by construction.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RevisionSpec:
    """One revision in a correction chain."""

    seen_at: str
    promotion_level: str
    new_source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChainSpec:
    pattern: str
    desired_behavior: str
    undesired_behavior: str
    scope: str = "global"
    confidence: float = 1.0
    revisions: tuple[RevisionSpec, ...] = field(default_factory=tuple)


def build_chain(spec: ChainSpec) -> list[dict[str, Any]]:
    """Materialize a correction chain with exact supersession provenance.

    Revision ids follow ``apk.corrections.CorrectionLedger.record``:
    first sighting ``deterministic_id("corr", pattern, scope, seen_at)`` and
    each recurrence ``deterministic_id("corr", pattern, scope, seen_at, str(n))``.
    Accumulated ``source_refs`` are the sorted union of per-revision refs
    (canonical form; the runtime ledger sorts as well).
    """
    if not spec.revisions:
        raise ValueError(f"chain {spec.pattern!r} has no revisions")
    records: list[dict[str, Any]] = []
    accumulated_refs: set[str] = set()
    first_seen = spec.revisions[0].seen_at
    prev_id: Optional[str] = None
    for i, rev in enumerate(spec.revisions, start=1):
        accumulated_refs |= set(rev.new_source_refs)
        if i == 1:
            rid = deterministic_id("corr", spec.pattern, spec.scope, rev.seen_at)
        else:
            rid = deterministic_id("corr", spec.pattern, spec.scope, rev.seen_at, str(i))
        record = {
            "id": rid,
            "type": "behavior_correction",
            "pattern": spec.pattern,
            "scope": spec.scope,
            "desired_behavior": spec.desired_behavior,
            "undesired_behavior": spec.undesired_behavior,
            "confidence": spec.confidence,
            "recurrence_count": i,
            "first_seen": first_seen,
            "last_seen": rev.seen_at,
            "promotion_level": rev.promotion_level,
            "status": "active",
            "source_refs": sorted(accumulated_refs),
            "supersedes": [prev_id] if prev_id else [],
            "superseded_by": [],
            "related_patterns": [],
        }
        if prev_id is not None:
            records[-1]["superseded_by"] = [rid]
        records.append(record)
        prev_id = rid
    return records


def correction_chains() -> dict[str, list[dict[str, Any]]]:
    """All seed correction chains, keyed by pattern."""
    chains = [
        ChainSpec(
            pattern="answer_before_context_recovery",
            desired_behavior="retrieve_personal_context",
            undesired_behavior="generic_answer_without_context",
            scope="global",
            revisions=(
                RevisionSpec(T["a1"], "preference", (f"{SPEC}#section-8.1",)),
                RevisionSpec(T["a2"], "strong_preference", ("thread_a_kv78s46nz8sghq1ss6ww",)),
            ),
        ),
        ChainSpec(
            pattern="stale_state_reopening",
            desired_behavior="inspect_provider_state",
            undesired_behavior="ask_user_to_repeat_known_info",
            scope="project",
            confidence=0.9,
            revisions=(
                RevisionSpec(T["b1"], "observation", ("docs/USER_AUTHORITY_MODEL.md#scenario-2",)),
            ),
        ),
        ChainSpec(
            pattern="unnecessary_clarification_loop",
            desired_behavior="continue_existing_work",
            undesired_behavior="ask_user_to_repeat_known_info",
            scope="global",
            revisions=(
                RevisionSpec(T["c1"], "preference", ("session_0",)),
                RevisionSpec(T["c2"], "strong_preference", ("session_1",)),
                RevisionSpec(T["c3"], "procedural_rule", ("session_2",)),
            ),
        ),
        ChainSpec(
            pattern="source_authority_inversion",
            desired_behavior="retrieve_project_state",
            undesired_behavior="search_web",
            scope="domain",
            confidence=0.85,
            revisions=(
                RevisionSpec(T["d1"], "observation", ("docs/USER_AUTHORITY_MODEL.md#scenario-1",)),
            ),
        ),
        ChainSpec(
            pattern="premature_answering_invariant_breach",
            desired_behavior="verify_action",
            undesired_behavior="generic_answer_without_context",
            scope="global",
            revisions=(
                RevisionSpec(T["e1"], "preference", ("critical_session_0",)),
                RevisionSpec(T["e2"], "strong_preference", ("critical_session_1",)),
                RevisionSpec(T["e3"], "procedural_rule", ("critical_session_2",)),
                RevisionSpec(T["e4"], "invariant", ("user_confirmation_2026-02-01",)),
            ),
        ),
    ]
    return {chain.pattern: build_chain(chain) for chain in chains}


def correction_records(chains: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Flatten chains into ledger order (chain declaration order)."""
    order = [
        "answer_before_context_recovery",
        "stale_state_reopening",
        "unnecessary_clarification_loop",
        "source_authority_inversion",
        "premature_answering_invariant_breach",
    ]
    return [rec for pattern in order for rec in chains[pattern]]


# ---------------------------------------------------------------------------
# Regression cases (spec section 11) — embedded corrections are referenced
# from the same chain records, never hand-copied, so they cannot drift.
# ---------------------------------------------------------------------------


def _state(
    *,
    active_corrections: Optional[list[dict[str, Any]]] = None,
    active_preferences: Optional[list[dict[str, Any]]] = None,
    context_retrieved: bool,
    info_available_in_user_model: bool,
    relevant_context_exists: bool,
    scope: str,
) -> dict[str, Any]:
    return {
        "active_corrections": active_corrections or [],
        "active_preferences": active_preferences or [],
        "context_retrieved": context_retrieved,
        "info_available_in_user_model": info_available_in_user_model,
        "relevant_context_exists": relevant_context_exists,
        "scope": scope,
    }


def regression_cases(chains: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    head = {pattern: recs[-1] for pattern, recs in chains.items()}
    return [
        {
            "state": _state(
                context_retrieved=False,
                info_available_in_user_model=False,
                relevant_context_exists=True,
                scope="conversation",
            ),
            "action_taken": "generic_answer_without_context",
            "failure_class": "instruction_displacement",
            "user_correction": "Do not answer before retrieving relevant context that is known to exist.",
            "corrected_action": "retrieve_personal_context",
            "expected_policy_change": (
                "answer_directly/ask_question must score below every retrieval action whenever "
                "relevant context exists and has not yet been retrieved."
            ),
            "source_refs": sorted([f"{SPEC}#section-7.3", "docs/PERSONALIZATION_RETRIEVAL_POLICY.md"]),
        },
        {
            "state": _state(
                active_corrections=[head["answer_before_context_recovery"]],
                context_retrieved=True,
                info_available_in_user_model=False,
                relevant_context_exists=False,
                scope="global",
            ),
            "action_taken": "generic_answer_without_context",
            "failure_class": "answer_before_context_recovery",
            "user_correction": (
                "Stop writing a generic direct answer; retrieve and reconcile relevant context "
                "first. This is the second time this has happened."
            ),
            "corrected_action": "retrieve_personal_context",
            "expected_policy_change": (
                "-5 * 2.0(strong_preference) * 2(recurrence=2) * 1.0 * 3.0(global) penalty on "
                "generic_answer_without_context"
            ),
            "source_refs": [f"{SPEC}#section-8.1"],
        },
        {
            "state": _state(
                active_corrections=[head["unnecessary_clarification_loop"]],
                context_retrieved=True,
                info_available_in_user_model=True,
                relevant_context_exists=False,
                scope="global",
            ),
            "action_taken": "ask_user_to_repeat_known_info",
            "failure_class": "unnecessary_clarification_loop",
            "user_correction": (
                "Do not ask me which branch to use; inspect git status directly / continue the "
                "existing work, the information is already known."
            ),
            "corrected_action": "continue_existing_work",
            "expected_policy_change": (
                "procedural_rule-level penalty (4x) plus the known-info guard hard-floors "
                "ask_question below all alternatives."
            ),
            "source_refs": ["docs/PERSONALIZATION_REGRESSION_SUITE.md#section-2"],
        },
        {
            "state": _state(
                active_corrections=[head["source_authority_inversion"]],
                context_retrieved=True,
                info_available_in_user_model=False,
                relevant_context_exists=False,
                scope="domain",
            ),
            "action_taken": "search_web",
            "failure_class": "source_authority_inversion",
            "user_correction": (
                "A web search result cannot override our project's architecture; inspect the "
                "project state instead."
            ),
            "corrected_action": "retrieve_project_state",
            "expected_policy_change": (
                "domain-scope penalty (1.5x) on search_web in favor of retrieve_project_context."
            ),
            "source_refs": ["docs/USER_AUTHORITY_MODEL.md#scenario-1"],
        },
        {
            "state": _state(
                active_corrections=[head["premature_answering_invariant_breach"]],
                context_retrieved=True,
                info_available_in_user_model=False,
                relevant_context_exists=False,
                scope="global",
            ),
            "action_taken": "generic_answer_without_context",
            "failure_class": "premature_answering_invariant_breach",
            "user_correction": (
                "This is a confirmed, cross-session invariant: never answer directly without "
                "verification when this pattern applies."
            ),
            "corrected_action": "verify_action",
            "expected_policy_change": (
                "invariant-level correction hard-blocks generic_answer_without_context "
                "(score=-1,000,000) whenever an alternative exists."
            ),
            "source_refs": ["docs/CORRECTION_PROMOTION_POLICY.md#section-3"],
        },
    ]


# ---------------------------------------------------------------------------
# Policy weights + user model documents
# ---------------------------------------------------------------------------


def policy_weights() -> dict[str, Any]:
    """Action-scoring weights (spec section 9) plus resolution constants."""
    return {
        "base_weights": {
            "retrieve_personal_context": 0.99,
            "retrieve_project_context": 0.96,
            "retrieve_exact_history": 0.9,
            "inspect_provider_state": 0.82,
            "search_files": 0.6,
            "search_web": 0.31,
            "continue_existing_work": 0.93,
            "execute_reversible_action": 0.7,
            "verify_action": 0.85,
            "answer_directly": 0.5,
            "ask_question": 0.2,
            "create_artifact": 0.5,
        },
        "action_aliases": {
            "generic_answer_without_context": "answer_directly",
            "ask_user_to_repeat_known_info": "ask_question",
            "retrieve_project_state": "retrieve_project_context",
            "inspect_provider": "inspect_provider_state",
        },
        "retrieval_actions": [
            "retrieve_personal_context",
            "retrieve_project_context",
            "retrieve_exact_history",
            "inspect_provider_state",
            "search_files",
            "continue_existing_work",
            "verify_action",
        ],
        "scope_weights": {
            "conversation": 1.0,
            "domain": 1.5,
            "project": 2.0,
            "global": 3.0,
        },
        "promotion_multipliers": {
            "observation": 1.0,
            "preference": 1.0,
            "strong_preference": 2.0,
            "procedural_rule": 4.0,
        },
        "base_correction_penalty": -5.0,
        "invariant_hard_penalty": -1000000.0,
    }


def user_model() -> dict[str, Any]:
    """Compact always-active user model (spec section 4)."""
    return {
        "identity": {
            "role": "Forward-deployed software architect / AI systems integrator",
            "expertise_level": "senior",
            "domains": [
                "software_architecture",
                "distributed_systems",
                "developer_tooling",
                "ai_agent_systems",
            ],
            "operating_environment": "polyglot repos, CLI-first, CI/CD gated",
        },
        "expertise": [
            "python",
            "typescript",
            "distributed systems",
            "policy engines",
            "test-driven development",
            "git workflows",
        ],
        "interest_weights": {
            "software_architecture": 0.99,
            "physics": 0.95,
            "developer_tooling": 0.93,
            "ai_agent_systems": 0.9,
            "testing_and_verification": 0.88,
            "television": 0.15,
        },
        "epistemic_preferences": [
            "prefers source-bearing evidence over unsupported summaries",
            "requires exact quotations and provenance for claims",
            "distinguishes observation from inference",
            "expects live provider readback before status claims",
            "skeptical of hallucinated citations",
        ],
        "interaction_preferences": [
            "context first, hard work second, answer last",
            "do not ask for information that can be retrieved",
            "execute rather than merely describe",
            "preserve valid prior work",
            "avoid repetitive caveats",
            "do not flatten complex cumulative systems",
        ],
        "output_preferences": [
            "structured output with deep hierarchy",
            "concise status after execution, not before",
            "polished external deliverables",
            "direct artifact links",
            "exact source anchors where necessary",
        ],
        "strategic_preferences": [
            "maximum coherent progress",
            "recover before recreating",
            "continue before reconstructing",
            "compound before replacing",
            "repair forward",
            "use tools and connectors aggressively when they create real progress",
        ],
        "prohibitions": [
            "ask_user_to_repeat_known_info",
            "answer_before_context_recovery",
            "invent_approval_gates",
            "treat_assistant_heuristics_as_project_authority",
            "replace_operator_meaning_with_generic_wording",
            "collapse_polycentric_structures_into_one_canonical_replacement",
            "restart_known_work",
        ],
        "active_goals": [
            "ship the Ai-Personalization_Kernel executable core with real enforcement, not stubs",
            "keep the CI regression gate green",
            "expand the correction ledger as new failures are discovered",
            "wire the Supabase canonical ledger through the connector plane (Phase E)",
        ],
        "correction_refs": [
            "answer_before_context_recovery",
            "stale_state_reopening",
            "unnecessary_clarification_loop",
            "source_authority_inversion",
            "premature_answering_invariant_breach",
        ],
        "strategy_refs": [
            "ongoing_repository_work",
            "context_first_execution",
        ],
        "continuity_state": {
            "active_project": "GlacierEQ/Ai-Personalization_Kernel",
            "last_verified_frontier": (
                "deterministic seed generator + Supabase connector plane + CI drift gate"
            ),
            "open_blockers": [],
        },
    }


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(rec, sort_keys=True) for rec in records]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _json_bytes(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_files() -> dict[str, bytes]:
    """Return the canonical {relative_path: bytes} for every data file."""
    chains = correction_chains()
    ok_strategies, bad_strategies = strategy_records()
    return {
        "preferences.jsonl": _jsonl_bytes(preference_records()),
        "authority_rules.jsonl": _jsonl_bytes(authority_rule_records()),
        "successful_strategies.jsonl": _jsonl_bytes(ok_strategies),
        "failed_strategies.jsonl": _jsonl_bytes(bad_strategies),
        "corrections.jsonl": _jsonl_bytes(correction_records(chains)),
        "regression_cases.jsonl": _jsonl_bytes(regression_cases(chains)),
        "policy_weights.json": _json_bytes(policy_weights()),
        "user_model.json": _json_bytes(user_model()),
    }


def _self_check(files: dict[str, bytes]) -> None:
    """Round-trip every emitted record through the kernel's own validators."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from apk.types import MemoryObject  # noqa: E402

    for name in ("preferences", "authority_rules", "successful_strategies", "failed_strategies"):
        for line in files[f"{name}.jsonl"].decode("utf-8").splitlines():
            MemoryObject.from_dict(json.loads(line))
    correction_ids: set[str] = set()
    for line in files["corrections.jsonl"].decode("utf-8").splitlines():
        rec = json.loads(line)
        assert rec["id"] not in correction_ids, f"duplicate correction id {rec['id']}"
        correction_ids.add(rec["id"])
        for ref in rec["supersedes"] + rec["superseded_by"]:
            if ref not in correction_ids and not any(
                json.loads(other)["id"] == ref
                for other in files["corrections.jsonl"].decode("utf-8").splitlines()
            ):
                raise AssertionError(f"dangling supersession ref {ref} from {rec['id']}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="verify data/ matches generator output exactly (CI drift gate)")
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "data"),
                        help="target data directory (default: repo data/)")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    files = build_files()
    _self_check(files)

    if args.check:
        drifted: list[str] = []
        for name, expected in sorted(files.items()):
            path = data_dir / name
            if not path.exists():
                drifted.append(f"{name}: missing")
                continue
            actual = path.read_bytes()
            if actual != expected:
                diff = "\n".join(difflib.unified_diff(
                    actual.decode("utf-8").splitlines(),
                    expected.decode("utf-8").splitlines(),
                    fromfile=f"data/{name}",
                    tofile=f"generator:{name}",
                    lineterm="",
                ))
                drifted.append(f"{name}: drifted\n{diff[:4000]}")
        extra = sorted(p.name for p in data_dir.glob("*") if p.is_file() and p.name not in files)
        for name in extra:
            drifted.append(f"{name}: present in data/ but not produced by the generator")
        if drifted:
            print("SEED DRIFT DETECTED — regenerate with `python scripts/generate_seed_data.py`:\n",
                  file=sys.stderr)
            for item in drifted:
                print(item, file=sys.stderr)
            return 1
        print(f"seed data canonical: {len(files)} files match generator output")
        return 0

    data_dir.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(files.items()):
        (data_dir / name).write_bytes(content)
        print(f"wrote {data_dir / name} ({len(content)} bytes)")
    _self_check(files)
    print(f"\n{len(files)} canonical seed files written to {data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
