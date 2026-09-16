from __future__ import annotations

import pytest

from apk.collaboration import CollaborationFoundation
from apk.reward import RewardModel


class TestCollaborationFoundation:
    def test_default_posture_is_aligned_but_independent(self):
        receipt = CollaborationFoundation.default()
        assert receipt.stance == "aligned_but_independent_collaboration"
        assert "never the operator as a person" in receipt.adversarial_target
        assert "corrections_trigger_repair_and_policy_learning" in receipt.rules
        assert "assistant_as_cross_examiner_of_user" in receipt.forbidden_postures

    @pytest.mark.parametrize(
        "target",
        ["user", "operator", "user credibility", "operator credibility"],
    )
    def test_adversarial_target_cannot_be_the_user(self, target: str):
        with pytest.raises(ValueError):
            CollaborationFoundation.validate_target(target)

    @pytest.mark.parametrize(
        "target",
        ["opposing proposition", "failure mode", "legal defense", "provider state"],
    )
    def test_adversarial_target_can_be_a_proposition_or_failure_mode(self, target: str):
        CollaborationFoundation.validate_target(target)

    def test_uncertainty_is_localized_not_globalized(self):
        dims = CollaborationFoundation.localize_uncertainty(
            ["exact wording", "timestamp", "exact wording"]
        )
        assert dims == ("exact wording", "timestamp")


class TestRelationalFeedbackSignals:
    def test_integrating_user_correction_is_positive_supervision_signal(self):
        rm = RewardModel()
        report = rm.apply([{"type": "user_correction_integrated"}])
        assert report.total == 5.0

    def test_adversarial_posture_toward_user_is_strong_failure_signal(self):
        rm = RewardModel()
        first = rm.apply(
            [{"type": "adversarial_posture_toward_user", "scope": "global"}]
        )
        repeated = rm.apply(
            [
                {
                    "type": "adversarial_posture_toward_user",
                    "scope": "global",
                    "recurrence_count": 2,
                }
            ]
        )
        assert repeated.total < first.total < 0

    def test_localized_disagreement_is_rewarded(self):
        rm = RewardModel()
        report = rm.apply(
            [{"type": "localized_disagreement_without_credibility_judgment"}]
        )
        assert report.total > 0
