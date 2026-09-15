"""Always-active compact user model loader (spec section 4 / axiom 1 of
PERSONALIZATION_RETRIEVAL_POLICY.md).

Loading is mandatory, not optional: if the model file is missing, this
module raises loudly rather than silently falling back to a generic default.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from apk.store import JsonlStore


class UserModelMissingError(RuntimeError):
    """Raised when the always-active user model cannot be loaded.

    Personalization is not optional (spec section 1 / invariant 1): a
    missing user model is a hard failure, never a silent generic fallback.
    """


@dataclass
class UserModel:
    identity: dict[str, Any]
    expertise: list[str]
    interest_weights: dict[str, float]
    epistemic_preferences: list[str]
    interaction_preferences: list[str]
    output_preferences: list[str]
    strategic_preferences: list[str]
    prohibitions: list[str]
    active_goals: list[str]
    correction_refs: list[str]
    strategy_refs: list[str]
    continuity_state: dict[str, Any]
    _store: Optional[JsonlStore] = field(default=None, repr=False, compare=False)
    _corrections_path: Optional[Path] = field(default=None, repr=False, compare=False)

    # -- loading ------------------------------------------------------------

    @classmethod
    def load(
        cls,
        path: str | Path,
        store: Optional[JsonlStore] = None,
        corrections_path: Optional[str | Path] = None,
    ) -> "UserModel":
        p = Path(path)
        if not p.exists():
            raise UserModelMissingError(
                f"always-active user model not found at {p}; personalization is not "
                "optional, refusing to proceed with a generic default"
            )
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UserModelMissingError(f"user model at {p} is not valid JSON: {exc}") from exc

        required = [
            "identity", "expertise", "interest_weights", "epistemic_preferences",
            "interaction_preferences", "output_preferences", "strategic_preferences",
            "prohibitions", "active_goals", "correction_refs", "strategy_refs",
            "continuity_state",
        ]
        missing = [k for k in required if k not in data]
        if missing:
            raise UserModelMissingError(
                f"user model at {p} is missing required fields: {missing}"
            )
        return cls(
            identity=data["identity"],
            expertise=list(data["expertise"]),
            interest_weights=dict(data["interest_weights"]),
            epistemic_preferences=list(data["epistemic_preferences"]),
            interaction_preferences=list(data["interaction_preferences"]),
            output_preferences=list(data["output_preferences"]),
            strategic_preferences=list(data["strategic_preferences"]),
            prohibitions=list(data["prohibitions"]),
            active_goals=list(data["active_goals"]),
            correction_refs=list(data["correction_refs"]),
            strategy_refs=list(data["strategy_refs"]),
            continuity_state=dict(data["continuity_state"]),
            _store=store,
            _corrections_path=Path(corrections_path) if corrections_path else None,
        )

    # -- compact always-active accessors ------------------------------------

    def has_prohibition(self, pattern: str) -> bool:
        """True if ``pattern`` matches a known prohibition (exact or substring)."""
        pattern_l = pattern.lower()
        return any(pattern_l == p.lower() or pattern_l in p.lower() or p.lower() in pattern_l
                   for p in self.prohibitions)

    def interest_weight(self, topic: str) -> float:
        """Relative salience of a topic; unknown topics default to 0.0 (spec 4.2)."""
        if topic in self.interest_weights:
            return self.interest_weights[topic]
        topic_l = topic.lower()
        for k, v in self.interest_weights.items():
            if k.lower() == topic_l:
                return v
        return 0.0

    def active_corrections(self) -> list[dict[str, Any]]:
        """Load referenced (or all) active corrections from the correction ledger."""
        if self._corrections_path is None or not Path(self._corrections_path).exists():
            return []
        from apk.corrections import CorrectionLedger

        ledger = CorrectionLedger(self._corrections_path)
        corrections = ledger.active_corrections()
        if self.correction_refs:
            wanted = set(self.correction_refs)
            corrections = [c for c in corrections if c.id in wanted or c.pattern in wanted]
        return [c.to_dict() for c in corrections]

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "expertise": self.expertise,
            "interest_weights": self.interest_weights,
            "epistemic_preferences": self.epistemic_preferences,
            "interaction_preferences": self.interaction_preferences,
            "output_preferences": self.output_preferences,
            "strategic_preferences": self.strategic_preferences,
            "prohibitions": self.prohibitions,
            "active_goals": self.active_goals,
            "correction_refs": self.correction_refs,
            "strategy_refs": self.strategy_refs,
            "continuity_state": self.continuity_state,
        }
