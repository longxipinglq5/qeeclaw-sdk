from __future__ import annotations

import json
from typing import Any


def extract_tool_call_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Hermes assistant/tool messages into stable tool call events."""
    messages = result.get("messages")
    if not isinstance(messages, list):
        return []

    events: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}

    for message in messages:
        if not isinstance(message, dict):
            continue

        if message.get("role") == "assistant":
            for call in _iter_tool_calls(message):
                tool_call_id = _tool_call_id(call)
                if not tool_call_id:
                    continue
                payload = _tool_call_payload(tool_call_id, call)
                pending[tool_call_id] = payload
                events.append({"type": "tool_call.started", "payload": dict(payload)})
            continue

        if message.get("role") != "tool":
            continue
        tool_call_id = str(message.get("tool_call_id") or "")
        if not tool_call_id:
            continue
        base_payload = pending.get(tool_call_id) or {
            "tool_call_id": tool_call_id,
            "tool_name": str(message.get("tool_name") or message.get("name") or "tool"),
            "arguments": {},
            "raw_arguments": "",
        }
        content = message.get("content")
        payload = {
            **base_payload,
            "result": {
                "content": coerce_tool_content_to_text(content),
                "raw_content": content,
            },
        }
        event_type = "tool_call.failed" if _is_tool_failure(content) else "tool_call.completed"
        events.append({"type": event_type, "payload": payload})

    return events


def coerce_tool_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    if isinstance(content, dict):
        text_summary = content.get("text_summary")
        if text_summary:
            return str(text_summary)
        for key in ("text", "body", "output", "result", "content"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return json.dumps(content, ensure_ascii=False, default=str)
    return str(content)


def _iter_tool_calls(message: dict[str, Any]) -> list[Any]:
    tool_calls = message.get("tool_calls")
    return tool_calls if isinstance(tool_calls, list) else []


def _tool_call_id(call: Any) -> str:
    if isinstance(call, dict):
        return str(call.get("id") or call.get("call_id") or "")
    return str(getattr(call, "id", "") or getattr(call, "call_id", "") or "")


def _tool_call_payload(tool_call_id: str, call: Any) -> dict[str, Any]:
    function = call.get("function") if isinstance(call, dict) else getattr(call, "function", None)
    if isinstance(function, dict):
        tool_name = str(function.get("name") or "")
        raw_arguments = function.get("arguments")
    else:
        tool_name = str(getattr(function, "name", "") or "")
        raw_arguments = getattr(function, "arguments", "")

    raw_arguments_text = (
        raw_arguments
        if isinstance(raw_arguments, str)
        else json.dumps(raw_arguments or {}, ensure_ascii=False, default=str)
    )
    return {
        "tool_call_id": tool_call_id,
        "tool_name": tool_name or "tool",
        "arguments": _parse_arguments(raw_arguments),
        "raw_arguments": raw_arguments_text,
    }


def _parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str) and raw_arguments.strip():
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _is_tool_failure(content: Any) -> bool:
    if isinstance(content, dict) and content.get("error"):
        return True
    text = coerce_tool_content_to_text(content).strip().lower()
    return text.startswith("error") or text.startswith("failed")
