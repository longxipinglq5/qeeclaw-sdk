from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal


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
    model_config = ConfigDict(extra="allow")

    text: str | None = None


class CreateRunRequest(BaseModel):
    kind: RunKind
    session_id: str
    agent_profile: str = "default"
    parent_run_id: str | None = None
    capability_id: str | None = None
    expert_id: str | None = None
    employee_id: str | None = None
    goal_id: str | None = None
    input: CreateRunInput
    output_contract: str | None = None
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
    parent_run_id: str | None = None
    artifact_id: str | None = None
    urls: RunUrls

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


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


class CapabilityManifest(BaseModel):
    capability_id: str
    kind: Literal["skill_app", "tool", "expert", "automation"]
    title: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_contract: str
    hermes_profile: str
    slash_command: str
    permissions: list[str] = Field(default_factory=list)
    approval_policy: str = "preview"


class CapabilitySelection(BaseModel):
    selection_id: str
    capability_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    context_refs: list[str] = Field(default_factory=list)
    output_contract: str | None = None
    confidence: float = 0.0
    reasoning_summary: str = ""
    missing_inputs: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    fallback_behavior: Literal[
        "run_capability",
        "ask_clarification",
        "invoke_default",
        "require_approval",
    ] = "invoke_default"
    source: str = "deterministic_rule"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExpertManifest(BaseModel):
    expert_id: str
    name: str = ""
    title: str
    description: str
    category: str = "legacy"
    source_agent_id: str = ""
    source_path: str = ""
    hermes_skill: str = ""
    recommended_tool_ids: list[str] = Field(default_factory=list)
    starter_prompts: list[str] = Field(default_factory=list)
    ui: dict[str, Any] = Field(default_factory=dict)
    context_scope: Literal["owner", "conversation"]
    hermes_profile: str
    permissions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def fill_compat_defaults(self) -> "ExpertManifest":
        if not self.name:
            self.name = self.title
        if not self.source_agent_id:
            self.source_agent_id = self.expert_id
        if not self.source_path:
            self.source_path = f"legacy/{self.expert_id}.md"
        if not self.hermes_skill:
            self.hermes_skill = self.expert_id
        return self

    def session_id_for(self, *, owner_id: str, conversation_id: str) -> str:
        base = f"edge:{owner_id}:expert:{self.expert_id}"
        if self.context_scope == "conversation":
            return f"{base}:conv:{conversation_id}"
        return base


class LinkedSession(BaseModel):
    source_session_id: str
    linked_session_id: str
    expert_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ApprovalEffect(BaseModel):
    action_kind: str
    outbox_ids: list[str] = Field(default_factory=list)
    memory_write: dict[str, Any] | None = None
    form_submission: dict[str, Any] | None = None
    automation_rule: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRecord(BaseModel):
    approval_id: str
    run_id: str
    session_id: str
    action_kind: str
    gate_type: str
    status: Literal["pending", "approved", "denied", "revision_requested"]
    summary: str
    effect: ApprovalEffect
    decision: Literal["approved", "denied", "revision_requested"] | None = None
    decided_by: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None


class RuntimeArtifact(BaseModel):
    artifact_id: str
    session_id: str
    run_id: str
    kind: str
    title: str
    content: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class CardManifest(BaseModel):
    card_id: str
    card_type: Literal[
        "result_preview",
        "artifact_reference",
        "approval_request",
        "plan_card",
        "draft_card",
        "publish_card",
        "feedback_request",
        "review_card",
        "memory_card",
        "progress_card",
        "error_card",
    ]
    title: str
    summary: str = ""
    body: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    run_id: str
    cycle_id: str | None = None
    approval_id: str | None = None
    action_kind: str | None = None
    status: str | None = None
    progress: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)
    imageUrl: str | None = None
    imagePrompt: str | None = None
    fallback_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
