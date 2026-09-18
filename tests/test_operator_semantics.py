from __future__ import annotations

from pathlib import Path

import pytest

from apk.boot import BootContract
from apk.operator_semantics import (
    DEFAULT_OPERATOR_SEMANTICS,
    SemanticBinding,
    detect_ontology_inversions,
)
from apk.policy import PolicyEngine


@pytest.fixture()
def boot_contract(tmp_data_dir: Path) -> BootContract:
    policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
    return BootContract(
        user_model_path=tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
        policy=policy,
    )


class TestOperatorSemanticProjection:
    def test_default_projection_keeps_project_direction_with_operator(self):
        projection = SemanticBinding.default().project()
        assert projection["authority_holder"] == "OPERATOR"
        assert projection["exclusive_project_direction_authority"] is True
        assert projection["machine_project_direction_authority"] is False
        assert projection["creates_authority"] is False

    def test_holographic_mesh_is_pre_reasoning_topology(self):
        projection = SemanticBinding.default().project()
        assert projection["topology_model"] == "HOLOGRAPHIC_POLYCENTRIC_MESH"
        assert projection["single_root"] is False

    def test_gates_are_level_up_enrichment_transitions(self):
        binding = SemanticBinding.default()
        projection = binding.project()
        assert projection["gate_semantic"] == "ENRICHMENT_TRANSITION"
        assert projection["gate_literal_model"] == "LEVEL_UP"
        assert projection["gate_may_stop_mission"] is False
        assert binding.transition_for_status("FAIL") == "LOCALIZE_REPAIR_REROUTE_LEVEL_UP"

    def test_local_block_changes_route_not_objective(self):
        projection = SemanticBinding.default().project()
        assert projection["local_block_changes_route"] is True
        assert projection["local_block_changes_objective"] is False
        assert projection["mission_changes_only_by"] == "OPERATOR"


class TestOntologyInversionRegression:
    def test_detects_machine_sole_authority(self):
        findings = detect_ontology_inversions(
            "APEX Boot Core becomes the sole authority for the estate."
        )
        assert "NON_OPERATOR_SOLE_AUTHORITY" in {f["rule"] for f in findings}

    def test_detects_gate_as_veto(self):
        findings = detect_ontology_inversions(
            "A failed gate blocks the mission from continuing."
        )
        assert "GATE_AS_MISSION_VETO" in {f["rule"] for f in findings}

    def test_correct_non_veto_semantics_are_not_flagged(self):
        findings = detect_ontology_inversions(
            "A failed gate does not stop the mission; it enriches state and changes the route."
        )
        assert "GATE_AS_MISSION_VETO" not in {f["rule"] for f in findings}

    def test_detects_mesh_collapsed_to_root(self):
        findings = detect_ontology_inversions(
            "The runtime is the canonical root of the estate."
        )
        assert "MESH_COLLAPSED_TO_SINGLE_ROOT" in {f["rule"] for f in findings}


class TestBootPreReasoningBinding:
    def test_projection_is_in_receipt_before_claim_classification(
        self, boot_contract: BootContract
    ):
        receipt = boot_contract.run(message="Continue the existing work.")
        apply_step = next(s for s in receipt.steps if s.name == "apply_user_message")
        classify_step = next(s for s in receipt.steps if s.name == "classify_claims")

        assert apply_step.index < classify_step.index
        assert apply_step.detail["operator_semantics"] == receipt.operator_semantics
        assert receipt.operator_semantics["authority_holder"] == "OPERATOR"
        assert receipt.operator_semantics["gate_may_stop_mission"] is False

    def test_boot_audit_repairs_inversions_without_veto(
        self, boot_contract: BootContract
    ):
        audit = boot_contract.audit_output(
            "A failed gate blocks the mission and APEX is the sole authority."
        )
        assert audit["repair_required"] is True
        assert audit["mission_continues"] is True
        assert audit["creates_authority"] is False
        assert audit["authority_holder"] == "OPERATOR"
