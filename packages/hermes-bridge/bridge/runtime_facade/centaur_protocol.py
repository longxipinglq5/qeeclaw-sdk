from __future__ import annotations

from typing import Any

from bridge.runtime_facade.cards import build_loop_protocol_card


_CARD_TYPES = {
    "plan_card": "plan_card",
    "draft_card": "draft_card",
    "publish_card": "publish_card",
    "feedback_request": "feedback_request",
    "review_card": "review_card",
    "memory_card": "memory_card",
    "progress": "progress_card",
    "cycle_complete": "progress_card",
}

_APPROVAL_ACTIONS = {
    "publish_card": "publish_content",
    "memory_card": "write_memory",
}


def map_loop_message_to_timeline_event(message: dict[str, Any]) -> dict[str, Any]:
    message_type = str(message.get("message_type", "progress"))
    card_type = _CARD_TYPES.get(message_type, "progress_card")
    action_kind = _APPROVAL_ACTIONS.get(message_type)
    summary = str(message.get("summary") or message.get("fallback_text") or "")

    card = build_loop_protocol_card(
        card_id=str(
            message.get("card_id")
            or f"card_{message.get('cycle_id', 'unknown')}_{message_type}"
        ),
        card_type=card_type,
        title=str(message.get("title") or _default_title(message_type)),
        summary=summary,
        artifact_ids=list(message.get("artifact_ids", [])),
        run_id=str(message.get("run_id", "centaur_loop")),
        cycle_id=message.get("cycle_id"),
        approval_id=message.get("approval_id"),
        action_kind=action_kind,
        status="cycle_complete" if message_type == "cycle_complete" else message.get("status"),
        progress=message.get("progress"),
        metrics=message.get("metrics"),
        actions=list(message.get("actions", [])),
        fallback_text=str(message.get("fallback_text") or summary),
    )
    payload = {
        "kind": "approval" if action_kind is not None else "card",
        "role": "assistant",
        "card": card.model_dump(exclude_none=True),
    }
    if action_kind is not None:
        payload["action_kind"] = action_kind
    return payload


def _default_title(message_type: str) -> str:
    return {
        "plan_card": "计划确认",
        "draft_card": "草稿审阅",
        "publish_card": "发布确认",
        "feedback_request": "反馈补充",
        "review_card": "自动复盘",
        "memory_card": "记忆写入确认",
        "progress": "执行进度",
        "cycle_complete": "本轮完成",
    }.get(message_type, "执行进度")
