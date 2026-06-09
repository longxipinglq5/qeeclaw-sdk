"""个人微信网关 HTTP 包装。"""

from __future__ import annotations

import traceback
import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


def _gateway():
    from bridge import legacy_server as _bs
    _bs._ensure_hermes_on_path()
    import wechat_gateway
    return wechat_gateway


def _json(status: int, body: dict) -> JSONResponse:
    return JSONResponse(body, status_code=status)


@router.get("/wechat/credentials")
async def wechat_credentials() -> JSONResponse:
    try:
        return _json(200, _gateway().get_wechat_credentials())
    except Exception as exc:
        traceback.print_exc()
        return _json(500, {"error": str(exc)})


@router.get("/wechat/status")
async def wechat_status() -> JSONResponse:
    try:
        gw = _gateway()
        return _json(200, {
            "qr": gw.get_qr_login_status(),
            "adapter": gw.get_adapter_status(),
            "recent_chat_ids": gw.list_recent_chat_ids(),
        })
    except Exception as exc:
        traceback.print_exc()
        return _json(500, {"error": str(exc)})


@router.post("/wechat/adapter/start")
async def wechat_adapter_start() -> JSONResponse:
    try:
        result = _gateway().start_adapter()
        return _json(200 if "error" not in result else 400, result)
    except Exception as exc:
        traceback.print_exc()
        return _json(500, {"error": str(exc)})


@router.post("/wechat/adapter/stop")
async def wechat_adapter_stop() -> JSONResponse:
    try:
        result = _gateway().stop_adapter()
        return _json(200 if "error" not in result else 400, result)
    except Exception as exc:
        traceback.print_exc()
        return _json(500, {"error": str(exc)})


@router.post("/wechat/send")
async def wechat_send(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        chat_id = str(body.get("chat_id") or body.get("chatId") or "")
        message = str(body.get("message") or "")
        media_files = body.get("media_files") or body.get("mediaFiles")
        if not chat_id:
            return _json(400, {"error": "chat_id is required"})
        if not message and not media_files:
            return _json(400, {"error": "message or media_files is required"})
        result = await asyncio.to_thread(
            _gateway().send_message,
            chat_id=chat_id,
            message=message,
            media_files=media_files,
        )
        return _json(200 if "error" not in result else 400, result)
    except Exception as exc:
        traceback.print_exc()
        return _json(500, {"error": str(exc)})
