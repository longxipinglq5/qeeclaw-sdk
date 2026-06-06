from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

router = APIRouter()


def _facade(request: Request):
    return request.app.state.runtime_facade


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> JSONResponse:
    run = _facade(request).get_run(run_id)
    if run is None:
        return JSONResponse(status_code=404, content={"error": "run_not_found"})
    return JSONResponse({"run": run.model_dump(mode="json")})


@router.get("/api/runs/{run_id}/events")
async def get_run_events(run_id: str, request: Request) -> JSONResponse:
    run = _facade(request).get_run(run_id)
    if run is None:
        return JSONResponse(status_code=404, content={"error": "run_not_found"})
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
        return JSONResponse(status_code=404, content={"error": "run_not_found"})

    after_event_id = request.headers.get("Last-Event-ID")

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
