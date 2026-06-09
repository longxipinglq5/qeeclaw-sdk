from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.errors import api_error

router = APIRouter()


@router.get("/api/experts")
async def list_experts(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "experts": request.app.state.runtime_facade.experts.list_public_experts()
        }
    )


@router.get("/api/experts/{expert_id}")
async def get_expert(expert_id: str, request: Request) -> JSONResponse:
    try:
        expert = request.app.state.runtime_facade.experts.get_public_expert(expert_id)
    except KeyError:
        return api_error(
            "EXPERT_NOT_FOUND",
            "Expert not found",
            404,
            {"expert_id": expert_id},
        )
    return JSONResponse({"expert": expert})
