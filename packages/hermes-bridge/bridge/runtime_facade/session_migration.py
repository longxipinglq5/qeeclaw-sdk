from __future__ import annotations

from datetime import timezone
from typing import Protocol

from bridge.runtime_facade.models import RuntimeSession, utc_now
from bridge.runtime_facade.session_store import SessionStore


class LegacySessionReader(Protocol):
    def get_messages(self, session_id: str) -> list[dict[str, str]]: ...


def migrate_legacy_employee_session(
    session: RuntimeSession | None,
    session_store: SessionStore,
    legacy_reader: LegacySessionReader,
) -> dict | None:
    if session is None:
        return None
    if session.metadata.get("migration"):
        return None

    legacy_session_id = session.metadata.get("legacy_employee_session_id")
    if not legacy_session_id:
        return None

    legacy_messages = legacy_reader.get_messages(str(legacy_session_id))
    imported_count = 0
    for message in legacy_messages[-12:]:
        role = message.get("role")
        content = message.get("content")
        if not role or not content:
            continue
        session_store.append_message(
            session.session_id,
            role=role,
            content=content,
            metadata={"migration": "legacy_employee_session"},
        )
        imported_count += 1

    migration = {
        "from_session_id": legacy_session_id,
        "source": "session_manager",
        "imported_message_count": imported_count,
        "summary": _build_summary(legacy_messages),
        "migrated_at": utc_now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cleanup_milestone": "Remove with VITE_HERMES_TIMELINE after two stable versions, 95% target traffic on new session ids, and Web/App/IM all reading timeline.",
    }
    session_store.update_metadata(session.session_id, {"migration": migration})
    return migration


def _build_summary(messages: list[dict[str, str]]) -> str:
    contents = [message.get("content", "") for message in messages if message.get("content")]
    return " ".join(contents)[0:240]
