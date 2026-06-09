from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.errors import api_error
from bridge.runtime_facade.approvals import (
    ApprovalAlreadyResolvedError,
    ApprovalNotFoundError,
)
from bridge.runtime_facade.models import RunStatus

router = APIRouter()


def _facade(request: Request):
    return request.app.state.runtime_facade


@router.post("/api/runs/{run_id}/approvals/{approval_id}/approve")
async def approve_run_action(run_id: str, approval_id: str, request: Request) -> JSONResponse:
    return await _decide(run_id, approval_id, request, decision="approved")


@router.post("/api/runs/{run_id}/approvals/{approval_id}/deny")
async def deny_run_action(run_id: str, approval_id: str, request: Request) -> JSONResponse:
    return await _decide(run_id, approval_id, request, decision="denied")


@router.post("/api/runs/{run_id}/approvals/{approval_id}/revise")
async def revise_run_action(run_id: str, approval_id: str, request: Request) -> JSONResponse:
    return await _decide(run_id, approval_id, request, decision="revision_requested")


async def _decide(
    run_id: str,
    approval_id: str,
    request: Request,
    *,
    decision: str,
) -> JSONResponse:
    facade = _facade(request)
    run = facade.runs.get(run_id)
    if run is None:
        return api_error("RUN_NOT_FOUND", "Run not found", 404, {"run_id": run_id})
    if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
        return api_error("RUN_TERMINAL", "Run is already terminal", 409, {"run_id": run_id})

    body = await _json_or_empty(request)
    decided_by = str(body.get("decided_by") or body.get("owner_id") or "owner")
    note = body.get("note")
    try:
        record = facade.approvals.resolve_approval(
            approval_id,
            decision=decision,
            decided_by=decided_by,
            note=str(note) if note is not None else None,
        )
    except ApprovalNotFoundError:
        return api_error(
            "APPROVAL_NOT_FOUND",
            "Approval not found",
            404,
            {"approval_id": approval_id},
        )
    except ApprovalAlreadyResolvedError:
        return api_error(
            "APPROVAL_ALREADY_RESOLVED",
            "Approval is already resolved",
            409,
            {"approval_id": approval_id},
        )

    decision_event = facade.events.append(
        session_id=run.session_id,
        run_id=run.run_id,
        type="approval_decision",
        payload={
            "approval_id": record.approval_id,
            "decision": decision,
            "decided_by": decided_by,
            "note": record.note,
        },
        trace_id=run.trace_id,
    )
    facade.events.append(
        session_id=run.session_id,
        run_id=run.run_id,
        type="human_review",
        payload={
            "approval_id": record.approval_id,
            "decision": decision,
            "source_event_id": decision_event.event_id,
            "summary": record.summary,
        },
        trace_id=run.trace_id,
    )

    if decision == "approved" and record.effect.action_kind == "write_memory":
        facade.events.append(
            session_id=run.session_id,
            run_id=run.run_id,
            type="memory_write_requested",
            payload={
                "approval_id": record.approval_id,
                "memory_write": record.effect.memory_write,
            },
            trace_id=run.trace_id,
        )

    return JSONResponse(
        {
            "approval_id": record.approval_id,
            "status": record.status,
            "run_status": run.status.value,
            "effect": record.effect.model_dump(mode="json"),
        }
    )


async def _json_or_empty(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}
