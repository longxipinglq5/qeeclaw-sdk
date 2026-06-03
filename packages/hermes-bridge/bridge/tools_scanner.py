from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import yaml

from bridge.api.models import ToolInfo
from bridge.config import settings

logger = logging.getLogger(__name__)

_scan_cache: list[ToolInfo] | None = None
_scan_cache_ts: float = 0.0
_scan_lock = threading.Lock()
_CACHE_TTL = 60.0


def scan_edge_skills(force: bool = False) -> list[ToolInfo]:
    global _scan_cache, _scan_cache_ts

    with _scan_lock:
        now = time.time()
        if not force and _scan_cache is not None and (now - _scan_cache_ts) < _CACHE_TTL:
            return _scan_cache

        skills_dir = settings.hermes_home_path / "skills" / "edge"
        if not skills_dir.exists():
            logger.warning("Edge skills 目录不存在: %s", skills_dir)
            _scan_cache = []
            _scan_cache_ts = now
            return []

        tools: list[ToolInfo] = []
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                tool = _parse_skill_md(skill_md)
                if tool:
                    tools.append(tool)
            except Exception:
                logger.warning("解析 SKILL.md 失败: %s", skill_md, exc_info=True)

        logger.info("扫描到 %d 个 Edge skill", len(tools))
        _scan_cache = tools
        _scan_cache_ts = now
        return tools


def _parse_skill_md(path: Path) -> ToolInfo | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        logger.warning("SKILL.md 缺少 frontmatter: %s", path)
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("SKILL.md frontmatter 不完整: %s", path)
        return None

    _, fm_text, _ = parts
    meta = yaml.safe_load(fm_text)
    if not isinstance(meta, dict):
        return None

    name = meta.get("name") or path.parent.name
    description = meta.get("description") or ""
    category = meta.get("category")
    input_schema = _convert_input_schema(meta.get("input_schema"))
    card_template = meta.get("card_template")

    return ToolInfo(
        name=name,
        description=description,
        category=category,
        input_schema=input_schema,
        card_template=card_template,
    )


def _convert_input_schema(raw: list[dict] | dict | None) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw

    properties: dict[str, dict] = {}
    required: list[str] = []
    for field in raw:
        if not isinstance(field, dict):
            continue
        key = field.get("key")
        if not key:
            continue
        field_type = field.get("type", "string")
        properties[key] = {
            "type": field_type,
            "description": field.get("label", key),
        }
        if field.get("options"):
            properties[key]["enum"] = field["options"]
        if field.get("required"):
            required.append(key)

    result: dict = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result
