from __future__ import annotations

import json
from pathlib import Path

import pytest

from apk.policy import PolicyEngine
from apk.replay import CORE_METRICS, ExperienceReplay


class TestReplayWithSeedPolicy:
    def test_all_bundled_regression_cases_pass(self, tmp_data_dir: Path):
        policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
        replay = ExperienceReplay(policy)
        run = replay.run(tmp_data_dir / "regression_cases.jsonl")
        assert run.total_cases >= 4
        assert run.regression_reintroduction_count == 0
        assert run.passed is True
        assert run.failed_cases == 0

    def test_metrics_report_structure(self, tmp_data_dir: Path):
        policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
        replay = ExperienceReplay(policy)
        run = replay.run(tmp_data_dir / "regression_cases.jsonl")
        d = run.to_dict()
        assert set(CORE_METRICS) <= set(d["metrics"].keys())
        for name, m in d["metrics"].items():
            assert "value" in m or "not_computable" in m
            if m.get("not_computable"):
                assert "reason" in m and m["reason"]


class TestReplayDetectsCorruptedPolicy:
    def test_corrupted_policy_fails_replay_and_lists_recurring_cases(self, tmp_data_dir: Path):
        weights = json.loads((tmp_data_dir / "policy_weights.json").read_text())
        # Deliberately corrupt the policy: strip correction penalties entirely
        # and zero out the instruction-displacement guard's effect by making
        # the base weights for undesired actions dominate.
        corrupted = dict(weights)
        corrupted["base_correction_penalty"] = 0.0
        corrupted["invariant_hard_penalty"] = 0.0
        corrupted["base_weights"] = dict(weights["base_weights"])
        corrupted["base_weights"]["answer_directly"] = 999.0
        corrupted["base_weights"]["ask_question"] = 999.0
        corrupted["base_weights"]["search_web"] = 999.0

        corrupted_path = tmp_data_dir / "policy_weights.corrupted.json"
        corrupted_path.write_text(json.dumps(corrupted))

        policy = PolicyEngine.from_file(corrupted_path)
        replay = ExperienceReplay(policy)
        run = replay.run(tmp_data_dir / "regression_cases.jsonl")

        assert run.passed is False
        assert run.regression_reintroduction_count > 0
        failing = run.failing_results()
        assert len(failing) > 0
        for r in failing:
            assert "REGRESSION" in r.reason


class TestReplayCaseMechanics:
    def test_replay_case_uses_only_relevant_candidates_plus_full_base_set(self, tmp_data_dir: Path):
        policy = PolicyEngine.from_file(tmp_data_dir / "policy_weights.json")
        replay = ExperienceReplay(policy)
        cases = replay.load_cases(tmp_data_dir / "regression_cases.jsonl")
        result = replay.replay_case(0, cases[0])
        assert result.corrected_action_score > result.action_taken_score
        assert result.passed is True
