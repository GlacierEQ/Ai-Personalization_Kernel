"""Typed memory objects (spec section 12).

``MemoryObject`` is the common metadata envelope every canonical ledger
record is stored under. Validation is real: constructing an invalid object
raises immediately, it does not silently coerce or accept unknown types.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict, replace
from typing import Any, Optional

# The 24 required typed memory object kinds (spec section 12).
MEMORY_TYPES: tuple[str, ...] = (
    "identity",
    "expertise",
    "preference",
    "negative_preference",
    "interaction_rule",
    "epistemic_preference",
    "authority_rule",
    "correction",
    "failure_pattern",
    "successful_strategy",
    "failed_strategy",
    "project_state",
    "operator_decision",
    "firsthand_observation",
    "verified_external_fact",
    "unverified_external_claim",
    "resolution",
    "superseded_state",
    "tool_capability",
    "provider_state",
    "relationship",
    "goal",
    "constraint",
    "temporary_state",
)

SCOPES: tuple[str, ...] = ("global", "project", "domain", "conversation")
STATUSES: tuple[str, ...] = ("active", "superseded", "resolved", "quarantined")

Scope = str
Status = str


class MemoryObjectValidationError(ValueError):
    """Raised when a MemoryObject is constructed with invalid field values."""


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON serialization used for content hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_content_hash(payload: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of a payload (spec section 12 content_hash)."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryObject:
    id: str
    type: str
    scope: str
    status: str
    confidence: float
    source: str
    source_refs: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    valid_from: str = ""
    valid_until: Optional[str] = None
    supersedes: list[str] = field(default_factory=list)
    superseded_by: list[str] = field(default_factory=list)
    related_to: list[str] = field(default_factory=list)
    content_hash: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        errors: list[str] = []
        if self.type not in MEMORY_TYPES:
            errors.append(f"type {self.type!r} is not one of the 24 canonical memory types")
        if self.scope not in SCOPES:
            errors.append(f"scope {self.scope!r} is not one of {SCOPES}")
        if self.status not in STATUSES:
            errors.append(f"status {self.status!r} is not one of {STATUSES}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            errors.append(f"confidence {self.confidence!r} must be within [0, 1]")
        if not self.id:
            errors.append("id must be a non-empty string")
        if not isinstance(self.payload, dict):
            errors.append("payload must be an object")
        if errors:
            raise MemoryObjectValidationError("; ".join(errors))
        expected_hash = compute_content_hash(self.payload)
        if not self.content_hash:
            object.__setattr__(self, "content_hash", expected_hash)
        elif self.content_hash != expected_hash:
            errors.append(
                f"content_hash mismatch: stored={self.content_hash} expected={expected_hash}"
            )
            raise MemoryObjectValidationError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryObject":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in known}
        return cls(**clean)

    def with_updates(self, **kwargs: Any) -> "MemoryObject":
        """Return a new object with fields replaced (used for controlled, auditable mutation)."""
        return replace(self, **kwargs)
