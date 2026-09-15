"""Connector plane for the Ai-Personalization_Kernel (spec section 13).

Canonical truth lives in the JSONL ledger. Sinks are projections. See
``docs/CONNECTOR_PLANE.md`` for the orchestration contract that
``backend-ops`` implements.
"""

from apk.connectors.base import (
    RowsByTable,
    SyncError,
    SyncEvent,
    SyncReport,
    SyncSink,
    redact,
)
from apk.connectors.supabase import SupabaseConnector, build_rows_by_table

__all__ = [
    "RowsByTable",
    "SyncError",
    "SyncEvent",
    "SyncReport",
    "SyncSink",
    "redact",
    "SupabaseConnector",
    "build_rows_by_table",
]
