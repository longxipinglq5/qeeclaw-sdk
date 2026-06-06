"""会话/Agent 管理端点"""

from __future__ import annotations

import logging
import json
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.errors import api_error

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.post("/sessions")
async def session_create(request: Request):
    try:
        from session_manager import get_session_manager
        try:
            body = await request.json()
        except Exception:
            body = {}
        sm = get_session_manager()
        session = sm.create_session(
            user_id=body.get("user_id", "anonymous"),
            agent_profile=body.get("agent_profile", "default"),
        )
        return JSONResponse({
            "session_id": session.session_id,
            "user_id": session.user_id,
            "agent_profile": session.agent_profile,
        })
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/api/sessions")
async def facade_sessions_list(request: Request):
    sessions = [
        session.model_dump(mode="json")
        for session in request.app.state.runtime_facade.sessions.list()
    ]
    return JSONResponse({"sessions": sessions})


@router.get("/api/sessions/{session_id}")
async def facade_session_get(session_id: str, request: Request):
    session = request.app.state.runtime_facade.sessions.get(session_id)
    if session is None:
        return JSONResponse({"error": "session_not_found"}, status_code=404)
    return JSONResponse({"session": session.model_dump(mode="json")})


@router.get("/api/sessions/{session_id}/context")
async def facade_session_context_get(session_id: str, request: Request):
    facade = request.app.state.runtime_facade
    session = facade.sessions.get(session_id)
    if session is None:
        return api_error(
            "SESSION_NOT_FOUND",
            "Session not found",
            404,
            {"session_id": session_id},
        )

    artifact_summaries = list(session.metadata.get("artifact_summaries") or [])
    messages = []
    if artifact_summaries:
        messages.append(
            {
                "role": "system",
                "content": json.dumps(
                    artifact_summaries,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "metadata": {"section": "artifact_summaries"},
            }
        )
    messages.extend(facade.sessions.get_recent_messages(session_id, token_budget=None))
    approx_token_count = sum(
        facade.sessions.approx_token_count(message["content"])
        for message in messages
    )
    return JSONResponse(
        {
            "session_id": session_id,
            "message_count": len(messages),
            "approx_token_count": approx_token_count,
            "prompt_prefix_hash": facade._prompt_prefix_hash_for_session(session_id),
            "messages": messages,
        }
    )


@router.post("/sessions/{session_id}/clear")
async def session_clear(session_id: str):
    try:
        from session_manager import get_session_manager
        sm = get_session_manager()
        session = sm.get_session(session_id)
        if not session:
            return JSONResponse({"error": f"session {session_id} not found"}, status_code=404)
        session.clear_messages()
        return JSONResponse({"status": "cleared", "session_id": session_id})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/sessions/{session_id}/delete")
async def session_delete(session_id: str):
    try:
        from session_manager import get_session_manager
        sm = get_session_manager()
        ok = sm.delete_session(session_id)
        if not ok:
            return JSONResponse({"error": f"session {session_id} not found"}, status_code=404)
        return JSONResponse({"status": "deleted", "session_id": session_id})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


@router.get("/agents")
async def agents_list():
    try:
        from session_manager import get_session_manager
        sm = get_session_manager()
        profiles = sm.list_profiles()
        return JSONResponse({"agents": profiles})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/agents/{agent_name}")
async def agent_get(agent_name: str):
    try:
        from session_manager import get_session_manager
        sm = get_session_manager()
        profile = sm.get_profile(agent_name)
        if not profile:
            return JSONResponse({"error": f"agent '{agent_name}' not found"}, status_code=404)
        return JSONResponse(profile.to_dict())
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/agents")
async def agent_create(request: Request):
    try:
        from session_manager import get_session_manager
        body = await request.json()
        name = body.get("name")
        if not name:
            return JSONResponse({"error": "name is required"}, status_code=400)
        sm = get_session_manager()
        profile = sm.create_profile(body)
        return JSONResponse({"status": "created", "agent": profile.to_dict()})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/agents/{agent_name}/delete")
async def agent_delete(agent_name: str):
    try:
        from session_manager import get_session_manager
        sm = get_session_manager()
        ok = sm.delete_profile(agent_name)
        if not ok:
            return JSONResponse({"error": f"agent '{agent_name}' not found or is builtin"}, status_code=404)
        return JSONResponse({"status": "deleted", "agent": agent_name})
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Agent Config (模板)
# ---------------------------------------------------------------------------


@router.get("/agent_config/default")
async def agent_config_default():
    try:
        from session_manager import get_session_manager, _BUILTIN_PROFILES
        sm = get_session_manager()
        templates = []
        idx = 0
        import bridge_server as _bs
        for name, profile in _BUILTIN_PROFILES.items():
            idx += 1
            templates.append({
                "id": idx,
                "code": name,
                "name": profile.display_name,
                "description": profile.system_prompt[:200] if profile.system_prompt else None,
                "avatar": None,
                "allowed_tools": ["web_search", "memory"],
            })
        return JSONResponse(templates)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/agent_config/{code}")
async def agent_config_get(code: str):
    try:
        from session_manager import get_session_manager
        import bridge_server as _bs
        sm = get_session_manager()
        profile = sm.get_profile(code)
        if not profile:
            return JSONResponse({"error": f"template '{code}' not found"}, status_code=404)
        template = {
            "id": _bs._get_agent_id(profile.name),
            "code": profile.name,
            "name": profile.display_name,
            "description": profile.system_prompt[:200] if profile.system_prompt else None,
            "avatar": (profile.metadata or {}).get("avatar"),
            "allowed_tools": ["web_search", "memory"],
        }
        return JSONResponse(template)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)
