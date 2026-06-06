from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    input_text: str | None = None
    result_text: str | None = None
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
