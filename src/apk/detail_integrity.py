"""Lossless source-detail integrity guard.

This module prevents a high-consequence failure mode: treating partial source
inspection as complete review and then converting assistant-side omissions into
uncertainty in the underlying matter.

The guard is deliberately simple and auditable. It does not decide what the
evidence means. It decides whether the runtime is allowed to synthesize as if
the source set has been exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SYNTHESIS_ACTIONS = frozenset({"answer_directly", "create_artifact"})
CONTINUATION_ACTION = "continue_existing_work"


class DetailIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class SourceCoverage:
    """Coverage receipt for an evidence/source set.

    indexed_items means the item was discovered/catalogued.
    partially_reviewed_items means some content was inspected.
    fully_reviewed_items means the source was reviewed at the level
    required by the task. These states are intentionally not interchangeable.
    """

    requires_exhaustive_review: bool = False
    source_set_declared: bool = False
    total_items: int = 0
    indexed_items: int = 0
    partially_reviewed_items: int = 0
    fully_reviewed_items: int = 0
    material_detail_extraction_complete: bool = True
    representative_sampling_only: bool = False

    def __post_init__(self) -> None:
        numeric = {
            "total_items": self.total_items,
            "indexed_items": self.indexed_items,
            "partially_reviewed_items": self.partially_reviewed_items,
            "fully_reviewed_items": self.fully_reviewed_items,
        }
        for name, value in numeric.items():
            if value < 0:
                raise DetailIntegrityError(f"{name} cannot be negative")
        if self.source_set_declared:
            for name in ("indexed_items", "partially_reviewed_items", "fully_reviewed_items"):
                if getattr(self, name) > self.total_items:
                    raise DetailIntegrityError(f"{name} cannot exceed total_items")

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any] | None,
        *,
        force_exhaustive: bool = False,
    ) -> "SourceCoverage":
        data = dict(value or {})
        if force_exhaustive:
            data["requires_exhaustive_review"] = True
            data.setdefault("source_set_declared", False)
            data.setdefault("material_detail_extraction_complete", False)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def incomplete_reasons(self) -> tuple[str, ...]:
        if not self.requires_exhaustive_review:
            return ()
        reasons: list[str] = []
        if not self.source_set_declared:
            reasons.append("source_set_not_declared")
        if self.representative_sampling_only:
            reasons.append("representative_sampling_is_not_full_review")
        if self.source_set_declared and self.fully_reviewed_items < self.total_items:
            reasons.append("source_items_not_fully_reviewed")
        if not self.material_detail_extraction_complete:
            reasons.append("material_detail_extraction_incomplete")
        return tuple(reasons)

    @property
    def complete(self) -> bool:
        return not self.incomplete_reasons()

    def to_receipt(self) -> dict[str, Any]:
        return {
            "requires_exhaustive_review": self.requires_exhaustive_review,
            "source_set_declared": self.source_set_declared,
            "total_items": self.total_items,
            "indexed_items": self.indexed_items,
            "partially_reviewed_items": self.partially_reviewed_items,
            "fully_reviewed_items": self.fully_reviewed_items,
            "material_detail_extraction_complete": self.material_detail_extraction_complete,
            "representative_sampling_only": self.representative_sampling_only,
            "complete": self.complete,
            "incomplete_reasons": list(self.incomplete_reasons()),
        }


def enforce_detail_integrity(action: str, coverage: SourceCoverage) -> tuple[str, dict[str, Any]]:
    """Prevent partial review from being laundered into apparent completion."""

    receipt = coverage.to_receipt()
    receipt["policy_selected_action"] = action
    if coverage.complete or action not in SYNTHESIS_ACTIONS:
        receipt["enforced_action"] = action
        receipt["override_applied"] = False
        return action, receipt

    receipt["enforced_action"] = CONTINUATION_ACTION
    receipt["override_applied"] = True
    return CONTINUATION_ACTION, receipt
