"""Drift detector: diff two policy-weight or user-model states.

Used to audit exactly what changed between two policy revisions (added,
removed, changed weights/rules) with content hashes, so a policy update can
be reviewed before being replayed against the regression corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apk.types import canonical_json, compute_content_hash


@dataclass
class DriftReport:
    added: dict[str, Any]
    removed: dict[str, Any]
    changed: dict[str, dict[str, Any]]
    old_hash: str
    new_hash: str

    @property
    def has_drift(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "has_drift": self.has_drift,
        }


class DriftDetector:
    @staticmethod
    def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        flat: dict[str, Any] = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                flat.update(DriftDetector._flatten(v, key))
            else:
                flat[key] = v
        return flat

    @staticmethod
    def compare(old: dict[str, Any], new: dict[str, Any]) -> DriftReport:
        old_flat = DriftDetector._flatten(old)
        new_flat = DriftDetector._flatten(new)
        old_keys, new_keys = set(old_flat), set(new_flat)

        added = {k: new_flat[k] for k in new_keys - old_keys}
        removed = {k: old_flat[k] for k in old_keys - new_keys}
        changed = {
            k: {"old": old_flat[k], "new": new_flat[k]}
            for k in old_keys & new_keys
            if old_flat[k] != new_flat[k]
        }
        return DriftReport(
            added=added,
            removed=removed,
            changed=changed,
            old_hash=compute_content_hash(old),
            new_hash=compute_content_hash(new),
        )
