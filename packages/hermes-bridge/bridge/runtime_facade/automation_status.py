from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

from bridge.runtime_facade.models import RuntimeEvent


_STAGE_PROGRESS = {
    "planning": 0,
    "awaiting_plan_review": 20,
    "generating": 35,
    "awaiting_review": 45,
    "awaiting_publish": 60,
    "awaiting_feedback": 75,
    "reviewing_auto": 85,
    "awaiting_memory": 92,
    "cycle_complete": 100,
}


class AutomationCheckpoint(BaseModel):
    checkpoint_id: str
    cycle_id: str
    approval_id: str
    status: str = "waiting"


class LoopSubstepProgress(BaseModel):
    cycle_id: str
    loop_id: str
    stage: str = "planning"
    progress_percent: int = 0


class AutomationRunStatus(BaseModel):
    run_id: str
    goal_id: str
    session_id: str
    state: Literal["running", "waiting_approval", "completed", "failed", "paused"] = "running"
    current_step: str = ""
    progress_percent: int = 0
    last_event_id: str | None = None
    heartbeat_at: datetime | None = None
    pending_approval_id: str | None = None
    child_run_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    current_cycle_id: str | None = None
    cycles: list[LoopSubstepProgress] = Field(default_factory=list)
    next_wakeup_at: datetime | None = None
    checkpoints: list[AutomationCheckpoint] = Field(default_factory=list)
    is_stale: bool = False


class AutomationStatusProjector:
    def __init__(self, *, heartbeat_timeout: timedelta | None = None) -> None:
        self._heartbeat_timeout = heartbeat_timeout or timedelta(minutes=5)

    def project(
        self,
        events: list[RuntimeEvent],
        *,
        now: datetime | None = None,
    ) -> AutomationRunStatus:
        if not events:
            raise ValueError("Automation status requires at least one event")

        first = events[0]
        status = AutomationRunStatus(
            run_id=first.run_id,
            goal_id=str(first.payload.get("goal_id") or ""),
            session_id=first.session_id,
        )
        cycles_by_id: dict[str, LoopSubstepProgress] = {}

        for event in events:
            status.last_event_id = event.event_id
            if event.type == "automation_started":
                status.goal_id = str(event.payload.get("goal_id") or status.goal_id)
                status.current_step = str(event.payload.get("current_step") or status.current_step)
                status.state = "running"
            elif event.type == "cycle_planned":
                cycle_id = str(event.payload["cycle_id"])
                cycles_by_id[cycle_id] = LoopSubstepProgress(
                    cycle_id=cycle_id,
                    loop_id=str(event.payload["loop_id"]),
                )
            elif event.type == "cycle_started":
                status.current_cycle_id = str(event.payload.get("cycle_id") or status.current_cycle_id)
            elif event.type == "loop_stage_changed":
                self._apply_stage_change(status, cycles_by_id, event)
            elif event.type == "approval_required":
                status.state = "waiting_approval"
                status.pending_approval_id = str(event.payload.get("approval_id") or "")
                status.current_cycle_id = str(event.payload.get("cycle_id") or status.current_cycle_id)
                status.current_step = str(event.payload.get("current_step") or status.current_step)
                if status.pending_approval_id and status.current_cycle_id:
                    status.checkpoints.append(
                        AutomationCheckpoint(
                            checkpoint_id=f"chk_{status.pending_approval_id}",
                            cycle_id=status.current_cycle_id,
                            approval_id=status.pending_approval_id,
                        )
                    )
            elif event.type == "human_review":
                status.pending_approval_id = None
                status.state = "running"
            elif event.type == "app_started":
                child_run_id = event.payload.get("child_run_id") or event.payload.get("run_id")
                if child_run_id:
                    _append_unique(status.child_run_ids, str(child_run_id))
            elif event.type == "artifact_created":
                artifact_id = event.payload.get("artifact_id")
                if artifact_id:
                    _append_unique(status.artifact_ids, str(artifact_id))
            elif event.type == "automation_heartbeat":
                status.heartbeat_at = _parse_datetime(str(event.payload["heartbeat_at"]))
            elif event.type == "next_cycle_planned":
                next_wakeup_at = event.payload.get("next_wakeup_at")
                if next_wakeup_at:
                    status.next_wakeup_at = _parse_datetime(str(next_wakeup_at))
            elif event.type == "automation_completed":
                status.state = "completed"
                status.pending_approval_id = None
                status.current_step = str(event.payload.get("current_step") or status.current_step)

        status.cycles = list(cycles_by_id.values())
        if status.cycles:
            status.progress_percent = round(
                sum(cycle.progress_percent for cycle in status.cycles) / len(status.cycles)
            )
        if status.state == "completed":
            status.progress_percent = 100

        status.is_stale = self._is_stale(status.heartbeat_at, now=now)
        return status

    def _apply_stage_change(
        self,
        status: AutomationRunStatus,
        cycles_by_id: dict[str, LoopSubstepProgress],
        event: RuntimeEvent,
    ) -> None:
        cycle_id = str(event.payload["cycle_id"])
        stage = str(event.payload["stage"])
        cycle = cycles_by_id.get(cycle_id)
        if cycle is None:
            cycle = LoopSubstepProgress(cycle_id=cycle_id, loop_id=str(event.payload.get("loop_id") or ""))
            cycles_by_id[cycle_id] = cycle
        updated = cycle.model_copy(
            update={
                "stage": stage,
                "progress_percent": _STAGE_PROGRESS.get(stage, cycle.progress_percent),
            }
        )
        cycles_by_id[cycle_id] = updated
        status.current_cycle_id = cycle_id

    def _is_stale(self, heartbeat_at: datetime | None, *, now: datetime | None) -> bool:
        if heartbeat_at is None:
            return False
        current = now or datetime.now(timezone.utc)
        return current - heartbeat_at > self._heartbeat_timeout


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
