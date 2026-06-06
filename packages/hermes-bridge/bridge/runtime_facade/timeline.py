from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from bridge.runtime_facade.models import RuntimeEvent


_STANDARD_EVENT_TYPES = {
    "artifact_created",
    "app_result",
    "approval_required",
    "clarify_required",
    "work_plan",
    "human_review",
    "memory_candidate",
    "loop_stage_changed",
    "feedback_request",
    "review_card",
    "error",
    "cancelled",
}

_DEBUG_EVENT_TYPES = {
    "capability_selected",
    "app_started",
    "done",
}


class TimelineEvent(BaseModel):
    event_id: str
    source_event_id: str
    source_event_type: str
    session_id: str
    run_id: str
    source: str = "runtime"
    kind: str
    role: str = "assistant"
    cursor: str
    artifact_id: str | None = None
    card: dict[str, Any] | None = None
    text: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    read_at: str | None = None
    seen_by: list[str] = Field(default_factory=list)


class TimelineProjectionFilter(BaseModel):
    mode: Literal["standard", "debug"] = "standard"

    def includes(self, event: RuntimeEvent) -> bool:
        if event.type in _STANDARD_EVENT_TYPES:
            return True
        return self.mode == "debug" and event.type in _DEBUG_EVENT_TYPES


class TimelinePage(BaseModel):
    events: list[TimelineEvent]
    next_cursor: str | None = None
    has_more: bool = False


class TimelineStore:
    def __init__(self, projection_filter: TimelineProjectionFilter | None = None) -> None:
        self._filter = projection_filter or TimelineProjectionFilter()
        self._events: list[TimelineEvent] = []
        self._events_by_source_event_id: dict[str, TimelineEvent] = {}
        self._next_timeline_number = 1

    def append_from_runtime_event(self, event: RuntimeEvent) -> TimelineEvent | None:
        existing = self._events_by_source_event_id.get(event.event_id)
        if existing is not None:
            return existing
        if not self._filter.includes(event):
            return None

        timeline_event_id = self._create_timeline_event_id()
        projected = self._project_event(event, timeline_event_id)
        self._events.append(projected)
        self._events_by_source_event_id[event.event_id] = projected
        return projected

    def list_session(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> TimelinePage:
        events = [event for event in self._events if event.session_id == session_id]
        if cursor:
            events = [
                event
                for event in events
                if int(event.cursor.removeprefix("tl_")) > int(cursor.removeprefix("tl_"))
            ]
        page_events = events[:limit]
        return TimelinePage(
            events=page_events,
            next_cursor=page_events[-1].cursor if page_events else cursor,
            has_more=len(events) > len(page_events),
        )

    def _project_event(self, event: RuntimeEvent, timeline_event_id: str) -> TimelineEvent:
        kind = self._kind_for(event)
        return TimelineEvent(
            event_id=timeline_event_id,
            source_event_id=event.event_id,
            source_event_type=event.type,
            session_id=event.session_id,
            run_id=event.run_id,
            source=self._source_for(event),
            kind=kind,
            role=self._role_for(event),
            cursor=timeline_event_id,
            artifact_id=event.payload.get("artifact_id") if kind == "artifact" else None,
            card=self._card_for(event),
            text=self._text_for(event),
            payload=event.payload,
        )

    def _create_timeline_event_id(self) -> str:
        event_id = f"tl_{self._next_timeline_number:06d}"
        self._next_timeline_number += 1
        return event_id

    @staticmethod
    def _kind_for(event: RuntimeEvent) -> str:
        if event.type == "artifact_created":
            return "artifact"
        if event.type in {
            "app_result",
            "approval_required",
            "clarify_required",
            "work_plan",
            "memory_candidate",
            "loop_stage_changed",
            "feedback_request",
            "review_card",
        }:
            return "card"
        if event.type == "human_review":
            return "approval"
        if event.type in {"error", "cancelled"}:
            return "system"
        return "debug"

    @staticmethod
    def _source_for(event: RuntimeEvent) -> str:
        if event.run_id.startswith("run_skill") or event.type in {"app_result", "artifact_created"}:
            return "skill"
        if event.run_id.startswith("run_auto") or "cycle_id" in event.payload:
            return "automation"
        return "runtime"

    @staticmethod
    def _role_for(event: RuntimeEvent) -> str:
        if event.type == "human_review":
            return "user"
        return "assistant"

    @staticmethod
    def _text_for(event: RuntimeEvent) -> str | None:
        if event.type in {"error", "cancelled", "done"}:
            return str(event.payload.get("text") or event.payload.get("error") or event.type)
        return None

    @staticmethod
    def _card_for(event: RuntimeEvent) -> dict[str, Any] | None:
        if event.type == "app_result":
            card = event.payload.get("card")
            return card if isinstance(card, dict) else None
        if event.type == "loop_stage_changed":
            cycle_id = str(event.payload["cycle_id"])
            return {
                "card_id": f"card_progress_{cycle_id}",
                "card_type": "progress_card",
                "cycle_id": cycle_id,
                "status": event.payload.get("stage"),
                "summary": str(event.payload.get("summary") or event.payload.get("stage") or ""),
                "fallback_text": str(event.payload.get("summary") or event.payload.get("stage") or ""),
            }
        if event.type in {
            "approval_required",
            "clarify_required",
            "work_plan",
            "memory_candidate",
            "feedback_request",
            "review_card",
        }:
            return {
                "card_id": f"card_{event.type}_{event.event_id}",
                "card_type": "progress_card" if event.type != "approval_required" else "approval_request",
                "summary": str(event.payload.get("summary") or event.type),
                "fallback_text": str(event.payload.get("summary") or event.type),
            }
        return None
