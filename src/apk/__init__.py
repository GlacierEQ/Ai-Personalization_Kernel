"""Ai-Personalization_Kernel: an executable personalization-to-behavior binding layer.

This package makes durable user state part of the decision policy that
determines what an assistant does next, instead of leaving personalization as
optional, retrievable-but-ignorable context. See ``docs/`` and the master
specification for the governing architecture.
"""

from apk.types import MemoryObject, Scope, Status, MEMORY_TYPES
from apk.store import JsonlStore
from apk.user_model import UserModel, UserModelMissingError
from apk.authority import AuthorityResolver, Claim, ConflictResolution
from apk.router import RetrievalRouter, TurnContext, ReingestionError
from apk.policy import PolicyEngine, DecisionContext, ScoredAction
from apk.corrections import Correction, CorrectionLedger, PromotionEngine
from apk.supersession import SupersessionResolver, ReopenNotAuthorizedError
from apk.reward import RewardModel
from apk.replay import ExperienceReplay, EvalRun
from apk.drift import DriftDetector
from apk.boot import BootContract, BootReceipt, BootContractError
from apk.connectors import SupabaseConnector, SyncError, SyncReport, SyncSink

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "MemoryObject",
    "Scope",
    "Status",
    "MEMORY_TYPES",
    "JsonlStore",
    "UserModel",
    "UserModelMissingError",
    "AuthorityResolver",
    "Claim",
    "ConflictResolution",
    "RetrievalRouter",
    "TurnContext",
    "ReingestionError",
    "PolicyEngine",
    "DecisionContext",
    "ScoredAction",
    "Correction",
    "CorrectionLedger",
    "PromotionEngine",
    "SupersessionResolver",
    "ReopenNotAuthorizedError",
    "RewardModel",
    "ExperienceReplay",
    "EvalRun",
    "DriftDetector",
    "BootContract",
    "BootReceipt",
    "BootContractError",
    "SupabaseConnector",
    "SyncError",
    "SyncReport",
    "SyncSink",
]
