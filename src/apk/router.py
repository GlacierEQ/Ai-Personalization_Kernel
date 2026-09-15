"""Retrieval router (spec section 7 / docs/PERSONALIZATION_RETRIEVAL_POLICY.md).

Implements the two-axiom retrieval model:

1. The compact user model is always loaded first, unconditionally
   (no relevance gate).
2. Deeper retrieval across the 9-tier cascade is selective, activated only
   by concrete triggers on the current turn.

Also implements the anti-recursion guard: any context assembled by this
router is tagged ``injected`` and must never be re-ingested as new raw
memory by a harvester/store.append call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from apk.user_model import UserModel

# The 9-tier retrieval cascade (spec section 7.3).
TIERS: tuple[str, ...] = (
    "always_active_user_model",
    "current_conversation",
    "recent_exact_messages",
    "project_state",
    "historical_chats",
    "canonical_artifacts",
    "external_memory_indexes",
    "live_provider_state",
    "general_web",
)

TRIGGERS: tuple[str, ...] = (
    "topic_overlap",
    "project_overlap",
    "correction_overlap",
    "unresolved_state",
    "failure_signature",
    "continuity",
    "exact_factual_need",
)

# Which tiers a given trigger is permitted to activate (spec section 7.2).
_TRIGGER_TIER_MAP: dict[str, tuple[str, ...]] = {
    "topic_overlap": ("project_state", "historical_chats"),
    "project_overlap": ("project_state",),
    "correction_overlap": ("canonical_artifacts",),
    "unresolved_state": ("project_state",),
    "failure_signature": ("canonical_artifacts", "historical_chats"),
    "continuity": ("project_state", "historical_chats"),
    "exact_factual_need": ("live_provider_state",),
}


class ReingestionError(RuntimeError):
    """Raised when injected/derived context is about to be re-ingested as new raw memory."""


@dataclass(frozen=True)
class TurnContext:
    message: str
    triggers: frozenset[str] = field(default_factory=frozenset)
    needs_general_web: bool = False

    def __post_init__(self) -> None:
        unknown = set(self.triggers) - set(TRIGGERS)
        if unknown:
            raise ValueError(f"unknown retrieval triggers: {sorted(unknown)}")


@dataclass(frozen=True)
class InjectedItem:
    tier: str
    source: str
    ref_id: str
    content: Any
    injected: bool = True
    reingest_eligible: bool = False

    def tag(self) -> str:
        return f"<!-- BEGIN INJECTED_CONTEXT: source={self.source} id={self.ref_id} tier={self.tier} -->"


@dataclass(frozen=True)
class RetrievalReceipt:
    tiers_activated: tuple[str, ...]
    triggers_fired: tuple[str, ...]
    items: tuple[InjectedItem, ...]

    def injected_hashes(self) -> set[int]:
        return {hash((i.tier, i.ref_id)) for i in self.items}


class RetrievalRouter:
    """Assembles context following the mandatory retrieval order.

    ``deep_sources`` maps tier name -> callable(turn) -> list[InjectedItem],
    letting callers plug in real project-state/history/provider lookups
    without this module needing to know their storage details.
    """

    def __init__(
        self,
        user_model: UserModel,
        deep_sources: Optional[dict[str, Any]] = None,
    ) -> None:
        self.user_model = user_model
        self.deep_sources = deep_sources or {}

    def assemble(self, turn: TurnContext) -> RetrievalReceipt:
        items: list[InjectedItem] = [
            InjectedItem(
                tier="always_active_user_model",
                source="user_model",
                ref_id="compact_user_model",
                content=self.user_model.to_dict(),
            )
        ]
        tiers_activated = ["always_active_user_model"]

        activated_tiers: set[str] = set()
        for trigger in turn.triggers:
            activated_tiers.update(_TRIGGER_TIER_MAP.get(trigger, ()))
        if turn.needs_general_web:
            activated_tiers.add("general_web")

        # Preserve canonical tier ordering.
        for tier in TIERS:
            if tier == "always_active_user_model":
                continue
            if tier not in activated_tiers:
                continue
            tiers_activated.append(tier)
            fetch = self.deep_sources.get(tier)
            if fetch is None:
                continue
            fetched = fetch(turn)
            for idx, content in enumerate(fetched or []):
                items.append(
                    InjectedItem(
                        tier=tier,
                        source=tier,
                        ref_id=f"{tier}:{idx}",
                        content=content,
                    )
                )

        return RetrievalReceipt(
            tiers_activated=tuple(tiers_activated),
            triggers_fired=tuple(sorted(turn.triggers)),
            items=tuple(items),
        )

    @staticmethod
    def guard_against_reingestion(
        candidate_source: str, receipt: RetrievalReceipt, candidate_ref_id: Optional[str] = None
    ) -> None:
        """Anti-recursion law: injected context must never be re-ingested as new raw memory.

        Raise if a harvester/store.append call attempts to treat a tagged
        injected item as fresh user-sourced truth.
        """
        for item in receipt.items:
            if item.injected and not item.reingest_eligible:
                if candidate_source == item.source or candidate_ref_id == item.ref_id:
                    raise ReingestionError(
                        f"refusing to re-ingest injected context (tier={item.tier}, "
                        f"source={item.source}, id={item.ref_id}) as new raw memory; "
                        "derived/injected context is immutable and harvester-isolated "
                        "(PERSONALIZATION_RETRIEVAL_POLICY.md section 5)"
                    )
