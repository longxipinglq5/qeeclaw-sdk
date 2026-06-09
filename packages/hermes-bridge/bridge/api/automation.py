from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.errors import api_error

router = APIRouter()


def _facade(request: Request):
    return request.app.state.runtime_facade


@router.get("/api/automation/{goal_id}/status")
async def get_automation_goal_status(goal_id: str, request: Request) -> JSONResponse:
    status = _facade(request).get_automation_status_for_goal(goal_id)
    if status is None:
        return api_error("AUTOMATION_GOAL_NOT_FOUND", "Automation goal not found", 404, {"goal_id": goal_id})
    return JSONResponse(status.model_dump(mode="json"))


@router.get("/api/automation/{goal_id}/loops")
async def list_automation_goal_loops(goal_id: str, request: Request) -> JSONResponse:
    status = _facade(request).get_automation_status_for_goal(goal_id)
    if status is None:
        return api_error("AUTOMATION_GOAL_NOT_FOUND", "Automation goal not found", 404, {"goal_id": goal_id})
    return JSONResponse(
        {
            "goal_id": goal_id,
            "loops": [
                {"loop_id": cycle.loop_id, "cycle_id": cycle.cycle_id}
                for cycle in status.cycles
            ],
        }
    )


@router.get("/api/automation/{goal_id}/cycles")
async def list_automation_goal_cycles(goal_id: str, request: Request) -> JSONResponse:
    status = _facade(request).get_automation_status_for_goal(goal_id)
    if status is None:
        return api_error("AUTOMATION_GOAL_NOT_FOUND", "Automation goal not found", 404, {"goal_id": goal_id})
    return JSONResponse(
        {
            "goal_id": goal_id,
            "cycles": [
                cycle.model_dump(mode="json")
                for cycle in status.cycles
            ],
        }
    )


@router.post("/api/automation/{goal_id}/resume")
async def resume_automation_goal(goal_id: str, request: Request) -> JSONResponse:
    result = _facade(request).request_automation_resume(goal_id)
    if result is None:
        return api_error("AUTOMATION_GOAL_NOT_FOUND", "Automation goal not found", 404, {"goal_id": goal_id})
    return JSONResponse(result)
