"""
QeeClaw Memory Store — Bridge 层轻量记忆存储

为 SDK 的 MemoryModule 提供后端实现，匹配 /api/platform/memory/* 接口。
数据以 JSON 文件持久化，支持按 agent_id / team_id / runtime_type 过滤。

后续可升级为：
- 接入 hermes-agent 的 MemoryManager（当 AgentPool 就绪后）
- 使用向量检索替代简单文本匹配
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

_HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.qeeclaw_hermes"))
_MEMORY_DIR = os.path.join(_HERMES_HOME, "memory")
_MEMORY_FILE = os.path.join(_MEMORY_DIR, "entries.json")


# ---------------------------------------------------------------------------
# 内存存储
# ---------------------------------------------------------------------------

_entries: List[Dict[str, Any]] = []
_lock = threading.Lock()
_initialized = False


def _ensure_init():
    global _initialized, _entries
    if _initialized:
        return
    _initialized = True
    os.makedirs(_MEMORY_DIR, exist_ok=True)
    if os.path.isfile(_MEMORY_FILE):
        try:
            with open(_MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    _entries = data
        except Exception as e:
            print(f"[memory-store] WARNING: Failed to load {_MEMORY_FILE}: {e}")


def _persist():
    """将内存数据写入磁盘。"""
    try:
        os.makedirs(_MEMORY_DIR, exist_ok=True)
        with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_entries, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[memory-store] WARNING: Failed to persist: {e}")


def _matches_scope(entry: dict, scope: dict) -> bool:
    """检查 entry 是否匹配给定的 scope 过滤条件。"""
    for key in ("team_id", "runtime_type", "device_id", "agent_id"):
        val = scope.get(key)
        if val is not None and str(entry.get(key, "")) != str(val):
            return False
    return True


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def store_memory(
    content: str,
    category: str = "other",
    importance: float = 0.5,
    team_id: Any = None,
    runtime_type: str = "openclaw",
    device_id: Any = None,
    agent_id: Any = None,
    source_session: Optional[str] = None,
    skip_duplicate_check: bool = False,
) -> Dict[str, Any]:
    """存入一条记忆。"""
    _ensure_init()
    with _lock:
        # 去重检查
        if not skip_duplicate_check:
            for e in _entries:
                if (
                    e.get("content") == content
                    and e.get("agent_id") == agent_id
                    and e.get("runtime_type") == runtime_type
                ):
                    return e  # 已存在，直接返回

        entry = {
            "id": f"mem-{int(time.time() * 1000)}",
            "content": content,
            "category": category,
            "importance": importance,
            "team_id": team_id,
            "runtime_type": runtime_type or "openclaw",
            "device_id": device_id,
            "agent_id": agent_id,
            "source_session": source_session,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _entries.insert(0, entry)
        _persist()
        return entry


def search_memory(
    query: str,
    limit: int = 5,
    threshold: float = 0.0,
    scope: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """搜索记忆（当前为简单文本匹配，后续可升级为向量检索）。"""
    _ensure_init()
    scope = scope or {}
    query_lower = query.lower()
    with _lock:
        results = []
        for entry in _entries:
            if not _matches_scope(entry, scope):
                continue
            if query_lower and query_lower not in entry.get("content", "").lower():
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results


def delete_memory(entry_id: str, scope: Optional[Dict[str, Any]] = None) -> bool:
    """删除单条记忆。"""
    _ensure_init()
    scope = scope or {}
    with _lock:
        for i, entry in enumerate(_entries):
            if entry.get("id") == entry_id and _matches_scope(entry, scope):
                _entries.pop(i)
                _persist()
                return True
    return False


def clear_agent_memory(
    agent_id: str,
    scope: Optional[Dict[str, Any]] = None,
) -> int:
    """清除某个 agent 的全部记忆。"""
    _ensure_init()
    scope = scope or {}
    scope["agent_id"] = agent_id
    with _lock:
        cleared = 0
        i = len(_entries) - 1
        while i >= 0:
            if _matches_scope(_entries[i], scope):
                _entries.pop(i)
                cleared += 1
            i -= 1
        if cleared:
            _persist()
        return cleared


def get_memory_stats(scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取记忆统计信息。"""
    _ensure_init()
    scope = scope or {}
    with _lock:
        scoped = [e for e in _entries if _matches_scope(e, scope)]
        by_category: Dict[str, int] = {}
        for e in scoped:
            cat = e.get("category", "other")
            by_category[cat] = by_category.get(cat, 0) + 1
        return {
            "total": len(scoped),
            "by_category": by_category,
        }
