"""Context-first retrieval router v2.

Counter-engineers the trigger-gated deep-retrieval defect without deleting the
existing router. Core continuity/history lanes are requested every turn.
Provider freshness and public web remain task-scoped. Receipts distinguish
requested, attempted, retrieved, and unavailable lanes so a selected tier can
never masquerade as completed retrieval.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from apk.user_model import UserModel


CORE_CONTEXT_TIERS: tuple[str, ...] = (
    "current_conversation",
    "recent_exact_messages",
    "project_state",
    "historical_chats",
    "canonical_artifacts",
    "external_memory_indexes",
)

OPTIONAL_TIERS: tuple[str, ...] = (
    "live_provider_state",
    "general_web",
)

ALL_TIERS: tuple[str, ...] = (
    "always_active_user_model",
    *CORE_CONTEXT_TIERS,
    *OPTIONAL_TIERS,
)


@dataclass(frozen=True)
class ContextRequest:
    message: str
    require_live_provider_state: bool = False
    require_general_web: bool = False


@dataclass(frozen=True)
class ContextItem:
    tier: str
    source: str
    ref_id: str
    content: Any


@dataclass(frozen=True)
class ContextRecoveryReceipt:
    requested_tiers: tuple[str, ...]
    attempted_tiers: tuple[str, ...]
    retrieved_tiers: tuple[str, ...]
    unavailable_tiers: tuple[str, ...]
    empty_tiers: tuple[str, ...]
    items: tuple[ContextItem, ...]

    @property
    def core_recovery_attempted(self) -> bool:
        return all(
            tier in self.attempted_tiers or tier in self.unavailable_tiers
            for tier in CORE_CONTEXT_TIERS
        )

    @property
    def core_recovery_complete(self) -> bool:
        return all(tier in self.retrieved_tiers for tier in CORE_CONTEXT_TIERS)

    @property
    def any_deep_context_retrieved(self) -> bool:
        return any(
            tier != "always_active_user_model" for tier in self.retrieved_tiers
        )


class ContextFirstRouter:
    """Recover core context before action selection on every turn.

    The sources mapping maps a tier to a callable returning context payloads.
    Missing adapters are explicit receipt state; they are never interpreted as
    successful retrieval.
    """

    def __init__(
        self,
        user_model: UserModel,
        sources: Mapping[
            str, Callable[[ContextRequest], list[Any] | tuple[Any, ...]]
        ] | None = None,
    ) -> None:
        self.user_model = user_model
        self.sources = dict(sources or {})

    def recover(self, request: ContextRequest) -> ContextRecoveryReceipt:
        requested = list(CORE_CONTEXT_TIERS)
        if request.require_live_provider_state:
            requested.append("live_provider_state")
        if request.require_general_web:
            requested.append("general_web")

        items: list[ContextItem] = [
            ContextItem(
                tier="always_active_user_model",
                source="user_model",
                ref_id="compact_user_model",
                content=self.user_model.to_dict(),
            )
        ]
        attempted: list[str] = []
        retrieved: list[str] = ["always_active_user_model"]
        unavailable: list[str] = []
        empty: list[str] = []

        for tier in requested:
            fetch = self.sources.get(tier)
            if fetch is None:
                unavailable.append(tier)
                continue

            attempted.append(tier)
            payloads = list(fetch(request) or ())
            if not payloads:
                empty.append(tier)
                continue

            retrieved.append(tier)
            for index, payload in enumerate(payloads):
                items.append(
                    ContextItem(
                        tier=tier,
                        source=tier,
                        ref_id=f"{tier}:{index}",
                        content=payload,
                    )
                )

        return ContextRecoveryReceipt(
            requested_tiers=tuple(requested),
            attempted_tiers=tuple(attempted),
            retrieved_tiers=tuple(retrieved),
            unavailable_tiers=tuple(unavailable),
            empty_tiers=tuple(empty),
            items=tuple(items),
        )


def action_selection_may_treat_context_as_retrieved(
    receipt: ContextRecoveryReceipt,
    *,
    require_complete_core: bool = False,
) -> bool:
    """Truthful bridge for action policy.

    Selecting or activating a tier is not retrieval. Callers may choose the
    stronger complete-core requirement; either way, no missing adapter can
    produce a false positive.
    """
    if require_complete_core:
        return receipt.core_recovery_complete
    return receipt.any_deep_context_retrieved
