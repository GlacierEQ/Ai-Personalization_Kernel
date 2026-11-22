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


@dataclass(frozen=True)
class EvidenceContinuity:
    """Structured cumulative evidence coverage independent of legal sufficiency.

    established_propositions are already supported *within their stated scope*.
    affirmatively_carried are the established IDs retained in the proposed
    synthesis. A missing order or actor link remains an open dimension rather
    than silently cancelling every earlier filing, notice or admission.

    The caller supplies source-grounded proposition IDs, not generated claims.
    This guard cannot confer admissibility, authenticate sources or invent
    legal liability.
    """

    established_propositions: tuple[str, ...] = ()
    affirmatively_carried: tuple[str, ...] = ()
    open_dimensions: tuple[str, ...] = ()
    next_executable_transition: str = ""
    global_stop_inferred: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "EvidenceContinuity":
        data = dict(value or {})
        fields = ("established_propositions", "affirmatively_carried", "open_dimensions")
        for key in fields:
            data[key] = tuple(dict.fromkeys(data.get(key) or ()))
            if any(not isinstance(x, str) or not x.strip() for x in data[key]):
                raise DetailIntegrityError(f"{key} must contain nonempty proposition identifiers")
        established = set(data["established_propositions"])
        unknown = set(data["affirmatively_carried"]) - established
        if unknown:
            raise DetailIntegrityError(
                "affirmatively carried proposition not established: "
                + ", ".join(sorted(unknown))
            )
        return cls(
            established_propositions=data["established_propositions"],
            affirmatively_carried=data["affirmatively_carried"],
            open_dimensions=data["open_dimensions"],
            next_executable_transition=str(data.get("next_executable_transition") or ""),
            global_stop_inferred=bool(data.get("global_stop_inferred", False)),
        )

    def missing_established_propositions(self) -> tuple[str, ...]:
        retained = set(self.affirmatively_carried)
        return tuple(p for p in self.established_propositions if p not in retained)

    def incomplete_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.missing_established_propositions():
            reasons.append("established_evidence_atomized_or_omitted")
        if self.global_stop_inferred and (self.open_dimensions or self.established_propositions):
            reasons.append("local_gap_promoted_to_global_stop")
        return tuple(reasons)

    @property
    def complete(self) -> bool:
        return not self.incomplete_reasons()

    def to_receipt(self) -> dict[str, Any]:
        return {
            "established_propositions": list(self.established_propositions),
            "affirmatively_carried": list(self.affirmatively_carried),
            "missing_established_propositions": list(self.missing_established_propositions()),
            "open_dimensions": list(self.open_dimensions),
            "next_executable_transition": self.next_executable_transition,
            "global_stop_inferred": self.global_stop_inferred,
            "complete": self.complete,
            "incomplete_reasons": list(self.incomplete_reasons()),
            "mission_continues": True,
        }


def enforce_evidence_continuity(
    action: str, continuity: EvidenceContinuity
) -> tuple[str, dict[str, Any]]:
    """Reject omission-based synthesis, not legitimate localized legal caveats.

    Missing record dimensions cannot convert affirmed propositions into
    unproven facts or mission vetoes. Failed synthesis returns to existing
    evidence work, without inventing sources or erasing the unresolved gap.
    """
    receipt = continuity.to_receipt()
    receipt["policy_selected_action"] = action
    if continuity.complete or action not in SYNTHESIS_ACTIONS:
        receipt["enforced_action"] = action
        receipt["override_applied"] = False
        return action, receipt
    receipt["enforced_action"] = CONTINUATION_ACTION
    receipt["override_applied"] = True
    return CONTINUATION_ACTION, receipt
