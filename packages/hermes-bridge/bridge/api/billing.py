"""计费 + API Keys 端点"""

from __future__ import annotations

import logging
import time
import traceback
import uuid

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _platform_ok(data):
    return JSONResponse({"success": True, "data": data})


def _platform_error(status: int, message: str):
    return JSONResponse({"success": False, "data": None, "error": {"message": message}}, status_code=status)


# ---------------------------------------------------------------------------
# 计费
# ---------------------------------------------------------------------------


@router.get("/api/billing/wallet")
async def billing_wallet():
    try:
        from bridge import legacy_server as _bs
        wallet = _bs._load_finance_wallet()
        items = _bs._load_finance_usage_records()
        currency = _bs._resolve_finance_currency(wallet, items)
        now_struct = time.gmtime()
        month_start_ts = time.mktime((now_struct.tm_year, now_struct.tm_mon, 1, 0, 0, 0, 0, 0, -1))
        return _platform_ok({
            "balance": _bs._safe_float(wallet.get("balance")),
            "currency": currency,
            "total_spent": _bs._sum_usage_amount(items),
            "total_recharge": _bs._safe_float(wallet.get("total_recharge")),
            "current_month_spent": _bs._sum_usage_amount(items, start_ts=month_start_ts),
            "updated_time": wallet.get("updated_time"),
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/billing/records")
async def billing_records(
    page: int = Query(default=1),
    page_size: int = Query(default=20),
    type: str | None = Query(default=None),
):
    try:
        from bridge import legacy_server as _bs
        items = _bs._load_finance_usage_records()
        if type:
            items = [item for item in items if str(item.get("record_type") or "") == type]
        total = len(items)
        start = max((page - 1) * page_size, 0)
        page_items = items[start:start + page_size]
        return _platform_ok({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": item["id"],
                    "product_name": item["product_name"],
                    "record_type": item.get("record_type") or "consumption",
                    "duration_seconds": item.get("duration_seconds") or 0,
                    "text_input_length": item.get("text_input_chars") or 0,
                    "text_output_length": item.get("text_output_chars") or 0,
                    "unit_price": 0,
                    "output_unit_price": 0,
                    "amount": item.get("amount") or 0,
                    "currency": item.get("currency") or "USD",
                    "remark": item.get("remark"),
                    "balance_snapshot": item.get("balance_snapshot") or 0,
                    "created_time": item.get("created_time"),
                }
                for item in page_items
            ],
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


@router.get("/api/users/app-keys")
async def app_keys_list(
    page: int = Query(default=1),
    page_size: int = Query(default=20),
):
    try:
        from bridge import legacy_server as _bs
        data = _bs._load_api_keys()
        items = data.get("app_keys", [])
        total = len(items)
        start = (page - 1) * page_size
        return _platform_ok({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items[start:start + page_size],
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/llm/keys")
async def llm_keys_list():
    try:
        from bridge import legacy_server as _bs
        data = _bs._load_api_keys()
        return _platform_ok(data.get("llm_keys", []))
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.post("/api/users/app-keys")
async def app_key_create(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        key_id = int(time.time() * 1000) % 1000000
        app_key = f"ak_{uuid.uuid4().hex[:16]}"
        app_secret = f"sk_{uuid.uuid4().hex}"
        entry = {
            "id": key_id,
            "name": body.get("name", ""),
            "app_key": app_key,
            "app_secret": app_secret,
            "role": "USER",
            "is_active": True,
            "expire_time": None,
            "create_time": now,
        }
        data = _bs._load_api_keys()
        data.setdefault("app_keys", []).append(entry)
        _bs._save_api_keys(data)
        return _platform_ok(entry)
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.delete("/api/users/app-keys/{key_id}")
async def app_key_delete(key_id: int):
    try:
        from bridge import legacy_server as _bs
        data = _bs._load_api_keys()
        data["app_keys"] = [k for k in data.get("app_keys", []) if k.get("id") != key_id]
        _bs._save_api_keys(data)
        return _platform_ok(None)
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.patch("/api/users/app-keys/{key_id}")
async def app_key_set_active(key_id: int, request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        data = _bs._load_api_keys()
        for k in data.get("app_keys", []):
            if k.get("id") == key_id:
                k["is_active"] = body.get("is_active", True)
                _bs._save_api_keys(data)
                return _platform_ok(k)
        return _platform_error(404, "Key not found")
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.put("/api/users/app-keys/{key_id}/name")
async def app_key_rename(key_id: int, request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        new_name = body.get("name") or body.get("key_name", "")
        data = _bs._load_api_keys()
        for k in data.get("app_keys", []):
            if k.get("id") == key_id:
                k["name"] = new_name
                k["key_name"] = new_name
                _bs._save_api_keys(data)
                return _platform_ok(k)
        return _platform_error(404, "Key not found")
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.post("/api/users/app-keys/default/token")
async def app_key_issue_token():
    try:
        from bridge import legacy_server as _bs
        data = _bs._load_api_keys()
        keys = data.get("app_keys", [])
        if not keys:
            key_id = 1
            app_key = f"ak_default_{uuid.uuid4().hex[:8]}"
            keys.append({
                "id": key_id,
                "app_key": app_key,
                "key_name": "default",
                "role": "ADMIN",
                "is_active": True,
                "expire_time": None,
                "create_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            data["app_keys"] = keys
            _bs._save_api_keys(data)
        first = keys[0]
        token = f"tok_{uuid.uuid4().hex}"
        return _platform_ok({
            "token": token,
            "expires_in": 86400,
            "app_key": first.get("app_key", ""),
            "app_key_id": first.get("id", 1),
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))
