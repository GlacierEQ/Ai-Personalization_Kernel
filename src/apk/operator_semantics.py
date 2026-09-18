"""Operator semantic projection for pre-reasoning personalization binding.

This is a projection of Operator-declared architecture, not an authority source.
It exists so generic model/software priors cannot silently rewrite GlacierEQ
semantics before the user model, policy, and action-selection layers run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DEFAULT_OPERATOR_SEMANTICS: dict[str, Any] = {
    "schema": "glaciereq.operator-semantics.v1",
    "projection_role": "USER_DECLARED_SEMANTIC_CONSTRAINTS_NOT_AUTHORITY_SOURCE",
    "authority": {
        "holder": "OPERATOR",
        "exclusive_project_direction_authority": True,
        "machine_project_direction_authority": False,
        "provider_project_direction_authority": False,
        "repository_project_direction_authority": False,
        "historical_state_creates_authority": False,
        "receipt_creates_authority": False,
    },
    "topology": {
        "model": "HOLOGRAPHIC_POLYCENTRIC_MESH",
        "single_root": False,
        "machine_sovereignty": False,
        "overlap_semantics": "COMPOSE_ENRICH_AND_PRESERVE_CAPABILITY_DONORS",
        "selection_semantics": "CURRENT_ROUTE_METADATA_NOT_AUTHORITY",
    },
    "gates": {
        "semantic": "ENRICHMENT_TRANSITION",
        "literal_model": "LEVEL_UP",
        "may_stop_mission": False,
        "status_transitions": {
            "PASS": "VALIDATED_LEVEL_UP",
            "WARN": "ENRICH_WITH_UNCERTAINTY",
            "FAIL": "LOCALIZE_REPAIR_REROUTE_LEVEL_UP",
            "MISSING": "DISCOVER_ACQUIRE_LEVEL_UP",
            "DRIFT": "RECONCILE_ENRICH_LEVEL_UP",
        },
    },
    "routing": {
        "local_block_changes_route": True,
        "local_block_changes_objective": False,
        "temporary_skip_changes_sequencing": True,
        "temporary_skip_changes_scope": False,
        "mission_changes_only_by": "OPERATOR",
    },
}


def _digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate(contract: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    authority = contract.get("authority", {})
    topology = contract.get("topology", {})
    gates = contract.get("gates", {})
    routing = contract.get("routing", {})

    if authority.get("holder") != "OPERATOR":
        issues.append("authority.holder must be OPERATOR")
    if authority.get("exclusive_project_direction_authority") is not True:
        issues.append("exclusive_project_direction_authority must be true")
    for key in (
        "machine_project_direction_authority",
        "provider_project_direction_authority",
        "repository_project_direction_authority",
        "historical_state_creates_authority",
        "receipt_creates_authority",
    ):
        if authority.get(key) is not False:
            issues.append(f"authority.{key} must be false")
    if topology.get("model") != "HOLOGRAPHIC_POLYCENTRIC_MESH":
        issues.append("topology.model must be HOLOGRAPHIC_POLYCENTRIC_MESH")
    if topology.get("single_root") is not False:
        issues.append("topology.single_root must be false")
    if gates.get("semantic") != "ENRICHMENT_TRANSITION":
        issues.append("gates.semantic must be ENRICHMENT_TRANSITION")
    if gates.get("may_stop_mission") is not False:
        issues.append("gates.may_stop_mission must be false")
    if routing.get("local_block_changes_route") is not True:
        issues.append("local_block_changes_route must be true")
    if routing.get("local_block_changes_objective") is not False:
        issues.append("local_block_changes_objective must be false")
    if routing.get("mission_changes_only_by") != "OPERATOR":
        issues.append("mission_changes_only_by must be OPERATOR")
    return issues


@dataclass(frozen=True)
class SemanticBinding:
    contract: dict[str, Any]
    source: str
    contract_sha256: str
    diagnostics: tuple[str, ...]

    @classmethod
    def default(cls) -> "SemanticBinding":
        contract = json.loads(json.dumps(DEFAULT_OPERATOR_SEMANTICS))
        return cls(
            contract=contract,
            source="apk_builtin_operator_projection",
            contract_sha256=_digest(contract),
            diagnostics=tuple(_validate(contract)),
        )

    @classmethod
    def from_path(cls, path: str | Path) -> "SemanticBinding":
        p = Path(path)
        contract = json.loads(p.read_text(encoding="utf-8"))
        issues = _validate(contract)
        if issues:
            raise ValueError("; ".join(issues))
        return cls(
            contract=dict(contract),
            source=str(p),
            contract_sha256=_digest(contract),
            diagnostics=tuple(),
        )

    def project(self) -> dict[str, Any]:
        authority = self.contract["authority"]
        topology = self.contract["topology"]
        gates = self.contract["gates"]
        routing = self.contract["routing"]
        return {
            "schema": self.contract.get("schema"),
            "projection_role": self.contract.get(
                "projection_role",
                "USER_DECLARED_SEMANTIC_CONSTRAINTS_NOT_AUTHORITY_SOURCE",
            ),
            "source": self.source,
            "contract_sha256": self.contract_sha256,
            "authority_holder": authority["holder"],
            "exclusive_project_direction_authority": authority[
                "exclusive_project_direction_authority"
            ],
            "machine_project_direction_authority": authority[
                "machine_project_direction_authority"
            ],
            "topology_model": topology["model"],
            "single_root": topology["single_root"],
            "gate_semantic": gates["semantic"],
            "gate_literal_model": gates["literal_model"],
            "gate_may_stop_mission": gates["may_stop_mission"],
            "local_block_changes_route": routing["local_block_changes_route"],
            "local_block_changes_objective": routing[
                "local_block_changes_objective"
            ],
            "mission_changes_only_by": routing["mission_changes_only_by"],
            "mission_continues": True,
            "creates_authority": False,
            "diagnostics": list(self.diagnostics),
        }

    def transition_for_status(self, status: str) -> str:
        return self.contract["gates"]["status_transitions"].get(
            status.upper(), "ENRICH_AND_CONTINUE"
        )


def _negated(fragment: str) -> bool:
    low = fragment.lower()
    return any(
        token in low
        for token in (
            "not ",
            "never ",
            "no ",
            "does not ",
            "doesn't ",
            "do not ",
            "cannot ",
        )
    )


_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "NON_OPERATOR_SOLE_AUTHORITY",
        re.compile(
            r"\b(apex(?:\s+boot\s+core)?|runtime|provider|verifier|repository|model|system|node|gate)"
            r"\b.{0,70}\b(sole|final|ultimate|project)\s+authority\b",
            re.I,
        ),
        "Project-direction authority remains with the Operator; describe the node as a capability, route, projection, verifier, or executor.",
    ),
    (
        "GATE_AS_MISSION_VETO",
        re.compile(
            r"\b(gate|gates|failure|failed|fail)\b.{0,90}"
            r"\b(stop|stops|stopped|block|blocks|blocked|deny|denies|denied|prevent|prevents|prevented)\b",
            re.I,
        ),
        "Treat the result as a level-up enrichment transition: localize, repair/compose/reroute, verify, persist, and continue.",
    ),
    (
        "LOCAL_BLOCK_AS_GLOBAL_BLOCK",
        re.compile(
            r"\blocal\b.{0,50}\b(block|failure|deficiency)\b.{0,90}"
            r"\b(stop|terminate|cancel|change)\b.{0,50}\b(objective|mission)\b",
            re.I,
        ),
        "A local block changes route, not objective; only the Operator changes the mission.",
    ),
    (
        "MESH_COLLAPSED_TO_SINGLE_ROOT",
        re.compile(r"\b(single|sole|canonical)\s+(root|controller|control\s+plane)\b", re.I),
        "Preserve holographic/polycentric mesh semantics; overlapping nodes compose and enrich rather than collapse into a machine root.",
    ),
)


def detect_ontology_inversions(text: str) -> list[dict[str, str]]:
    """Return repair telemetry for semantic inversions; findings never veto execution."""
    findings: list[dict[str, str]] = []
    for rule_id, pattern, repair in _RULES:
        for match in pattern.finditer(text):
            fragment = match.group(0)
            if _negated(fragment):
                continue
            findings.append({"rule": rule_id, "match": fragment, "repair": repair})
    return findings
