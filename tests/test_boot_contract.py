from __future__ import annotations

from pathlib import Path

import pytest

from apk.boot import BootContract, BootContractError, STEP_NAMES
from apk.policy import PolicyEngine
from apk.user_model import UserModelMissingError


@pytest.fixture()
def boot_contract(tmp_data_dir: Path) -> BootContract:
    policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
    return BootContract(
        user_model_path=tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
        policy=policy,
    )


class TestBootReceiptShape:
    def test_receipt_has_all_twelve_steps_in_order(self, boot_contract: BootContract):
        receipt = boot_contract.run(message="Continue the ongoing repository work.")
        assert len(receipt.steps) == 12
        assert receipt.step_names_in_order() == list(STEP_NAMES)
        for expected_index, step in enumerate(receipt.steps, start=1):
            assert step.index == expected_index

    def test_answer_step_is_always_last(self, boot_contract: BootContract):
        receipt = boot_contract.run(message="What should we do next?")
        assert receipt.steps[-1].name == "answer"

    def test_receipt_is_json_serializable(self, boot_contract: BootContract):
        import json

        receipt = boot_contract.run(message="Continue.")
        json.dumps(receipt.to_dict())

    def test_selected_action_recorded(self, boot_contract: BootContract):
        receipt = boot_contract.run(
            message="Just answer without checking anything.",
            relevant_context_exists=True,
            context_retrieved=False,
        )
        assert receipt.selected_action is not None
        assert receipt.selected_action != "answer_directly"

    def test_collaboration_posture_is_established_before_claim_classification(
        self, boot_contract: BootContract
    ):
        receipt = boot_contract.run(message="I am correcting the way you treated my account.")
        apply_step = next(s for s in receipt.steps if s.name == "apply_user_message")
        classify_step = next(s for s in receipt.steps if s.name == "classify_claims")
        assert apply_step.index < classify_step.index
        collaboration = apply_step.detail["collaboration"]
        assert collaboration["stance"] == "aligned_but_independent_collaboration"
        assert "never the operator as a person" in collaboration["adversarial_target"]
        assert "assistant_as_gatekeeper_over_user" in collaboration["forbidden_postures"]


class TestVerificationStep:
    def test_verification_recorded_when_provider_claim_flagged(self, boot_contract: BootContract):
        receipt = boot_contract.run(
            message="Check the current state.",
            claims=[
                {
                    "content": "git status right now shows a clean tree",
                    "claim_type": "provider_state",
                }
            ],
        )
        verify_step = next(s for s in receipt.steps if s.name == "verify_externally")
        assert verify_step.status == "ok"
        assert verify_step.detail["verification_required"] is True
        assert "preserve user source role" in verify_step.detail["verification_posture"]

    def test_verification_skipped_when_no_factual_claims(self, boot_contract: BootContract):
        receipt = boot_contract.run(
            message="Continue existing work.",
            claims=[],
            relevant_context_exists=False,
        )
        verify_step = next(s for s in receipt.steps if s.name == "verify_externally")
        assert verify_step.status in ("ok", "skipped")


class TestCorrectionPosture:
    def test_corrections_are_supervision_signals_not_conflict(self, boot_contract: BootContract):
        receipt = boot_contract.run(message="That was wrong. Correct it and continue.")
        correction_step = next(s for s in receipt.steps if s.name == "update_correction_state")
        assert correction_step.detail["correction_posture"] == "supervision_signal_repair_and_learn"


class TestBootFailsLoudlyWithoutUserModel:
    def test_missing_user_model_raises(self, tmp_path: Path, tmp_data_dir: Path):
        policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
        contract = BootContract(
            user_model_path=tmp_path / "does_not_exist.json",
            corrections_path=tmp_data_dir / "corrections.jsonl",
            policy=policy,
        )
        with pytest.raises(BootContractError):
            contract.run(message="anything")

    def test_underlying_error_is_user_model_missing(self, tmp_path: Path, tmp_data_dir: Path):
        policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
        contract = BootContract(
            user_model_path=tmp_path / "does_not_exist.json",
            corrections_path=tmp_data_dir / "corrections.jsonl",
            policy=policy,
        )
        try:
            contract.run(message="anything")
            pytest.fail("expected BootContractError")
        except BootContractError as exc:
            assert isinstance(exc.__cause__, UserModelMissingError)
