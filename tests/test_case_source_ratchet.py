"""Cross-case non-regression requires prior state from an independent ledger.

A caller-supplied empty evidence list is not proof a case had no earlier
filings, witnesses, notices, communications, or executed work.
"""
from __future__ import annotations

from apk.case_ratchet import collect_case_sources, enforce_case_ratchet
from apk.store import JsonlStore
from apk.types import MemoryObject
from apk.boot import BootContract
from apk.policy import PolicyEngine


def record(store, id, case_id, kind="verified_external_fact", status="active"):
    store.append(MemoryObject(
        id=id, type=kind, scope="project", status=status, confidence=1.0,
        source="case_registry", source_refs=[f"provider://{id}"],
        payload={"case_id": case_id, "proposition": id},
    ))


def test_prior_record_is_independently_loaded_when_caller_omits_it(tmp_path):
    ledger=JsonlStore(tmp_path / "case.jsonl")
    record(ledger, "filed_motion", "alpha")
    record(ledger, "court_notice", "alpha")
    record(ledger, "later_agency_response", "alpha", "provider_state")
    prior=collect_case_sources(ledger, "alpha", ["later_agency_response"])
    assert prior["expected_source_ids"] == [
        "filed_motion", "court_notice", "later_agency_response"
    ]
    assert prior["missing_source_ids"] == ["filed_motion", "court_notice"]
    action, receipt=enforce_case_ratchet("answer_directly",prior)
    assert action == "continue_existing_work"
    assert receipt["silent_loss_detected"] is True
    assert receipt["mission_continues"] is True


def test_all_roles_preserved_without_promoting_unverified_claims(tmp_path):
    ledger=JsonlStore(tmp_path / "case.jsonl")
    record(ledger,"filed_receipt","alpha")
    record(ledger,"witness_statement","alpha","firsthand_observation")
    record(ledger,"disputed_claim","alpha","unverified_external_claim")
    record(ledger,"other_case","beta")
    prior=collect_case_sources(ledger,"alpha",[
        "filed_receipt","witness_statement","disputed_claim"
    ])
    assert prior["expected_source_ids"] == [
        "filed_receipt","witness_statement","disputed_claim"
    ]
    assert prior["source_roles"]["disputed_claim"] == "unverified_external_claim"
    assert prior["missing_source_ids"] == []
    assert prior["coverage_status"] == "COVERED"
    assert enforce_case_ratchet("create_artifact",prior)[0] == "create_artifact"


def test_history_is_retained_after_supersession(tmp_path):
    ledger=JsonlStore(tmp_path / "case.jsonl")
    record(ledger,"old_record","alpha",status="superseded")
    record(ledger,"replacement","alpha")
    prior=collect_case_sources(ledger,"alpha",["replacement"])
    assert prior["missing_source_ids"] == ["old_record"]


def test_scope_with_unavailable_provider_is_not_misclassified_complete():
    prior=collect_case_sources(None,"alpha",[])
    assert prior["coverage_status"] == "SOURCE_UNAVAILABLE"
    assert prior["coverage_proved"] is False
    assert prior["mission_continues"] is True
    assert enforce_case_ratchet("execute_reversible_action",prior)[0] == "execute_reversible_action"


def test_absent_carried_id_list_cannot_masquerade_as_full_review(tmp_path):
    ledger=JsonlStore(tmp_path / "case.jsonl")
    record(ledger,"existing_record","alpha")
    prior=collect_case_sources(ledger,"alpha",None)
    assert prior["coverage_status"] == "CARRY_LIST_MISSING"
    assert prior["missing_source_ids"] == ["existing_record"]
    assert enforce_case_ratchet("answer_directly",prior)[0] == "continue_existing_work"


def test_boot_uses_actual_ledger_for_case_coverage(tmp_path,tmp_data_dir):
    ledger=JsonlStore(tmp_path / "case.jsonl")
    record(ledger,"signed_motion","alpha")
    record(ledger,"agency_notice","alpha")
    boot=BootContract(
        user_model_path=tmp_data_dir / "user_model.json",
        corrections_path=tmp_data_dir / "corrections.jsonl",
        policy=PolicyEngine.from_file(tmp_data_dir / "policy_weights.json"),
        store=ledger,
    )
    receipt=boot.run(
        message="Continue case alpha and analyze its new notice.",
        case_id="alpha",
        retained_case_record_ids=["agency_notice"],
    )
    step=next(s for s in receipt.steps if s.name=="select_action_policy")
    check=step.detail["case_source_ratchet"]
    assert check["missing_source_ids"] == ["signed_motion"]
    assert check["silent_loss_detected"] is True


def test_case_scope_absent_is_not_marked_full_coverage():
    prior=collect_case_sources(None,None,None)
    assert prior["coverage_status"] == "NOT_REQUESTED"
    assert prior["coverage_proved"] is False
