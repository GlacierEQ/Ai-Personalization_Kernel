"""Supersession resolver (spec invariants 10 & 11).

- Resolved issues must not be reopened merely because an older memory says
  unresolved (invariant 10) -> reopening a resolved record requires an
  explicit flag.
- Supersession preserves provenance (invariant 11) -> superseding a record
  never deletes it; it links old<->new and marks status, keeping the full
  chain traversable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from apk.store import JsonlStore
from apk.types import MemoryObject


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupersessionError(RuntimeError):
    pass


class ReopenNotAuthorizedError(SupersessionError):
    """Raised when reopening a resolved/superseded record is attempted without explicit=True."""


class SupersessionResolver:
    def __init__(self, store: JsonlStore):
        self.store = store

    def supersede(self, old_id: str, new_id: str) -> tuple[MemoryObject, MemoryObject]:
        old = self.store.find_by_id(old_id)
        new = self.store.find_by_id(new_id)
        if old is None:
            raise SupersessionError(f"unknown record id={old_id!r}")
        if new is None:
            raise SupersessionError(f"unknown record id={new_id!r}")
        updated_old = old.with_updates(
            status="superseded",
            superseded_by=sorted(set(old.superseded_by) | {new_id}),
            updated_at=now_iso(),
        )
        updated_new = new.with_updates(
            supersedes=sorted(set(new.supersedes) | {old_id}),
            updated_at=now_iso(),
        )
        self.store.update(updated_old)
        self.store.update(updated_new)
        return updated_old, updated_new

    def resolve(self, obj_id: str) -> MemoryObject:
        obj = self.store.find_by_id(obj_id)
        if obj is None:
            raise SupersessionError(f"unknown record id={obj_id!r}")
        updated = obj.with_updates(status="resolved", updated_at=now_iso())
        self.store.update(updated)
        return updated

    def reopen(self, obj_id: str, explicit: bool = False) -> MemoryObject:
        """Reopen a resolved or superseded record. Requires explicit=True
        (invariant 10): an older/background process must never silently
        reopen a resolved issue.
        """
        obj = self.store.find_by_id(obj_id)
        if obj is None:
            raise SupersessionError(f"unknown record id={obj_id!r}")
        if obj.status not in ("resolved", "superseded"):
            return obj
        if not explicit:
            raise ReopenNotAuthorizedError(
                f"record {obj_id!r} is {obj.status!r}; reopening requires an explicit "
                "user action (explicit=True), it cannot be reopened implicitly by stale "
                "memory (invariant 10)"
            )
        updated = obj.with_updates(status="active", updated_at=now_iso())
        self.store.update(updated)
        return updated

    def active_only(self, objs: Optional[list[MemoryObject]] = None) -> list[MemoryObject]:
        objs = objs if objs is not None else self.store.read_all()
        return [o for o in objs if o.status == "active"]

    def chain(self, obj_id: str) -> list[MemoryObject]:
        """Traverse the full supersession chain (oldest -> newest) containing obj_id."""
        all_objs = {o.id: o for o in self.store.read_all()}
        if obj_id not in all_objs:
            raise SupersessionError(f"unknown record id={obj_id!r}")

        # Walk backwards to the earliest ancestor.
        current = all_objs[obj_id]
        visited_back = {current.id}
        while current.supersedes:
            parent_ids = [pid for pid in current.supersedes if pid in all_objs and pid not in visited_back]
            if not parent_ids:
                break
            current = all_objs[parent_ids[0]]
            visited_back.add(current.id)

        # Walk forward collecting the whole chain.
        chain: list[MemoryObject] = [current]
        visited_fwd = {current.id}
        while chain[-1].superseded_by:
            next_ids = [nid for nid in chain[-1].superseded_by if nid in all_objs and nid not in visited_fwd]
            if not next_ids:
                break
            nxt = all_objs[next_ids[0]]
            chain.append(nxt)
            visited_fwd.add(nxt.id)
        return chain
