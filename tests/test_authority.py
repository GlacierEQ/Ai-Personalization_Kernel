from __future__ import annotations

from apk.authority import AuthorityResolver, Claim


class TestClassification:
    def test_user_intent_classified(self):
        assert AuthorityResolver.classify("I want the CLI tool built this way") == "user_intent"

    def test_firsthand_experience_classified(self):
        assert AuthorityResolver.classify("When I run the build it crashed with SIGSEGV") == "firsthand_experience"

    def test_legal_firsthand_experience_classified(self):
        assert AuthorityResolver.classify("They made me sign it and I was given three minutes") == "firsthand_experience"

    def test_project_meaning_classified(self):
        assert AuthorityResolver.classify("Our architecture uses an actor model") == "project_meaning"

    def test_provider_state_classified(self):
        assert AuthorityResolver.classify("git status right now shows a clean tree") == "provider_state"

    def test_public_fact_default(self):
        assert AuthorityResolver.classify("Python 3.12 was released in 2023") == "public_fact"

    def test_explicit_type_overrides_heuristic(self):
        assert AuthorityResolver.classify("anything at all", explicit_type="provider_state") == "provider_state"


class TestControllingAuthority:
    def test_each_claim_type_routes_to_correct_authority(self):
        assert AuthorityResolver.controlling_authority("user_intent") == "user_sovereign"
        assert AuthorityResolver.controlling_authority("firsthand_experience") == "user_witness"
        assert AuthorityResolver.controlling_authority("project_meaning") == "user_architect"
        assert AuthorityResolver.controlling_authority("provider_state") == "live_readback_for_provider_state"
        assert AuthorityResolver.controlling_authority("public_fact") == "primary_sources_for_public_fact"


class TestConflictResolution:
    def test_web_vs_firsthand_preserves_parallel_evidence_not_dispute(self):
        firsthand = Claim(
            content="It fails with SIGSEGV in libuv on Debian Bookworm",
            claim_type="firsthand_experience",
            source="user_terminal",
        )
        web = Claim(
            content="Bun natively supports Debian Bookworm compilation",
            claim_type="public_fact",
            source="web_search",
        )
        resolution = AuthorityResolver.resolve_conflict(firsthand, web)
        assert resolution.resolution_type == "parallel_evidence_lanes"
        assert resolution.requires_user_adjudication is False
        assert resolution.winner is None
        assert resolution.preserved_claims == (firsthand, web)
        assert "truth rank" in resolution.rationale

    def test_document_does_not_own_actuality_over_lived_experience(self):
        firsthand = Claim(
            content="They made me sign it and I was given about three minutes to review it",
            claim_type="firsthand_experience",
            source="user_witness",
        )
        document = Claim(
            content="The written agreement contains a tardiness wage-reduction clause",
            claim_type="public_fact",
            source="signed_agreement",
        )
        resolution = AuthorityResolver.resolve_conflict(firsthand, document)
        assert resolution.winner is None
        assert resolution.resolution_type == "parallel_evidence_lanes"
        assert resolution.requires_user_adjudication is False
        assert firsthand in resolution.preserved_claims
        assert document in resolution.preserved_claims

    def test_live_provider_state_does_not_erase_historical_firsthand_observation(self):
        firsthand = Claim(
            content="I saw the table exist yesterday and queried it",
            claim_type="firsthand_experience",
            source="user_witness",
        )
        live = Claim(
            content="relation does not exist right now",
            claim_type="provider_state",
            source="live_sql_query",
        )
        resolution = AuthorityResolver.resolve_conflict(firsthand, live)
        assert resolution.winner is None
        assert resolution.resolution_type == "parallel_evidence_lanes"
        assert resolution.preserved_claims == (firsthand, live)

    def test_intent_controls_direction_without_erasing_other_source(self):
        intent = Claim(content="I want an internal CLI tool", claim_type="user_intent", source="user")
        web = Claim(content="Web apps are generally better", claim_type="public_fact", source="web_search")
        resolution = AuthorityResolver.resolve_conflict(intent, web)
        assert resolution.resolution_type == "user_intent_controls_direction"
        assert resolution.winner is intent
        assert resolution.requires_user_adjudication is False
        assert resolution.preserved_claims == (intent, web)

    def test_intent_controls_direction_even_with_provider_state(self):
        intent = Claim(content="I want to keep the sync queue design", claim_type="user_intent", source="user")
        provider = Claim(content="the live repo shows an async actor module", claim_type="provider_state", source="git")
        resolution = AuthorityResolver.resolve_conflict(intent, provider)
        assert resolution.winner is intent
        assert resolution.resolution_type == "user_intent_controls_direction"
        assert resolution.preserved_claims == (intent, provider)

    def test_provider_readback_controls_current_provider_state_over_cached_public_claim(self):
        stale_memory = Claim(content="the table exists", claim_type="public_fact", source="cached_memory")
        live = Claim(content="relation does not exist", claim_type="provider_state", source="live_sql_query")
        resolution = AuthorityResolver.resolve_conflict(stale_memory, live)
        assert resolution.winner is live
        assert resolution.resolution_type == "provider_readback_controls_current_provider_state"
        assert resolution.requires_user_adjudication is False
        assert resolution.preserved_claims == (stale_memory, live)

    def test_project_meaning_controls_intended_architecture_without_deleting_drift(self):
        meaning = Claim(content="our kernel uses an actor model", claim_type="project_meaning", source="user")
        drift = Claim(content="legacy modules use sync queues", claim_type="public_fact", source="repo_scan")
        resolution = AuthorityResolver.resolve_conflict(meaning, drift)
        assert resolution.winner is meaning
        assert resolution.resolution_type == "project_meaning_controls_intended_architecture"
        assert resolution.preserved_claims == (meaning, drift)

    def test_two_public_sources_do_not_get_arbitrary_winner(self):
        a = Claim(content="Source A says X", claim_type="public_fact", source="source_a")
        b = Claim(content="Source B says Y", claim_type="public_fact", source="source_b")
        resolution = AuthorityResolver.resolve_conflict(a, b)
        assert resolution.winner is None
        assert resolution.resolution_type == "provenance_comparison_required"
        assert resolution.requires_user_adjudication is False
