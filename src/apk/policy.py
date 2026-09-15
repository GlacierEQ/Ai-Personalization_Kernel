"""Policy engine: candidate action scoring (spec section 9 /
docs/CORRECTION_PROMOTION_POLICY.md section 5).

This is the binding enforcement layer. Corrections, preferences, and the
instruction-displacement guard are not documentation; they mutate the
numeric score used to rank candidate actions, and ``select()`` returns full
auditable score breakdowns (receipts) for every candidate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

CANONICAL_ACTIONS: tuple[str, ...] = (
    "retrieve_personal_context",
    "retrieve_project_context",
    "retrieve_exact_history",
    "inspect_provider_state",
    "search_files",
    "search_web",
    "continue_existing_work",
    "execute_reversible_action",
    "verify_action",
    "answer_directly",
    "ask_question",
    "create_artifact",
)

DEFAULT_ACTION_ALIASES: dict[str, str] = {
    "generic_answer_without_context": "answer_directly",
    "ask_user_to_repeat_known_info": "ask_question",
    "retrieve_project_state": "retrieve_project_context",
    "inspect_provider": "inspect_provider_state",
}

DEFAULT_RETRIEVAL_ACTIONS: tuple[str, ...] = (
    "retrieve_personal_context",
    "retrieve_project_context",
    "retrieve_exact_history",
    "inspect_provider_state",
    "search_files",
    "continue_existing_work",
    "verify_action",
)

DEFAULT_SCOPE_WEIGHTS: dict[str, float] = {
    "conversation": 1.0,
    "domain": 1.5,
    "project": 2.0,
    "global": 3.0,
}

DEFAULT_PROMOTION_MULTIPLIERS: dict[str, float] = {
    "observation": 1.0,
    "preference": 1.0,
    "strong_preference": 2.0,
    "procedural_rule": 4.0,
}

DEFAULT_BASE_CORRECTION_PENALTY = -5.0
DEFAULT_INVARIANT_HARD_PENALTY = -1_000_000.0


class PolicyError(ValueError):
    pass


@dataclass
class CorrectionLike:
    """Minimal shape a correction-like object must have to influence scoring."""

    id: str
    pattern: str
    desired_behavior: str
    undesired_behavior: str
    promotion_level: str
    recurrence_count: int
    confidence: float
    scope: str = "global"
    status: str = "active"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CorrectionLike":
        return cls(
            id=d["id"],
            pattern=d.get("pattern", d["id"]),
            desired_behavior=d["desired_behavior"],
            undesired_behavior=d["undesired_behavior"],
            promotion_level=d["promotion_level"],
            recurrence_count=int(d.get("recurrence_count", 1)),
            confidence=float(d.get("confidence", 1.0)),
            scope=d.get("scope", "global"),
            status=d.get("status", "active"),
        )


@dataclass
class PreferenceLike:
    id: str
    desired_action: str
    confidence: float = 1.0


@dataclass
class DecisionContext:
    """Everything the policy needs to score candidate actions for one turn."""

    relevant_context_exists: bool = False
    context_retrieved: bool = False
    info_available_in_user_model: bool = False
    active_corrections: list[CorrectionLike] = field(default_factory=list)
    active_preferences: list[PreferenceLike] = field(default_factory=list)
    scope: str = "conversation"


@dataclass
class Adjustment:
    reason: str
    delta: float


@dataclass
class ScoredAction:
    name: str
    base_score: float
    adjustments: list[Adjustment]
    final_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "base_score": self.base_score,
            "adjustments": [{"reason": a.reason, "delta": a.delta} for a in self.adjustments],
            "final_score": self.final_score,
        }


@dataclass
class PolicyDecision:
    ranked: list[ScoredAction]

    def selected(self) -> ScoredAction:
        return self.ranked[0]

    def to_dict(self) -> dict[str, Any]:
        return {"ranked": [a.to_dict() for a in self.ranked]}


class PolicyEngine:
    def __init__(
        self,
        base_weights: dict[str, float],
        action_aliases: Optional[dict[str, str]] = None,
        retrieval_actions: Optional[tuple[str, ...]] = None,
        scope_weights: Optional[dict[str, float]] = None,
        promotion_multipliers: Optional[dict[str, float]] = None,
        base_correction_penalty: float = DEFAULT_BASE_CORRECTION_PENALTY,
        invariant_hard_penalty: float = DEFAULT_INVARIANT_HARD_PENALTY,
    ) -> None:
        self.base_weights = dict(base_weights)
        self.action_aliases = dict(action_aliases or DEFAULT_ACTION_ALIASES)
        self.retrieval_actions = tuple(retrieval_actions or DEFAULT_RETRIEVAL_ACTIONS)
        self.scope_weights = dict(scope_weights or DEFAULT_SCOPE_WEIGHTS)
        self.promotion_multipliers = dict(promotion_multipliers or DEFAULT_PROMOTION_MULTIPLIERS)
        self.base_correction_penalty = base_correction_penalty
        self.invariant_hard_penalty = invariant_hard_penalty

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyEngine":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            base_weights=data["base_weights"],
            action_aliases=data.get("action_aliases"),
            retrieval_actions=tuple(data.get("retrieval_actions", DEFAULT_RETRIEVAL_ACTIONS)),
            scope_weights=data.get("scope_weights"),
            promotion_multipliers=data.get("promotion_multipliers"),
            base_correction_penalty=data.get(
                "base_correction_penalty", DEFAULT_BASE_CORRECTION_PENALTY
            ),
            invariant_hard_penalty=data.get(
                "invariant_hard_penalty", DEFAULT_INVARIANT_HARD_PENALTY
            ),
        )

    def canonical(self, action: str) -> str:
        return self.action_aliases.get(action, action)

    def _correction_penalty(self, corr: CorrectionLike) -> float:
        if corr.promotion_level == "invariant":
            return self.invariant_hard_penalty
        scale = self.promotion_multipliers.get(corr.promotion_level, 1.0)
        recurrence_multiplier = 2 ** max(corr.recurrence_count - 1, 0)
        scope_weight = self.scope_weights.get(corr.scope, 1.0)
        return (
            self.base_correction_penalty
            * scale
            * recurrence_multiplier
            * corr.confidence
            * scope_weight
        )

    def _correction_boost(self, corr: CorrectionLike) -> float:
        # Symmetric positive reinforcement of the desired_behavior, scaled the
        # same way but without the invariant hard-block (desired behavior has
        # no ceiling to hard-block, only floor at 0 avoidance handled by caller).
        scale = self.promotion_multipliers.get(corr.promotion_level, 1.0)
        if corr.promotion_level == "invariant":
            scale = self.promotion_multipliers.get("procedural_rule", 4.0) * 2
        recurrence_multiplier = 2 ** max(corr.recurrence_count - 1, 0)
        scope_weight = self.scope_weights.get(corr.scope, 1.0)
        return abs(self.base_correction_penalty) * 0.3 * scale * corr.confidence * min(
            recurrence_multiplier, 4
        ) * (scope_weight / 3.0)

    def score_action(self, action: str, context: DecisionContext) -> ScoredAction:
        canonical_name = self.canonical(action)
        if canonical_name not in self.base_weights:
            raise PolicyError(f"unknown candidate action {action!r} (canonical={canonical_name!r})")
        base = self.base_weights[canonical_name]
        adjustments: list[Adjustment] = []
        total = base

        # Rule 1: active corrections penalize their undesired_behavior and
        # boost their desired_behavior, scaled by promotion_level and recurrence.
        for corr in context.active_corrections:
            if corr.status != "active":
                continue
            if self.canonical(corr.undesired_behavior) == canonical_name:
                penalty = self._correction_penalty(corr)
                adjustments.append(Adjustment(f"correction[{corr.id}].undesired_behavior_penalty", penalty))
                total += penalty
            if self.canonical(corr.desired_behavior) == canonical_name:
                boost = self._correction_boost(corr)
                adjustments.append(Adjustment(f"correction[{corr.id}].desired_behavior_boost", boost))
                total += boost

        # Rule 2: known applicable preferences boost aligned actions.
        for pref in context.active_preferences:
            if self.canonical(pref.desired_action) == canonical_name:
                boost = 0.5 * pref.confidence
                adjustments.append(Adjustment(f"preference[{pref.id}].boost", boost))
                total += boost

        # Rule 3: instruction-displacement guard. When relevant context exists
        # and has not yet been retrieved, answer_directly/ask_question must
        # score BELOW every retrieval action.
        if canonical_name in ("answer_directly", "ask_question"):
            if context.relevant_context_exists and not context.context_retrieved:
                retrieval_scores = [
                    self.base_weights[a] for a in self.retrieval_actions if a in self.base_weights
                ]
                min_retrieval_score = min(retrieval_scores) if retrieval_scores else 0.0
                target_ceiling = min_retrieval_score - 1.0
                penalty = target_ceiling - total
                adjustments.append(Adjustment("instruction_displacement_guard", penalty))
                total += penalty

        # Rule 5: asking for info that already exists in the user model is
        # always bottom-ranked.
        if canonical_name == "ask_question" and context.info_available_in_user_model:
            penalty = -(abs(base) + 1000.0)
            adjustments.append(Adjustment("known_info_guard", penalty))
            total += penalty

        return ScoredAction(name=action, base_score=base, adjustments=adjustments, final_score=total)

    def select(
        self, context: DecisionContext, candidates: Optional[list[str]] = None
    ) -> PolicyDecision:
        names = candidates or list(self.base_weights.keys())
        scored = [self.score_action(name, context) for name in names]
        scored.sort(key=lambda s: s.final_score, reverse=True)
        return PolicyDecision(ranked=scored)
