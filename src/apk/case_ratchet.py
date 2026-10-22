"""Case-scoped provenance ratchet backed by the independent source ledger.

Never infer an empty case from a missing callback or an empty caller summary.
No content is reclassified as fact: inventory preservation is orthogonal to
authentication, source authority, evidentiary admissibility and legal effects.
"""
from __future__ import annotations

from typing import Any, Iterable

from apk.detail_integrity import SYNTHESIS_ACTIONS, CONTINUATION_ACTION


def _case_matches(item: Any, case_id: str) -> bool:
    payload = getattr(item, "payload", {}) or {}
    if not isinstance(payload, dict):
        return False
    identifiers = [payload.get("case_id"), payload.get("matter_id")]
    identifiers.extend(payload.get("case_ids") or ())
    return case_id in identifiers


def collect_case_sources(
    store: Any | None,
    case_id: str | None,
    retained_source_ids: Iterable[str] | None,
) -> dict[str, Any]:
    """Reconstruct expected sources without trusting the proposed synthesis.

    The caller provides only the case scope and which prior record IDs its
    analysis retained. Expected records always come from the durable store.
    Both active and superseded records remain in the historical inventory.
    """
    result: dict[str, Any] = {
        "case_id": case_id,
        "coverage_status": "NOT_REQUESTED",
        "coverage_proved": False,
        "expected_source_ids": [],
        "retained_source_ids": list(dict.fromkeys(retained_source_ids or ())),
        "missing_source_ids": [],
        "source_roles": {},
        "silent_loss_detected": False,
        "mission_continues": True,
        "adjudicates_liability": False,
        "source": "case_ledger",
    }
    if not case_id:
        return result
    if store is None:
        result["coverage_status"] = "SOURCE_UNAVAILABLE"
        return result
    try:
        records = store.read_all()
    except (OSError, ValueError, TypeError):
        result["coverage_status"] = "SOURCE_UNAVAILABLE"
        return result
    scoped = [item for item in records if _case_matches(item, case_id)]
    # The stored inventory is read in append/source order and deduplicated
    # by durable ID only. Do not collapse distinct evidence with same content.
    seen: set[str] = set()
    ordered = []
    for item in scoped:
        if item.id not in seen:
            seen.add(item.id)
            ordered.append(item)
    ids = [item.id for item in ordered]
    result["expected_source_ids"] = ids
    result["source_roles"] = {item.id: item.type for item in ordered}
    if not ids:
        result["coverage_status"] = "NO_CASE_ENTRIES_IN_LEDGER"
        return result
    carried = set(result["retained_source_ids"])
    missing = [source_id for source_id in ids if source_id not in carried]
    result["missing_source_ids"] = missing
    result["silent_loss_detected"] = bool(missing)
    if retained_source_ids is None:
        result["coverage_status"] = "CARRY_LIST_MISSING"
    elif missing:
        result["coverage_status"] = "MISSING_PRIOR_SOURCES"
    else:
        result["coverage_status"] = "COVERED"
        result["coverage_proved"] = True
    return result


def enforce_case_ratchet(
    action: str,
    record: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Block *claiming completed synthesis* after silent history loss.

    Other lawful work, evidence collection and provider actions continue.
    Missing storage never becomes proof that the case has no prior history.
    """
    receipt = dict(record)
    receipt["policy_selected_action"] = action
    if action in SYNTHESIS_ACTIONS and record.get("silent_loss_detected"):
        receipt["enforced_action"] = CONTINUATION_ACTION
        receipt["override_applied"] = True
        return CONTINUATION_ACTION, receipt
    receipt["enforced_action"] = action
    receipt["override_applied"] = False
    return action, receipt
