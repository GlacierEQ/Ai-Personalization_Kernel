"""Authority and source-integrity model.

The user controls direction. Each source controls only the propositions it is
competent to observe or record. Verification changes confidence in a specific
proposition or external state; it never grants one source class ontological
superiority over another.

Most importantly: a person's firsthand account of their own experience is
itself evidence. A document can corroborate, conflict with, contextualize, or
quantify that account, but a document does not become "what actually happened"
while the witness becomes merely "a description." Authentication,
admissibility, corroboration, and legal sufficiency are separate dimensions
from whether a witness personally observed an event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

CLAIM_TYPES: tuple[str, ...] = (
    "user_intent",
    "firsthand_experience",
    "project_meaning",
    "provider_state",
    "public_fact",
)

CONTROLLING_AUTHORITY: dict[str, str] = {
    "user_intent": "user_sovereign",
    "firsthand_experience": "user_witness",
    "project_meaning": "user_architect",
    "provider_state": "live_readback_for_provider_state",
    "public_fact": "primary_sources_for_public_fact",
}

_INTENT_KEYWORDS = (
    "i want", "i intend", "i need", "please build", "our goal", "the goal is",
)
_FIRSTHAND_KEYWORDS = (
    "i ran", "i observed", "it failed", "i saw", "when i run", "it crashed",
    "it returned", "i tested", "i executed", "i was", "i experienced",
    "i remember", "i signed", "i received", "i witnessed", "they told me",
    "they made me", "i was given", "when i worked", "happened to me",
)
_PROJECT_KEYWORDS = (
    "our architecture", "our project", "our system uses", "our kernel",
    "the codebase", "our design",
)
_PROVIDER_KEYWORDS = (
    "current status", "live", "right now", "git status", "the api returns",
    "the database shows",
)


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
    """Relationship between source claims.

    ``winner`` is retained for directional/current-provider compatibility, but
    must remain ``None`` when the relationship is evidentiary rather than a
    true authority override. ``preserved_claims`` makes non-erasure explicit.
    """

    winner: Optional[Claim]
    resolution_type: str
    requires_user_adjudication: bool
    rationale: str
    preserved_claims: tuple[Claim, ...] = field(default_factory=tuple)
    unresolved_dimensions: tuple[str, ...] = field(default_factory=tuple)


class AuthorityResolver:
    """Classifies claims without turning provenance classes into a truth ladder."""

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
        """Resolve authority only where an authority override is actually valid.

        Source disagreement is normally *not* a winner/loser problem. The
        resolver preserves both source claims and localizes uncertainty to the
        proposition that differs. This prevents documentary supremacy and
        witness subordination.
        """

        ta, tb = a.resolved_type(), b.resolved_type()
        preserved = (a, b)

        # Direction: user intent controls what should be done. This does not
        # convert the user's intent into a claim about external factual state.
        if ta == "user_intent" or tb == "user_intent":
            winner = a if ta == "user_intent" else b
            return ConflictResolution(
                winner=winner,
                resolution_type="user_intent_controls_direction",
                requires_user_adjudication=False,
                rationale=(
                    "user intent controls direction; the other source is preserved for any "
                    "separate factual proposition it actually supports"
                ),
                preserved_claims=preserved,
            )

        # Project meaning: user-owned intended architecture controls intended
        # meaning. Existing implementation may still be preserved as drift.
        if ta == "project_meaning" or tb == "project_meaning":
            winner = a if ta == "project_meaning" else b
            return ConflictResolution(
                winner=winner,
                resolution_type="project_meaning_controls_intended_architecture",
                requires_user_adjudication=False,
                rationale=(
                    "user-owned project meaning controls intended architecture; repository "
                    "state remains evidence of implementation state or drift"
                ),
                preserved_claims=preserved,
            )

        # Witness integrity: firsthand experience is a primary source lane for
        # what the witness personally observed. External/provider/public
        # records may corroborate or conflict with discrete propositions, but
        # cannot demote the witness to a lesser reality class.
        if ta == "firsthand_experience" or tb == "firsthand_experience":
            return ConflictResolution(
                winner=None,
                resolution_type="parallel_evidence_lanes",
                requires_user_adjudication=False,
                rationale=(
                    "firsthand observation and external records are preserved as parallel "
                    "evidence lanes; source type is provenance, not a truth rank. Corroboration, "
                    "authentication, admissibility, and legal sufficiency are tracked separately."
                ),
                preserved_claims=preserved,
                unresolved_dimensions=("cross_source_consistency",),
            )

        # Live provider readback controls the provider's *current external
        # state* over cached/public descriptions of that same state. This rule
        # is deliberately scoped so it cannot erase firsthand history.
        if ta == "provider_state" or tb == "provider_state":
            winner = a if ta == "provider_state" else b
            other_type = tb if ta == "provider_state" else ta
            return ConflictResolution(
                winner=winner,
                resolution_type="provider_readback_controls_current_provider_state",
                requires_user_adjudication=False,
                rationale=(
                    f"live provider readback ({winner.source}) controls the provider's current "
                    f"external state over {other_type}; this rule does not erase historical or "
                    "firsthand observations"
                ),
                preserved_claims=preserved,
            )

        # Two external/public claims do not receive a synthetic winner merely
        # from their category. Compare provenance, scope, time, and competence.
        return ConflictResolution(
            winner=None,
            resolution_type="provenance_comparison_required",
            requires_user_adjudication=False,
            rationale=(
                "no source-class winner is assigned; compare proposition scope, time, provenance, "
                "source competence, and directness before drawing a conclusion"
            ),
            preserved_claims=preserved,
            unresolved_dimensions=("proposition_scope", "provenance", "temporal_scope"),
        )
