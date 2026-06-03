"""兼容路由：POST /invoke

适配 core-sdk HermesAdapter 的非流式调用契约：
- 请求: {prompt, model?, provider?, max_tokens?, temperature?, system_prompt?}
- 响应: {text, model, provider, usage: {prompt_tokens, completion_tokens, total_tokens}}

不参与 scenario 映射；如提供 system_prompt，直接作为 ephemeral_system_prompt 注入。
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.models import CompatInvokeRequest, CompatInvokeResponse, CompatUsage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/invoke")
async def invoke_compat(req: CompatInvokeRequest, request: Request) -> JSONResponse:
    runtime = request.app.state.runtime
    session_id = f"hermes-adapter:{uuid.uuid4().hex[:12]}"

    try:
        result = await runtime.invoke_raw(
            session_id=session_id,
            user_text=req.prompt,
            system_prompt=req.system_prompt,
        )
    except Exception as exc:
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

    return JSONResponse(
        status_code=200,
        content=CompatInvokeResponse(
            text=text,
            model=result.get("model", ""),
            provider=result.get("provider", ""),
            usage=usage,
        ).model_dump(),
    )
