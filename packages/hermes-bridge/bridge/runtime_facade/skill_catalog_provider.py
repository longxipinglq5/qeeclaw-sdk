from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from bridge.tools_scanner import scan_edge_skills


class EdgeSkillCatalogProvider:
    def __init__(
        self,
        *,
        scanner: Callable[..., list[Any]] = scan_edge_skills,
        ttl_seconds: float = 60.0,
    ) -> None:
        self._scanner = scanner
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._tools: list[dict[str, Any]] = []
        self._loaded_at = 0.0

    def preload(self) -> None:
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            now = time.time()
            if not force and self._tools and now - self._loaded_at < self._ttl_seconds:
                return list(self._tools)
            tools = self._scanner(force=force)
            self._tools = [
                tool.model_dump(mode="json") if hasattr(tool, "model_dump") else dict(tool)
                for tool in tools
            ]
            self._loaded_at = now
            return list(self._tools)

    def as_dicts(self) -> list[dict[str, Any]]:
        return self.refresh(force=False)
