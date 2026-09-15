from __future__ import annotations

import pytest

from apk.types import MemoryObject, MemoryObjectValidationError, compute_content_hash


def make_obj(**overrides):
    defaults = dict(
        id="obj_1",
        type="preference",
        scope="global",
        status="active",
        confidence=0.9,
        source="test",
        source_refs=["ref1"],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        valid_from="2026-01-01T00:00:00+00:00",
        valid_until=None,
        payload={"desired_action": "retrieve_personal_context"},
    )
    defaults.update(overrides)
    return MemoryObject(**defaults)


class TestValidation:
    def test_valid_object_constructs(self):
        obj = make_obj()
        assert obj.type == "preference"
        assert obj.content_hash == compute_content_hash(obj.payload)

    def test_invalid_type_rejected(self):
        with pytest.raises(MemoryObjectValidationError):
            make_obj(type="not_a_real_type")

    def test_invalid_scope_rejected(self):
        with pytest.raises(MemoryObjectValidationError):
            make_obj(scope="galaxy")

    def test_invalid_status_rejected(self):
        with pytest.raises(MemoryObjectValidationError):
            make_obj(status="deleted")

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(MemoryObjectValidationError):
            make_obj(confidence=1.5)
        with pytest.raises(MemoryObjectValidationError):
            make_obj(confidence=-0.1)

    def test_content_hash_mismatch_rejected(self):
        with pytest.raises(MemoryObjectValidationError):
            make_obj(content_hash="0" * 64)

    def test_content_hash_is_deterministic_over_payload(self):
        a = make_obj(id="a", payload={"x": 1, "y": 2})
        b = make_obj(id="b", payload={"y": 2, "x": 1})
        assert a.content_hash == b.content_hash


class TestStore:
    def test_append_and_read_all(self, empty_store):
        obj = make_obj()
        empty_store.append(obj)
        all_objs = empty_store.read_all()
        assert len(all_objs) == 1
        assert all_objs[0].id == "obj_1"

    def test_atomic_write_leaves_no_tmp_files(self, empty_store, tmp_path):
        empty_store.append(make_obj())
        leftovers = list(tmp_path.glob("*.jsonlstore-*.tmp"))
        assert leftovers == []

    def test_dedup_preserves_both_records_and_links_related_to(self, empty_store):
        a = make_obj(id="a", payload={"same": "payload"})
        b = make_obj(id="b", payload={"same": "payload"}, source="different_source")
        empty_store.append(a)
        stored_b = empty_store.append(b)

        all_objs = empty_store.read_all()
        assert len(all_objs) == 2, "duplicate content hash must NOT destroy either record"
        assert stored_b.content_hash == a.content_hash
        assert "a" in stored_b.related_to, "dedup must link the duplicate via related_to"

    def test_read_by_type_and_status(self, empty_store):
        empty_store.append(make_obj(id="a", type="preference", status="active"))
        empty_store.append(make_obj(id="b", type="correction", status="active"))
        empty_store.append(make_obj(id="c", type="preference", status="resolved"))

        prefs = empty_store.read_by_type("preference")
        assert {o.id for o in prefs} == {"a", "c"}
        active = empty_store.read_active()
        assert {o.id for o in active} == {"a", "b"}

    def test_superseded_filtering_excludes_from_active(self, empty_store):
        empty_store.append(make_obj(id="a", status="active"))
        obj_a = empty_store.find_by_id("a")
        updated = obj_a.with_updates(status="superseded", superseded_by=["b"])
        empty_store.update(updated)
        empty_store.append(make_obj(id="b", payload={"desired_action": "x"}, supersedes=["a"]))

        active_ids = {o.id for o in empty_store.read_active()}
        assert active_ids == {"b"}
        superseded_ids = {o.id for o in empty_store.read_superseded()}
        assert superseded_ids == {"a"}
        # provenance preserved: record "a" still exists in full, just relabeled.
        assert empty_store.find_by_id("a") is not None

    def test_update_unknown_id_raises(self, empty_store):
        from apk.store import StoreError

        with pytest.raises(StoreError):
            empty_store.update(make_obj(id="ghost"))
