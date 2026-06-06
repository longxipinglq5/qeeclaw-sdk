"""渠道/微信端点：企微、飞书、个人微信插件、OpenClaw、绑定管理"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from bridge.api.errors import api_error
from bridge.runtime_facade.channel_stores import (
    ChannelUnavailableError,
    OutboxNotFoundError,
    OutboxNotRetryableError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _ok(data):
    return JSONResponse({"success": True, "data": data})


def _err(status: int, message: str):
    return JSONResponse({"success": False, "data": None, "error": {"message": message}}, status_code=status)


def _facade(request: Request):
    return request.app.state.runtime_facade


@router.post("/api/channels/outbox/{outbox_id}/retry")
async def retry_channel_outbox(outbox_id: str, request: Request, adapter_available: bool = True) -> JSONResponse:
    try:
        record = _facade(request).outbox.retry(
            outbox_id,
            adapter_available=adapter_available,
        )
    except OutboxNotFoundError:
        return api_error("OUTBOX_NOT_FOUND", "Outbox message not found", 404, {"outbox_id": outbox_id})
    except OutboxNotRetryableError:
        return api_error("OUTBOX_NOT_RETRYABLE", "Outbox message is not retryable", 409, {"outbox_id": outbox_id})
    except ChannelUnavailableError:
        return api_error("CHANNEL_UNAVAILABLE", "Channel adapter is unavailable", 503, {"outbox_id": outbox_id})
    return JSONResponse(record.model_dump(mode="json"))


def _make_channel_item(channel_id: str, display_name: str, category: str, adapter_key: str, **kw):
    return {
        "channel_id": channel_id,
        "display_name": display_name,
        "category": category,
        "adapter_key": adapter_key,
        **kw,
    }


# ---------------------------------------------------------------------------
# 渠道列表
# ---------------------------------------------------------------------------


@router.get("/api/platform/channels")
async def channels_list():
    try:
        import bridge_server as _bs
        stored_wechat_work = _bs._load_wechat_work_channel_config()
        stored_feishu = _bs._load_feishu_channel_config()
        stored_plugin = _bs._load_wechat_personal_plugin_channel_config()
        channels = [
            _make_channel_item(
                "wechat_work", "企业微信", "enterprise_collab", "wechat_work",
                configured=bool(stored_wechat_work.get("configured")),
                enabled=bool(stored_wechat_work.get("enabled")),
            ),
            _make_channel_item(
                "feishu", "飞书", "enterprise_collab", "feishu",
                configured=bool(stored_feishu.get("configured")),
                enabled=bool(stored_feishu.get("enabled")),
            ),
            _make_channel_item(
                "wechat_personal_plugin", "微信个人号(插件)", "personal_reach", "wechat_work_plugin",
                configured=bool(stored_plugin.get("configured")),
                enabled=bool(stored_plugin.get("enabled")),
            ),
            _make_channel_item(
                "wechat_personal_openclaw", "微信个人号(OpenClaw)", "personal_reach",
                "openclaw_wechat_plugin",
                configured=True,
                enabled=False,
            ),
        ]
        return _ok(channels)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 企业微信
# ---------------------------------------------------------------------------


@router.get("/api/platform/channels/wechat-work/config")
async def wechat_work_config():
    try:
        import bridge_server as _bs
        stored = _bs._load_wechat_work_channel_config()
        config = _make_channel_item(
            "wechat_work", "企业微信", "enterprise_collab", "wechat_work",
            configured=bool(stored.get("configured")),
            enabled=bool(stored.get("enabled")),
        )
        config.update({
            "corp_id": stored.get("corp_id", ""),
            "agent_id": stored.get("agent_id", ""),
            "secret": "",
            "secret_configured": bool(stored.get("secret_configured")),
            "verify_token": stored.get("verify_token", ""),
            "aes_key": stored.get("aes_key", ""),
            "bot_webhook_url": stored.get("bot_webhook_url", ""),
            "bot_webhook_configured": bool(stored.get("bot_webhook_configured")),
            "updated_time": stored.get("updated_time"),
        })
        return _ok(config)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/channels/wechat-work/config")
async def wechat_work_config_update(request: Request):
    try:
        import bridge_server as _bs
        body = await request.json()
        previous = _bs._load_wechat_work_channel_config()
        secret_configured = bool(body.get("secret")) or bool(previous.get("secret_configured"))
        bot_webhook_configured = bool(body.get("bot_webhook_url", previous.get("bot_webhook_url", "")))
        stored = {
            "corp_id": body.get("corp_id", previous.get("corp_id", "")),
            "agent_id": body.get("agent_id", previous.get("agent_id", "")),
            "secret_configured": secret_configured,
            "verify_token": body.get("verify_token", previous.get("verify_token", "")),
            "aes_key": body.get("aes_key", previous.get("aes_key", "")),
            "bot_webhook_url": body.get("bot_webhook_url", previous.get("bot_webhook_url", "")),
            "bot_webhook_configured": bot_webhook_configured,
            "enabled": bool(body.get("enabled", previous.get("enabled", False))),
            "updated_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        stored["configured"] = bool(bot_webhook_configured or (stored["corp_id"] and stored["agent_id"] and secret_configured))
        _bs._save_wechat_work_channel_config(stored)
        config = _make_channel_item("wechat_work", "企业微信", "enterprise_collab", "wechat_work", configured=stored["configured"], enabled=stored["enabled"])
        config.update({
            "corp_id": stored["corp_id"], "agent_id": stored["agent_id"], "secret": "",
            "secret_configured": stored["secret_configured"], "verify_token": stored["verify_token"],
            "aes_key": stored["aes_key"], "bot_webhook_url": stored["bot_webhook_url"],
            "bot_webhook_configured": stored["bot_webhook_configured"], "updated_time": stored["updated_time"],
        })
        return _ok(config)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 飞书
# ---------------------------------------------------------------------------


@router.get("/api/platform/channels/feishu/config")
async def feishu_config():
    try:
        import bridge_server as _bs
        stored = _bs._load_feishu_channel_config()
        config = _make_channel_item("feishu", "飞书", "enterprise_collab", "feishu", configured=bool(stored.get("configured")), enabled=bool(stored.get("enabled")))
        config.update({
            "app_id": stored.get("app_id", ""), "app_secret": "",
            "verification_token": stored.get("verification_token", ""),
            "encrypt_key": stored.get("encrypt_key", ""),
            "secret_configured": bool(stored.get("secret_configured")),
            "bot_webhook_url": stored.get("bot_webhook_url", ""),
            "bot_webhook_configured": bool(stored.get("bot_webhook_configured")),
            "updated_time": stored.get("updated_time"),
        })
        return _ok(config)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/channels/feishu/config")
async def feishu_config_update(request: Request):
    try:
        import bridge_server as _bs
        body = await request.json()
        previous = _bs._load_feishu_channel_config()
        secret_configured = bool(body.get("app_secret")) or bool(previous.get("secret_configured"))
        bot_webhook_configured = bool(body.get("bot_webhook_url", previous.get("bot_webhook_url", "")))
        stored = {
            "app_id": body.get("app_id", previous.get("app_id", "")),
            "verification_token": body.get("verification_token", previous.get("verification_token", "")),
            "encrypt_key": body.get("encrypt_key", previous.get("encrypt_key", "")),
            "secret_configured": secret_configured,
            "bot_webhook_url": body.get("bot_webhook_url", previous.get("bot_webhook_url", "")),
            "bot_webhook_configured": bot_webhook_configured,
            "enabled": bool(body.get("enabled", previous.get("enabled", False))),
            "updated_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        stored["configured"] = bool(bot_webhook_configured or (stored["app_id"] and secret_configured))
        _bs._save_feishu_channel_config(stored)
        config = _make_channel_item("feishu", "飞书", "enterprise_collab", "feishu", configured=stored["configured"], enabled=stored["enabled"])
        config.update({
            "app_id": stored["app_id"], "app_secret": "", "verification_token": stored["verification_token"],
            "encrypt_key": stored["encrypt_key"], "secret_configured": stored["secret_configured"],
            "bot_webhook_url": stored["bot_webhook_url"], "bot_webhook_configured": stored["bot_webhook_configured"],
            "updated_time": stored["updated_time"],
        })
        return _ok(config)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 个人微信插件
# ---------------------------------------------------------------------------


@router.get("/api/platform/channels/wechat-personal-plugin/config")
async def wechat_personal_plugin_config():
    try:
        import bridge_server as _bs
        stored = _bs._load_wechat_personal_plugin_channel_config()
        config = _make_channel_item("wechat_personal_plugin", "微信个人号(插件)", "personal_reach", "wechat_work_plugin", configured=bool(stored.get("configured")), enabled=bool(stored.get("enabled")))
        config.update(stored)
        return _ok(config)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/channels/wechat-personal-plugin/config")
async def wechat_personal_plugin_config_update(request: Request):
    try:
        import bridge_server as _bs
        body = await request.json()
        previous = _bs._load_wechat_personal_plugin_channel_config()
        kernel_corp_id = body.get("kernel_corp_id", previous.get("kernel_corp_id", ""))
        kernel_agent_id = body.get("kernel_agent_id", previous.get("kernel_agent_id", ""))
        kernel_secret = body.get("kernel_secret", "")
        kernel_verify_token = body.get("kernel_verify_token", previous.get("kernel_verify_token", ""))
        kernel_aes_key = body.get("kernel_aes_key", previous.get("kernel_aes_key", ""))
        kernel_secret_configured = bool(kernel_secret) or bool(previous.get("kernel_secret_configured"))
        kernel_configured = bool(kernel_corp_id and kernel_agent_id and kernel_secret_configured)
        configured = bool(body.get("display_name", previous.get("display_name", "")).strip()) and kernel_configured
        enabled_requested = bool(body.get("enabled", previous.get("enabled", False)))
        binding_enabled_requested = bool(body.get("binding_enabled", previous.get("binding_enabled", False)))
        enabled = bool(configured and enabled_requested)
        binding_enabled = bool(configured and binding_enabled_requested)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        stored = {
            "display_name": body.get("display_name", previous.get("display_name", "微信个人号(插件)")),
            "kernel_source": "independent" if kernel_configured else previous.get("kernel_source", "unconfigured"),
            "kernel_configured": kernel_configured, "kernel_isolated": kernel_configured,
            "kernel_corp_id": kernel_corp_id, "kernel_agent_id": kernel_agent_id,
            "kernel_secret": "", "kernel_secret_configured": kernel_secret_configured,
            "kernel_verify_token": kernel_verify_token, "kernel_aes_key": kernel_aes_key,
            "effective_kernel_corp_id": kernel_corp_id, "effective_kernel_agent_id": kernel_agent_id,
            "effective_kernel_verify_token": kernel_verify_token, "effective_kernel_aes_key": kernel_aes_key,
            "setup_status": "active" if configured else ("beta" if kernel_configured else "planned"),
            "assistant_name": body.get("assistant_name", previous.get("assistant_name", "")),
            "welcome_message": body.get("welcome_message", previous.get("welcome_message", "")),
            "capability_stage": "beta" if configured else "planned",
            "binding_enabled": binding_enabled, "enabled": enabled, "configured": configured,
            "updated_time": now,
        }
        _bs._save_wechat_personal_plugin_channel_config(stored)
        config = _make_channel_item("wechat_personal_plugin", "微信个人号(插件)", "personal_reach", "wechat_work_plugin", configured=configured, enabled=enabled)
        config.update(stored)
        return _ok(config)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# OpenClaw
# ---------------------------------------------------------------------------


@router.get("/api/platform/channels/wechat-personal-openclaw/config")
async def openclaw_config():
    try:
        gateway_online = False
        try:
            import bridge_server as _bs
            _bs._ensure_hermes_on_path()
            from gateway.gateway_manager import GatewayManager
            gm = GatewayManager()
            gateway_online = gm.is_running() if hasattr(gm, "is_running") else False
        except Exception:
            pass
        config = _make_channel_item("wechat_personal_openclaw", "微信个人号(OpenClaw)", "personal_reach", "openclaw_wechat_plugin", configured=True, enabled=gateway_online)
        config.update({
            "display_name": "微信个人号(插件)", "channel_mode": "hermes_plugin",
            "setup_status": "ready", "manual_cli_required": False, "preinstall_supported": True,
            "qr_supported": True, "gateway_online": gateway_online, "official_plugin_available": None,
            "install_hint": "请通过 /wechat/qr-login 发起扫码登录", "capability_stage": "production",
        })
        return _ok(config)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/platform/channels/wechat-personal-openclaw/qr/status")
async def openclaw_qr_status():
    try:
        import bridge_server as _bs
        _bs._ensure_hermes_on_path()
        from wechat_gateway import get_qr_login_status
        result = get_qr_login_status()
        return _ok(result)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/channels/wechat-personal-openclaw/qr/start")
async def openclaw_qr_start(request: Request):
    try:
        import bridge_server as _bs
        _bs._ensure_hermes_on_path()
        from wechat_gateway import start_qr_login
        body = await request.json()
        binding_id = int(body.get("binding_id") or body.get("bindingId") or 0)
        binding_context = None
        if binding_id > 0:
            binding_context = {
                "binding_id": binding_id,
                "team_id": int(body.get("team_id") or body.get("teamId") or 1),
                "channel_key": "wechat_personal_openclaw",
            }

        def _on_qr_success(credentials, context):
            target_id = int(context.get("binding_id") or 0)
            if target_id > 0:
                _bs._claim_channel_binding_record(target_id, credentials, context)

        result = await asyncio.to_thread(
            start_qr_login,
            binding_context=binding_context,
            on_success=_on_qr_success if binding_context else None,
        )
        status = str(result.get("status") or "unknown")
        qr_url = result.get("qr_url", "") or ""
        return _ok({
            "status": "waiting_scan" if status in {"started", "already_in_progress"} else status,
            "message": result.get("message") or "请使用微信扫描二维码",
            "qr_data_url": _bs._url_to_qr_data_url(qr_url) if qr_url else "",
            "qr_url": qr_url,
            "session_id": result.get("session_id", ""),
            "account_id": "",
            "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 300)) if status in {"started", "already_in_progress"} else None,
            "connected": False,
            "binding": _bs._claim_channel_binding_record(binding_id, result.get("credentials") or {}, binding_context)
                if binding_id > 0 and status in {"success", "bound"} and isinstance(result.get("credentials"), dict)
                else None,
            "raw": result,
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 绑定管理
# ---------------------------------------------------------------------------


@router.get("/api/platform/channels/bindings")
async def bindings_list(
    team_id: int = Query(default=1),
    channel_key: str = Query(default="wechat_personal_plugin"),
):
    try:
        import bridge_server as _bs
        bindings = [
            item for item in _bs._load_channel_bindings()
            if int(item.get("team_id", 1)) == team_id and item.get("channel_key") == channel_key
            and item.get("binding_target_id") != _bs._CHANNELS_BINDINGS_VALIDATE_PROBE_TARGET
        ]
        return _ok({"items": bindings, "total": len(bindings)})
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/platform/channels/bindings/validate")
async def bindings_validate(
    team_id: int = Query(default=1),
    channel_key: str = Query(default="wechat_personal_plugin"),
):
    try:
        import bridge_server as _bs
        import os
        storage_dir = os.path.dirname(_bs._CHANNELS_BINDINGS_FILE)
        storage_parent = os.path.dirname(storage_dir) or storage_dir
        storage_file_exists = os.path.isfile(_bs._CHANNELS_BINDINGS_FILE)
        storage_dir_exists = os.path.isdir(storage_dir)
        storage_readable = storage_file_exists and os.access(_bs._CHANNELS_BINDINGS_FILE, os.R_OK)
        storage_writable = (
            os.access(_bs._CHANNELS_BINDINGS_FILE, os.W_OK) if storage_file_exists
            else os.access(storage_dir, os.W_OK) if storage_dir_exists
            else os.access(storage_parent, os.W_OK)
        )
        bindings = [
            item for item in _bs._load_channel_bindings()
            if int(item.get("team_id", 1)) == team_id and item.get("channel_key") == channel_key
            and item.get("binding_target_id") != _bs._CHANNELS_BINDINGS_VALIDATE_PROBE_TARGET
        ]
        probe_result = _bs._probe_channel_bindings_write_path(team_id, channel_key) if storage_writable else {"ok": False, "error": "bindings storage is not writable", "cleanup_error": None}
        return _ok({
            "team_id": team_id, "channel_key": channel_key,
            "ready": bool(storage_writable and probe_result.get("ok")),
            "storage_file": _bs._CHANNELS_BINDINGS_FILE, "storage_file_exists": storage_file_exists,
            "storage_dir": storage_dir, "storage_dir_exists": storage_dir_exists,
            "storage_readable": storage_readable, "storage_writable": storage_writable,
            "bindings_count": len(bindings),
            "binding_enabled": bool(_bs._load_wechat_personal_plugin_channel_config().get("binding_enabled", False)),
            "supported_operations": ["list", "create", "disable", "regenerate-code"],
            "probe_write_ok": bool(probe_result.get("ok")),
            "probe_cleanup_ok": probe_result.get("cleanup_error") is None,
            "probe_error": probe_result.get("error"),
            "validation_mode": "active-write-no-residue",
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/channels/bindings/create")
async def binding_create(request: Request):
    try:
        import bridge_server as _bs
        body = await request.json()
        channel_key = body.get("channel_key", "wechat_personal_plugin")
        if channel_key == "wechat_personal_plugin":
            plugin_config = _bs._load_wechat_personal_plugin_channel_config()
            if not bool(plugin_config.get("configured")):
                return _err(400, "wechat personal plugin channel is not fully configured")
            if not bool(plugin_config.get("enabled")):
                return _err(400, "wechat personal plugin channel is not enabled")
            if not bool(plugin_config.get("binding_enabled")):
                return _err(400, "wechat personal plugin binding is not enabled")
        binding = _bs._create_channel_binding_record(body)
        return _ok(binding)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/channels/bindings/disable")
async def binding_disable(request: Request):
    try:
        import bridge_server as _bs
        body = await request.json()
        binding_id = int(body.get("binding_id", 0))
        binding = _bs._disable_channel_binding_record(binding_id)
        if binding is None:
            return _err(404, f"binding {binding_id} not found")
        return _ok(binding)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/channels/bindings/regenerate-code")
async def binding_regenerate_code(request: Request):
    try:
        import bridge_server as _bs
        body = await request.json()
        expires_hours = int(body.get("expires_in_hours", 72))
        binding_id = int(body.get("binding_id", 0))
        binding = _bs._regenerate_channel_binding_code_record(binding_id, expires_hours=expires_hours)
        if binding is None:
            return _err(404, f"binding {binding_id} not found")
        return _ok(binding)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))
