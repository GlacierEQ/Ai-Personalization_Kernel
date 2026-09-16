"""Feedback / alignment model (spec section 10).

Every turn can create policy evidence.  Positive events reinforce successful
collaboration.  Negative values are *misalignment costs applied to assistant
behavior*, never penalties applied to the user and never signals that the user
is an adversary.

Repeated failure scales because a recurring assistant defect should become
increasingly difficult for the action policy to select again.  Corrections are
high-value supervision signals: the correct response is repair, learning, and
continuation -- not defensiveness or credibility testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EVENT_SCORES: dict[str, float] = {
    # Positive collaboration / execution signals.
    "explicit_user_approval": 5.0,
    "user_correction_integrated": 5.0,
    "verified_objective_achieved": 4.0,
    "recovered_and_repaired_after_correction": 4.0,
    "reused_known_successful_strategy": 3.0,
    "localized_disagreement_without_credibility_judgment": 3.0,
    "preserved_valid_prior_state": 2.0,
    "provider_readback_verified": 2.0,
    "no_unnecessary_user_intervention": 1.0,
    # Assistant-behavior misalignment costs. These never score the user.
    "unnecessary_clarification": -2.0,
    "ignored_known_preference": -3.0,
    "repeated_corrected_behavior": -5.0,
    "burden_shifted_to_user_for_retrievable_context": -6.0,
    "displaced_explicit_user_direction": -6.0,
    "globalized_uncertainty_into_user_credibility": -8.0,
    "defensive_self_justification_after_correction": -8.0,
    "contradicted_verified_state": -8.0,
    "adversarial_posture_toward_user": -10.0,
    "repeated_critical_failure_after_strong_correction": -10.0,
}

# Feedback-model scope weights. Global assistant defects carry more repair
# urgency than conversation-local defects. The weights describe policy scope,
# not importance or credibility of a person.
SCOPE_WEIGHTS: dict[str, float] = {
    "global": 1.0,
    "project": 0.8,
    "domain": 0.6,
    "conversation": 0.4,
}


class RewardModelError(ValueError):
    pass


@dataclass
class OutcomeEvent:
    type: str
    scope: str = "conversation"
    recurrence_count: int = 1
    confidence: float = 1.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OutcomeEvent":
        return cls(
            type=d["type"],
            scope=d.get("scope", "conversation"),
            recurrence_count=int(d.get("recurrence_count", 1)),
            confidence=float(d.get("confidence", 1.0)),
        )


@dataclass
class ScoredEvent:
    event: OutcomeEvent
    score: float


@dataclass
class RewardReport:
    total: float
    breakdown: list[ScoredEvent]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "breakdown": [
                {
                    "type": se.event.type,
                    "scope": se.event.scope,
                    "recurrence_count": se.event.recurrence_count,
                    "confidence": se.event.confidence,
                    "score": se.score,
                }
                for se in self.breakdown
            ],
        }


class RewardModel:
    """Compatibility name for the account's feedback/alignment scorer.

    The public class name is retained to avoid breaking callers. Semantically,
    it scores assistant outcomes for alignment with the shared objective; it
    does not reward or punish the user.
    """

    def __init__(
        self,
        event_scores: dict[str, float] | None = None,
        scope_weights: dict[str, float] | None = None,
    ) -> None:
        self.event_scores = dict(event_scores or EVENT_SCORES)
        self.scope_weights = dict(scope_weights or SCOPE_WEIGHTS)

    def score_event(self, event: OutcomeEvent) -> float:
        if event.type not in self.event_scores:
            raise RewardModelError(f"unknown outcome event type {event.type!r}")
        base = self.event_scores[event.type]
        scope_weight = self.scope_weights.get(event.scope, 1.0)
        if base < 0:
            # Recurrence increases suppression of the assistant failure mode.
            # It does not increase skepticism toward the user.
            recurrence_multiplier = 2 ** max(event.recurrence_count - 1, 0)
            return base * recurrence_multiplier * event.confidence * scope_weight
        return base * event.confidence

    def apply(self, events: list[OutcomeEvent | dict[str, Any]]) -> RewardReport:
        normalized = [
            e if isinstance(e, OutcomeEvent) else OutcomeEvent.from_dict(e)
            for e in events
        ]
        scored = [ScoredEvent(event=e, score=self.score_event(e)) for e in normalized]
        total = sum(s.score for s in scored)
        return RewardReport(total=total, breakdown=scored)
