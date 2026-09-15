"""Correction ledger and promotion engine (spec section 8 /
docs/CORRECTION_PROMOTION_POLICY.md).

Corrections are structured, machine-readable records that mutate policy
scoring (see ``apk.policy``), not prose notes. Recurrence is detected by
exact pattern match; each recurrence appends a new revision (never mutates
history destructively) and re-evaluates the promotion ladder.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROMOTION_LADDER: tuple[str, ...] = (
    "observation",
    "preference",
    "strong_preference",
    "procedural_rule",
    "invariant",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deterministic_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


@dataclass
class Correction:
    id: str
    type: str
    pattern: str
    scope: str
    desired_behavior: str
    undesired_behavior: str
    confidence: float
    recurrence_count: int
    first_seen: str
    last_seen: str
    promotion_level: str
    status: str = "active"
    source_refs: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    superseded_by: list[str] = field(default_factory=list)
    related_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Correction":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


class PromotionEngine:
    """Implements the five-stage promotion ladder deterministically.

    Promotion never demotes: a call that does not satisfy the criteria for
    the *next* stage simply returns the current stage unchanged.
    """

    @staticmethod
    def evaluate(
        current_level: Optional[str],
        recurrence_count: int,
        explicit: bool = False,
        cross_domain: bool = False,
        severity: str = "normal",
        user_confirmed: bool = False,
    ) -> str:
        idx = PROMOTION_LADDER.index(current_level or "observation")
        if idx == 0 and explicit:
            return PROMOTION_LADDER[1]
        if idx == 1 and (recurrence_count >= 2 or cross_domain):
            return PROMOTION_LADDER[2]
        if idx == 2 and (recurrence_count >= 3 and severity == "high"):
            return PROMOTION_LADDER[3]
        if idx == 3 and user_confirmed:
            return PROMOTION_LADDER[4]
        return PROMOTION_LADDER[idx]


class CorrectionLedger:
    """Append-only, provenance-preserving JSONL ledger of corrections.

    Each logical correction (identified by ``pattern``) may have multiple
    revisions in the file (recurrence updates, promotions). The "head" of a
    pattern's chain is whichever revision is not referenced by another
    revision's ``supersedes`` list.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    # -- I/O -----------------------------------------------------------------

    def _load_all(self) -> list[Correction]:
        text = self.path.read_text(encoding="utf-8")
        records = []
        for line in text.splitlines():
            if line.strip():
                records.append(Correction.from_dict(json.loads(line)))
        return records

    def _save_all(self, records: list[Correction]) -> None:
        import os
        import tempfile

        fd, tmp_name = tempfile.mkstemp(
            prefix=".corrections-", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for r in records:
                    fh.write(json.dumps(r.to_dict(), sort_keys=True))
                    fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    # -- reads ------------------------------------------------------------

    def all_revisions(self) -> list[Correction]:
        return self._load_all()

    def heads(self) -> dict[str, Correction]:
        """Return pattern -> latest (head) revision."""
        records = self._load_all()
        superseded_ids = {sid for r in records for sid in r.supersedes}
        heads: dict[str, Correction] = {}
        for r in records:
            if r.id in superseded_ids:
                continue
            existing = heads.get(r.pattern)
            if existing is None or r.last_seen >= existing.last_seen:
                heads[r.pattern] = r
        return heads

    def active_corrections(self) -> list[Correction]:
        return [c for c in self.heads().values() if c.status == "active"]

    def get(self, pattern: str) -> Optional[Correction]:
        return self.heads().get(pattern)

    # -- writes -------------------------------------------------------------

    def record(
        self,
        pattern: str,
        desired_behavior: str,
        undesired_behavior: str,
        scope: str = "global",
        confidence: float = 1.0,
        source_refs: Optional[list[str]] = None,
        explicit: bool = False,
        cross_domain: bool = False,
        severity: str = "normal",
        user_confirmed: bool = False,
        correction_type: str = "behavior_correction",
    ) -> Correction:
        records = self._load_all()
        existing = self.heads().get(pattern)
        now = now_iso()

        if existing is None:
            new_level = PromotionEngine.evaluate(None, 1, explicit, cross_domain, severity, user_confirmed)
            new = Correction(
                id=deterministic_id("corr", pattern, scope, now),
                type=correction_type,
                pattern=pattern,
                scope=scope,
                desired_behavior=desired_behavior,
                undesired_behavior=undesired_behavior,
                confidence=confidence,
                recurrence_count=1,
                first_seen=now,
                last_seen=now,
                promotion_level=new_level,
                status="active",
                source_refs=source_refs or [],
                supersedes=[],
                superseded_by=[],
                related_patterns=[],
            )
            records.append(new)
            self._save_all(records)
            return new

        new_recurrence = existing.recurrence_count + 1
        new_level = PromotionEngine.evaluate(
            existing.promotion_level, new_recurrence, explicit, cross_domain, severity, user_confirmed
        )
        new_id = deterministic_id("corr", pattern, scope, now, str(new_recurrence))
        new = Correction(
            id=new_id,
            type=correction_type,
            pattern=pattern,
            scope=scope,
            desired_behavior=desired_behavior or existing.desired_behavior,
            undesired_behavior=undesired_behavior or existing.undesired_behavior,
            confidence=max(confidence, existing.confidence),
            recurrence_count=new_recurrence,
            first_seen=existing.first_seen,
            last_seen=now,
            promotion_level=new_level,
            status="active",
            source_refs=list({*existing.source_refs, *(source_refs or [])}),
            supersedes=[existing.id],
            superseded_by=[],
            related_patterns=existing.related_patterns,
        )
        # Preserve provenance: link the prior revision forward instead of
        # deleting it, then append (not overwrite) the new revision.
        updated_records = [
            replace(r, superseded_by=list({*r.superseded_by, new_id})) if r.id == existing.id else r
            for r in records
        ]
        updated_records.append(new)
        self._save_all(updated_records)
        return new

    def promote(
        self,
        pattern: str,
        explicit: bool = False,
        cross_domain: bool = False,
        severity: str = "normal",
        user_confirmed: bool = False,
    ) -> Correction:
        """Re-evaluate promotion for an existing pattern without incrementing recurrence."""
        existing = self.heads().get(pattern)
        if existing is None:
            raise KeyError(f"no correction recorded for pattern {pattern!r}")
        new_level = PromotionEngine.evaluate(
            existing.promotion_level, existing.recurrence_count, explicit, cross_domain, severity, user_confirmed
        )
        if new_level == existing.promotion_level:
            return existing
        records = self._load_all()
        now = now_iso()
        new_id = deterministic_id("corr", pattern, "promote", now)
        new = replace(existing, id=new_id, promotion_level=new_level, last_seen=now, supersedes=[existing.id], superseded_by=[])
        updated_records = [
            replace(r, superseded_by=list({*r.superseded_by, new_id})) if r.id == existing.id else r
            for r in records
        ]
        updated_records.append(new)
        self._save_all(updated_records)
        return new
