from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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
