from __future__ import annotations

import pytest


def test_loop_stage_order_is_stable():
    from bridge.runtime_facade.centaur_state import LoopStage

    assert [stage.value for stage in LoopStage] == [
        "planning",
        "awaiting_plan_review",
        "generating",
        "awaiting_review",
        "awaiting_publish",
        "awaiting_feedback",
        "reviewing_auto",
        "awaiting_memory",
        "cycle_complete",
    ]


def test_loop_state_guard_accepts_legal_stage_path():
    from bridge.runtime_facade.centaur_state import LoopStage, LoopStateGuard

    guard = LoopStateGuard()
    stage = LoopStage.PLANNING
    for next_stage in [
        LoopStage.AWAITING_PLAN_REVIEW,
        LoopStage.GENERATING,
        LoopStage.AWAITING_REVIEW,
        LoopStage.AWAITING_PUBLISH,
        LoopStage.AWAITING_FEEDBACK,
        LoopStage.REVIEWING_AUTO,
        LoopStage.AWAITING_MEMORY,
        LoopStage.CYCLE_COMPLETE,
    ]:
        assert guard.can_transition("cycle_001", stage, next_stage)
        stage = next_stage


def test_loop_state_guard_rejects_invalid_stage_skip():
    from bridge.runtime_facade.centaur_state import InvalidLoopTransitionError, LoopStage, LoopStateGuard

    guard = LoopStateGuard()
    with pytest.raises(InvalidLoopTransitionError):
        guard.require_transition(
            "cycle_001",
            LoopStage.PLANNING,
            LoopStage.GENERATING,
        )


def test_cycle_complete_requires_memory_or_no_memory_candidate_event():
    from bridge.runtime_facade.centaur_state import InvalidLoopTransitionError, LoopStage, LoopStateGuard

    guard = LoopStateGuard()
    with pytest.raises(InvalidLoopTransitionError):
        guard.require_transition(
            "cycle_001",
            LoopStage.REVIEWING_AUTO,
            LoopStage.CYCLE_COMPLETE,
        )

    guard.record_runtime_event("cycle_001", "no_memory_candidate")
    assert guard.require_transition(
        "cycle_001",
        LoopStage.REVIEWING_AUTO,
        LoopStage.CYCLE_COMPLETE,
    ) == LoopStage.CYCLE_COMPLETE


def test_next_round_creates_new_cycle_instead_of_resetting_completed_cycle():
    from bridge.runtime_facade.centaur_state import LoopStage, create_next_cycle

    completed = {
        "cycle_id": "cycle_content_generation_001",
        "loop_id": "content_generation",
        "index": 1,
        "stage": LoopStage.CYCLE_COMPLETE,
    }

    next_cycle = create_next_cycle(completed)

    assert completed["stage"] == LoopStage.CYCLE_COMPLETE
    assert next_cycle["cycle_id"] == "cycle_content_generation_002"
    assert next_cycle["loop_id"] == "content_generation"
    assert next_cycle["index"] == 2
    assert next_cycle["stage"] == LoopStage.PLANNING


def test_approval_required_is_rejected_before_matching_checkpoint_exists():
    from bridge.runtime_facade.human_gates import (
        ApprovalCheckpointMissingError,
        HumanCheckpoint,
        require_approval_checkpoint,
    )

    with pytest.raises(ApprovalCheckpointMissingError):
        require_approval_checkpoint(
            checkpoints=[],
            cycle_id="cycle_content_001",
            approval_id="appr_plan_001",
        )

    checkpoint = HumanCheckpoint(
        checkpoint_id="chk_plan_001",
        cycle_id="cycle_content_001",
        gate_id="plan_review",
        type="plan_review",
        status="waiting",
        approval_id="appr_plan_001",
    )

    assert require_approval_checkpoint(
        checkpoints=[checkpoint],
        cycle_id="cycle_content_001",
        approval_id="appr_plan_001",
    ) == checkpoint


def test_human_gate_timeout_actions_emit_stable_events():
    from bridge.runtime_facade.centaur_state import LoopStage, LoopStateGuard
    from bridge.runtime_facade.human_gates import (
        HumanCheckpoint,
        HumanGateConfig,
        handle_checkpoint_timeout,
    )

    checkpoint = HumanCheckpoint(
        checkpoint_id="chk_plan_001",
        cycle_id="cycle_content_001",
        gate_id="plan_review",
        type="plan_review",
        status="waiting",
        approval_id="appr_plan_001",
    )
    guard = LoopStateGuard()

    reminder = handle_checkpoint_timeout(
        HumanGateConfig(gate_id="plan_review", type="plan_review", timeout_action="remind"),
        checkpoint,
        guard=guard,
        current_stage=LoopStage.AWAITING_PLAN_REVIEW,
        next_stage=LoopStage.GENERATING,
    )
    skipped = handle_checkpoint_timeout(
        HumanGateConfig(gate_id="plan_review", type="plan_review", timeout_action="skip"),
        checkpoint,
        guard=guard,
        current_stage=LoopStage.AWAITING_PLAN_REVIEW,
        next_stage=LoopStage.GENERATING,
    )
    paused = handle_checkpoint_timeout(
        HumanGateConfig(gate_id="plan_review", type="plan_review", timeout_action="pause"),
        checkpoint,
        guard=guard,
        current_stage=LoopStage.AWAITING_PLAN_REVIEW,
        next_stage=LoopStage.GENERATING,
    )

    assert reminder == {
        "event_type": "reminder",
        "cycle_id": "cycle_content_001",
        "checkpoint_id": "chk_plan_001",
        "stage": LoopStage.AWAITING_PLAN_REVIEW,
        "advance_blocked": False,
    }
    assert skipped == {
        "event_type": "checkpoint_skipped",
        "cycle_id": "cycle_content_001",
        "checkpoint_id": "chk_plan_001",
        "stage": LoopStage.GENERATING,
        "advance_blocked": False,
    }
    assert paused == {
        "event_type": "automation_paused",
        "cycle_id": "cycle_content_001",
        "checkpoint_id": "chk_plan_001",
        "stage": LoopStage.AWAITING_PLAN_REVIEW,
        "advance_blocked": True,
    }


def test_skip_timeout_cannot_bypass_loop_state_guard():
    from bridge.runtime_facade.centaur_state import InvalidLoopTransitionError, LoopStage, LoopStateGuard
    from bridge.runtime_facade.human_gates import (
        HumanCheckpoint,
        HumanGateConfig,
        handle_checkpoint_timeout,
    )

    checkpoint = HumanCheckpoint(
        checkpoint_id="chk_plan_001",
        cycle_id="cycle_content_001",
        gate_id="plan_review",
        type="plan_review",
        status="waiting",
        approval_id="appr_plan_001",
    )

    with pytest.raises(InvalidLoopTransitionError):
        handle_checkpoint_timeout(
            HumanGateConfig(gate_id="plan_review", type="plan_review", timeout_action="skip"),
            checkpoint,
            guard=LoopStateGuard(),
            current_stage=LoopStage.PLANNING,
            next_stage=LoopStage.GENERATING,
        )
