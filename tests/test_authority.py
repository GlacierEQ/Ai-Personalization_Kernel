from __future__ import annotations

from apk.authority import AuthorityResolver, Claim


class TestClassification:
    def test_user_intent_classified(self):
        assert AuthorityResolver.classify("I want the CLI tool built this way") == "user_intent"

    def test_firsthand_experience_classified(self):
        assert AuthorityResolver.classify("When I run the build it crashed with SIGSEGV") == "firsthand_experience"

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
        assert AuthorityResolver.controlling_authority("firsthand_experience") == "user_primary"
        assert AuthorityResolver.controlling_authority("project_meaning") == "user_architect"
        assert AuthorityResolver.controlling_authority("provider_state") == "live_readback"
        assert AuthorityResolver.controlling_authority("public_fact") == "primary_sources"


class TestConflictResolution:
    def test_web_vs_firsthand_returns_dispute_not_overwrite(self):
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
        assert resolution.resolution_type == "dispute_firsthand_vs_external"
        assert resolution.requires_user_adjudication is True
        assert resolution.winner is None, "must never silently overwrite firsthand observation"

    def test_intent_beats_search(self):
        intent = Claim(content="I want an internal CLI tool", claim_type="user_intent", source="user")
        web = Claim(content="Web apps are generally better", claim_type="public_fact", source="web_search")
        resolution = AuthorityResolver.resolve_conflict(intent, web)
        assert resolution.resolution_type == "user_intent_sovereign"
        assert resolution.winner is intent
        assert resolution.requires_user_adjudication is False

    def test_intent_beats_provider_state_too(self):
        # Direction and factual certainty are different dimensions (section 5.3):
        # a live provider fact never overrides what the user has decided to build.
        intent = Claim(content="I want to keep the sync queue design", claim_type="user_intent", source="user")
        provider = Claim(content="the live repo shows an async actor module", claim_type="provider_state", source="git")
        resolution = AuthorityResolver.resolve_conflict(intent, provider)
        assert resolution.winner is intent
        assert resolution.resolution_type == "user_intent_sovereign"

    def test_provider_readback_controls_current_state(self):
        stale_memory = Claim(content="the table exists", claim_type="public_fact", source="cached_memory")
        live = Claim(content="relation does not exist", claim_type="provider_state", source="live_sql_query")
        resolution = AuthorityResolver.resolve_conflict(stale_memory, live)
        assert resolution.winner is live
        assert resolution.resolution_type == "provider_readback_controls"
        assert resolution.requires_user_adjudication is False

    def test_project_meaning_overrules_implementation_drift(self):
        meaning = Claim(content="our kernel uses an actor model", claim_type="project_meaning", source="user")
        drift = Claim(content="legacy modules use sync queues", claim_type="public_fact", source="repo_scan")
        resolution = AuthorityResolver.resolve_conflict(meaning, drift)
        assert resolution.winner is meaning
        assert resolution.resolution_type == "project_meaning_sovereign"
