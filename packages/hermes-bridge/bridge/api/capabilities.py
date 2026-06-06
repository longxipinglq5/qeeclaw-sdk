from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.errors import api_error

router = APIRouter()


@router.get("/api/capabilities")
async def list_capabilities(request: Request) -> JSONResponse:
    capabilities = [
        capability.model_dump(mode="json")
        for capability in request.app.state.runtime_facade.capabilities.list_capabilities()
    ]
    return JSONResponse({"capabilities": capabilities})


@router.get("/api/capabilities/{capability_id}")
async def get_capability(capability_id: str, request: Request) -> JSONResponse:
    try:
        capability = request.app.state.runtime_facade.capabilities.get_capability(
            capability_id
        )
    except KeyError:
        return api_error(
            "CAPABILITY_NOT_FOUND",
            "Capability not found",
            404,
            {"capability_id": capability_id},
        )
    return JSONResponse({"capability": capability.model_dump(mode="json")})
