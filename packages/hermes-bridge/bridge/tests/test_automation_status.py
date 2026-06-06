from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_automation_status_projects_required_fields_from_events():
    from bridge.runtime_facade.automation_status import AutomationStatusProjector
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore

    event_bus = EventBus(InMemoryStore())
    run_id = "run_auto_001"
    session_id = "edge:owner_1:automation:marketing_employee:goal_lamp_001"
    now = datetime(2026, 6, 6, 10, 0, tzinfo=timezone.utc)

    events = [
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="automation_started",
            payload={
                "goal_id": "goal_lamp_001",
                "current_step": "启动营销半人马环",
            },
        ),
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="cycle_planned",
            payload={"cycle_id": "cycle_content_001", "loop_id": "content_generation"},
        ),
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="loop_stage_changed",
            payload={"cycle_id": "cycle_content_001", "stage": "awaiting_plan_review"},
        ),
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="approval_required",
            payload={
                "cycle_id": "cycle_content_001",
                "approval_id": "appr_plan_001",
                "action_kind": "plan_review",
                "current_step": "等待确认内容生成计划",
            },
        ),
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="app_started",
            payload={"child_run_id": "run_skill_xhs_001"},
        ),
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="artifact_created",
            payload={"artifact_id": "art_xhs_001"},
        ),
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="automation_heartbeat",
            payload={"heartbeat_at": now.isoformat()},
        ),
        event_bus.append(
            session_id=session_id,
            run_id=run_id,
            type="next_cycle_planned",
            payload={"next_wakeup_at": "2026-06-13T09:00:00+00:00"},
        ),
    ]

    status = AutomationStatusProjector().project(events)

    assert status.run_id == run_id
    assert status.goal_id == "goal_lamp_001"
    assert status.session_id == session_id
    assert status.state == "waiting_approval"
    assert status.current_step == "等待确认内容生成计划"
    assert status.progress_percent == 20
    assert status.last_event_id == events[-1].event_id
    assert status.heartbeat_at == now
    assert status.pending_approval_id == "appr_plan_001"
    assert status.child_run_ids == ["run_skill_xhs_001"]
    assert status.artifact_ids == ["art_xhs_001"]
    assert status.current_cycle_id == "cycle_content_001"
    assert status.next_wakeup_at == datetime(2026, 6, 13, 9, 0, tzinfo=timezone.utc)
    assert [cycle.model_dump(mode="json") for cycle in status.cycles] == [
        {
            "cycle_id": "cycle_content_001",
            "loop_id": "content_generation",
            "stage": "awaiting_plan_review",
            "progress_percent": 20,
        }
    ]


def test_automation_status_can_be_reconstructed_with_fresh_projector():
    from bridge.runtime_facade.automation_status import AutomationStatusProjector
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore

    event_bus = EventBus(InMemoryStore())
    events = [
        event_bus.append(
            session_id="session_automation",
            run_id="run_auto_001",
            type="automation_started",
            payload={"goal_id": "goal_001"},
        ),
        event_bus.append(
            session_id="session_automation",
            run_id="run_auto_001",
            type="cycle_planned",
            payload={"cycle_id": "cycle_content_001", "loop_id": "content_generation"},
        ),
        event_bus.append(
            session_id="session_automation",
            run_id="run_auto_001",
            type="loop_stage_changed",
            payload={"cycle_id": "cycle_content_001", "stage": "cycle_complete"},
        ),
        event_bus.append(
            session_id="session_automation",
            run_id="run_auto_001",
            type="automation_completed",
            payload={"current_step": "自动化完成"},
        ),
    ]

    first = AutomationStatusProjector().project(events)
    reconstructed = AutomationStatusProjector().project(events)

    assert reconstructed == first
    assert reconstructed.state == "completed"
    assert reconstructed.progress_percent == 100
    assert reconstructed.cycles[0].progress_percent == 100


def test_automation_status_detects_stale_heartbeat_with_configurable_timeout():
    from bridge.runtime_facade.automation_status import AutomationStatusProjector
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore

    event_bus = EventBus(InMemoryStore())
    heartbeat_at = datetime(2026, 6, 6, 10, 0, tzinfo=timezone.utc)
    events = [
        event_bus.append(
            session_id="session_automation",
            run_id="run_auto_001",
            type="automation_started",
            payload={"goal_id": "goal_001"},
        ),
        event_bus.append(
            session_id="session_automation",
            run_id="run_auto_001",
            type="automation_heartbeat",
            payload={"heartbeat_at": heartbeat_at.isoformat()},
        ),
    ]

    fresh = AutomationStatusProjector(heartbeat_timeout=timedelta(minutes=10)).project(
        events,
        now=heartbeat_at + timedelta(minutes=5),
    )
    stale = AutomationStatusProjector(heartbeat_timeout=timedelta(minutes=10)).project(
        events,
        now=heartbeat_at + timedelta(minutes=11),
    )

    assert fresh.is_stale is False
    assert stale.is_stale is True
