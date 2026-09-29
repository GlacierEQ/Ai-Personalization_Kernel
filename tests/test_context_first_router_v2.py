from __future__ import annotations

from apk.context_first_router_v2 import (
    CORE_CONTEXT_TIERS,
    ContextFirstRouter,
    ContextRequest,
    action_selection_may_treat_context_as_retrieved,
)


def test_core_context_is_requested_on_every_turn(user_model) -> None:
    receipt = ContextFirstRouter(user_model).recover(ContextRequest(message="hello"))
    assert receipt.requested_tiers == CORE_CONTEXT_TIERS
    assert receipt.core_recovery_attempted is True
    assert set(receipt.unavailable_tiers) == set(CORE_CONTEXT_TIERS)
    assert action_selection_may_treat_context_as_retrieved(receipt) is False


def test_missing_adapter_never_masquerades_as_retrieval(user_model) -> None:
    receipt = ContextFirstRouter(user_model).recover(ContextRequest(message="anything"))
    assert receipt.retrieved_tiers == ("always_active_user_model",)
    assert receipt.any_deep_context_retrieved is False
    assert receipt.core_recovery_complete is False


def test_history_is_retrieved_without_relevance_trigger(user_model) -> None:
    sources = {
        tier: (lambda request, tier=tier: [{"tier": tier, "message": request.message}])
        for tier in CORE_CONTEXT_TIERS
    }
    receipt = ContextFirstRouter(user_model, sources).recover(
        ContextRequest(message="simple question")
    )
    assert receipt.core_recovery_complete is True
    assert "historical_chats" in receipt.retrieved_tiers
    assert "project_state" in receipt.retrieved_tiers
    assert action_selection_may_treat_context_as_retrieved(
        receipt, require_complete_core=True
    ) is True


def test_provider_and_web_are_additive_not_context_gates(user_model) -> None:
    sources = {
        tier: (lambda request, tier=tier: [{"tier": tier}])
        for tier in (*CORE_CONTEXT_TIERS, "live_provider_state", "general_web")
    }
    base = ContextFirstRouter(user_model, sources).recover(ContextRequest(message="resume"))
    assert "live_provider_state" not in base.requested_tiers
    assert "general_web" not in base.requested_tiers

    expanded = ContextFirstRouter(user_model, sources).recover(
        ContextRequest(
            message="check current provider and public docs",
            require_live_provider_state=True,
            require_general_web=True,
        )
    )
    assert "live_provider_state" in expanded.retrieved_tiers
    assert "general_web" in expanded.retrieved_tiers


def test_empty_result_is_distinct_from_unavailable_and_retrieved(user_model) -> None:
    sources = {tier: (lambda request: []) for tier in CORE_CONTEXT_TIERS}
    receipt = ContextFirstRouter(user_model, sources).recover(ContextRequest(message="x"))
    assert set(receipt.attempted_tiers) == set(CORE_CONTEXT_TIERS)
    assert set(receipt.empty_tiers) == set(CORE_CONTEXT_TIERS)
    assert receipt.unavailable_tiers == ()
    assert action_selection_may_treat_context_as_retrieved(receipt) is False
