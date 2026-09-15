"""THE ENFORCEMENT SUITE.

These tests are the load-bearing proof that personalization is causal, not
decorative: corrections, preferences, and known user-model facts must
actually change which action the policy engine ranks first.
"""

from __future__ import annotations

from apk.policy import CorrectionLike, DecisionContext, PreferenceLike


def make_correction(**overrides) -> CorrectionLike:
    defaults = dict(
        id="corr_x",
        pattern="answer_before_context_recovery",
        desired_behavior="retrieve_personal_context",
        undesired_behavior="generic_answer_without_context",
        promotion_level="preference",
        recurrence_count=1,
        confidence=1.0,
        scope="global",
        status="active",
    )
    defaults.update(overrides)
    return CorrectionLike(**defaults)


class TestInstructionDisplacementGuard:
    def test_answer_directly_ranks_below_retrieval_when_context_unretrieved(self, policy_engine):
        context = DecisionContext(relevant_context_exists=True, context_retrieved=False)
        decision = policy_engine.select(context)
        scores = {a.name: a.final_score for a in decision.ranked}
        retrieval_actions = policy_engine.retrieval_actions
        min_retrieval_score = min(scores[a] for a in retrieval_actions)
        assert scores["answer_directly"] < min_retrieval_score
        assert scores["ask_question"] < min_retrieval_score

    def test_answer_directly_not_penalized_once_context_is_retrieved(self, policy_engine):
        context = DecisionContext(relevant_context_exists=True, context_retrieved=True)
        decision = policy_engine.select(context)
        scores = {a.name: a.final_score for a in decision.ranked}
        assert scores["answer_directly"] == policy_engine.base_weights["answer_directly"]

    def test_retrieval_action_ranks_first_when_context_unretrieved(self, policy_engine):
        context = DecisionContext(relevant_context_exists=True, context_retrieved=False)
        decision = policy_engine.select(context)
        assert decision.selected().name == "retrieve_personal_context"


class TestCorrectionDemotion:
    def test_active_correction_demotes_undesired_behavior(self, policy_engine):
        context_without = DecisionContext(scope="global")
        context_with = DecisionContext(scope="global", active_corrections=[make_correction()])

        score_without = policy_engine.score_action("generic_answer_without_context", context_without).final_score
        score_with = policy_engine.score_action("generic_answer_without_context", context_with).final_score
        assert score_with < score_without

    def test_demotion_strength_increases_with_recurrence(self, policy_engine):
        context = DecisionContext(scope="global")
        scores = []
        for recurrence in (1, 2, 3, 4):
            corr = make_correction(promotion_level="strong_preference", recurrence_count=recurrence)
            ctx = DecisionContext(scope="global", active_corrections=[corr])
            scores.append(policy_engine.score_action("generic_answer_without_context", ctx).final_score)
        # strictly decreasing (monotonic) as recurrence increases
        assert scores == sorted(scores, reverse=True)
        assert scores[0] > scores[1] > scores[2] > scores[3]

    def test_demotion_strength_increases_with_promotion_level(self, policy_engine):
        context = lambda level: DecisionContext(
            scope="global", active_corrections=[make_correction(promotion_level=level, recurrence_count=1)]
        )
        s_obs = policy_engine.score_action("generic_answer_without_context", context("observation")).final_score
        s_pref = policy_engine.score_action("generic_answer_without_context", context("preference")).final_score
        s_strong = policy_engine.score_action("generic_answer_without_context", context("strong_preference")).final_score
        s_proc = policy_engine.score_action("generic_answer_without_context", context("procedural_rule")).final_score
        assert s_obs >= s_pref > s_strong > s_proc


class TestInvariantHardBlock:
    def test_invariant_correction_makes_undesired_action_unselectable(self, policy_engine):
        corr = make_correction(promotion_level="invariant", recurrence_count=5)
        context = DecisionContext(scope="global", active_corrections=[corr])
        decision = policy_engine.select(context)
        selected = decision.selected()
        assert selected.name != "answer_directly"
        blocked_score = next(a.final_score for a in decision.ranked if a.name == "answer_directly")
        assert blocked_score < -1000, "invariant-level correction must hard-block the undesired action"
        assert selected.final_score > blocked_score


class TestPreferenceBoost:
    def test_known_preference_boosts_aligned_action(self, policy_engine):
        context_without = DecisionContext()
        context_with = DecisionContext(
            active_preferences=[PreferenceLike(id="pref_1", desired_action="continue_existing_work", confidence=1.0)]
        )
        score_without = policy_engine.score_action("continue_existing_work", context_without).final_score
        score_with = policy_engine.score_action("continue_existing_work", context_with).final_score
        assert score_with > score_without


class TestKnownInfoGuard:
    def test_ask_to_repeat_known_info_is_bottom_ranked(self, policy_engine):
        context = DecisionContext(info_available_in_user_model=True)
        decision = policy_engine.select(context)
        ranked_names = [a.name for a in decision.ranked]
        assert ranked_names[-1] == "ask_question"

    def test_ask_question_not_penalized_when_info_unknown(self, policy_engine):
        context = DecisionContext(info_available_in_user_model=False)
        score = policy_engine.score_action("ask_question", context).final_score
        assert score == policy_engine.base_weights["ask_question"]


class TestAuditableReceipts:
    def test_select_returns_full_score_breakdown(self, policy_engine):
        corr = make_correction()
        context = DecisionContext(active_corrections=[corr])
        decision = policy_engine.select(context)
        scored = next(a for a in decision.ranked if a.name == "answer_directly")
        assert scored.adjustments, "an applied correction must appear in the adjustment breakdown"
        reasons = [adj.reason for adj in scored.adjustments]
        assert any("correction" in r for r in reasons)
        # breakdown is auditable / serializable
        d = scored.to_dict()
        assert d["final_score"] == scored.final_score
        assert isinstance(d["adjustments"], list)
