from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bridge.config import settings


@dataclass(frozen=True)
class ProfileContext:
    agent_profile: str
    owner_context: str = ""
    business_context: str = ""
    source: str = "edge"
    updated_at: str = ""


def _context_dir() -> Path:
    return settings.hermes_home_path / "edge" / "profile-context"


def _context_path(agent_profile: str) -> Path:
    safe_profile = "".join(
        char if char.isalnum() or char in ("-", "_", ".") else "_"
        for char in agent_profile
    )
    return _context_dir() / f"{safe_profile}.json"


def save_profile_context(context: ProfileContext) -> dict[str, Any]:
    _context_dir().mkdir(parents=True, exist_ok=True)
    payload = {
        "agent_profile": context.agent_profile,
        "owner_context": context.owner_context,
        "business_context": context.business_context,
        "source": context.source,
        "updated_at": context.updated_at,
    }
    _context_path(context.agent_profile).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def load_profile_context(agent_profile: str) -> ProfileContext | None:
    path = _context_path(agent_profile)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return ProfileContext(
        agent_profile=str(raw.get("agent_profile") or agent_profile),
        owner_context=str(raw.get("owner_context") or ""),
        business_context=str(raw.get("business_context") or ""),
        source=str(raw.get("source") or "edge"),
        updated_at=str(raw.get("updated_at") or ""),
    )


def build_profile_context_prompt(agent_profile: str) -> str:
    context = load_profile_context(agent_profile)
    if not context:
        return ""

    parts: list[str] = []
    if context.owner_context.strip():
        parts.append(f"用户资料与偏好：\n{context.owner_context.strip()}")
    if context.business_context.strip():
        parts.append(f"企业资料与业务背景：\n{context.business_context.strip()}")
    if not parts:
        return ""

    header = "## 已同步的用户与企业资料\n这些资料由 Edge 在首次打开或资料变更时同步到 Hermes Bridge。它们属于系统上下文，不是用户本轮输入。"
    return f"{header}\n\n" + "\n\n".join(parts)
