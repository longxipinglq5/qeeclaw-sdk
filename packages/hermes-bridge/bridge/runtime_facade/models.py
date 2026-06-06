from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_CLARIFICATION = "waiting_clarification"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunKind(str, Enum):
    INVOKE = "invoke"
    SKILL_RUN = "skill_run"
    EXPERT_RUN = "expert_run"
    AUTOMATION_RUN = "automation_run"
    CHANNEL_RUN = "channel_run"


class RuntimeEvent(BaseModel):
    event_id: str
    session_id: str
    run_id: str
    trace_id: str | None = None
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class RuntimeSession(BaseModel):
    session_id: str
    agent_profile: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RuntimeRun(BaseModel):
    run_id: str
    session_id: str
    agent_profile: str
    kind: RunKind = RunKind.INVOKE
    status: RunStatus = RunStatus.QUEUED
    trace_id: str | None = None
    parent_run_id: str | None = None
    created_by: str | None = None
    source: str | None = None
    input_text: str | None = None
    result_text: str | None = None
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CreateRunInput(BaseModel):
    text: str


class CreateRunRequest(BaseModel):
    kind: RunKind
    session_id: str
    agent_profile: str = "default"
    input: CreateRunInput
    context_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_owner_matches_session(self) -> "CreateRunRequest":
        owner_id = self.metadata.get("owner_id")
        if owner_id is None:
            return self

        parts = self.session_id.split(":")
        if len(parts) >= 2 and parts[0] == "edge" and parts[1] != owner_id:
            raise ValueError("metadata.owner_id conflicts with session_id owner")
        return self


class RunUrls(BaseModel):
    status_url: str
    events_url: str
    stream_url: str
    timeline_url: str | None = None

    @classmethod
    def for_run(cls, run_id: str, session_id: str) -> "RunUrls":
        return cls(
            status_url=f"/api/runs/{run_id}",
            events_url=f"/api/runs/{run_id}/events",
            stream_url=f"/api/runs/{run_id}/events/stream",
            timeline_url=f"/api/sessions/{session_id}/timeline",
        )


class CreateRunResponse(BaseModel):
    run_id: str
    session_id: str
    kind: RunKind
    status: RunStatus
    trace_id: str | None = None
    urls: RunUrls


class PromptCacheUsage(BaseModel):
    prompt_prefix_hash: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_hit_percent: float = 0.0
    turn_cache_hit_percent: float = 0.0
    context_length: int = 0
    threshold_tokens: int = 0
    last_prompt_tokens: int = 0
