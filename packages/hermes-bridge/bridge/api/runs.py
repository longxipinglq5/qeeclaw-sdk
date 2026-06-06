from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.responses import StreamingResponse

from bridge.api.errors import api_error
from bridge.runtime_facade.models import CreateRunRequest
from bridge.runtime_facade.run_manager import RunResumeNotAllowedError, RunTerminalError

router = APIRouter()


def _facade(request: Request):
    return request.app.state.runtime_facade


@router.post("/api/runs")
async def create_run(request: Request) -> JSONResponse:
    try:
        req = CreateRunRequest.model_validate(await request.json())
    except ValidationError as exc:
        errors = exc.errors()
        if any("owner_id" in str(error.get("ctx", {})) or "owner_id" in str(error.get("msg", "")) for error in errors):
            return api_error(
                "SESSION_OWNER_MISMATCH",
                "metadata.owner_id conflicts with session_id owner",
                400,
            )
        return api_error("RUN_REQUEST_INVALID", "Run request is invalid", 422, {"errors": errors})

    try:
        response = await _facade(request).create_run(req)
    except ValueError as exc:
        if str(exc) == "RUN_KIND_UNSUPPORTED":
            return api_error(
                "RUN_KIND_UNSUPPORTED",
                "Run kind is not implemented yet",
                400,
                {"kind": req.kind.value},
            )
        raise
    return JSONResponse(response.model_dump(mode="json"))


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> JSONResponse:
    run = _facade(request).get_run(run_id)
    if run is None:
        return api_error("RUN_NOT_FOUND", "Run not found", 404, {"run_id": run_id})
    return JSONResponse({"run": run.model_dump(mode="json")})


@router.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request) -> JSONResponse:
    try:
        run = _facade(request).runs.cancel_run(run_id)
    except KeyError:
        return api_error("RUN_NOT_FOUND", "Run not found", 404, {"run_id": run_id})
    except RunTerminalError:
        return api_error("RUN_TERMINAL", "Run is already terminal", 409, {"run_id": run_id})
    return JSONResponse({"run": run.model_dump(mode="json")})


@router.post("/api/runs/{run_id}/resume")
async def resume_run(run_id: str, request: Request) -> JSONResponse:
    try:
        run = _facade(request).runs.resume_run(run_id)
    except KeyError:
        return api_error("RUN_NOT_FOUND", "Run not found", 404, {"run_id": run_id})
    except RunResumeNotAllowedError:
        return api_error("RUN_RESUME_NOT_ALLOWED", "Run cannot be resumed", 409, {"run_id": run_id})
    return JSONResponse({"run": run.model_dump(mode="json")})


@router.get("/api/runs/{run_id}/events")
async def get_run_events(run_id: str, request: Request) -> JSONResponse:
    run = _facade(request).get_run(run_id)
    if run is None:
        return api_error("RUN_NOT_FOUND", "Run not found", 404, {"run_id": run_id})
    events = [
        event.model_dump(mode="json")
        for event in _facade(request).get_run_events(run_id)
    ]
    return JSONResponse({"events": events})


@router.get("/api/runs/{run_id}/events/stream", response_model=None)
async def stream_run_events(run_id: str, request: Request):
    facade = _facade(request)
    run = facade.get_run(run_id)
    if run is None:
        return api_error("RUN_NOT_FOUND", "Run not found", 404, {"run_id": run_id})

    after_event_id = request.headers.get("Last-Event-ID")
    events = facade.events.list_by_run(run_id)
    if after_event_id and events and after_event_id not in {event.event_id for event in events}:
        return api_error(
            "EVENT_CURSOR_EXPIRED",
            "Event cursor is outside the retained event range",
            409,
            {"run_id": run_id, "last_event_id": after_event_id},
        )

    async def _generator():
        for event in facade.events.list_by_run(run_id, after_event_id=after_event_id):
            data = json.dumps(event.payload, ensure_ascii=False)
            yield f"id: {event.event_id}\n"
            yield f"event: {event.type}\n"
            yield f"data: {data}\n\n"
            if event.type in {"done", "error", "cancelled"}:
                break

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
