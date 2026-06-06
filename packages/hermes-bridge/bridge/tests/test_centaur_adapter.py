from __future__ import annotations


async def test_post_automation_run_returns_immediately_with_urls(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(
        app.state.runtime,
        artifact_root_dir=tmp_path,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/runs",
            json={
                "kind": "automation_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {
                    "goal": "本周主推儿童护眼台灯，完成小红书、朋友圈、客户群跟进和效果复盘",
                    "employee_id": "marketing_employee",
                    "loop_package": "marketing_growth_v1",
                    "goal_id": "goal_lamp_001",
                },
                "metadata": {
                    "owner_id": "owner_1",
                    "conversation_id": "conv_abc",
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "automation_run"
    assert body["status"] == "waiting_approval"
    assert body["trace_id"] == "trc_000001"
    assert body["session_id"] == "edge:owner_1:automation:marketing_employee:goal_lamp_001"
    assert body["urls"] == {
        "status_url": "/api/runs/run_000001",
        "events_url": "/api/runs/run_000001/events",
        "stream_url": "/api/runs/run_000001/events/stream",
        "timeline_url": "/api/sessions/edge:owner_1:supervisor:conv_abc/timeline",
    }


async def test_automation_run_derives_owner_and_rejects_conflicting_metadata(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(
        app.state.runtime,
        artifact_root_dir=tmp_path,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/runs",
            json={
                "kind": "automation_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {
                    "goal": "启动营销半人马环",
                    "employee_id": "marketing_employee",
                    "goal_id": "goal_lamp_001",
                },
                "metadata": {"owner_id": "other_owner", "conversation_id": "conv_abc"},
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SESSION_OWNER_MISMATCH"


async def test_centaur_adapter_emits_initial_events_and_pauses_on_plan_approval(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(
        app.state.runtime,
        artifact_root_dir=tmp_path,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/runs",
            json={
                "kind": "automation_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {
                    "goal": "本周主推儿童护眼台灯",
                    "employee_id": "marketing_employee",
                    "loop_package": "marketing_growth_v1",
                    "goal_id": "goal_lamp_001",
                },
                "metadata": {"owner_id": "owner_1", "conversation_id": "conv_abc"},
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")
        status_resp = await client.get("/api/runs/run_000001/status")

    events = events_resp.json()["events"]
    assert [event["type"] for event in events] == [
        "run_started",
        "automation_started",
        "loop_registered",
        "loop_registered",
        "loop_registered",
        "loop_registered",
        "cycle_planned",
        "cycle_planned",
        "cycle_planned",
        "cycle_planned",
        "cycle_started",
        "loop_stage_changed",
        "work_plan",
        "approval_required",
    ]
    assert [event["payload"]["loop_id"] for event in events if event["type"] == "loop_registered"] == [
        "content_generation",
        "content_publishing",
        "customer_followup",
        "metrics_review",
    ]
    assert events[-1]["payload"]["approval_id"] == "appr_plan_001"
    status = status_resp.json()
    assert status["state"] == "waiting_approval"
    assert status["current_cycle_id"] == "cycle_content_generation_001"
    assert status["pending_approval_id"] == "appr_plan_001"


def test_centaur_adapter_falls_back_when_reviewer_omits_memory_decision(tmp_path):
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
        metadata={"goal_id": "goal_lamp_001"},
    )
    adapter = CentaurLoopRuntimeAdapter(
        event_bus=events,
        run_manager=runs,
        missing_memory_decision_policy="emit_no_memory_candidate",
    )

    adapter.handle_reviewer_done_without_memory_decision(
        run=run,
        cycle_id="cycle_review_001",
    )

    emitted = events.list_by_run(run.run_id)
    assert [event.type for event in emitted] == [
        "run_started",
        "review_output_incomplete",
        "no_memory_candidate",
        "learning_recorded",
        "cycle_completed",
    ]
    assert emitted[1].payload == {
        "cycle_id": "cycle_review_001",
        "missing": ["memory_candidate", "no_memory_candidate"],
    }
    assert emitted[2].payload == {
        "cycle_id": "cycle_review_001",
        "reason": "reviewer_omitted_memory_decision",
    }
