"""Additional coverage for router.py, reward.py, and drift.py.

Not part of the enforcement suite named in the build contract, but these
modules are shipped as real, tested components rather than stubs.
"""

from __future__ import annotations

import pytest

from apk.drift import DriftDetector
from apk.reward import RewardModel
from apk.router import ReingestionError, RetrievalRouter, TurnContext


class TestRetrievalRouter:
    def test_user_model_tier_always_present_with_no_triggers(self, user_model):
        router = RetrievalRouter(user_model)
        receipt = router.assemble(TurnContext(message="hello"))
        assert receipt.tiers_activated == ("always_active_user_model",)
        assert receipt.items[0].tier == "always_active_user_model"

    def test_triggers_activate_mapped_tiers_in_canonical_order(self, user_model):
        from apk.router import TIERS

        router = RetrievalRouter(user_model)
        receipt = router.assemble(
            TurnContext(message="resume the project", triggers=frozenset({"continuity", "exact_factual_need"}))
        )
        assert receipt.tiers_activated[0] == "always_active_user_model"
        assert "project_state" in receipt.tiers_activated
        assert "historical_chats" in receipt.tiers_activated
        assert "live_provider_state" in receipt.tiers_activated
        # canonical cascade order preserved
        indices = [TIERS.index(t) for t in receipt.tiers_activated]
        assert indices == sorted(indices)

    def test_unknown_trigger_rejected(self):
        with pytest.raises(ValueError):
            TurnContext(message="x", triggers=frozenset({"not_a_real_trigger"}))

    def test_anti_recursion_guard_blocks_reingestion(self, user_model):
        router = RetrievalRouter(user_model)
        receipt = router.assemble(TurnContext(message="hello"))
        with pytest.raises(ReingestionError):
            RetrievalRouter.guard_against_reingestion("user_model", receipt)

    def test_anti_recursion_guard_allows_unrelated_new_source(self, user_model):
        router = RetrievalRouter(user_model)
        receipt = router.assemble(TurnContext(message="hello"))
        # should not raise: genuinely new raw source, not a re-ingestion of injected content
        RetrievalRouter.guard_against_reingestion("raw_user_message", receipt)


class TestRewardModel:
    def test_positive_event_scores_directly(self):
        rm = RewardModel()
        report = rm.apply([{"type": "explicit_user_approval"}])
        assert report.total == 5.0

    def test_negative_event_scales_with_recurrence_and_scope(self):
        rm = RewardModel()
        first = rm.apply([{"type": "repeated_corrected_behavior", "recurrence_count": 1, "scope": "global"}])
        second = rm.apply([{"type": "repeated_corrected_behavior", "recurrence_count": 2, "scope": "global"}])
        assert second.total < first.total < 0

    def test_scope_weight_applied_to_penalties(self):
        rm = RewardModel()
        global_penalty = rm.apply([{"type": "ignored_known_preference", "scope": "global"}]).total
        conv_penalty = rm.apply([{"type": "ignored_known_preference", "scope": "conversation"}]).total
        assert global_penalty < conv_penalty < 0

    def test_unknown_event_type_raises(self):
        rm = RewardModel()
        with pytest.raises(Exception):
            rm.apply([{"type": "not_a_real_event"}])


class TestDriftDetector:
    def test_detects_added_removed_changed(self):
        old = {"base_weights": {"a": 1.0, "b": 2.0}}
        new = {"base_weights": {"a": 1.5, "c": 3.0}}
        report = DriftDetector.compare(old, new)
        assert "base_weights.c" in report.added
        assert "base_weights.b" in report.removed
        assert "base_weights.a" in report.changed
        assert report.has_drift is True
        assert report.old_hash != report.new_hash

    def test_identical_states_have_no_drift(self):
        state = {"x": 1, "y": {"z": 2}}
        report = DriftDetector.compare(state, state)
        assert report.has_drift is False
        assert report.old_hash == report.new_hash
