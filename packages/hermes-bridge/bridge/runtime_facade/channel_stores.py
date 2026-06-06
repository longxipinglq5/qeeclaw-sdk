from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InboxRecord(BaseModel):
    inbox_id: str
    dedupe_key: str
    channel_key: str
    external_message_id: str
    session_id: str
    content: str
    deduped: bool = False


class InboxStore:
    def __init__(self) -> None:
        self._records_by_dedupe_key: dict[str, InboxRecord] = {}
        self._next_record_number = 1

    def record_inbound(
        self,
        *,
        channel_key: str,
        external_message_id: str,
        session_id: str,
        content: str,
    ) -> InboxRecord:
        dedupe_key = f"{channel_key}:{external_message_id}"
        existing = self._records_by_dedupe_key.get(dedupe_key)
        if existing is not None:
            return existing.model_copy(update={"deduped": True})
        record = InboxRecord(
            inbox_id=f"in_{self._next_record_number:06d}",
            dedupe_key=dedupe_key,
            channel_key=channel_key,
            external_message_id=external_message_id,
            session_id=session_id,
            content=content,
        )
        self._next_record_number += 1
        self._records_by_dedupe_key[dedupe_key] = record
        return record

    def list_records(self) -> list[InboxRecord]:
        return list(self._records_by_dedupe_key.values())


class OutboxPayload(BaseModel):
    kind: Literal[
        "text_reply",
        "card_reply",
        "publish_confirmation",
        "contact_message",
        "memory_write",
    ]
    text: str | None = None
    card: dict | None = None
    approval_id: str | None = None
    contact_id: str | None = None
    memory_candidate_id: str | None = None


class OutboxRecord(BaseModel):
    outbox_id: str
    dedupe_key: str
    run_id: str
    source_event_id: str
    channel_key: str
    conversation_key: str
    payload: OutboxPayload
    status: Literal["pending", "sent", "failed", "suppressed", "requires_approval"] = "pending"
    attempt_count: int = 1
    error: str | None = None
    provider_message_id: str | None = None
    deduped: bool = False


class OutboxNotFoundError(KeyError):
    pass


class OutboxNotRetryableError(RuntimeError):
    pass


class ChannelUnavailableError(RuntimeError):
    pass


class OutboxStore:
    def __init__(self) -> None:
        self._records_by_id: dict[str, OutboxRecord] = {}
        self._records_by_dedupe_key: dict[str, OutboxRecord] = {}
        self._next_record_number = 1

    def enqueue(
        self,
        *,
        run_id: str,
        source_event_id: str,
        channel_key: str,
        conversation_key: str,
        payload: dict,
        status: Literal["pending", "sent", "failed", "suppressed", "requires_approval"] = "pending",
        error: str | None = None,
    ) -> OutboxRecord:
        dedupe_key = f"{run_id}:{source_event_id}:{channel_key}"
        existing = self._records_by_dedupe_key.get(dedupe_key)
        if existing is not None:
            return existing.model_copy(update={"deduped": True})
        record = OutboxRecord(
            outbox_id=f"out_{self._next_record_number:06d}",
            dedupe_key=dedupe_key,
            run_id=run_id,
            source_event_id=source_event_id,
            channel_key=channel_key,
            conversation_key=conversation_key,
            payload=OutboxPayload.model_validate(payload),
            status=status,
            error=error,
        )
        self._next_record_number += 1
        self._records_by_id[record.outbox_id] = record
        self._records_by_dedupe_key[dedupe_key] = record
        return record

    def get(self, outbox_id: str) -> OutboxRecord | None:
        return self._records_by_id.get(outbox_id)

    def retry(self, outbox_id: str, *, adapter_available: bool = True) -> OutboxRecord:
        record = self.get(outbox_id)
        if record is None:
            raise OutboxNotFoundError(outbox_id)
        if record.status != "failed":
            raise OutboxNotRetryableError(outbox_id)
        if not adapter_available:
            raise ChannelUnavailableError(outbox_id)
        updated = record.model_copy(
            update={
                "status": "sent",
                "attempt_count": record.attempt_count + 1,
                "error": None,
                "provider_message_id": f"{record.channel_key}_reply_{record.attempt_count + 1:03d}",
            }
        )
        self._records_by_id[outbox_id] = updated
        self._records_by_dedupe_key[record.dedupe_key] = updated
        return updated
