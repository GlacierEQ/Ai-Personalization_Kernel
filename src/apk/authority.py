"""Authority model (spec section 5 / docs/USER_AUTHORITY_MODEL.md).

Separates directional authority from factual authority: the user controls
direction, sources control factual certainty, verification controls
confidence labels. This module implements the per-claim-type factual
authority matrix and conflict resolution between two claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

CLAIM_TYPES: tuple[str, ...] = (
    "user_intent",
    "firsthand_experience",
    "project_meaning",
    "provider_state",
    "public_fact",
)

# Controlling authority label per claim type (spec section 5.2 / matrix).
CONTROLLING_AUTHORITY: dict[str, str] = {
    "user_intent": "user_sovereign",
    "firsthand_experience": "user_primary",
    "project_meaning": "user_architect",
    "provider_state": "live_readback",
    "public_fact": "primary_sources",
}

# Rank used only as a last-resort tiebreak; user-owned claim types always
# outrank external/public ones, but this is NOT the sole conflict mechanism
# (see resolve_conflict for the actual, more nuanced rules).
_RANK = {
    "user_intent": 5,
    "firsthand_experience": 4,
    "project_meaning": 3,
    "provider_state": 2,
    "public_fact": 1,
}

_INTENT_KEYWORDS = ("i want", "i intend", "i need", "please build", "our goal", "the goal is")
_FIRSTHAND_KEYWORDS = ("i ran", "i observed", "it failed", "i saw", "when i run", "it crashed",
                       "it returned", "i tested", "i executed")
_PROJECT_KEYWORDS = ("our architecture", "our project", "our system uses", "our kernel",
                     "the codebase", "our design")
_PROVIDER_KEYWORDS = ("current status", "live", "right now", "git status", "the api returns",
                     "the database shows")


class AuthorityError(ValueError):
    pass


@dataclass(frozen=True)
class Claim:
    content: str
    claim_type: Optional[str] = None
    source: str = "unspecified"

    def resolved_type(self) -> str:
        if self.claim_type:
            if self.claim_type not in CLAIM_TYPES:
                raise AuthorityError(f"unknown claim_type {self.claim_type!r}")
            return self.claim_type
        return AuthorityResolver.classify(self.content)


@dataclass(frozen=True)
class ConflictResolution:
    winner: Optional[Claim]
    resolution_type: str
    requires_user_adjudication: bool
    rationale: str


class AuthorityResolver:
    """Classifies claims and resolves conflicts per the claim-type authority matrix."""

    @staticmethod
    def classify(text: str, explicit_type: Optional[str] = None) -> str:
        if explicit_type:
            if explicit_type not in CLAIM_TYPES:
                raise AuthorityError(f"unknown claim_type {explicit_type!r}")
            return explicit_type
        low = text.lower()
        if any(k in low for k in _INTENT_KEYWORDS):
            return "user_intent"
        if any(k in low for k in _FIRSTHAND_KEYWORDS):
            return "firsthand_experience"
        if any(k in low for k in _PROJECT_KEYWORDS):
            return "project_meaning"
        if any(k in low for k in _PROVIDER_KEYWORDS):
            return "provider_state"
        return "public_fact"

    @staticmethod
    def controlling_authority(claim_type: str) -> str:
        if claim_type not in CONTROLLING_AUTHORITY:
            raise AuthorityError(f"unknown claim_type {claim_type!r}")
        return CONTROLLING_AUTHORITY[claim_type]

    @staticmethod
    def resolve_conflict(a: Claim, b: Claim) -> ConflictResolution:
        ta, tb = a.resolved_type(), b.resolved_type()

        # Rule: user intent is never overwritten (invariant 6). Sovereign over
        # everything, including live provider state -- direction is a
        # different dimension than factual certainty (section 5.3).
        if ta == "user_intent" or tb == "user_intent":
            winner = a if ta == "user_intent" else b
            return ConflictResolution(
                winner=winner,
                resolution_type="user_intent_sovereign",
                requires_user_adjudication=False,
                rationale="user intent/desired outcome is sovereign and is never overwritten "
                          "by search results, priors, live state, or external claims (invariant 6)",
            )

        # Rule: provider readback controls current-state facts (overrules
        # cached memory, public claims, and prior firsthand observations for
        # what is true *right now*).
        if ta == "provider_state" or tb == "provider_state":
            winner = a if ta == "provider_state" else b
            other_type = tb if ta == "provider_state" else ta
            return ConflictResolution(
                winner=winner,
                resolution_type="provider_readback_controls",
                requires_user_adjudication=False,
                rationale=(
                    f"live provider readback ({winner.source}) controls current-state "
                    f"facts over {other_type}; cached/memory/model state is superseded"
                ),
            )

        # Rule: firsthand experience vs external/public claim => DISPUTE, never silent overwrite.
        firsthand_vs_public = {ta, tb} == {"firsthand_experience", "public_fact"}
        if firsthand_vs_public:
            return ConflictResolution(
                winner=None,
                resolution_type="dispute_firsthand_vs_external",
                requires_user_adjudication=True,
                rationale="firsthand user observation cannot be silently replaced by a "
                          "third-party/public claim (invariant 7); flagged for user "
                          "adjudication instead of being overwritten",
            )

        # Rule: user-owned project meaning overrules repository/implementation drift claims.
        if ta == "project_meaning" or tb == "project_meaning":
            winner = a if ta == "project_meaning" else b
            return ConflictResolution(
                winner=winner,
                resolution_type="project_meaning_sovereign",
                requires_user_adjudication=False,
                rationale="user controls intended project meaning/architecture; "
                          "implementation drift does not redefine it (spec 5.2/invariant 8)",
            )

        # Fallback: static authority-matrix rank order.
        winner = a if _RANK[ta] >= _RANK[tb] else b
        return ConflictResolution(
            winner=winner,
            resolution_type="authority_matrix_default",
            requires_user_adjudication=False,
            rationale=f"default authority-matrix ranking: {ta} vs {tb}",
        )
