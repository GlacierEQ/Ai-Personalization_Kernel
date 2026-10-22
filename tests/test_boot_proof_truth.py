"""Regression: planning, acknowledgement, and verification are distinct stages.

The 2026-10-22 cross-chat directive incident showed why a memory tool ACK
must not be promoted into deployed/enforced behavior. These tests exercise
the real BootContract receipt, not prose or a mocked completion signal.
"""
from __future__ import annotations

from pathlib import Path

from apk.boot import BootContract
from apk.policy import PolicyEngine


def _boot(tmp_data_dir: Path) -> BootContract:
    return BootContract(
        user_model_path=tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
        policy=PolicyEngine.from_file(tmp_data_dir / "policy_weights.json"),
    )


def _step(receipt, name):
    return next(step for step in receipt.steps if step.name == name)


def test_selected_action_is_not_recorded_as_executed_without_executor(tmp_data_dir):
    receipt = _boot(tmp_data_dir).run(message="Execute the authorized existing mission.")
    step = _step(receipt, "execute_action")
    assert receipt.selected_action is not None
    assert step.status == "not_executed"
    assert step.detail["planned_action"] == receipt.selected_action
    assert step.detail["executed_action"] is None
    assert step.detail["execution_performed"] is False
    assert step.detail["provider_receipt"] is None


def test_memory_update_acknowledgement_does_not_prove_cross_chat_enforcement(tmp_data_dir):
    receipt = _boot(tmp_data_dir).run(
        message="Prove that my directive controls a new chat, not just that memory accepted it.",
        claims=[{
            "claim_type": "provider_state",
            "content": "The memory update tool returned Model set context updated.",
        }],
    )
    step = _step(receipt, "verify_externally")
    assert step.detail["verification_required"] is True
    assert step.status == "not_verified"
    assert step.detail["verification_attempted"] is False
    assert step.detail["verified"] is False
    assert step.detail["readback"] is None


def test_provenance_not_reported_as_persisted_without_write(tmp_data_dir):
    receipt = _boot(tmp_data_dir).run(message="Preserve this result in the owning system.")
    step = _step(receipt, "preserve_provenance")
    assert step.status == "not_persisted"
    assert step.detail["provenance_preserved"] is False
    assert step.detail["persistence_executed"] is False
    assert step.detail["persistence_receipt"] is None


def test_correction_not_reported_as_updated_without_ledger_mutation(tmp_data_dir):
    receipt = _boot(tmp_data_dir).run(message="Remember this failure and update future behavior.")
    step = _step(receipt, "update_correction_state")
    assert step.status == "not_updated"
    assert step.detail["corrections_updated"] is False
    assert step.detail["correction_receipt"] is None
