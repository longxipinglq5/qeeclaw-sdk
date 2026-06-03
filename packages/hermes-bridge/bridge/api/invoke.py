from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.api.models import ChatInvokeRequest, ChatInvokeResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/invoke")
async def invoke(req: ChatInvokeRequest, request: Request) -> JSONResponse:
    runtime = request.app.state.runtime
    try:
        result = await runtime.invoke(
            session_id=req.session_id,
            scenario=req.scenario,
            user_text=req.user_text,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=ChatInvokeResponse(
                session_id=req.session_id,
                completed=False,
                error=str(exc),
            ).model_dump(),
        )
    except Exception as exc:
        ref = uuid.uuid4().hex[:8]
        logger.exception("invoke 异常 ref=%s: %s", ref, exc)
        return JSONResponse(
            status_code=500,
            content=ChatInvokeResponse(
                session_id=req.session_id,
                completed=False,
                error=f"内部服务错误 (ref: {ref})",
            ).model_dump(),
        )

    return JSONResponse(
        status_code=200,
        content=ChatInvokeResponse(
            final_response=result.get("final_response"),
            completed=not result.get("failed", False),
            model=result.get("model", ""),
            provider=result.get("provider", ""),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
            session_id=req.session_id,
            error=result.get("error"),
        ).model_dump(),
    )
