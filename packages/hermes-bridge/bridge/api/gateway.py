"""Legacy gateway/cloud compatibility endpoints."""

from __future__ import annotations

import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


def _json(status: int, body: dict) -> JSONResponse:
    return JSONResponse(body, status_code=status)


@router.get("/gateway/status")
async def gateway_status() -> JSONResponse:
    return _json(
        200,
        {
            "running": False,
            "pid": None,
            "platforms": [],
            "activePlatformCount": 0,
            "platformDetails": [],
        },
    )


@router.get("/gateway/supported-platforms")
async def gateway_supported_platforms() -> JSONResponse:
    return _json(
        200,
        {
            "platforms": [
                {
                    "id": "weixin",
                    "name": "个人微信",
                    "authType": "qr_login",
                    "envVar": "WEIXIN_ACCOUNT_ID",
                }
            ]
        },
    )


@router.get("/cloud/status")
async def cloud_status() -> JSONResponse:
    try:
        from cloud_tunnel import get_tunnel_status

        return _json(200, get_tunnel_status())
    except Exception as exc:
        traceback.print_exc()
        return _json(500, {"error": str(exc)})
