from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bridge.profile_context import ProfileContext, save_profile_context

router = APIRouter()


class ProfileContextSyncRequest(BaseModel):
    agent_profile: str = Field(..., min_length=1, max_length=128)
    owner_context: str = Field(default="", max_length=80_000)
    business_context: str = Field(default="", max_length=160_000)
    source: str = Field(default="edge", max_length=64)


@router.post("/profile-context/sync")
async def sync_profile_context(req: ProfileContextSyncRequest, request: Request) -> JSONResponse:
    updated_at = datetime.now(timezone.utc).isoformat()
    payload = save_profile_context(
        ProfileContext(
            agent_profile=req.agent_profile,
            owner_context=req.owner_context,
            business_context=req.business_context,
            source=req.source,
            updated_at=updated_at,
        )
    )

    runtime = getattr(request.app.state, "runtime", None)
    evicted = 0
    if runtime is not None and hasattr(runtime, "evict_agent_profile"):
        evicted = runtime.evict_agent_profile(req.agent_profile)

    return JSONResponse({"success": True, "context": payload, "evicted_agents": evicted})
