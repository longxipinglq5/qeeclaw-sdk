from __future__ import annotations

import pytest


def test_approval_store_creates_pending_record_with_effect():
    from bridge.runtime_facade.approvals import ApprovalStore

    store = ApprovalStore()
    record = store.create_approval(
        approval_id="appr_publish_001",
        run_id="run_skill_001",
        session_id="edge:owner_1:supervisor:conv_abc",
        action_kind="publish_content",
        gate_type="publish",
        summary="发布朋友圈文案和配图",
        effect={"action_kind": "publish_content", "outbox_ids": []},
    )

    assert record.status == "pending"
    assert record.effect.action_kind == "publish_content"
    assert record.effect.outbox_ids == []
    assert store.get_approval("appr_publish_001") == record


def test_approval_store_supports_plan_effect_variants():
    from bridge.runtime_facade.approvals import ApprovalStore

    store = ApprovalStore()
    action_kinds = [
        "plan_review",
        "draft_review",
        "publish_content",
        "contact_customer",
        "write_memory",
        "submit_form",
        "save_automation_rule",
        "custom_action",
    ]

    records = [
        store.create_approval(
            approval_id=f"appr_{index}",
            run_id="run_001",
            session_id="session_1",
            action_kind=action_kind,
            gate_type="review",
            summary=action_kind,
            effect={"action_kind": action_kind},
        )
        for index, action_kind in enumerate(action_kinds)
    ]

    assert [record.effect.action_kind for record in records] == action_kinds


def test_write_memory_approval_does_not_write_memory_when_created():
    from bridge.runtime_facade.approvals import ApprovalStore

    store = ApprovalStore()
    record = store.create_approval(
        approval_id="appr_memory_001",
        run_id="run_001",
        session_id="session_1",
        action_kind="write_memory",
        gate_type="memory",
        summary="写入用户偏好记忆",
        effect={
            "action_kind": "write_memory",
            "memory_write": {"content": "用户偏好真实、生活化文案。"},
        },
    )

    assert record.status == "pending"
    assert record.effect.memory_write == {"content": "用户偏好真实、生活化文案。"}
    assert store.side_effects == []


def test_approval_store_transitions_to_supported_terminal_statuses():
    from bridge.runtime_facade.approvals import ApprovalAlreadyResolvedError, ApprovalStore

    store = ApprovalStore()
    store.create_approval(
        approval_id="appr_001",
        run_id="run_001",
        session_id="session_1",
        action_kind="draft_review",
        gate_type="draft",
        summary="审阅草稿",
        effect={"action_kind": "draft_review"},
    )

    approved = store.resolve_approval(
        "appr_001",
        decision="approved",
        decided_by="owner_1",
        note="可以",
    )
    assert approved.status == "approved"
    assert approved.decision == "approved"
    assert approved.decided_by == "owner_1"

    with pytest.raises(ApprovalAlreadyResolvedError):
        store.resolve_approval(
            "appr_001",
            decision="denied",
            decided_by="owner_1",
        )


@pytest.mark.parametrize(
    ("decision", "status"),
    [
        ("approved", "approved"),
        ("denied", "denied"),
        ("revision_requested", "revision_requested"),
    ],
)
def test_approval_store_decision_statuses(decision, status):
    from bridge.runtime_facade.approvals import ApprovalStore

    store = ApprovalStore()
    store.create_approval(
        approval_id=f"appr_{decision}",
        run_id="run_001",
        session_id="session_1",
        action_kind="plan_review",
        gate_type="plan",
        summary="审阅计划",
        effect={"action_kind": "plan_review"},
    )

    record = store.resolve_approval(
        f"appr_{decision}",
        decision=decision,
        decided_by="owner_1",
    )
    assert record.status == status
