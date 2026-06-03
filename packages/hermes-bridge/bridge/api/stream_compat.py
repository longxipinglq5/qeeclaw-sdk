"""兼容路由：POST /invoke/stream

适配 core-sdk HermesAdapter 的流式调用契约：
- 请求: {prompt, session_id?, agent_profile?, model?, provider?, max_tokens?, temperature?, system_prompt?}
- 响应: text/event-stream，每行 `data: <json>\n\n`，最后 `data: [DONE]\n\n`

JSON chunk 格式遵循 RuntimeStreamChunk：
  {type: "text" | "tool_call" | "done" | "error", content?, error?}

HermesAdapter 解析逻辑（见 hermes-adapter.ts invokeStream）：
  - 仅识别 `data: ` 前缀
  - `data: [DONE]` 终止
  - 其他每行 JSON.parse 后 yield
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from bridge.api.models import CompatStreamRequest
from bridge.api.invoke_compat import _resolve_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter()


def _encode_chunk(chunk: dict) -> str:
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


@router.post("/invoke/stream")
async def stream_compat(req: CompatStreamRequest, request: Request) -> StreamingResponse:
    runtime = request.app.state.runtime
    session_id = req.session_id or "hermes-adapter:default"
    agent_profile = req.agent_profile or "default"

    async def _generator():
        try:
            handle = await runtime.stream_raw(
                session_id=session_id,
                user_text=req.prompt,
                agent_profile=agent_profile,
                system_prompt=_resolve_system_prompt(req),
            )
        except Exception:
            logger.exception("/invoke/stream 兼容路由初始化异常")
            yield _encode_chunk({"type": "error", "error": "服务不可用"})
            return

        try:
            while True:
                event_type, payload = await handle.queue.get()
                if event_type == "delta":
                    yield _encode_chunk({"type": "text", "content": payload})
                elif event_type == "done":
                    yield _encode_chunk({"type": "done", "content": payload})
                    yield "data: [DONE]\n\n"
                    break
                elif event_type == "error":
                    yield _encode_chunk({"type": "error", "error": payload})
                    yield "data: [DONE]\n\n"
                    break
        except Exception:
            logger.exception("/invoke/stream 兼容路由生成器异常")
            yield _encode_chunk({"type": "error", "error": "流中断"})
            yield "data: [DONE]\n\n"
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
