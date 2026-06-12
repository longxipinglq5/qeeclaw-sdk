"""LAN mobile channel endpoints for NexusAOS App."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bridge.config import settings

router = APIRouter()

_DEFAULT_CONVERSATION_ID = "mobile-default"
_ZERO_CURSOR = "evt_000000000000"


def _ok(data: Any) -> JSONResponse:
    return JSONResponse({"success": True, "data": data})


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"success": False, "data": None, "error": {"message": message}},
        status_code=status,
    )


def _state_path() -> Path:
    return Path(settings.hermes_home).expanduser() / "mobile_channel_state.json"


def _empty_state() -> dict[str, Any]:
    return {
        "messages": [],
        "tasks": [],
        "events": [],
        "event_seq": 0,
    }


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_state()
    state = _empty_state()
    state.update(data if isinstance(data, dict) else {})
    return state


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _cursor(seq: int) -> str:
    return f"evt_{seq:012d}"


def _next_cursor(state: dict[str, Any]) -> str:
    return _cursor(int(state.get("event_seq") or 0))


def _append_event(
    state: dict[str, Any],
    *,
    event_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    seq = int(state.get("event_seq") or 0) + 1
    state["event_seq"] = seq
    event = {
        "id": f"evt_mobile_{uuid.uuid4().hex[:12]}",
        "cursor": _cursor(seq),
        "type": event_type,
        "entityId": entity_id,
        "payload": payload,
        "createdAt": _now_iso(),
    }
    state.setdefault("events", []).append(event)
    state["events"] = state["events"][-1000:]
    return event


def _mobile_message(conversation_id: str, role: str, content: str) -> dict[str, Any]:
    return {
        "id": f"msg_{role}_{uuid.uuid4().hex[:12]}",
        "conversationId": conversation_id,
        "role": role,
        "content": content,
        "createdAt": _now_iso(),
    }


def _map_approval(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    status = str(item.get("status") or "pending")
    if status == "denied":
        status = "rejected"
    risk = str(item.get("risk") or item.get("risk_level") or "low")
    if risk not in {"low", "medium", "high"}:
        risk = "low"
    return {
        "id": str(item.get("approval_id") or item.get("id") or ""),
        "title": str(item.get("title") or payload.get("title") or "待确认事项"),
        "summary": str(payload.get("summary") or item.get("summary") or item.get("reason") or "有一项内容需要确认。"),
        "reason": str(item.get("reason") or payload.get("reason") or "需要确认"),
        "risk": risk,
        "status": status,
        "primaryActionLabel": str(payload.get("primaryActionLabel") or "确认"),
        "secondaryActionLabel": str(payload.get("secondaryActionLabel") or "再改一下"),
        "originalText": payload.get("originalText") or payload.get("original_text"),
        "suggestedText": payload.get("suggestedText") or payload.get("suggested_text"),
    }


def _load_approvals() -> list[dict[str, Any]]:
    from bridge import legacy_server as _bs

    return _bs._load_approvals()


def _save_approvals(items: list[dict[str, Any]]) -> None:
    from bridge import legacy_server as _bs

    _bs._save_approvals(items)


def _status_for_action(action: str) -> str:
    if action == "approve":
        return "approved"
    if action == "reject":
        return "rejected"
    if action == "rewrite":
        return "rewriting"
    raise ValueError(f"unsupported approval action: {action}")


def _task_status_for_action(action: str) -> str:
    if action in {"done", "dismiss"}:
        return "done"
    if action == "open":
        return "active"
    if action == "snooze":
        return "waiting"
    raise ValueError(f"unsupported task action: {action}")


def _default_task(task_id: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "title": "移动端任务",
        "summary": "有一项任务需要处理。",
        "status": "waiting",
        "updatedAt": _now_iso(),
    }


def _map_task(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or item.get("taskId") or item.get("task_id") or ""),
        "title": str(item.get("title") or "待处理任务"),
        "summary": str(item.get("summary") or item.get("description") or "有一项任务需要处理。"),
        "status": str(item.get("status") or item.get("state") or "waiting"),
        "updatedAt": item.get("updatedAt") or item.get("updated_at"),
    }


def _fallback_assistant_reply_text(content: str) -> str:
    if "今天" in content or "做什么" in content:
        return "收到，建议先确认今天最重要的一项内容任务。"
    return "收到，我会继续处理并在需要确认时提醒你。"


async def _assistant_reply_text(request: Request, *, conversation_id: str, content: str) -> str:
    facade = getattr(request.app.state, "runtime_facade", None)
    invoke = getattr(facade, "invoke_app_im_free_text", None)
    if invoke is None:
        return _fallback_assistant_reply_text(content)
    try:
        result = await invoke(
            session_id=conversation_id,
            user_text=content,
            agent_profile="edge_supervisor",
            metadata={
                "source": "mobile_app",
                "channel_key": "mobile_app",
                "conversation_id": conversation_id,
            },
        )
    except Exception:
        return _fallback_assistant_reply_text(content)
    reply = str(result.get("renderable_reply_text") or result.get("final_response") or "").strip()
    return reply or _fallback_assistant_reply_text(content)


@router.get("/api/platform/mobile-channel/snapshot")
async def mobile_channel_snapshot() -> JSONResponse:
    state = _load_state()
    approvals = [_map_approval(item) for item in _load_approvals()]
    approvals = [item for item in approvals if item["id"]]
    tasks = [_map_task(item) for item in state.get("tasks", []) if isinstance(item, dict)]
    messages = [
        item
        for item in state.get("messages", [])
        if isinstance(item, dict) and item.get("conversationId") == _DEFAULT_CONVERSATION_ID
    ]
    return _ok(
        {
            "device": {
                "displayName": "CentaurOS Edge",
                "online": True,
                "lastSyncText": "刚刚同步",
            },
            "channel": {"key": "mobile_app", "status": "active"},
            "conversation": {"id": _DEFAULT_CONVERSATION_ID, "messages": messages},
            "approvals": approvals,
            "tasks": tasks,
            "nextCursor": _next_cursor(state),
        }
    )


@router.get("/api/platform/mobile-channel/events")
async def mobile_channel_events(cursor: str = _ZERO_CURSOR) -> JSONResponse:
    state = _load_state()
    try:
        cursor_value = int(str(cursor or _ZERO_CURSOR).replace("evt_", ""))
    except ValueError:
        return _err(400, "invalid cursor")
    items = [
        item
        for item in state.get("events", [])
        if isinstance(item, dict)
        and int(str(item.get("cursor") or _ZERO_CURSOR).replace("evt_", "")) > cursor_value
    ]
    return _ok({"items": items, "nextCursor": _next_cursor(state)})


@router.post("/api/platform/mobile-channel/messages")
async def mobile_channel_messages(request: Request) -> JSONResponse:
    body = await request.json()
    content = str(body.get("content") or "").strip()
    if not content:
        return _err(400, "content is required")
    conversation_id = str(body.get("conversationId") or _DEFAULT_CONVERSATION_ID)

    state = _load_state()
    user_message = _mobile_message(conversation_id, "user", content)
    assistant_message = _mobile_message(
        conversation_id,
        "assistant",
        await _assistant_reply_text(request, conversation_id=conversation_id, content=content),
    )
    state.setdefault("messages", []).extend([user_message, assistant_message])
    _append_event(state, event_type="message.created", entity_id=user_message["id"], payload=user_message)
    _append_event(state, event_type="message.created", entity_id=assistant_message["id"], payload=assistant_message)
    _save_state(state)

    return _ok(
        {
            "conversationId": conversation_id,
            "userMessage": user_message,
            "assistantMessage": assistant_message,
            "createdApprovals": [],
            "createdTasks": [],
        }
    )


@router.post("/api/platform/mobile-channel/approvals/{approval_id}/resolve")
async def mobile_channel_approval_resolve(approval_id: str, request: Request) -> JSONResponse:
    body = await request.json()
    action = str(body.get("action") or "")
    try:
        target_status = _status_for_action(action)
    except ValueError as exc:
        return _err(400, str(exc))

    approvals = _load_approvals()
    for item in approvals:
        if str(item.get("approval_id") or item.get("id") or "") != approval_id:
            continue
        current_status = str(item.get("status") or "pending")
        if current_status != "pending":
            if current_status == target_status:
                return _ok(_map_approval(item))
            return _err(409, "approval already resolved")

        item["status"] = target_status
        item["resolved_at"] = _now_iso()
        item["resolved_by"] = {"user_id": 1, "username": "mobile_app"}
        item["resolution_comment"] = body.get("comment")
        _save_approvals(approvals)

        mapped = _map_approval(item)
        state = _load_state()
        _append_event(state, event_type="approval.updated", entity_id=approval_id, payload=mapped)
        _save_state(state)
        return _ok(mapped)

    return _err(404, "approval not found")


@router.post("/api/platform/mobile-channel/tasks/{task_id}/action")
async def mobile_channel_task_action(task_id: str, request: Request) -> JSONResponse:
    body = await request.json()
    action = str(body.get("action") or "")
    try:
        target_status = _task_status_for_action(action)
    except ValueError as exc:
        return _err(400, str(exc))

    state = _load_state()
    tasks = [item for item in state.get("tasks", []) if isinstance(item, dict)]
    task = next((item for item in tasks if str(item.get("id") or "") == task_id), None)
    if task is None:
        task = _default_task(task_id)
        tasks.append(task)

    previous_status = str(task.get("status") or "waiting")
    task["status"] = target_status
    task["comment"] = body.get("comment")
    task["updatedAt"] = _now_iso()
    state["tasks"] = tasks

    mapped = _map_task(task)
    if previous_status != target_status:
        _append_event(state, event_type="task.updated", entity_id=task_id, payload=mapped)
    _save_state(state)
    return _ok(mapped)
