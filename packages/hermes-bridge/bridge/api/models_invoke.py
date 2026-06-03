"""模型调用端点：/api/platform/models/invoke, invoke_local, /invoke_local"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import traceback
import urllib.request
import urllib.parse
import urllib.error
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# 从 bridge_server.py 直接 import 辅助函数（顶层函数可直接导入）
# ---------------------------------------------------------------------------

def _import_helpers():
    """延迟 import bridge_server 的顶层辅助函数，避免循环依赖。"""
    import bridge_server as _bs
    return (
        _bs._has_skill_invocation_metadata,
        _bs._truthy_body_flag,
        _bs._build_memory_context,
        _bs._append_context,
        _bs._resolve_skill_invocation_prompt,
        _bs._normalize_runtime_scope,
        _bs._runtime_scope_defaults,
        _bs._record_finance_usage,
        _bs._llm_debug_log,
        _bs.get_agent_pool,
        _bs._body_value,
    )


# ---------------------------------------------------------------------------
# Nexus 后端代理
# ---------------------------------------------------------------------------


def _proxy_to_nexus_sync(method: str, backend_path: str, body: dict | None) -> dict:
    """同步代理请求到 Nexus 后端。"""
    nexus_url = os.environ.get("NEXUS_URL", "").strip().rstrip("/")
    nexus_api_key = os.environ.get("NEXUS_API_KEY", "").strip()

    if not nexus_url:
        return {"error": {"message": "NEXUS_URL not configured", "type": "server_error", "code": "nexus_url_not_configured"}}

    url = f"{nexus_url}{backend_path}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {nexus_api_key}",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
        return {"error": {"message": f"Nexus returned {exc.code}: {detail}", "type": "server_error"}}
    except Exception as exc:
        return {"error": {"message": f"Nexus proxy failed: {exc}", "type": "server_error"}}


# ---------------------------------------------------------------------------
# 核心本地 invoke 逻辑
# ---------------------------------------------------------------------------


def _do_local_invoke_sync(body: dict, runtime_scope: str | None = None) -> dict:
    """同步执行本地模型调用，从旧 bridge_server._handle_invoke 提取。"""
    (
        _has_skill_meta,
        _truthy_flag,
        _build_mem_ctx,
        _append_ctx,
        _resolve_skill,
        _norm_scope,
        _scope_defaults,
        _record_finance,
        _debug_log,
        _get_pool,
        _body_val,
    ) = _import_helpers()

    from session_manager import get_session_manager

    started_at = time.perf_counter()
    prompt = body.get("prompt", "")
    model = body.get("model") or body.get("model_id") or body.get("modelId")
    provider = body.get("provider")
    effective_scope = _norm_scope(body.get("runtime_scope") or body.get("runtimeScope") or runtime_scope)
    defaults = _scope_defaults(effective_scope)
    if effective_scope and not model and defaults.get("model"):
        model = defaults["model"]
    if effective_scope and not provider and defaults.get("provider"):
        provider = defaults["provider"]
    max_tokens = body.get("max_tokens") or body.get("maxTokens")
    temperature = body.get("temperature")
    system_prompt = body.get("system_prompt") or body.get("systemPrompt")
    use_agent = _truthy_flag(body, "use_agent", "useAgent", default=(effective_scope != "local"))
    use_knowledge = _truthy_flag(body, "use_knowledge", "useKnowledge", default=(effective_scope != "local"))
    kb_scope = body.get("kb_scope")
    session_id = body.get("session_id") or body.get("sessionId")
    user_id = body.get("user_id") or body.get("userId") or "anonymous"
    agent_profile = body.get("agent_profile") or body.get("agentProfile") or "default"
    max_history_turns = body.get("max_history_turns") or body.get("maxHistoryTurns")
    if max_history_turns is None:
        max_history_turns = 0 if effective_scope == "local" else 20

    if not prompt:
        return {"error": "prompt is required"}

    # session 管理
    sm = get_session_manager()
    session = sm.get_or_create_session(session_id=session_id, user_id=user_id, agent_profile=agent_profile)
    actual_session_id = session.session_id

    # agent profile 默认参数
    profile = sm.get_profile(session.agent_profile)
    if profile:
        if not system_prompt and profile.system_prompt:
            system_prompt = profile.system_prompt
        if temperature is None and profile.temperature is not None:
            temperature = profile.temperature

    # skill 解析
    pool = _get_pool()
    profile_home = profile.hermes_home if (profile and profile.hermes_home) else None
    if not profile_home and hasattr(pool, "_ensure_profile_home"):
        profile_home = pool._ensure_profile_home(session.agent_profile)
    prompt, skill_meta, skill_error = _resolve_skill(prompt, body, hermes_home=profile_home)
    if skill_error:
        return {"error": skill_error}

    # RAG: 知识库检索
    rag_context = ""
    if use_knowledge:
        try:
            from knowledge_store import build_rag_context, is_kb_available
            if is_kb_available():
                rag_context = build_rag_context(prompt, scope=kb_scope)
        except ImportError:
            pass
        except Exception as e:
            logger.warning("KB retrieval warning: %s", e)

    # 记忆上下文
    memory_context = ""
    if _truthy_flag(body, "use_memory", "useMemory", default=(effective_scope != "local")):
        memory_context = _build_mem_ctx(prompt, body, agent_profile=session.agent_profile)

    effective_system_prompt = _append_ctx(system_prompt, memory_context, rag_context)

    _debug_log(
        "invoke.request", "Bridge non-stream invoke", {
            "session_id": actual_session_id,
            "runtime_scope": effective_scope,
            "agent_profile": session.agent_profile,
            "provider": provider,
            "model": model,
            "use_agent": use_agent,
            "use_knowledge": use_knowledge,
        },
    )

    # 调用
    if use_agent:
        result = pool.invoke(
            prompt=prompt,
            profile=profile,
            session=session,
            system_prompt=effective_system_prompt or None,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
            max_history_turns=max_history_turns,
            runtime_scope=effective_scope,
        )
    else:
        result = pool._invoke_fallback(
            prompt=prompt,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=effective_system_prompt or None,
            history=session.get_messages(max_turns=max_history_turns) if max_history_turns else None,
            runtime_scope=effective_scope,
        )

    # 记录 session turn
    assistant_text = result.get("text", "")
    if assistant_text:
        sm.append_turn(actual_session_id, prompt, assistant_text)

    result["session_id"] = actual_session_id
    result["agent_profile"] = session.agent_profile
    result["turn_count"] = session.turn_count
    if rag_context:
        result["_rag_used"] = True
    if memory_context:
        result["_memory_used"] = True
    if skill_meta:
        result["_skill_command"] = skill_meta["skill_command"]
        result["_skill_command_resolved"] = skill_meta["skill_command_resolved"]

    _record_finance(
        prompt=prompt,
        text=assistant_text,
        model=result.get("model"),
        provider=result.get("provider"),
        usage=result.get("usage"),
        duration_seconds=time.perf_counter() - started_at,
    )
    _debug_log("invoke.response", "Bridge non-stream invoke response", {
        "session_id": actual_session_id,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
    })

    return result


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.post("/api/platform/models/invoke")
async def platform_models_invoke(request: Request):
    """POST /api/platform/models/invoke — 主模型调用入口。

    有 skill invocation metadata 时走本地 invoke，否则代理到 Nexus 后端。
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    try:
        (
            _has_skill_meta,
            *_,
        ) = _import_helpers()

        if _has_skill_meta(body):
            result = await asyncio.to_thread(_do_local_invoke_sync, body)
            if "error" in result and isinstance(result["error"], str):
                return JSONResponse({"error": result["error"]}, status_code=400)
            if "error" in result and isinstance(result["error"], dict):
                return JSONResponse(result, status_code=500)
            return JSONResponse(result)

        # 无 skill metadata → proxy 到 Nexus
        proxy_result = await asyncio.to_thread(_proxy_to_nexus_sync, "POST", "/api/platform/models/invoke", body)
        if "error" in proxy_result:
            code = proxy_result["error"].get("code", "")
            status = 503 if code == "nexus_url_not_configured" else 500
            return JSONResponse(status, proxy_result)
        return JSONResponse(proxy_result)

    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({
            "error": {"message": str(exc), "type": "server_error", "code": "platform_model_invoke_error"},
        }, status_code=500)


@router.post("/api/platform/models/invoke_local")
async def platform_models_invoke_local(request: Request):
    """POST /api/platform/models/invoke_local — 本地模型调用。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    try:
        result = await asyncio.to_thread(_do_local_invoke_sync, body, runtime_scope="local")
        if "error" in result and isinstance(result["error"], str):
            return JSONResponse({"error": result["error"]}, status_code=400)
        return JSONResponse(result)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": f"Internal bridge error: {exc}"}, status_code=500)


@router.post("/invoke_local")
async def invoke_local(request: Request):
    """POST /invoke_local — 本地模型备用路径。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    try:
        result = await asyncio.to_thread(_do_local_invoke_sync, body, runtime_scope="local")
        if "error" in result and isinstance(result["error"], str):
            return JSONResponse({"error": result["error"]}, status_code=400)
        return JSONResponse(result)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": f"Internal bridge error: {exc}"}, status_code=500)
