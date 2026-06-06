from __future__ import annotations

from typing import Any

from bridge.runtime_facade.models import RuntimeEvent
from bridge.runtime_facade.store import BaseStore
from bridge.runtime_facade.timeline import TimelineStore


class EventBus:
    def __init__(self, store: BaseStore, timeline_store: TimelineStore | None = None) -> None:
        self._store = store
        self._timeline_store = timeline_store
        self._next_event_number = 1

    def append(
        self,
        *,
        session_id: str,
        run_id: str,
        type: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=self._create_event_id(),
            session_id=session_id,
            run_id=run_id,
            trace_id=trace_id,
            type=type,
            payload=payload or {},
        )
        self._store.set("events", event.event_id, event)
        if self._timeline_store is not None:
            self._timeline_store.append_from_runtime_event(event)
        return event

    def list_by_run(
        self,
        run_id: str,
        *,
        after_event_id: str | None = None,
    ) -> list[RuntimeEvent]:
        events = [
            event
            for event in self._store.list("events")
            if isinstance(event, RuntimeEvent) and event.run_id == run_id
        ]
        if after_event_id is None:
            return events

        return [
            event
            for event in events
            if int(event.event_id.removeprefix("evt_")) > int(after_event_id.removeprefix("evt_"))
        ]

    def _create_event_id(self) -> str:
        event_id = f"evt_{self._next_event_number:06d}"
        self._next_event_number += 1
        return event_id
