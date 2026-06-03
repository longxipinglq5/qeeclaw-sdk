"""模型管理 + 图片生成端点"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _platform_ok(data):
    return JSONResponse({"success": True, "data": data})


def _platform_error(status: int, message: str):
    return JSONResponse({"success": False, "data": None, "error": {"message": message}}, status_code=status)


# ---------------------------------------------------------------------------
# 模型管理
# ---------------------------------------------------------------------------


@router.get("/api/platform/models")
async def models_list():
    try:
        import bridge_server as _bs
        models = _bs._discover_models()
        return _platform_ok(models)
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/platform/models/providers")
async def models_providers():
    try:
        import bridge_server as _bs
        models = _bs._discover_models()
        return _platform_ok(_bs._summarize_providers(models))
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/platform/models/runtimes")
async def models_runtimes():
    runtime = {
        "runtime_type": "hermes",
        "runtime_label": "Hermes",
        "runtime_status": "active",
        "runtime_stage": "production",
        "is_default": True,
        "adapter_registered": True,
        "bridge_registered": True,
        "online_team_count": 1,
        "supports_im_relay": True,
        "supports_device_bridge": True,
        "supports_managed_download": False,
        "notes": "Local Hermes Bridge runtime",
    }
    return _platform_ok([runtime])


@router.get("/api/platform/models/resolve")
async def models_resolve(model_name: str = Query(default="")):
    try:
        import bridge_server as _bs
        if not model_name:
            return _platform_error(400, "model_name is required")
        models = _bs._discover_models()
        selected = None
        for m in models:
            if m["model_name"] == model_name:
                selected = m
                break
        if not selected:
            selected = models[0] if models else None
        if not selected:
            return _platform_error(404, f"no models available to resolve '{model_name}'")
        return _platform_ok({
            "requested_model": model_name,
            "resolved_model": selected["model_name"],
            "provider_name": selected["provider_name"],
            "provider_model_id": selected["provider_model_id"],
            "candidate_count": len(models),
            "selected": selected,
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/platform/models/route")
async def models_route_get():
    try:
        import bridge_server as _bs
        models = _bs._discover_models()
        preferred = _bs._get_preferred_model()
        preferred_selected = None
        for m in models:
            if m["model_name"] == preferred:
                preferred_selected = m
                break
        selected = preferred_selected or (models[0] if models else None)
        local_selected = _bs._select_model_route(models, "local")
        return _platform_ok({
            "preferred_model": preferred,
            "preferred_model_available": preferred_selected is not None,
            "resolved_model": selected["model_name"] if selected else None,
            "resolved_provider_name": selected["provider_name"] if selected else None,
            "resolved_provider_model_id": selected["provider_model_id"] if selected else None,
            "candidate_count": len(models),
            "configured_provider_count": len(_bs._summarize_providers(models)),
            "available_model_count": len(models),
            "resolution_reason": "preferred_model_match" if preferred_selected else ("fallback" if selected else "no_models"),
            "selected": selected,
            "local_route": {
                "runtime_scope": "local",
                "invoke_path": "/api/platform/models/invoke_local",
                "selected": local_selected,
                "resolved_model": local_selected["model_name"] if local_selected else None,
                "resolved_provider_name": local_selected["provider_name"] if local_selected else None,
                "resolved_provider_model_id": local_selected["provider_model_id"] if local_selected else None,
                "available": local_selected is not None,
            },
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.put("/api/platform/models/route")
async def models_route_set(request: Request):
    try:
        import bridge_server as _bs
        body = await request.json()
        preferred_model = body.get("preferred_model", "")
        if not preferred_model:
            return _platform_error(400, "preferred_model is required")
        profile = _bs._load_user_profile()
        profile.setdefault("preference", {})["preferred_model"] = preferred_model
        _bs._save_user_profile(profile)
        models = _bs._discover_models()
        preferred_selected = None
        for m in models:
            if m["model_name"] == preferred_model:
                preferred_selected = m
                break
        selected = preferred_selected or (models[0] if models else None)
        return _platform_ok({
            "preferred_model": preferred_model,
            "preferred_model_available": preferred_selected is not None,
            "resolved_model": selected["model_name"] if selected else None,
            "resolved_provider_name": selected["provider_name"] if selected else None,
            "resolved_provider_model_id": selected["provider_model_id"] if selected else None,
            "candidate_count": len(models),
            "configured_provider_count": len(_bs._summarize_providers(models)),
            "available_model_count": len(models),
            "resolution_reason": "preferred_model_match" if preferred_selected else ("fallback" if selected else "no_models"),
            "selected": selected,
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/platform/models/quota")
async def models_quota():
    try:
        import bridge_server as _bs
        wallet = _bs._load_finance_wallet()
        items = _bs._load_finance_usage_records()
        currency = _bs._resolve_finance_currency(wallet, items)
        now_struct = time.gmtime()
        day_start_ts = time.mktime((now_struct.tm_year, now_struct.tm_mon, now_struct.tm_mday, 0, 0, 0, 0, 0, -1))
        month_start_ts = time.mktime((now_struct.tm_year, now_struct.tm_mon, 1, 0, 0, 0, 0, 0, -1))
        daily_spent = _bs._sum_usage_amount(items, start_ts=day_start_ts)
        monthly_spent = _bs._sum_usage_amount(items, start_ts=month_start_ts)
        daily_limit = wallet.get("daily_limit")
        monthly_limit = wallet.get("monthly_limit")
        return _platform_ok({
            "wallet_balance": _bs._safe_float(wallet.get("balance")),
            "currency": currency,
            "daily_limit": daily_limit,
            "daily_spent": daily_spent,
            "daily_remaining": None if daily_limit is None else round(_bs._safe_float(daily_limit) - daily_spent, 6),
            "daily_unlimited": daily_limit is None,
            "monthly_limit": monthly_limit,
            "monthly_spent": monthly_spent,
            "monthly_remaining": None if monthly_limit is None else round(_bs._safe_float(monthly_limit) - monthly_spent, 6),
            "monthly_unlimited": monthly_limit is None,
            "updated_time": wallet.get("updated_time"),
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/platform/models/usage")
async def models_usage(days: int = Query(default=30)):
    try:
        import bridge_server as _bs
        items = _bs._filter_finance_usage_records(days)
        breakdown = _bs._aggregate_usage_breakdown(items)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return _platform_ok({
            "window_days": days,
            "period_start": now,
            "period_end": now,
            "attribution_mode": "local",
            "record_count": len(items),
            "total_calls": sum(int(item.get("call_count") or 0) for item in items),
            "total_input_chars": sum(int(item.get("text_input_chars") or 0) for item in items),
            "total_output_chars": sum(int(item.get("text_output_chars") or 0) for item in items),
            "total_duration_seconds": round(sum(_bs._safe_float(item.get("duration_seconds")) for item in items), 3),
            "last_used_at": items[0].get("created_time") if items else None,
            "breakdown": [
                {
                    "product_name": item["product_name"],
                    "label": item["label"],
                    "group_type": item["group_type"],
                    "model_name": item["model_name"],
                    "provider_names": item["provider_names"],
                    "call_count": item["call_count"],
                    "text_input_chars": item["text_input_chars"],
                    "text_output_chars": item["text_output_chars"],
                    "duration_seconds": item["duration_seconds"],
                    "last_used_at": item["last_used_at"],
                }
                for item in breakdown
            ],
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


@router.get("/api/platform/models/cost")
async def models_cost(days: int = Query(default=30)):
    try:
        import bridge_server as _bs
        items = _bs._filter_finance_usage_records(days)
        breakdown = _bs._aggregate_usage_breakdown(items)
        currency_breakdown: dict[str, float] = {}
        for item in items:
            currency = str(item.get("currency") or "USD")
            currency_breakdown[currency] = currency_breakdown.get(currency, 0.0) + _bs._safe_float(item.get("amount"))
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return _platform_ok({
            "window_days": days,
            "period_start": now,
            "period_end": now,
            "attribution_mode": "local",
            "record_count": len(items),
            "total_amount": round(sum(_bs._safe_float(item.get("amount")) for item in items), 6),
            "primary_currency": next(iter(currency_breakdown.keys()), "USD"),
            "currency_breakdown": [
                {"currency": c, "amount": round(a, 6)} for c, a in currency_breakdown.items()
            ],
            "last_billed_at": items[0].get("created_time") if items else None,
            "breakdown": breakdown,
        })
    except Exception as exc:
        traceback.print_exc()
        return _platform_error(500, str(exc))


# ---------------------------------------------------------------------------
# 图片生成 (proxy to Nexus)
# ---------------------------------------------------------------------------


@router.post("/api/llm/images/generations")
async def llm_images_generations(request: Request):
    nexus_url = os.environ.get("NEXUS_URL", "").strip().rstrip("/")
    nexus_api_key = os.environ.get("NEXUS_API_KEY", "").strip()
    if not nexus_url:
        return JSONResponse({
            "error": {"message": "Image generation requires NEXUS_URL", "type": "server_error", "code": "nexus_url_not_configured"},
        }, status_code=503)
    try:
        body = await request.json()
    except Exception:
        body = None
    url = f"{nexus_url}/api/llm/images/generations"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {nexus_api_key}"}
    data = json.dumps(body).encode("utf-8") if body else None

    def _proxy():
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        result = await asyncio.to_thread(_proxy)
        return JSONResponse(result)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
        return JSONResponse({"error": {"message": detail}}, status_code=exc.code)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": {"message": str(exc)}}, status_code=500)


# ---------------------------------------------------------------------------
# 视频生成 (proxy to Nexus)
# ---------------------------------------------------------------------------


@router.post("/api/llm/video/generations")
async def llm_video_generations(request: Request):
    nexus_url = os.environ.get("NEXUS_URL", "").strip().rstrip("/")
    nexus_api_key = os.environ.get("NEXUS_API_KEY", "").strip()
    if not nexus_url:
        return JSONResponse({
            "error": {"message": "Video generation requires NEXUS_URL", "type": "server_error", "code": "nexus_url_not_configured"},
        }, status_code=503)
    try:
        body = await request.json()
    except Exception:
        body = None
    url = f"{nexus_url}/api/llm/video/generations"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {nexus_api_key}"}
    data = json.dumps(body).encode("utf-8") if body else None
    timeout = int(os.environ.get("NEXUS_LLM_TIMEOUT_SECONDS", "300"))

    def _proxy():
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        result = await asyncio.to_thread(_proxy)
        return JSONResponse(result)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
        return JSONResponse({"error": {"message": detail}}, status_code=exc.code)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": {"message": str(exc)}}, status_code=500)


@router.get("/api/llm/video/generations/{generation_id}")
async def llm_video_generations_get(generation_id: str, request: Request):
    nexus_url = os.environ.get("NEXUS_URL", "").strip().rstrip("/")
    nexus_api_key = os.environ.get("NEXUS_API_KEY", "").strip()
    if not nexus_url:
        return JSONResponse({
            "error": {"message": "Video generation requires NEXUS_URL", "type": "server_error", "code": "nexus_url_not_configured"},
        }, status_code=503)
    qs = str(request.url.query) if request.url.query else ""
    url = f"{nexus_url}/api/llm/video/generations/{generation_id}"
    if qs:
        url += f"?{qs}"
    headers = {"Authorization": f"Bearer {nexus_api_key}"}
    timeout = int(os.environ.get("NEXUS_LLM_TIMEOUT_SECONDS", "300"))

    def _proxy():
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        result = await asyncio.to_thread(_proxy)
        return JSONResponse(result)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
        return JSONResponse({"error": {"message": detail}}, status_code=exc.code)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": {"message": str(exc)}}, status_code=500)
