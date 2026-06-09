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


def test_loop_protocol_maps_plan_and_draft_cards_to_timeline_events():
    from bridge.runtime_facade.centaur_protocol import map_loop_message_to_timeline_event

    plan = map_loop_message_to_timeline_event(
        {
            "message_type": "plan_card",
            "cycle_id": "cycle_content_001",
            "summary": "先生成小红书，再生成朋友圈配图和客户群话术",
            "actions": [
                {"kind": "confirm", "label": "确认计划"},
                {"kind": "modify", "label": "修改计划"},
            ],
        }
    )
    draft = map_loop_message_to_timeline_event(
        {
            "message_type": "draft_card",
            "cycle_id": "cycle_content_001",
            "artifact_ids": ["art_xhs_001", "art_moments_001"],
            "summary": "已生成小红书和朋友圈草稿",
            "actions": [
                {"kind": "confirm", "label": "通过"},
                {"kind": "reject", "label": "拒绝"},
            ],
        }
    )

    assert plan["kind"] == "card"
    assert plan["role"] == "assistant"
    assert plan["card"]["card_type"] == "plan_card"
    assert plan["card"]["cycle_id"] == "cycle_content_001"
    assert plan["card"]["fallback_text"] == "先生成小红书，再生成朋友圈配图和客户群话术"
    assert draft["card"]["card_type"] == "draft_card"
    assert draft["card"]["artifact_ids"] == ["art_xhs_001", "art_moments_001"]
    assert draft["card"]["actions"] == [
        {"kind": "confirm", "label": "通过"},
        {"kind": "reject", "label": "拒绝"},
    ]


def test_loop_protocol_maps_publish_and_memory_cards_to_approval_events():
    from bridge.runtime_facade.centaur_protocol import map_loop_message_to_timeline_event

    publish = map_loop_message_to_timeline_event(
        {
            "message_type": "publish_card",
            "cycle_id": "cycle_content_001",
            "approval_id": "appr_publish_001",
            "summary": "发布朋友圈文案和配图",
        }
    )
    memory = map_loop_message_to_timeline_event(
        {
            "message_type": "memory_card",
            "cycle_id": "cycle_content_001",
            "approval_id": "appr_memory_001",
            "summary": "写入本轮营销复盘记忆",
        }
    )

    assert publish["kind"] == "approval"
    assert publish["action_kind"] == "publish_content"
    assert publish["card"]["card_type"] == "publish_card"
    assert publish["card"]["approval_id"] == "appr_publish_001"
    assert publish["card"]["action_kind"] == "publish_content"
    assert memory["kind"] == "approval"
    assert memory["action_kind"] == "write_memory"
    assert memory["card"]["card_type"] == "memory_card"
    assert memory["card"]["approval_id"] == "appr_memory_001"
    assert memory["card"]["action_kind"] == "write_memory"


def test_loop_protocol_maps_feedback_review_progress_and_cycle_complete():
    from bridge.runtime_facade.centaur_protocol import map_loop_message_to_timeline_event

    feedback = map_loop_message_to_timeline_event(
        {
            "message_type": "feedback_request",
            "cycle_id": "cycle_content_001",
            "summary": "请补充发布反馈",
        }
    )
    review = map_loop_message_to_timeline_event(
        {
            "message_type": "review_card",
            "cycle_id": "cycle_content_001",
            "metrics": {"views": 1200},
            "summary": "自动复盘完成",
        }
    )
    progress = map_loop_message_to_timeline_event(
        {
            "message_type": "progress",
            "cycle_id": "cycle_content_001",
            "progress": {"stage": "generating", "percent": 60},
            "summary": "正在生成草稿",
        }
    )
    complete = map_loop_message_to_timeline_event(
        {
            "message_type": "cycle_complete",
            "cycle_id": "cycle_content_001",
            "summary": "本轮完成",
        }
    )

    assert feedback["card"]["card_type"] == "feedback_request"
    assert review["card"]["card_type"] == "review_card"
    assert review["card"]["metrics"] == {"views": 1200}
    assert progress["card"]["card_type"] == "progress_card"
    assert progress["card"]["progress"] == {"stage": "generating", "percent": 60}
    assert complete["card"]["card_type"] == "progress_card"
    assert complete["card"]["status"] == "cycle_complete"


def test_loop_protocol_unknown_future_message_degrades_through_fallback_text():
    from bridge.runtime_facade.centaur_protocol import map_loop_message_to_timeline_event

    event = map_loop_message_to_timeline_event(
        {
            "message_type": "future_card",
            "cycle_id": "cycle_content_001",
            "summary": "未来协议消息",
            "fallback_text": "请在时间线查看最新进展。",
        }
    )

    assert event["kind"] == "card"
    assert event["card"]["card_type"] == "progress_card"
    assert event["card"]["cycle_id"] == "cycle_content_001"
    assert event["card"]["fallback_text"] == "请在时间线查看最新进展。"
