from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class SkillUseIntent(BaseModel):
    skill_id: str
    skill_name: str = ""
    summary: str = ""
    speech: str = ""
    prefilled: dict[str, Any] = Field(default_factory=dict)
    auto_run: bool = True
    source: str = "hermes_skill_intent"


class SkillIntentValidation(BaseModel):
    status: Literal["accepted", "needs_clarification", "rejected"]
    intent: SkillUseIntent
    reason: str = ""
    missing_inputs: list[str] = Field(default_factory=list)


def extract_skill_use_intent(result: dict[str, Any]) -> SkillUseIntent | None:
    text = str(result.get("final_response") or result.get("renderable_reply_text") or "")
    parsed = _parse_json_object(text)
    if parsed:
        intent = _intent_from_card(parsed)
        if intent:
            return intent

    for message in result.get("messages") or []:
        if not isinstance(message, dict):
            continue
        intent = _intent_from_tool_call_message(message)
        if intent:
            return intent
    return None


def validate_skill_use_intent(
    intent: SkillUseIntent,
    *,
    tools: list[dict[str, Any]],
) -> SkillIntentValidation:
    tool = _find_tool(intent.skill_id, tools)
    if tool is None:
        return SkillIntentValidation(
            status="rejected",
            intent=intent,
            reason=f"skill_id 不存在：{intent.skill_id}",
        )

    schema = tool.get("input_schema") if isinstance(tool.get("input_schema"), dict) else {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = list(schema.get("required") or [])
    if properties:
        filtered = {
            key: value
            for key, value in intent.prefilled.items()
            if key in properties and str(value).strip()
        }
    else:
        filtered = {key: value for key, value in intent.prefilled.items() if str(value).strip()}

    missing = [key for key in required if not str(filtered.get(key) or "").strip()]
    normalized = intent.model_copy(update={"prefilled": filtered})
    return SkillIntentValidation(
        status="needs_clarification" if missing else "accepted",
        intent=normalized,
        reason="缺少必填字段" if missing else "accepted",
        missing_inputs=missing,
    )


def _find_tool(skill_id: str, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    for tool in tools:
        if str(tool.get("name") or "") == skill_id:
            return tool
    return None


def _intent_from_card(card: dict[str, Any]) -> SkillUseIntent | None:
    card_type = str(card.get("card_type") or "")
    data = card.get("data") if isinstance(card.get("data"), dict) else {}
    if card_type == "open_skill_app":
        return _build_intent(card, data)
    if (
        card_type == "intent_confirm"
        and str(data.get("execution_mode") or data.get("executionMode") or "") == "toolbox"
    ):
        return _build_intent(card, data)
    return None


def _build_intent(card: dict[str, Any], data: dict[str, Any]) -> SkillUseIntent | None:
    skill_id = str(data.get("skill_id") or data.get("skillId") or "")
    if not skill_id:
        return None
    prefilled = data.get("prefilled") if isinstance(data.get("prefilled"), dict) else {}
    return SkillUseIntent(
        skill_id=skill_id,
        skill_name=str(data.get("skill_name") or data.get("skillName") or skill_id),
        summary=str(data.get("summary") or ""),
        speech=str(card.get("speech") or ""),
        prefilled=dict(prefilled),
        auto_run=bool(data.get("auto_run", data.get("autoRun", True))),
    )


def _intent_from_tool_call_message(message: dict[str, Any]) -> SkillUseIntent | None:
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return None
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        name = str(function.get("name") or "")
        # Compatibility aliases only. Verify the exact native Hermes function
        # schema before relying on tool-call messages beyond card JSON.
        if name not in {"open_skill_app", "skill_app_open", "skill_use"}:
            continue
        args = _parse_json_object(str(function.get("arguments") or "")) or {}
        return _build_intent({"speech": ""}, args)
    return None


def _parse_json_object(text: str) -> dict[str, Any] | None:
    """Return the first balanced JSON object found in text.

    Boundary: if Hermes emits a non-protocol JSON/Python-dict-looking object
    before the actual skill intent, this parser returns that first object.
    Callers must still verify card_type/tool intent before accepting it.
    """
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith("```"):
        stripped = stripped.strip("`").removeprefix("json").strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass
    candidate = _first_balanced_json_object(stripped)
    if candidate is None:
        return None
    try:
        parsed = json.loads(candidate)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _first_balanced_json_object(text: str) -> str | None:
    """Extract the first balanced object, not the last or most relevant one."""
    for start, char in enumerate(text):
        if char != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            current = text[index]
            if escaped:
                escaped = False
                continue
            if current == "\\":
                escaped = True
                continue
            if current == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return None
