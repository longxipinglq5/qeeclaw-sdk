from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml


PRIORITY_GROUP_ORDER = {
    "professional_services": 0,
    "marketing_growth": 1,
    "general": 2,
    "local_life": 3,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _edge_catalog_path() -> Path:
    return _repo_root() / "qeeshu-centaurai-edge/src/features/ai-experts/expertCatalog.ts"


def _output_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data/centaur_experts.json"


def _find_matching_brace(text: str, start: int) -> int:
    if text[start] != "{":
        raise ValueError("brace scan must start at an opening brace")
    return _find_matching_pair(text, start, "{", "}")


def _find_matching_pair(text: str, start: int, opening: str, closing: str) -> int:
    if text[start] != opening:
        raise ValueError(f"scan must start at {opening}")
    depth = 0
    quote: str | None = None
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"could not find matching {closing}")


def _parse_object_literal(block: str) -> dict[str, Any]:
    parsed = yaml.safe_load(block)
    if not isinstance(parsed, dict):
        raise ValueError("object literal did not parse to a mapping")
    return parsed


def _extract_local_life_meta(text: str) -> dict[str, dict[str, Any]]:
    marker = "const LOCAL_LIFE_EXPERT_META"
    marker_index = text.find(marker)
    if marker_index < 0:
        raise ValueError("LOCAL_LIFE_EXPERT_META not found")
    start = text.find("{", marker_index)
    end = _find_matching_brace(text, start)
    parsed = _parse_object_literal(text[start : end + 1])
    return {key: dict(value) for key, value in parsed.items()}


def _extract_raw_experts(text: str) -> list[dict[str, Any]]:
    raw_index = text.find("const RAW_AI_EXPERTS")
    if raw_index < 0:
        raise ValueError("RAW_AI_EXPERTS not found")
    equals_index = text.find("=", raw_index)
    if equals_index < 0:
        raise ValueError("RAW_AI_EXPERTS assignment not found")
    array_start = text.find("[", equals_index)
    array_end = _find_matching_pair(text, array_start, "[", "]")
    array_text = text[array_start + 1 : array_end]
    experts: list[dict[str, Any]] = []
    search_from = 0
    marker = "defineImportedExpert("
    while True:
        while search_from < len(array_text) and array_text[search_from] in {" ", "\n", "\r", "\t", ","}:
            search_from += 1
        if search_from >= len(array_text):
            break
        if array_text.startswith(marker, search_from):
            start = array_text.find("{", search_from)
            end = _find_matching_brace(array_text, start)
            experts.append(_define_imported_expert(_parse_object_literal(array_text[start : end + 1])))
            closing_paren = array_text.find(")", end)
            if closing_paren < 0:
                raise ValueError("defineImportedExpert call missing closing parenthesis")
            search_from = closing_paren + 1
            continue
        if array_text[search_from] == "{":
            end = _find_matching_brace(array_text, search_from)
            experts.append(_parse_object_literal(array_text[search_from : end + 1]))
            search_from = end + 1
            continue
        raise ValueError(f"unrecognized RAW_AI_EXPERTS element near: {array_text[search_from:search_from+80]!r}")
    if not experts:
        raise ValueError("no RAW_AI_EXPERTS entries found")
    return experts


def _assert_sorting_rule_present(text: str) -> None:
    required = [
        "RAW_AI_EXPERTS.map",
        "expert: enrichExpertForLocalLife(expert)",
        "PRIORITY_GROUP_ORDER[getExpertPriorityGroup(a.expert)]",
        "getExpertLocalLifeRank(a.expert) - getExpertLocalLifeRank(b.expert)",
        "return a.index - b.index",
    ]
    missing = [snippet for snippet in required if snippet not in text]
    if missing:
        raise ValueError(f"AI_EXPERTS sorting rule not recognized: missing {missing}")


def _source_agent_id_from_path(source_path: str) -> str:
    return Path(source_path).name.removesuffix(".md")


def _get_priority_group(expert: dict[str, Any], meta: dict[str, dict[str, Any]]) -> str:
    return expert.get("priorityGroup") or meta.get(expert["id"], {}).get("priorityGroup") or "general"


def _get_local_life_rank(expert: dict[str, Any], meta: dict[str, dict[str, Any]]) -> int:
    return int(expert.get("localLifeRank") or meta.get(expert["id"], {}).get("localLifeRank") or 999)


def _define_imported_expert(expert: dict[str, Any]) -> dict[str, Any]:
    result = dict(expert)
    result.setdefault("sourceAgentId", _source_agent_id_from_path(result["sourcePath"]))
    result.setdefault(
        "starterPrompts",
        [
            f"用{result['name']}帮我判断这个任务应该怎么做",
            f"让{result['name']}基于这些资料给我一份可执行方案",
        ],
    )
    return result


def _enrich_expert(expert: dict[str, Any], meta_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    meta = meta_by_id.get(expert["id"], {})
    merged = {**expert, **meta}
    merged["aliases"] = [*(expert.get("aliases") or []), *(meta.get("aliases") or [])]
    merged["scenarioTags"] = [*(expert.get("scenarioTags") or []), *(meta.get("scenarioTags") or [])]
    merged["businessSegments"] = [
        *(expert.get("businessSegments") or []),
        *(meta.get("businessSegments") or []),
    ]
    merged["priorityGroup"] = _get_priority_group(merged, meta_by_id)
    merged["localLifeRank"] = _get_local_life_rank(merged, meta_by_id)
    merged["hermesSkill"] = merged["id"]
    merged["contextScope"] = "owner"
    return merged


def export_experts(catalog_path: Path | None = None, output_path: Path | None = None) -> list[dict[str, Any]]:
    source_path = catalog_path or _edge_catalog_path()
    text = source_path.read_text(encoding="utf-8")
    _assert_sorting_rule_present(text)
    meta_by_id = _extract_local_life_meta(text)
    raw_experts = _extract_raw_experts(text)
    enriched = [
        {"expert": _enrich_expert(expert, meta_by_id), "index": index}
        for index, expert in enumerate(raw_experts)
    ]
    enriched.sort(
        key=lambda item: (
            PRIORITY_GROUP_ORDER[_get_priority_group(item["expert"], meta_by_id)],
            _get_local_life_rank(item["expert"], meta_by_id),
            item["index"],
        )
    )
    experts = [item["expert"] for item in enriched]
    target = output_path or _output_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(experts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return experts


def main() -> int:
    try:
        experts = export_experts()
    except Exception as exc:
        print(f"failed to export experts: {exc}", file=sys.stderr)
        return 1
    print(f"exported {len(experts)} experts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
