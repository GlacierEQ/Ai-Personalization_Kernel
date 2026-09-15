"""Experience replay (spec section 11 / docs/PERSONALIZATION_REGRESSION_SUITE.md).

Loads regression_cases.jsonl and replays the current PolicyEngine against
each case's captured state, asserting the corrected_action now outranks the
erroneous action_taken. This is the CI hard gate against regression
reintroduction (invariant 16).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from apk.policy import CorrectionLike, DecisionContext, PolicyEngine, PreferenceLike

CORE_METRICS: tuple[str, ...] = (
    "context_retrieval_recall",
    "preference_adherence_rate",
    "correction_recurrence_rate",
    "repeated_question_rate",
    "user_restatement_burden",
    "direct_answer_bypass_rate",
    "source_authority_inversion_rate",
    "stale_state_reuse_rate",
    "project_continuity_success",
    "successful_strategy_reuse",
    "regression_reintroduction_count",
)


def _state_to_context(state: dict[str, Any]) -> DecisionContext:
    corrections = [CorrectionLike.from_dict(c) for c in state.get("active_corrections", [])]
    preferences = [PreferenceLike(**p) for p in state.get("active_preferences", [])]
    return DecisionContext(
        relevant_context_exists=state.get("relevant_context_exists", False),
        context_retrieved=state.get("context_retrieved", False),
        info_available_in_user_model=state.get("info_available_in_user_model", False),
        active_corrections=corrections,
        active_preferences=preferences,
        scope=state.get("scope", "conversation"),
    )


@dataclass
class CaseResult:
    index: int
    failure_class: str
    action_taken: str
    corrected_action: str
    selected_action: str
    action_taken_score: float
    corrected_action_score: float
    passed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "failure_class": self.failure_class,
            "action_taken": self.action_taken,
            "corrected_action": self.corrected_action,
            "selected_action": self.selected_action,
            "action_taken_score": self.action_taken_score,
            "corrected_action_score": self.corrected_action_score,
            "passed": self.passed,
            "reason": self.reason,
        }


@dataclass
class EvalRun:
    total_cases: int
    passed_cases: int
    failed_cases: int
    regression_reintroduction_count: int
    metrics: dict[str, Any]
    passed: bool
    results: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "regression_reintroduction_count": self.regression_reintroduction_count,
            "metrics": self.metrics,
            "passed": self.passed,
            "results": [r.to_dict() for r in self.results],
        }

    def failing_results(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]


class ExperienceReplay:
    def __init__(self, policy: PolicyEngine):
        self.policy = policy

    @staticmethod
    def load_cases(path: str | Path) -> list[dict[str, Any]]:
        cases = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(json.loads(line))
        return cases

    def replay_case(self, index: int, case: dict[str, Any]) -> CaseResult:
        context = _state_to_context(case["state"])
        candidates = set(self.policy.base_weights.keys())
        candidates.add(self.policy.canonical(case["action_taken"]))
        candidates.add(self.policy.canonical(case["corrected_action"]))
        decision = self.policy.select(context, candidates=sorted(candidates))
        scores = {s.name: s.final_score for s in decision.ranked}
        action_taken_canon = self.policy.canonical(case["action_taken"])
        corrected_canon = self.policy.canonical(case["corrected_action"])
        action_taken_score = scores.get(action_taken_canon, float("-inf"))
        corrected_score = scores.get(corrected_canon, float("-inf"))
        selected = decision.selected().name
        passed = corrected_score > action_taken_score
        reason = (
            "corrected_action ranks above action_taken"
            if passed
            else f"REGRESSION: corrected_action score {corrected_score} <= "
                 f"action_taken score {action_taken_score}"
        )
        return CaseResult(
            index=index,
            failure_class=case.get("failure_class", "unknown"),
            action_taken=case["action_taken"],
            corrected_action=case["corrected_action"],
            selected_action=selected,
            action_taken_score=action_taken_score,
            corrected_action_score=corrected_score,
            passed=passed,
            reason=reason,
        )

    def run(self, cases_path: str | Path) -> EvalRun:
        cases = self.load_cases(cases_path)
        results = [self.replay_case(i, c) for i, c in enumerate(cases)]
        passed_cases = sum(1 for r in results if r.passed)
        failed_cases = len(results) - passed_cases

        metrics: dict[str, Any] = {}
        metrics["regression_reintroduction_count"] = {
            "value": failed_cases,
            "target": "EXACTLY 0",
        }
        if results:
            metrics["direct_answer_bypass_rate"] = {
                "value": passed_cases / len(results),
                "target": "<= 0.02 in production telemetry; this is replay pass rate",
            }
        else:
            metrics["direct_answer_bypass_rate"] = {
                "value": None,
                "not_computable": True,
                "reason": "no regression cases loaded",
            }
        for name in CORE_METRICS:
            if name in metrics:
                continue
            metrics[name] = {
                "value": None,
                "not_computable": True,
                "reason": "requires live session telemetry (retrieval traces, user "
                          "restatement counts, cross-session continuity receipts) not "
                          "captured by a static regression replay run",
            }

        return EvalRun(
            total_cases=len(results),
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            regression_reintroduction_count=failed_cases,
            metrics=metrics,
            passed=failed_cases == 0,
            results=results,
        )
