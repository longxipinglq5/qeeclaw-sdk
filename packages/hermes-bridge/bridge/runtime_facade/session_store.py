from __future__ import annotations

from typing import Any

from bridge.runtime_facade.models import RuntimeSession, utc_now
from bridge.runtime_facade.store import BaseStore


class SessionStore:
    def __init__(self, store: BaseStore) -> None:
        self._store = store

    def get_or_create(
        self,
        *,
        session_id: str,
        agent_profile: str,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeSession:
        existing = self._store.get("sessions", session_id)
        if isinstance(existing, RuntimeSession):
            merged_metadata = dict(existing.metadata)
            merged_metadata.update(metadata or {})
            updated = existing.model_copy(
                update={
                    "agent_profile": agent_profile,
                    "metadata": merged_metadata,
                    "updated_at": utc_now(),
                }
            )
            self._store.set("sessions", session_id, updated)
            return updated

        session = RuntimeSession(
            session_id=session_id,
            agent_profile=agent_profile,
            metadata=metadata or {},
        )
        self._store.set("sessions", session_id, session)
        self._store.set("session_messages", session_id, [])
        return session

    def get(self, session_id: str) -> RuntimeSession | None:
        session = self._store.get("sessions", session_id)
        return session if isinstance(session, RuntimeSession) else None

    def append_message(self, session_id: str, *, role: str, text: str) -> None:
        messages = list(self.list_messages(session_id))
        messages.append({"role": role, "text": text})
        self._store.set("session_messages", session_id, messages)

    def list_messages(self, session_id: str) -> list[dict[str, str]]:
        messages = self._store.get("session_messages", session_id)
        return list(messages) if isinstance(messages, list) else []
