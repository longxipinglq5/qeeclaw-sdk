"""P2 平台端点：工作流、审批、审计、Builder、设备、用户上下文、会话、策略"""

from __future__ import annotations

import logging
import os
import time
import traceback
import uuid

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _ok(data):
    return JSONResponse({"success": True, "data": data})


def _err(status: int, message: str):
    return JSONResponse({"success": False, "data": None, "error": {"message": message}}, status_code=status)


# ---------------------------------------------------------------------------
# 用户上下文
# ---------------------------------------------------------------------------


@router.get("/api/users/me/context")
async def user_context():
    try:
        from bridge import legacy_server as _bs
        profile = _bs._load_user_profile()
        teams = profile.get("teams", [{"id": 1, "name": "local", "is_personal": True, "owner_id": 1}])
        first_team = teams[0] if teams else {}
        return _ok({
            "id": profile.get("id", 1),
            "username": profile.get("username", "local-admin"),
            "role": profile.get("role", "ADMIN"),
            "is_enterprise_verified": profile.get("is_enterprise_verified", False),
            "default_team_id": first_team.get("id", 1),
            "default_team_name": first_team.get("name", "local"),
            "default_team_is_personal": first_team.get("is_personal", True),
            "teams": teams,
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/users/me")
async def user_profile_get():
    try:
        from bridge import legacy_server as _bs
        return _ok(_bs._load_user_profile())
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.put("/api/users/me")
async def user_profile_update(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        profile = _bs._load_user_profile()
        for key in ("full_name", "email", "phone"):
            if key in body:
                profile[key] = body[key]
        _bs._save_user_profile(profile)
        return _ok(profile)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.put("/api/users/me/preference")
async def user_preference_update(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        preferred_model = body.get("preferred_model", "")
        profile = _bs._load_user_profile()
        profile.setdefault("preference", {})["preferred_model"] = preferred_model
        _bs._save_user_profile(profile)
        return _ok({"preferred_model": preferred_model})
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/users/products")
async def user_products():
    return _ok([])


@router.get("/api/users")
async def users_list(page: int = Query(default=1), page_size: int = Query(default=20)):
    try:
        from bridge import legacy_server as _bs
        profile = _bs._load_user_profile()
        return _ok({"total": 1, "page": page, "page_size": page_size, "items": [profile]})
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 企业认证
# ---------------------------------------------------------------------------


@router.get("/api/company/verification")
async def company_verification_get():
    return _ok({
        "status": "none", "company_name": None, "tax_number": None,
        "address": None, "phone": None, "bank_name": None,
        "bank_account": None, "license_url": None, "rejection_reason": None, "updated_time": None,
    })


@router.post("/api/company/verification")
async def company_verification_submit():
    return _ok({"status": "pending", "company_name": None, "updated_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


# ---------------------------------------------------------------------------
# 工作流
# ---------------------------------------------------------------------------


@router.get("/workflow/list")
async def workflow_list():
    try:
        from bridge import legacy_server as _bs
        return _ok(_bs._load_workflows())
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/workflow/run/{wf_id}")
async def workflow_get(wf_id: str):
    try:
        from bridge import legacy_server as _bs
        for wf in _bs._load_workflows():
            if str(wf.get("id")) == wf_id:
                return _ok(wf)
        return _err(404, "Workflow not found")
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/workflow/save")
async def workflow_save(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        wf_id = body.get("id") or f"wf_{uuid.uuid4().hex[:12]}"
        workflows = _bs._load_workflows()
        found = False
        for i, wf in enumerate(workflows):
            if wf.get("id") == wf_id:
                workflows[i] = body
                workflows[i]["id"] = wf_id
                found = True
                break
        if not found:
            body["id"] = wf_id
            body.setdefault("enabled", True)
            workflows.append(body)
        _bs._save_workflows(workflows)
        return _ok(body)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 审批
# ---------------------------------------------------------------------------


@router.get("/api/platform/approvals")
async def approvals_list(page: int = Query(default=1), page_size: int = Query(default=20), status: str | None = Query(default=None)):
    try:
        from bridge import legacy_server as _bs
        items = _bs._load_approvals()
        if status:
            items = [a for a in items if a.get("status") == status]
        total = len(items)
        start = (page - 1) * page_size
        return _ok({"total": total, "page": page, "page_size": page_size, "items": items[start:start + page_size]})
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/approvals/request")
async def approval_request(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        expires_seconds = body.get("expires_in_seconds", 86400)
        approval = {
            "approval_id": f"apr_{uuid.uuid4().hex[:12]}",
            "status": "pending",
            "approval_type": body.get("approval_type", "custom"),
            "title": body.get("title", ""),
            "reason": body.get("reason", ""),
            "risk_level": body.get("risk_level", "medium"),
            "payload": body.get("payload", {}),
            "requested_by": {"user_id": 1, "username": "local-admin"},
            "resolved_by": None, "resolution_comment": None,
            "created_at": now,
            "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_seconds)),
            "resolved_at": None,
        }
        items = _bs._load_approvals()
        items.insert(0, approval)
        _bs._save_approvals(items)
        return _ok(approval)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/platform/approvals/{approval_id}")
async def approval_get(approval_id: str):
    try:
        from bridge import legacy_server as _bs
        for item in _bs._load_approvals():
            if item.get("approval_id") == approval_id:
                return _ok(item)
        return _err(404, "Approval not found")
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/approvals/{approval_id}/resolve")
async def approval_resolve(approval_id: str, request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        items = _bs._load_approvals()
        for item in items:
            if item.get("approval_id") == approval_id:
                if body.get("action") == "approved" or body.get("approved"):
                    item["status"] = "approved"
                else:
                    item["status"] = "rejected"
                item["resolved_at"] = now
                item["resolved_by"] = {"user_id": 1, "username": "local-admin"}
                item["resolution_comment"] = body.get("comment")
                _bs._save_approvals(items)
                return _ok(item)
        return _err(404, "Approval not found")
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 审计
# ---------------------------------------------------------------------------


@router.get("/api/platform/audit/events")
async def audit_events(page: int = Query(default=1), page_size: int = Query(default=50)):
    try:
        from bridge import legacy_server as _bs
        events = _bs._load_audit_events()
        total = len(events)
        start = (page - 1) * page_size
        return _ok({"total": total, "page": page, "page_size": page_size, "items": events[start:start + page_size]})
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/audit/events")
async def audit_record(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "category": body.get("category", "operation"),
            "event_type": body.get("event_type") or body.get("action_type", "unknown"),
            "title": body.get("title", ""),
            "summary": body.get("summary"),
            "module": body.get("module", "SDK"),
            "path": body.get("path"),
            "status": body.get("status", "completed"),
            "risk_level": body.get("risk_level", "low"),
            "actor": {"user_id": 1, "username": "local-admin"},
            "metadata": body.get("metadata", {}),
            "created_at": now,
        }
        events = _bs._load_audit_events()
        events.insert(0, event)
        _bs._save_audit_events(events[:1000])
        return _ok(event)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/platform/audit/summary")
async def audit_summary():
    try:
        from bridge import legacy_server as _bs
        events = _bs._load_audit_events()
        approvals = _bs._load_approvals()
        return _ok({
            "total": len(events) + len(approvals),
            "operation_count": len(events),
            "approval_count": len(approvals),
            "pending_approval_count": sum(1 for a in approvals if a.get("status") == "pending"),
            "approved_approval_count": sum(1 for a in approvals if a.get("status") == "approved"),
            "rejected_approval_count": sum(1 for a in approvals if a.get("status") == "rejected"),
            "expired_approval_count": sum(1 for a in approvals if a.get("status") == "expired"),
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


@router.get("/api/builder/projects")
async def builder_projects_list():
    try:
        from bridge import legacy_server as _bs
        return _ok(_bs.list_builder_projects())
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/builder/projects/{project_id}")
async def builder_project_get(project_id: str):
    try:
        from bridge import legacy_server as _bs
        if not _bs._sanitize_builder_project_id(project_id):
            return _err(400, "invalid builder project id")
        project = _bs.load_builder_project(project_id)
        if not project:
            return _err(404, f"builder project {project_id} not found")
        return _ok(project)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/builder/projects")
async def builder_project_create(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        if not isinstance(body.get("blueprint"), dict):
            return _err(400, "blueprint is required")
        return _ok(_bs.save_builder_project(body))
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.put("/api/builder/projects/{project_id}")
async def builder_project_update(project_id: str, request: Request):
    try:
        from bridge import legacy_server as _bs
        if not _bs._sanitize_builder_project_id(project_id):
            return _err(400, "invalid builder project id")
        body = await request.json()
        if not isinstance(body.get("blueprint"), dict):
            return _err(400, "blueprint is required")
        previous = _bs.load_builder_project(project_id) or {}
        return _ok(_bs.save_builder_project({**previous, **body}, project_id=project_id))
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/builder/projects/{project_id}/test-runs")
async def builder_project_test_run(project_id: str):
    try:
        from bridge import legacy_server as _bs
        if not _bs._sanitize_builder_project_id(project_id):
            return _err(400, "invalid builder project id")
        project = _bs.load_builder_project(project_id)
        if not project:
            return _err(404, f"builder project {project_id} not found")
        return _ok(_bs.run_builder_project_test(project))
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.delete("/api/builder/projects/{project_id}")
async def builder_project_delete(project_id: str):
    try:
        from bridge import legacy_server as _bs
        _bs.delete_builder_project(project_id)
        return _ok(None)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 设备
# ---------------------------------------------------------------------------


@router.get("/api/platform/devices")
async def devices_list():
    try:
        from bridge import legacy_server as _bs
        info = _bs._load_device_info()
        info["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return _ok([info])
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/platform/devices/account-state")
async def device_account_state(installation_id: str = Query(default="")):
    try:
        from bridge import legacy_server as _bs
        info = _bs._load_device_info()
        return _ok({
            "installation_id": installation_id or info.get("installation_id", ""),
            "state": "current_user",
            "can_register_current_account": False,
            "current_user_device_id": info.get("id", 1),
            "current_user_has_devices": True,
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.get("/api/platform/devices/online")
async def devices_online():
    try:
        from bridge import legacy_server as _bs
        info = _bs._load_device_info()
        return _ok({
            "runtime_type": "hermes",
            "runtime_label": "Hermes",
            "runtime_status": "running",
            "runtime_stage": "phase_device_bridge_only",
            "supports_device_bridge": True,
            "supports_managed_download": False,
            "online_team_ids": [1],
            "notes": "当前设备中心仅管理 Hermes device bridge。",
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/devices/bootstrap")
async def device_bootstrap(request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        info = _bs._load_device_info()
        for key in ("device_name", "hostname", "os_info", "installation_id"):
            if body.get(key):
                info[key] = body[key]
        _bs._save_device_info(info)
        from bridge.config import settings
        return _ok({
            "api_key": "local-bridge-key",
            "base_url": f"http://127.0.0.1:{settings.bridge_port}",
            "ws_url": f"ws://127.0.0.1:{settings.bridge_port}",
            "device_id": info.get("id", 1),
            "device_name": info.get("device_name", ""),
            "installation_id": info.get("installation_id", ""),
            "registration_mode": "local",
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/devices/pair-code")
async def device_pair_code():
    try:
        return _ok({
            "pair_code": f"PAIR-{uuid.uuid4().hex[:6].upper()}",
            "expires_in_seconds": 600,
            "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 600)),
        })
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.post("/api/platform/devices/claim")
async def device_claim(request: Request):
    return await device_bootstrap(request)


@router.put("/api/platform/devices/{device_id}")
async def device_update(device_id: str, request: Request):
    try:
        from bridge import legacy_server as _bs
        body = await request.json()
        info = _bs._load_device_info()
        if body.get("device_name"):
            info["device_name"] = body["device_name"]
        _bs._save_device_info(info)
        return _ok(None)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


@router.delete("/api/platform/devices/{device_id}")
async def device_delete(device_id: str):
    try:
        from bridge import legacy_server as _bs
        import os
        if os.path.isfile(_bs._DEVICE_INFO_FILE):
            os.remove(_bs._DEVICE_INFO_FILE)
        return _ok(None)
    except Exception as exc:
        traceback.print_exc()
        return _err(500, str(exc))


# ---------------------------------------------------------------------------
# 会话 (conversations)
# ---------------------------------------------------------------------------


@router.get("/api/platform/conversations/stats")
async def conversations_stats():
    return _ok({"total_conversations": 0, "active_conversations": 0})


@router.get("/api/platform/conversations/groups")
async def conversations_groups():
    return _ok([])


@router.get("/api/platform/conversations/history")
async def conversations_history(request: Request, session_id: str | None = Query(default=None)):
    if session_id and hasattr(request.app.state, "runtime_facade"):
        facade_session = request.app.state.runtime_facade.sessions.get(session_id)
        if facade_session is not None:
            return _ok(
                request.app.state.runtime_facade.sessions.get_recent_messages(
                    session_id,
                    token_budget=None,
                )
            )
    return _ok([])


@router.post("/api/platform/conversations/messages")
async def conversations_send(request: Request):
    return _err(501, "Conversations relay not available on bridge")
