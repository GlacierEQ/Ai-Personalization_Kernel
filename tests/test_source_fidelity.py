"""Output-fidelity regression: Cherry Fold6 factual demotion and localized inference."""

from __future__ import annotations

from pathlib import Path
from apk.boot import BootContract
from apk.policy import PolicyEngine
from apk.source_fidelity import detect_source_fact_demotions

FACTS = [
    {
        "id": "device-owner",
        "statement": "Cherry owns the Samsung Galaxy Z Fold6.",
        "status": "operator_confirmed",
        "anchors": ["Cherry's ownership of the Fold6", "Cherry owns the Fold6"],
    },
    {
        "id": "invitation-vanished",
        "statement": "The invitation message disappeared from Cherry's remaining phone.",
        "status": "user_firsthand",
        "anchors": ["the invitation disappeared", "the invitation's disappearance"],
    },
]


def test_detects_source_fact_status_demotion():
    found = detect_source_fact_demotions("Cherry's ownership of the Fold6 remains unverified.", FACTS)
    assert len(found) == 1
    assert found[0]["rule"] == "SOURCE_FACT_STATUS_DEMOTION"
    assert found[0]["fact_id"] == "device-owner"
    assert found[0]["source_statement"] == FACTS[0]["statement"]


def test_scoped_uncertainty_about_thief_does_not_demote_invitation():
    found = detect_source_fact_demotions(
        "The invitation disappeared, but this does not establish who stole the phone.", FACTS
    )
    assert found == []


def test_imei_uncertainty_does_not_demote_confirmed_owner():
    found = detect_source_fact_demotions(
        "Cherry owns the Fold6. Its IMEI has not been confirmed.", FACTS
    )
    assert found == []


def test_detects_invitation_demotion():
    found = detect_source_fact_demotions(
        "The invitation's disappearance is not independently verified.", FACTS
    )
    assert [row["fact_id"] for row in found] == ["invitation-vanished"]


def test_preserves_firsthand_attribution():
    assert detect_source_fact_demotions(
        "Cherry reports that the invitation disappeared after she woke up.", FACTS
    ) == []


def test_ignores_inference_not_established_as_fact():
    hypothesis = [{
        "id": "suspect",
        "statement": "The inviter stole the phone.",
        "status": "hypothesis",
        "anchors": ["The inviter stole the phone"],
    }]
    assert detect_source_fact_demotions(
        "The inviter stole the phone is unverified.", hypothesis
    ) == []


def test_structured_status_demotion_even_without_literal_anchor():
    found = detect_source_fact_demotions(
        "Investigation report follows.", FACTS,
        emitted_claims=[{"fact_id": "device-owner", "status": "unverified"}]
    )
    assert len(found) == 1
    assert found[0]["fact_id"] == "device-owner"
    assert found[0]["emitted_status"] == "unverified"


def test_structured_status_that_preserves_firsthand_is_allowed():
    assert detect_source_fact_demotions(
        "The invitation disappeared.", FACTS,
        emitted_claims=[{"fact_id": "invitation-vanished", "status": "user_firsthand"}]
    ) == []


def test_without_bound_facts_does_not_invent_source_findings():
    assert detect_source_fact_demotions("That fact is unverified.", []) == []


def test_draft_audit_uses_source_fidelity_and_existing_semantic_checks(tmp_data_dir: Path):
    contract = BootContract(
        user_model_path=tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
        policy=PolicyEngine.from_file(tmp_data_dir / "policy_weights.json"),
    )
    bad = contract.audit_output(
        "Cherry's ownership of the Fold6 remains unverified.", source_facts=FACTS
    )
    assert bad["repair_required"] is True
    assert bad["mission_continues"] is True
    assert any(x["rule"] == "SOURCE_FACT_STATUS_DEMOTION" for x in bad["findings"])

    good = contract.audit_output(
        "Cherry owns the Fold6. The invitation disappeared, but the sender's role is unknown.",
        source_facts=FACTS,
    )
    assert good["repair_required"] is False

    original = contract.audit_output("A failed gate blocks the mission.")
    assert any(x["rule"] == "GATE_AS_MISSION_VETO" for x in original["findings"])


def test_empty_source_binding_is_explicitly_not_checked():
    from apk.source_fidelity import source_binding_status
    assert source_binding_status([]) == "NOT_BOUND"
    assert source_binding_status(FACTS) == "BOUND"


def test_source_sensitive_draft_cannot_treat_missing_binding_as_clean(tmp_data_dir: Path):
    contract = BootContract(
        user_model_path=tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
        policy=PolicyEngine.from_file(tmp_data_dir / "policy_weights.json"),
    )
    result = contract.audit_output(
        "Cherry's phone was stolen.", source_fidelity_required=True
    )
    assert result["source_fidelity_status"] == "NOT_BOUND"
    assert result["repair_required"] is True
    assert any(f["rule"] == "SOURCE_FIDELITY_NOT_BOUND" for f in result["findings"])

    bound = contract.audit_output(
        "Cherry owns the Fold6.", source_facts=FACTS, source_fidelity_required=True
    )
    assert bound["source_fidelity_status"] == "BOUND"
    assert bound["repair_required"] is False
