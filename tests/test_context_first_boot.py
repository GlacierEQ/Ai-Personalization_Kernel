from __future__ import annotations

from pathlib import Path

from apk.boot import BootContract
from apk.context_first_router_v2 import CORE_CONTEXT_TIERS
from apk.policy import PolicyEngine


def _contract(tmp_data_dir: Path, sources=None) -> BootContract:
    policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
    return BootContract(
        user_model_path=tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
        policy=policy,
        context_sources=sources,
    )


def test_boot_requests_core_context_before_action_selection(tmp_data_dir: Path) -> None:
    receipt = _contract(tmp_data_dir).run(
        message="simple question",
        relevant_context_exists=True,
        context_retrieved=False,
    )
    recovery = next(step for step in receipt.steps if step.name == "retrieve_deep_context")
    action = next(step for step in receipt.steps if step.name == "select_action_policy")
    assert recovery.index < action.index
    assert tuple(recovery.detail["requested_tiers"]) == CORE_CONTEXT_TIERS
    assert recovery.detail["context_retrieved"] is False
    assert set(recovery.detail["unavailable_tiers"]) == set(CORE_CONTEXT_TIERS)


def test_boot_does_not_call_selected_tier_retrieved_without_payload(tmp_data_dir: Path) -> None:
    sources = {tier: (lambda request: []) for tier in CORE_CONTEXT_TIERS}
    receipt = _contract(tmp_data_dir, sources).run(
        message="continue",
        relevant_context_exists=True,
        context_retrieved=False,
    )
    recovery = next(step for step in receipt.steps if step.name == "retrieve_deep_context")
    assert set(recovery.detail["attempted_tiers"]) == set(CORE_CONTEXT_TIERS)
    assert set(recovery.detail["empty_tiers"]) == set(CORE_CONTEXT_TIERS)
    assert recovery.detail["context_retrieved"] is False


def test_boot_recovers_history_without_turn_trigger(tmp_data_dir: Path) -> None:
    sources = {
        tier: (lambda request, tier=tier: [{"tier": tier, "message": request.message}])
        for tier in CORE_CONTEXT_TIERS
    }
    receipt = _contract(tmp_data_dir, sources).run(
        message="what now",
        triggers=set(),
        relevant_context_exists=True,
        context_retrieved=False,
    )
    recovery = next(step for step in receipt.steps if step.name == "retrieve_deep_context")
    assert recovery.detail["context_retrieved"] is True
    assert "historical_chats" in recovery.detail["retrieved_tiers"]
    assert "project_state" in recovery.detail["retrieved_tiers"]


def test_exact_factual_need_adds_live_provider_lane(tmp_data_dir: Path) -> None:
    sources = {
        **{
            tier: (lambda request, tier=tier: [{"tier": tier}])
            for tier in CORE_CONTEXT_TIERS
        },
        "live_provider_state": lambda request: [{"provider": "current"}],
    }
    receipt = _contract(tmp_data_dir, sources).run(
        message="get the exact current state",
        triggers={"exact_factual_need"},
        relevant_context_exists=True,
        context_retrieved=False,
    )
    recovery = next(step for step in receipt.steps if step.name == "retrieve_deep_context")
    assert "live_provider_state" in recovery.detail["requested_tiers"]
    assert "live_provider_state" in recovery.detail["retrieved_tiers"]
