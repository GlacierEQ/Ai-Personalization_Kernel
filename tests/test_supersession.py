from __future__ import annotations

import pytest

from apk.supersession import ReopenNotAuthorizedError, SupersessionResolver
from apk.types import MemoryObject


def make_obj(obj_id: str, **overrides) -> MemoryObject:
    defaults = dict(
        id=obj_id,
        type="project_state",
        scope="project",
        status="active",
        confidence=1.0,
        source="test",
        source_refs=[],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        valid_from="2026-01-01T00:00:00+00:00",
        valid_until=None,
        payload={"note": obj_id},
    )
    defaults.update(overrides)
    return MemoryObject(**defaults)


@pytest.fixture()
def resolver(empty_store):
    empty_store.append(make_obj("old"))
    empty_store.append(make_obj("new", payload={"note": "new"}))
    return SupersessionResolver(empty_store)


class TestSupersede:
    def test_supersede_marks_old_and_links_new(self, resolver: SupersessionResolver):
        old, new = resolver.supersede("old", "new")
        assert old.status == "superseded"
        assert "new" in old.superseded_by
        assert "old" in new.supersedes

    def test_superseded_record_excluded_from_active_policy_influence(self, resolver: SupersessionResolver):
        resolver.supersede("old", "new")
        active_ids = {o.id for o in resolver.active_only()}
        assert active_ids == {"new"}

    def test_supersede_preserves_provenance_record_still_readable(self, resolver: SupersessionResolver):
        resolver.supersede("old", "new")
        old = resolver.store.find_by_id("old")
        assert old is not None
        assert old.payload == {"note": "old"}

    def test_supersede_unknown_id_raises(self, resolver: SupersessionResolver):
        from apk.supersession import SupersessionError

        with pytest.raises(SupersessionError):
            resolver.supersede("ghost", "new")


class TestResolveAndReopen:
    def test_resolve_marks_resolved_and_excludes_from_active(self, resolver: SupersessionResolver):
        resolver.resolve("old")
        active_ids = {o.id for o in resolver.active_only()}
        assert "old" not in active_ids
        assert resolver.store.find_by_id("old").status == "resolved"

    def test_reopen_without_explicit_flag_raises(self, resolver: SupersessionResolver):
        resolver.resolve("old")
        with pytest.raises(ReopenNotAuthorizedError):
            resolver.reopen("old")

    def test_reopen_with_explicit_flag_succeeds(self, resolver: SupersessionResolver):
        resolver.resolve("old")
        reopened = resolver.reopen("old", explicit=True)
        assert reopened.status == "active"
        assert "old" in {o.id for o in resolver.active_only()}

    def test_reopen_active_record_is_noop(self, resolver: SupersessionResolver):
        result = resolver.reopen("new", explicit=False)
        assert result.status == "active"


class TestSupersessionChains:
    def test_chain_is_traversable_forward_and_backward(self, empty_store):
        empty_store.append(make_obj("v1"))
        empty_store.append(make_obj("v2", payload={"note": "v2"}))
        empty_store.append(make_obj("v3", payload={"note": "v3"}))
        r = SupersessionResolver(empty_store)
        r.supersede("v1", "v2")
        r.supersede("v2", "v3")

        chain_from_v1 = r.chain("v1")
        chain_from_v3 = r.chain("v3")
        assert [o.id for o in chain_from_v1] == ["v1", "v2", "v3"]
        assert [o.id for o in chain_from_v3] == ["v1", "v2", "v3"]

    def test_chain_unknown_id_raises(self, empty_store):
        r = SupersessionResolver(empty_store)
        empty_store.append(make_obj("only"))
        from apk.supersession import SupersessionError

        with pytest.raises(SupersessionError):
            r.chain("ghost")
