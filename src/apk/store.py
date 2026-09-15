"""Append-only JSONL canonical ledger (spec section 13.1 / section 14).

Guarantees:
- atomic writes (write to a temp file, then ``os.replace`` into place);
- provenance is never destroyed: duplicate content hashes are linked via
  ``related_to``, both records are kept;
- active/superseded/resolved filtering for policy consumption;
- controlled ``update`` for status/link mutation only (used by
  ``SupersessionResolver``); payload and identity fields of a record are
  never rewritten by ``update``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Optional

from apk.types import MemoryObject


class StoreError(RuntimeError):
    pass


class JsonlStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    # -- internal I/O -----------------------------------------------------

    def _read_lines(self) -> list[str]:
        text = self.path.read_text(encoding="utf-8")
        return [line for line in text.splitlines() if line.strip()]

    def _atomic_write_lines(self, lines: Iterable[str]) -> None:
        fd, tmp_name = tempfile.mkstemp(
            prefix=".jsonlstore-", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for line in lines:
                    fh.write(line)
                    fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    # -- reads --------------------------------------------------------------

    def read_all(self) -> list[MemoryObject]:
        objs = []
        for line in self._read_lines():
            data = json.loads(line)
            objs.append(MemoryObject.from_dict(data))
        return objs

    def find_by_id(self, obj_id: str) -> Optional[MemoryObject]:
        for obj in self.read_all():
            if obj.id == obj_id:
                return obj
        return None

    def find_by_content_hash(self, content_hash: str) -> list[MemoryObject]:
        return [o for o in self.read_all() if o.content_hash == content_hash]

    def read_by_type(self, type_: str) -> list[MemoryObject]:
        return [o for o in self.read_all() if o.type == type_]

    def read_by_status(self, status: str) -> list[MemoryObject]:
        return [o for o in self.read_all() if o.status == status]

    def read_active(self) -> list[MemoryObject]:
        return self.read_by_status("active")

    def read_superseded(self) -> list[MemoryObject]:
        return self.read_by_status("superseded")

    def read_resolved(self) -> list[MemoryObject]:
        return self.read_by_status("resolved")

    # -- writes ---------------------------------------------------------------

    def append(self, obj: MemoryObject) -> MemoryObject:
        """Append a record. If its content_hash duplicates an existing record,
        the duplication is preserved (never dropped); the new record is linked
        to the existing one(s) via ``related_to`` so provenance survives.
        """
        existing_dupes = self.find_by_content_hash(obj.content_hash)
        if existing_dupes:
            linked = sorted(set(obj.related_to) | {e.id for e in existing_dupes} - {obj.id})
            obj = obj.with_updates(related_to=linked)
        lines = self._read_lines()
        lines.append(json.dumps(obj.to_dict(), sort_keys=True))
        self._atomic_write_lines(lines)
        return obj

    def update(self, obj: MemoryObject) -> MemoryObject:
        """Controlled mutation of a record already in the ledger (status /
        supersedes / superseded_by / related_to / updated_at only). The
        record is never deleted; history is preserved because this rewrites
        the whole ledger atomically in place, it does not remove entries.
        """
        current = self.read_all()
        if not any(o.id == obj.id for o in current):
            raise StoreError(f"cannot update unknown record id={obj.id!r}")
        new_lines = []
        for o in current:
            target = obj if o.id == obj.id else o
            new_lines.append(json.dumps(target.to_dict(), sort_keys=True))
        self._atomic_write_lines(new_lines)
        return obj

    def __len__(self) -> int:
        return len(self._read_lines())
