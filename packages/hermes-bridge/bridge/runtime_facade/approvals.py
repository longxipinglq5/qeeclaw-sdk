from __future__ import annotations

from typing import Any

from bridge.runtime_facade.models import ApprovalEffect, ApprovalRecord, utc_now


class ApprovalAlreadyResolvedError(RuntimeError):
    pass


class ApprovalNotFoundError(KeyError):
    pass


class ApprovalStore:
    """Single-worker approval store for local-E2E.

    `approval_decision` is the structured audit event emitted after store
    transitions. `human_review` is the timeline/user-facing projection of the
    same decision. Both must carry the same approval id when wired to APIs.
    """

    def __init__(self) -> None:
        self._approvals: dict[str, ApprovalRecord] = {}
        self.side_effects: list[dict[str, Any]] = []

    def create_approval(
        self,
        *,
        approval_id: str,
        run_id: str,
        session_id: str,
        action_kind: str,
        gate_type: str,
        summary: str,
        effect: dict[str, Any],
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            approval_id=approval_id,
            run_id=run_id,
            session_id=session_id,
            action_kind=action_kind,
            gate_type=gate_type,
            status="pending",
            summary=summary,
            effect=ApprovalEffect.model_validate(effect),
        )
        self._approvals[approval_id] = record
        return record

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        return self._approvals.get(approval_id)

    def resolve_approval(
        self,
        approval_id: str,
        *,
        decision: str,
        decided_by: str,
        note: str | None = None,
    ) -> ApprovalRecord:
        record = self.get_approval(approval_id)
        if record is None:
            raise ApprovalNotFoundError(approval_id)
        if record.status != "pending":
            raise ApprovalAlreadyResolvedError(approval_id)
        if decision not in {"approved", "denied", "revision_requested"}:
            raise ValueError(f"Unsupported approval decision: {decision}")

        updated = record.model_copy(
            update={
                "status": decision,
                "decision": decision,
                "decided_by": decided_by,
                "note": note,
                "decided_at": utc_now(),
            }
        )
        self._approvals[approval_id] = updated
        return updated
