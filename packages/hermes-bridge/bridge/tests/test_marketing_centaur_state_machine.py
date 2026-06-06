from __future__ import annotations


def test_marketing_centaur_state_machine_completes_with_fake_outputs(tmp_path):
    from bridge.runtime_facade.centaur_adapter import CentaurLoopRuntimeAdapter
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.models import RunKind
    from bridge.runtime_facade.run_manager import RunManager
    from bridge.runtime_facade.store import InMemoryStore

    store = InMemoryStore()
    events = EventBus(store)
    runs = RunManager(store=store, event_bus=events)
    run = runs.start_run(
        session_id="edge:owner_1:automation:marketing_employee:goal_lamp_001",
        agent_profile="edge_automation",
        kind=RunKind.AUTOMATION_RUN,
        trace_id="trc_auto_001",
        metadata={"owner_id": "owner_1", "goal_id": "goal_lamp_001"},
    )
    adapter = CentaurLoopRuntimeAdapter(event_bus=events, run_manager=runs)

    adapter.start_run(
        run=run,
        employee_id="marketing_employee",
        goal_id="goal_lamp_001",
        input={"product": "儿童护眼台灯", "campaign_goal": "本周完成营销闭环"},
    )
    adapter.complete_marketing_flow_with_fake_outputs(
        run=runs.get(run.run_id),
        product="儿童护眼台灯",
        modification={
            "artifact_id": "art_moments_001",
            "revision_text": "朋友圈太官方了，改得更像朋友真实推荐",
        },
        metrics={
            "xiaohongshu.views": 8200,
            "xiaohongshu.likes": 310,
            "moments.leads": 12,
            "wechat_group.leads": 5,
        },
    )

    emitted = events.list_by_run(run.run_id)
    loop_order = [
        event.payload["loop_id"]
        for event in emitted
        if event.type == "loop_registered"
    ]
    assert loop_order == [
        "content_generation",
        "content_publishing",
        "customer_followup",
        "metrics_review",
    ]
    assert "automation_completed" in [event.type for event in emitted]
    artifact_ids = [
        event.payload["artifact_id"]
        for event in emitted
        if event.type == "artifact_created"
    ]
    assert artifact_ids == [
        "art_xhs_001",
        "art_moments_001",
        "art_group_followup_001",
        "art_moments_002",
    ]
    memory_events = [
        event.payload
        for event in emitted
        if event.type == "memory_write_requested"
    ]
    assert memory_events == [
        {
            "memory_candidate_id": "mem_candidate_001",
            "summary": "真实场景型朋友圈文案带来更多咨询",
        }
    ]

    final_status = adapter.project_status(run_id=run.run_id)
    assert final_status.state == "completed"
    assert final_status.progress_percent == 100
    assert final_status.artifact_ids == artifact_ids
    assert final_status.next_wakeup_at is not None
    assert [cycle.stage for cycle in final_status.cycles] == [
        "cycle_complete",
        "cycle_complete",
        "cycle_complete",
        "cycle_complete",
    ]
