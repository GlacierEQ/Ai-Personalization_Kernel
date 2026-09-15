from __future__ import annotations

from apk.corrections import CorrectionLedger, PromotionEngine


class TestPromotionEngineLadder:
    def test_observation_to_preference_requires_explicit(self):
        assert PromotionEngine.evaluate("observation", 1, explicit=False) == "observation"
        assert PromotionEngine.evaluate("observation", 1, explicit=True) == "preference"

    def test_preference_to_strong_preference_requires_recurrence_or_cross_domain(self):
        assert PromotionEngine.evaluate("preference", 1) == "preference"
        assert PromotionEngine.evaluate("preference", 2) == "strong_preference"
        assert PromotionEngine.evaluate("preference", 1, cross_domain=True) == "strong_preference"

    def test_strong_preference_to_procedural_rule_requires_recurrence_and_high_severity(self):
        assert PromotionEngine.evaluate("strong_preference", 3, severity="normal") == "strong_preference"
        assert PromotionEngine.evaluate("strong_preference", 2, severity="high") == "strong_preference"
        assert PromotionEngine.evaluate("strong_preference", 3, severity="high") == "procedural_rule"

    def test_procedural_rule_to_invariant_requires_user_confirmation(self):
        assert PromotionEngine.evaluate("procedural_rule", 10, user_confirmed=False) == "procedural_rule"
        assert PromotionEngine.evaluate("procedural_rule", 10, user_confirmed=True) == "invariant"

    def test_invariant_never_demotes(self):
        assert PromotionEngine.evaluate("invariant", 1) == "invariant"
        assert PromotionEngine.evaluate("invariant", 0, explicit=False) == "invariant"

    def test_ladder_never_skips_backwards_across_calls(self):
        level = "observation"
        history = [level]
        for kwargs in (
            {"explicit": True},
            {},  # recurrence bump handled by caller in this unit test
            {},
        ):
            level = PromotionEngine.evaluate(level, 2, **kwargs)
            history.append(level)
        assert history == ["observation", "preference", "strong_preference", "strong_preference"]


class TestCorrectionLedgerRecurrence:
    def test_first_record_creates_observation_level(self, correction_ledger: CorrectionLedger):
        c = correction_ledger.record(
            pattern="brand_new_pattern",
            desired_behavior="retrieve_project_context",
            undesired_behavior="search_web",
        )
        assert c.recurrence_count == 1
        assert c.promotion_level == "observation"

    def test_recurrence_increments_and_preserves_first_seen(self, correction_ledger: CorrectionLedger):
        first = correction_ledger.record(
            pattern="repeatable_pattern",
            desired_behavior="verify_action",
            undesired_behavior="answer_directly",
            explicit=True,
        )
        second = correction_ledger.record(
            pattern="repeatable_pattern",
            desired_behavior="verify_action",
            undesired_behavior="answer_directly",
        )
        assert second.recurrence_count == 2
        assert second.first_seen == first.first_seen
        assert second.promotion_level == "strong_preference"

    def test_recurrence_promotion_fires_exactly_at_criteria(self, correction_ledger: CorrectionLedger):
        pattern = "escalating_pattern"
        r1 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u", explicit=True)
        assert r1.promotion_level == "preference"
        r2 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u")
        assert r2.promotion_level == "strong_preference"
        r3 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u", severity="normal")
        assert r3.promotion_level == "strong_preference", "severity must be high to reach procedural_rule"
        r4 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u", severity="high")
        assert r4.promotion_level == "procedural_rule"
        r5 = correction_ledger.record(
            pattern=pattern, desired_behavior="d", undesired_behavior="u", severity="high", user_confirmed=True
        )
        assert r5.promotion_level == "invariant"

    def test_promotion_never_demotes_across_recurrences(self, correction_ledger: CorrectionLedger):
        pattern = "monotonic_pattern"
        r1 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u",
                                       explicit=True, cross_domain=True)
        assert r1.promotion_level in ("preference", "strong_preference")
        # A later recurrence with weaker signals must never rank below the prior level.
        r2 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u")
        ladder = ["observation", "preference", "strong_preference", "procedural_rule", "invariant"]
        assert ladder.index(r2.promotion_level) >= ladder.index(r1.promotion_level)

    def test_promotion_preserves_provenance_via_supersedes_chain(self, correction_ledger: CorrectionLedger):
        pattern = "provenance_pattern"
        r1 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u")
        r2 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u")
        all_revisions = {r.id: r for r in correction_ledger.all_revisions()}
        assert r1.id in all_revisions, "superseded revision must still exist in the ledger"
        assert r2.id in all_revisions
        assert r2.supersedes == [r1.id]
        assert r1.id in all_revisions[r1.id].superseded_by or all_revisions[r1.id].superseded_by == [r2.id]

    def test_heads_returns_only_latest_revision_per_pattern(self, correction_ledger: CorrectionLedger):
        pattern = "head_pattern"
        correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u")
        r2 = correction_ledger.record(pattern=pattern, desired_behavior="d", undesired_behavior="u")
        heads = correction_ledger.heads()
        assert heads[pattern].id == r2.id

    def test_seed_answer_before_context_recovery_has_recurrence_two(self, correction_ledger: CorrectionLedger):
        head = correction_ledger.get("answer_before_context_recovery")
        assert head is not None
        assert head.recurrence_count == 2
        assert head.promotion_level == "strong_preference"
