from __future__ import annotations

from typing import Any

from bridge.config import settings
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

    def update_metadata(self, session_id: str, metadata: dict[str, Any]) -> RuntimeSession:
        session = self.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        merged_metadata = dict(session.metadata)
        merged_metadata.update(metadata)
        updated = session.model_copy(
            update={"metadata": merged_metadata, "updated_at": utc_now()}
        )
        self._store.set("sessions", session_id, updated)
        return updated

    def list(self) -> list[RuntimeSession]:
        return [
            session
            for session in self._store.list("sessions")
            if isinstance(session, RuntimeSession)
        ]

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str | None = None,
        text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        message_content = content if content is not None else text
        if message_content is None:
            raise ValueError("content is required")

        messages = list(self.get_recent_messages(session_id, limit=None))
        messages.append(
            {
                "role": role,
                "content": message_content,
                "metadata": metadata or {},
            }
        )
        self._store.set("session_messages", session_id, messages)

    def append_turn(
        self,
        session_id: str,
        *,
        user_text: str,
        assistant_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.append_message(
            session_id,
            role="user",
            content=user_text,
            metadata=metadata,
        )
        self.append_message(
            session_id,
            role="assistant",
            content=assistant_text,
            metadata=metadata,
        )

    def get_recent_messages(
        self,
        session_id: str,
        *,
        limit: int | None = settings.context_recent_message_limit,
        token_budget: int | None = settings.context_recent_token_budget,
    ) -> list[dict[str, Any]]:
        messages = self._canonical_messages(session_id)
        if limit is not None:
            messages = messages[-limit:]
        if token_budget is None:
            return messages

        selected: list[dict[str, Any]] = []
        used_tokens = 0
        for message in reversed(messages):
            token_count = self.approx_token_count(message["content"])
            if selected and used_tokens + token_count > token_budget:
                break
            if not selected and token_count > token_budget:
                continue
            selected.append(message)
            used_tokens += token_count
        return list(reversed(selected))

    def approx_token_count(self, content: str) -> int:
        return max(1, -(-len(content) // 4))

    def list_messages(self, session_id: str) -> list[dict[str, str]]:
        return [
            {"role": message["role"], "text": message["content"]}
            for message in self._canonical_messages(session_id)
        ]

    def _canonical_messages(self, session_id: str) -> list[dict[str, Any]]:
        messages = self._store.get("session_messages", session_id)
        if not isinstance(messages, list):
            return []

        canonical: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("content", message.get("text", ""))
            canonical.append(
                {
                    "role": str(message.get("role", "")),
                    "content": str(content),
                    "metadata": dict(message.get("metadata") or {}),
                }
            )
        return canonical
