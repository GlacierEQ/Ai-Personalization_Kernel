"""Source-bound output fidelity checks.

Protect the source status of a specific firsthand or operator-confirmed
proposition without contaminating it with uncertainty about a neighboring
inference. Findings are repair instructions, never an automatic case verdict.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_CLAUSES = re.compile(
    r"(?<=[.!?;])\s+|,\s+(?=(?:but|yet|however|although|whereas)\b)", re.I
)
_STATUS_DEMOTION = re.compile(
    r"\b(?:unverified|unconfirmed|unsupported|speculative|merely\s+alleged|"
    r"not\s+(?:independently\s+)?(?:verified|confirmed|established|proven)|"
    r"(?:cannot|can't|could\s+not|couldn't)\s+(?:verify|confirm|establish|prove)|"
    r"(?:no|without)\s+(?:independent\s+)?(?:proof|evidence|confirmation))\b",
    re.I,
)
_PROTECTED_STATUSES = frozenset({
    "operator_confirmed", "user_confirmed", "user_firsthand", "firsthand", "documented"
})
_DEMOTED_STATUSES = frozenset({
    "unverified", "unconfirmed", "unsupported",
    "speculative", "merely_alleged", "not_established"
})


def _matches_anchor(clause: str, anchors: Sequence[str]) -> bool:
    """Require a proposition-specific phrase, not a person or device name."""
    normalized = " ".join(clause.casefold().split())
    return any(" ".join(anchor.casefold().split()) in normalized for anchor in anchors)


def detect_source_fact_demotions(
    text: str,
    source_facts: Sequence[Mapping[str, Any]],
    *,
    emitted_claims: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Find assistant-output demotion of independently recovered source facts.

    Bound facts contain id, statement, source status and precise textual anchors.
    Structured emitted_claims enable a status-level comparison independent of
    wording. Separate unknown inferences retain their uncertainty.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    findings: list[dict[str, Any]] = []
    protected: dict[str, Mapping[str, Any]] = {}
    clauses = [c.strip() for c in _CLAUSES.split(text) if c.strip()]

    for fact in source_facts:
        fact_id, statement, anchors = (
            fact.get("id"), fact.get("statement"), fact.get("anchors")
        )
        if not isinstance(fact_id, str) or not fact_id.strip():
            raise ValueError("source facts require a nonempty id")
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError(f"source fact {fact_id!r} requires a source statement")
        if not isinstance(anchors, (list, tuple)) or not anchors or not all(
            isinstance(a, str) and len(a.strip()) >= 8 for a in anchors
        ):
            raise ValueError(f"source fact {fact_id!r} requires proposition-specific anchors")
        if fact.get("status") not in _PROTECTED_STATUSES:
            continue
        if fact_id in protected:
            raise ValueError(f"duplicate protected fact id: {fact_id!r}")
        protected[fact_id] = fact
        for clause in clauses:
            if not _matches_anchor(clause, anchors):
                continue
            if not _STATUS_DEMOTION.search(clause):
                continue
            if re.match(r"^(?:do\s+not|don't|never|avoid|reject|forbid)\b", clause, re.I):
                continue
            findings.append({
                "rule": "SOURCE_FACT_STATUS_DEMOTION",
                "fact_id": fact_id,
                "source_statement": statement,
                "source_status": fact["status"],
                "draft_excerpt": clause,
                "repair": "Preserve the source fact; localize uncertainty to a distinct inference.",
            })

    for claim in emitted_claims or ():
        fact_id = claim.get("fact_id")
        if fact_id not in protected:
            continue
        emitted_status = str(claim.get("status", "")).casefold()
        if emitted_status not in _DEMOTED_STATUSES:
            continue
        fact = protected[fact_id]
        findings.append({
            "rule": "SOURCE_FACT_STATUS_DEMOTION",
            "fact_id": fact_id,
            "source_statement": fact["statement"],
            "source_status": fact["status"],
            "emitted_status": emitted_status,
            "repair": "Preserve recovered source status; attach uncertainty to its true target.",
        })
    return findings
