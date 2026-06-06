from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from bridge.runtime_facade.centaur_state import LoopStage, LoopStateGuard


class ApprovalCheckpointMissingError(RuntimeError):
    pass


class HumanGateConfig(BaseModel):
    gate_id: str
    type: str
    timeout_action: Literal["remind", "skip", "pause"] = "remind"


class HumanCheckpoint(BaseModel):
    checkpoint_id: str
    cycle_id: str
    gate_id: str
    type: str
    status: Literal["waiting", "resolved", "skipped", "paused"] = "waiting"
    approval_id: str


def require_approval_checkpoint(
    *,
    checkpoints: list[HumanCheckpoint],
    cycle_id: str,
    approval_id: str,
) -> HumanCheckpoint:
    for checkpoint in checkpoints:
        if checkpoint.cycle_id == cycle_id and checkpoint.approval_id == approval_id:
            return checkpoint
    raise ApprovalCheckpointMissingError(
        f"approval_required without checkpoint: {cycle_id}/{approval_id}"
    )


def handle_checkpoint_timeout(
    config: HumanGateConfig,
    checkpoint: HumanCheckpoint,
    *,
    guard: LoopStateGuard,
    current_stage: LoopStage,
    next_stage: LoopStage,
) -> dict[str, object]:
    if config.timeout_action == "remind":
        return _timeout_event("reminder", checkpoint, current_stage, advance_blocked=False)

    if config.timeout_action == "pause":
        return _timeout_event(
            "automation_paused",
            checkpoint,
            current_stage,
            advance_blocked=True,
        )

    stage = guard.require_transition(checkpoint.cycle_id, current_stage, next_stage)
    return _timeout_event("checkpoint_skipped", checkpoint, stage, advance_blocked=False)


def _timeout_event(
    event_type: str,
    checkpoint: HumanCheckpoint,
    stage: LoopStage,
    *,
    advance_blocked: bool,
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "cycle_id": checkpoint.cycle_id,
        "checkpoint_id": checkpoint.checkpoint_id,
        "stage": stage,
        "advance_blocked": advance_blocked,
    }
