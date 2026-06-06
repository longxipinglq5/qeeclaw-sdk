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


@dataclass(frozen=True)
class StoreCapabilities:
    durable: bool
    supports_retention: bool
    supports_replay: bool
    supports_cross_worker: bool
    safe_for_external_channels: bool


@dataclass(frozen=True)
class StoreReadinessResult:
    ready: bool
    warning: str | None = None
    error: dict[str, Any] | None = None


class BaseStore(Protocol):
    retention: StoreRetention
    capabilities: StoreCapabilities

    def set(self, namespace: str, key: str, value: Any) -> None: ...

    def get(self, namespace: str, key: str) -> Any | None: ...

    def list(self, namespace: str) -> list[Any]: ...

    def persist(self) -> dict[str, Any]: ...

    def restore(self) -> dict[str, Any]: ...


class InMemoryStore:
    def __init__(self, retention: StoreRetention | None = None) -> None:
        self.retention = retention or StoreRetention()
        self.capabilities = StoreCapabilities(
            durable=False,
            supports_retention=True,
            supports_replay=False,
            supports_cross_worker=False,
            safe_for_external_channels=False,
        )
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


def check_store_readiness(
    store: BaseStore,
    *,
    environment: str,
    uvicorn_workers: int = 1,
    external_channels: bool = False,
    outbox_retry: bool = False,
) -> StoreReadinessResult:
    unsafe_multi_worker = uvicorn_workers > 1 and not store.capabilities.supports_cross_worker
    unsafe_external = (
        (external_channels or outbox_retry)
        and not store.capabilities.safe_for_external_channels
    )

    if environment == "production" and (unsafe_multi_worker or unsafe_external):
        return StoreReadinessResult(
            ready=False,
            error={
                "code": "STORE_NOT_PRODUCTION_READY",
                "message": "InMemoryStore cannot run external channels or outbox retry in production",
                "details": {
                    "durable": store.capabilities.durable,
                    "supports_cross_worker": store.capabilities.supports_cross_worker,
                    "safe_for_external_channels": store.capabilities.safe_for_external_channels,
                },
            },
        )

    warning = None
    if unsafe_multi_worker or unsafe_external:
        warning = "InMemoryStore is only safe for local single-worker demos"
    return StoreReadinessResult(ready=True, warning=warning)
