from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Phase 1 assumes one uvicorn worker and one process. Concurrent request
# interleaving is acceptable because mutations are short synchronous dict
# operations with no await inside a mutation. Replace this store with a durable
# implementation for multi-worker or production ledger semantics.


@dataclass(frozen=True)
class StoreRetention:
    event_retention_after_terminal_hours: int = 24
    timeline_retention_days: int | None = None


class BaseStore(Protocol):
    retention: StoreRetention

    def set(self, namespace: str, key: str, value: Any) -> None: ...

    def get(self, namespace: str, key: str) -> Any | None: ...

    def list(self, namespace: str) -> list[Any]: ...

    def persist(self) -> dict[str, Any]: ...

    def restore(self) -> dict[str, Any]: ...


class InMemoryStore:
    def __init__(self, retention: StoreRetention | None = None) -> None:
        self.retention = retention or StoreRetention()
        self._data: dict[str, dict[str, Any]] = {}

    def set(self, namespace: str, key: str, value: Any) -> None:
        self._data.setdefault(namespace, {})[key] = value

    def get(self, namespace: str, key: str) -> Any | None:
        return self._data.get(namespace, {}).get(key)

    def list(self, namespace: str) -> list[Any]:
        return list(self._data.get(namespace, {}).values())

    def persist(self) -> dict[str, Any]:
        return {"persisted": False, "reason": "in_memory_store"}

    def restore(self) -> dict[str, Any]:
        return {"restored": False, "reason": "in_memory_store"}


def warn_if_in_memory_store_multi_worker(store: BaseStore) -> None:
    worker_count = os.environ.get("WEB_CONCURRENCY") or os.environ.get("UVICORN_WORKERS")
    if isinstance(store, InMemoryStore) and worker_count not in (None, "", "1"):
        logger.critical(
            "InMemoryStore is configured with multiple workers; use a durable store "
            "before enabling production runtime facade ledgers."
        )
