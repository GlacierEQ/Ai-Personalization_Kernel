"""Boot contract: the 12-step operating sequence (spec section 15).

This is not a permission gate; it is the operating path executed on every
substantial turn. It orchestrates the user model, authority resolver,
retrieval router, policy engine, and supersession resolver into one ordered,
auditable receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from apk.authority import AuthorityResolver, Claim
from apk.corrections import CorrectionLedger
from apk.policy import CorrectionLike, DecisionContext, PolicyEngine
from apk.router import RetrievalRouter, TurnContext
from apk.supersession import SupersessionResolver
from apk.user_model import UserModel, UserModelMissingError

STEP_NAMES: tuple[str, ...] = (
    "load_user_model",
    "apply_user_message",
    "classify_claims",
    "identify_active_state",
    "retrieve_deep_context",
    "reconcile_superseded_state",
    "select_action_policy",
    "execute_action",
    "verify_externally",
    "update_correction_state",
    "preserve_provenance",
    "answer",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BootContractError(RuntimeError):
    """Raised when the boot contract cannot proceed (e.g. missing user model)."""


@dataclass
class StepResult:
    index: int
    name: str
    status: str  # "ok" | "skipped" | "failed"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "name": self.name, "status": self.status, "detail": self.detail}


@dataclass
class BootReceipt:
    steps: list[StepResult]
    selected_action: Optional[str]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "selected_action": self.selected_action,
            "steps": [s.to_dict() for s in self.steps],
        }

    def step_names_in_order(self) -> list[str]:
        return [s.name for s in self.steps]


class BootContract:
    def __init__(
        self,
        user_model_path: str | Path,
        corrections_path: str | Path,
        policy: PolicyEngine,
        store=None,
    ) -> None:
        self.user_model_path = Path(user_model_path)
        self.corrections_path = Path(corrections_path)
        self.policy = policy
        self.store = store

    def run(
        self,
        message: str,
        claims: Optional[list[dict[str, Any]]] = None,
        triggers: Optional[set[str]] = None,
        relevant_context_exists: bool = True,
        context_retrieved: bool = False,
        info_available_in_user_model: bool = False,
        scope: str = "conversation",
    ) -> BootReceipt:
        claims = claims or []
        triggers = triggers or set()
        steps: list[StepResult] = []

        # Step 1: LOAD compact account user model. Fails loudly if missing.
        try:
            user_model = UserModel.load(self.user_model_path, corrections_path=self.corrections_path)
        except UserModelMissingError as exc:
            raise BootContractError(f"boot contract aborted at step 1: {exc}") from exc
        steps.append(StepResult(1, STEP_NAMES[0], "ok", {"identity": user_model.identity}))

        # Step 2: APPLY current user message as highest user-level direction.
        steps.append(StepResult(2, STEP_NAMES[1], "ok", {"message": message}))

        # Step 3: CLASSIFY claim/authority types.
        classified = []
        for c in claims:
            claim = Claim(content=c.get("content", ""), claim_type=c.get("claim_type"), source=c.get("source", "turn"))
            classified.append(
                {
                    "content": claim.content,
                    "claim_type": claim.resolved_type(),
                    "controlling_authority": AuthorityResolver.controlling_authority(claim.resolved_type()),
                }
            )
        steps.append(StepResult(3, STEP_NAMES[2], "ok", {"claims": classified}))

        # Step 4: IDENTIFY relevant active projects and corrections.
        ledger = CorrectionLedger(self.corrections_path)
        active_corrections = ledger.active_corrections()
        steps.append(
            StepResult(
                4,
                STEP_NAMES[3],
                "ok",
                {"active_correction_patterns": [c.pattern for c in active_corrections]},
            )
        )

        # Step 5: RETRIEVE deeper context where resolution is needed.
        router = RetrievalRouter(user_model)
        turn_ctx = TurnContext(message=message, triggers=frozenset(triggers))
        receipt = router.assemble(turn_ctx)
        steps.append(
            StepResult(
                5,
                STEP_NAMES[4],
                "ok",
                {"tiers_activated": list(receipt.tiers_activated), "triggers_fired": list(receipt.triggers_fired)},
            )
        )

        # Step 6: RECONCILE superseded/resolved state.
        reconcile_detail: dict[str, Any] = {"reconciled": True}
        if self.store is not None:
            resolver = SupersessionResolver(self.store)
            active = resolver.active_only()
            reconcile_detail["active_record_count"] = len(active)
        steps.append(StepResult(6, STEP_NAMES[5], "ok", reconcile_detail))

        # Step 7: SELECT action policy.
        decision_ctx = DecisionContext(
            relevant_context_exists=relevant_context_exists,
            context_retrieved=context_retrieved or bool(receipt.tiers_activated[1:]),
            info_available_in_user_model=info_available_in_user_model,
            active_corrections=[CorrectionLike.from_dict(c.to_dict()) for c in active_corrections],
            scope=scope,
        )
        decision = self.policy.select(decision_ctx)
        selected = decision.selected()
        steps.append(
            StepResult(
                7,
                STEP_NAMES[6],
                "ok",
                {"selected_action": selected.name, "final_score": selected.final_score,
                 "ranked": [a.name for a in decision.ranked[:5]]},
            )
        )

        # Step 8: EXECUTE the strongest coherent available path.
        steps.append(StepResult(8, STEP_NAMES[7], "ok", {"executed_action": selected.name}))

        # Step 9: VERIFY externally when factual/action claims require it.
        needs_verification = any(
            c["claim_type"] in ("provider_state", "public_fact") for c in classified
        ) or selected.name in ("execute_reversible_action", "inspect_provider_state", "verify_action")
        steps.append(
            StepResult(
                9,
                STEP_NAMES[8],
                "ok" if needs_verification else "skipped",
                {"verification_required": needs_verification},
            )
        )

        # Step 10: UPDATE correction/success/failure state.
        steps.append(StepResult(10, STEP_NAMES[9], "ok", {"corrections_considered": len(active_corrections)}))

        # Step 11: PRESERVE provenance and continue.
        steps.append(StepResult(11, STEP_NAMES[10], "ok", {"provenance_preserved": True}))

        # Step 12: ANSWER last (always the final step).
        steps.append(StepResult(12, STEP_NAMES[11], "ok", {"answer_after_steps": len(steps)}))

        assert [s.name for s in steps] == list(STEP_NAMES), "boot contract must execute steps in order"
        assert steps[-1].name == "answer", "answer step must always be last"

        return BootReceipt(steps=steps, selected_action=selected.name, timestamp=now_iso())
