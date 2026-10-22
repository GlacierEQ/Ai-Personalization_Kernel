"""Regression: a narrow unknown cannot erase the cumulative proven record.

These cases originate in the July 2 CSEA Dkt.217 filing and October 20
agency notice sequence. Use abstract proposition IDs: public tests do not
publish the underlying person's private case details.
"""

from __future__ import annotations

from apk.detail_integrity import EvidenceContinuity, enforce_evidence_continuity


def test_dropped_established_facts_force_continued_synthesis_not_caveat_answer():
    record = EvidenceContinuity.from_mapping({
        "established_propositions": (
            "motion_filed", "agency_notified", "agency_denied_record_categories"
        ),
        "affirmatively_carried": ("agency_denied_record_categories",),
        "open_dimensions": ("motion_disposition",),
        "next_executable_transition": "recover current docket and preserve notice",
    })
    action, receipt = enforce_evidence_continuity("answer_directly", record)
    assert action == "continue_existing_work"
    assert receipt["missing_established_propositions"] == [
        "motion_filed", "agency_notified"
    ]
    assert receipt["override_applied"] is True


def test_proposition_scoped_gap_keeps_all_cumulative_evidence_and_mission_active():
    record = EvidenceContinuity.from_mapping({
        "established_propositions": (
            "motion_filed", "agency_notified", "agency_denied_record_categories"
        ),
        "affirmatively_carried": (
            "motion_filed", "agency_notified", "agency_denied_record_categories"
        ),
        "open_dimensions": ("motion_disposition",),
        "next_executable_transition": "prepare supplemental record with existing exhibits",
    })
    action, receipt = enforce_evidence_continuity("create_artifact", record)
    assert action == "create_artifact"
    assert receipt["complete"] is True
    assert receipt["open_dimensions"] == ["motion_disposition"]
    assert receipt["missing_established_propositions"] == []


def test_local_uncertainty_as_global_stop_is_rejected_even_with_carried_sources():
    record = EvidenceContinuity.from_mapping({
        "established_propositions": ("filed_motion", "written_denial"),
        "affirmatively_carried": ("filed_motion", "written_denial"),
        "open_dimensions": ("order_status",),
        "global_stop_inferred": True,
    })
    action, receipt = enforce_evidence_continuity("answer_directly", record)
    assert action == "continue_existing_work"
    assert "local_gap_promoted_to_global_stop" in receipt["incomplete_reasons"]
    assert receipt["mission_continues"] is True


def test_localized_legal_caveat_is_not_prohibited():
    record = EvidenceContinuity.from_mapping({
        "established_propositions": ("filed_motion", "written_denial"),
        "affirmatively_carried": ("filed_motion", "written_denial"),
        "open_dimensions": ("whether_a_court_order_was_violated",),
        "next_executable_transition": "verify operative order while preparing independent claim",
        "global_stop_inferred": False,
    })
    action, receipt = enforce_evidence_continuity("answer_directly", record)
    assert action == "answer_directly"
    assert receipt["complete"] is True


def test_unknown_proposition_not_laundered_into_established_fact():
    try:
        EvidenceContinuity.from_mapping({
            "established_propositions": ("motion_filed",),
            "affirmatively_carried": ("motion_filed", "agency_violated_order"),
        })
    except ValueError as exc:
        assert "not established" in str(exc)
    else:
        raise AssertionError("Unknown propositions cannot be promoted to verified facts")


def test_no_evidence_record_keeps_backward_compatible_selection():
    action, receipt = enforce_evidence_continuity(
        "answer_directly", EvidenceContinuity.from_mapping(None)
    )
    assert action == "answer_directly"
    assert receipt["override_applied"] is False
