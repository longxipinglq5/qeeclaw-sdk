from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from bridge.api.models import ChatStreamRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/stream")
async def stream(req: ChatStreamRequest, request: Request) -> StreamingResponse:
    runtime = request.app.state.runtime

    async def _generator():
        try:
            handle = await runtime.stream(
                session_id=req.session_id,
                scenario=req.scenario,
                user_text=req.user_text,
                context=req.context,
                conversation_history=req.conversation_history,
            )
        except ValueError as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            return
        except Exception:
            logger.exception("stream 初始化异常")
            yield f"event: error\ndata: {json.dumps({'error': '服务不可用'})}\n\n"
            return

        try:
            while True:
                event_type, payload = await handle.queue.get()
                if event_type == "delta":
                    data = json.dumps({"text": payload}, ensure_ascii=False)
                    yield f"event: delta\ndata: {data}\n\n"
                elif event_type == "done":
                    data = json.dumps(
                        {"final_response": payload, "completed": True},
                        ensure_ascii=False,
                    )
                    yield f"event: done\ndata: {data}\n\n"
                    break
                elif event_type == "error":
                    data = json.dumps({"error": payload}, ensure_ascii=False)
                    yield f"event: error\ndata: {data}\n\n"
                    break
        except Exception:
            logger.exception("stream generator 异常")
            yield f"event: error\ndata: {json.dumps({'error': '流中断'})}\n\n"
        finally:
            if not handle.task.done():
                handle.task.cancel()

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
