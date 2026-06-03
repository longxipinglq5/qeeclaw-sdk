"""记忆端点：stats / search / store / delete"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class MemorySearchRequest(BaseModel):
    query: str = Field(default="", description="搜索查询文本")
    limit: int = Field(default=5, ge=1, description="最大返回数")
    threshold: float = Field(default=0.0, ge=0.0, description="最低匹配阈值")
    agent_id: str | None = None
    agent_profile: str | None = None
    team_id: str | int | None = None
    runtime_type: str | None = None
    device_id: str | None = None
    teamId: str | int | None = None
    runtimeType: str | None = None
    agentId: str | None = None


class MemoryStoreRequest(BaseModel):
    content: str = Field(default="", description="记忆内容")
    category: str = Field(default="other", description="记忆分类")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要程度")
    agent_id: str | None = None
    agent_profile: str | None = None
    team_id: str | int | None = None
    runtime_type: str = Field(default="openclaw", description="运行时类型")
    device_id: str | None = None
    source_session: str | None = None
    skip_duplicate_check: bool = False
    teamId: str | int | None = None
    runtimeType: str | None = None
    agentId: str | None = None


def _build_scope_from_query(
    agent_id: str | None = None,
    agent_profile: str | None = None,
    team_id: str | None = None,
    runtime_type: str | None = None,
    device_id: str | None = None,
) -> dict:
    scope: dict = {}
    effective_agent = agent_id or agent_profile
    if effective_agent:
        scope["agent_id"] = effective_agent
    for key, val in [("team_id", team_id), ("runtime_type", runtime_type), ("device_id", device_id)]:
        if val is not None:
            scope[key] = val
    return scope


@router.get("/memory/stats")
async def memory_stats(
    agent_id: str | None = Query(default=None),
    agent_profile: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    runtime_type: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
):
    try:
        from memory_store import get_memory_stats

        scope = _build_scope_from_query(
            agent_id=agent_id,
            agent_profile=agent_profile,
            team_id=team_id,
            runtime_type=runtime_type,
            device_id=device_id,
        )
        stats = get_memory_stats(scope=scope)
        return JSONResponse({"success": True, **stats})
    except Exception as exc:
        logger.exception("memory stats 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/memory/search")
async def memory_search(req: MemorySearchRequest):
    try:
        from memory_store import search_memory

        scope = _build_scope_from_query(
            agent_id=req.agent_id,
            agent_profile=req.agent_profile,
            team_id=req.team_id,
            runtime_type=req.runtime_type,
            device_id=req.device_id,
        )
        results = search_memory(
            query=req.query,
            limit=req.limit,
            threshold=req.threshold,
            scope=scope,
        )
        return JSONResponse({"success": True, "results": results})
    except Exception as exc:
        logger.exception("memory search 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/memory/store")
async def memory_store(req: MemoryStoreRequest):
    try:
        from memory_store import store_memory

        agent_id = req.agent_profile or req.agent_id
        entry = store_memory(
            content=req.content,
            category=req.category,
            importance=req.importance,
            team_id=req.team_id,
            runtime_type=req.runtime_type,
            device_id=req.device_id,
            agent_id=agent_id,
            source_session=req.source_session,
            skip_duplicate_check=req.skip_duplicate_check,
        )
        return JSONResponse({"success": True, "entry": entry})
    except Exception as exc:
        logger.exception("memory store 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.delete("/memory/{entry_id}")
async def memory_delete(
    entry_id: str,
    team_id: str | None = Query(default=None),
    runtime_type: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
):
    try:
        from memory_store import delete_memory

        scope: dict = {}
        for key, val in [
            ("team_id", team_id),
            ("runtime_type", runtime_type),
            ("device_id", device_id),
            ("agent_id", agent_id),
        ]:
            if val is not None:
                scope[key] = val

        deleted = delete_memory(entry_id, scope=scope)
        return JSONResponse({"success": deleted, "deleted": deleted})
    except Exception as exc:
        logger.exception("memory delete 异常")
        return JSONResponse({"error": str(exc)}, status_code=500)
