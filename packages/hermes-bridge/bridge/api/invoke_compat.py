"""兼容路由：POST /invoke

适配 core-sdk HermesAdapter 的非流式调用契约：
- 请求: {prompt, session_id?, agent_profile?, model?, provider?, max_tokens?, temperature?, system_prompt?}
- 响应: {text, model, provider, usage: {prompt_tokens, completion_tokens, total_tokens}}

不参与 scenario 映射；如提供 system_prompt，直接作为 ephemeral_system_prompt 注入。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.models import CompatInvokeRequest, CompatInvokeResponse, CompatUsage
from bridge.invocation import resolve_skill_dispatch
from bridge.scenarios import get_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter()

_PROFILE_SCENARIOS = {
    "edge_general": "general",
    "edge_supervisor": "supervisor",
    "edge_spark": "spark",
    "edge_xiaoke": "xiaoke",
    "edge_consultant": "consultant",
}


def _resolve_system_prompt(req: CompatInvokeRequest) -> str | None:
    if req.system_prompt:
        return req.system_prompt
    if not req.agent_profile:
        return None
    scenario = _PROFILE_SCENARIOS.get(req.agent_profile)
    return get_system_prompt(scenario, agent_profile=req.agent_profile) if scenario else None


@router.post("/invoke")
async def invoke_compat(req: CompatInvokeRequest, request: Request) -> JSONResponse:
    runtime = request.app.state.runtime_facade
    session_id = req.session_id or "hermes-adapter:default"
    agent_profile = req.agent_profile or "default"

    try:
        dispatch = resolve_skill_dispatch(
            req.prompt,
            skill_command=req.skill_command,
            task_id=req.task_id,
            runtime_note=req.runtime_note,
        )
        if dispatch.error:
            return JSONResponse(status_code=400, content={"error": dispatch.error})

        result = await runtime.invoke_raw(
            session_id=session_id,
            user_text=dispatch.user_text,
            agent_profile=agent_profile,
            system_prompt=_resolve_system_prompt(req),
        )
    except Exception as exc:
        import uuid

        ref = uuid.uuid4().hex[:8]
        logger.exception("/invoke 兼容路由异常 ref=%s: %s", ref, exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": f"内部服务错误 (ref: {ref})",
                "detail": str(exc) if logger.isEnabledFor(logging.DEBUG) else None,
            },
        )

    text = result.get("final_response") or ""
    if not text and result.get("error"):
        return JSONResponse(
            status_code=500,
            content={"error": result["error"]},
        )

    usage = CompatUsage(
        prompt_tokens=result.get("input_tokens", 0),
        completion_tokens=result.get("output_tokens", 0),
        total_tokens=result.get("total_tokens", 0),
    )

    content = CompatInvokeResponse(
        text=text,
        model=result.get("model", ""),
        provider=result.get("provider", ""),
        usage=usage,
    ).model_dump()
    content["session_id"] = session_id
    content["agent_profile"] = agent_profile
    if dispatch.skill_command:
        content["_skill_command"] = dispatch.skill_command
        content["_skill_command_resolved"] = dispatch.skill_command_resolved
    if result.get("run_id"):
        content["run_id"] = result["run_id"]

    return JSONResponse(status_code=200, content=content)
