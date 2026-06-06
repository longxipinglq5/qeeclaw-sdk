from __future__ import annotations

import asyncio


def _json_datetime(value):
    return value.isoformat().replace("+00:00", "Z")


def test_runtime_models_have_stable_defaults_and_serialization():
    from bridge.runtime_facade import (
        RunKind,
        RunStatus,
        RuntimeEvent,
        RuntimeRun,
        RuntimeSession,
    )

    session = RuntimeSession(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
    )
    assert session.metadata == {}
    assert session.model_dump(mode="json") == {
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "agent_profile": "edge_supervisor",
        "metadata": {},
        "created_at": _json_datetime(session.created_at),
        "updated_at": _json_datetime(session.updated_at),
    }

    run = RuntimeRun(
        run_id="run_inv_001",
        session_id=session.session_id,
        agent_profile=session.agent_profile,
    )
    assert run.kind == RunKind.INVOKE
    assert run.status == RunStatus.QUEUED
    assert run.input_text is None
    assert run.result_text is None
    assert run.error is None
    assert run.usage == {}
    assert run.model_dump(mode="json") == {
        "run_id": "run_inv_001",
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "agent_profile": "edge_supervisor",
        "kind": "invoke",
        "status": "queued",
        "trace_id": None,
        "parent_run_id": None,
        "created_by": None,
        "source": None,
        "input_text": None,
        "result_text": None,
        "error": None,
        "usage": {},
        "metadata": {},
        "created_at": _json_datetime(run.created_at),
        "updated_at": _json_datetime(run.updated_at),
    }

    event = RuntimeEvent(
        event_id="evt_001",
        session_id=session.session_id,
        run_id=run.run_id,
        type="run_started",
        payload={"kind": RunKind.INVOKE},
    )
    assert event.model_dump(mode="json") == {
        "event_id": "evt_001",
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "run_id": "run_inv_001",
        "trace_id": None,
        "type": "run_started",
        "payload": {"kind": "invoke"},
        "created_at": _json_datetime(event.created_at),
    }


def test_runtime_model_enums_cover_plan_values():
    from bridge.runtime_facade import RunKind, RunStatus

    assert {status.value for status in RunStatus} == {
        "queued",
        "running",
        "waiting_approval",
        "waiting_clarification",
        "completed",
        "failed",
        "cancelled",
    }
    assert {kind.value for kind in RunKind} == {
        "invoke",
        "skill_run",
        "expert_run",
        "automation_run",
        "channel_run",
    }


def test_session_id_builder_creates_canonical_ids():
    from bridge.runtime_facade.session_ids import SessionIdBuilder

    assert (
        SessionIdBuilder.supervisor("owner_1", "conv_abc")
        == "edge:owner_1:supervisor:conv_abc"
    )
    assert (
        SessionIdBuilder.expert("owner_1", "marketing_strategy_expert")
        == "edge:owner_1:expert:marketing_strategy_expert"
    )
    assert (
        SessionIdBuilder.channel("owner_1", "wechat", "room_42")
        == "edge:owner_1:channel:wechat:room_42"
    )
    assert (
        SessionIdBuilder.automation("owner_1", "marketing_employee", "goal_001")
        == "edge:owner_1:automation:marketing_employee:goal_001"
    )


def test_in_memory_store_contract_for_phase_one():
    from bridge.runtime_facade.store import InMemoryStore

    store = InMemoryStore()
    store.set("sessions", "session_1", {"message_count": 1})
    store.set("sessions", "session_2", {"message_count": 2})

    assert store.get("sessions", "session_1") == {"message_count": 1}
    assert store.get("sessions", "missing") is None
    assert store.list("sessions") == [
        {"message_count": 1},
        {"message_count": 2},
    ]
    assert store.persist() == {
        "persisted": False,
        "reason": "in_memory_store",
    }
    assert store.restore() == {
        "restored": False,
        "reason": "in_memory_store",
    }
    assert store.retention.event_retention_after_terminal_hours == 24
    assert store.retention.timeline_retention_days is None


def test_event_bus_appends_and_reads_ordered_run_events():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore

    bus = EventBus(InMemoryStore())
    first = bus.append(
        session_id="session_1",
        run_id="run_1",
        type="run_started",
        payload={"status": "running"},
    )
    second = bus.append(
        session_id="session_1",
        run_id="run_1",
        type="token",
        payload={"text": "第一句"},
    )
    bus.append(
        session_id="session_1",
        run_id="run_2",
        type="run_started",
        payload={},
    )

    assert first.event_id == "evt_000001"
    assert second.event_id == "evt_000002"
    assert [event.type for event in bus.list_by_run("run_1")] == [
        "run_started",
        "token",
    ]
    assert [event.event_id for event in bus.list_by_run("run_1", after_event_id=first.event_id)] == [
        "evt_000002",
    ]


def test_session_store_creates_updates_and_preserves_message_order():
    from bridge.runtime_facade.session_store import SessionStore
    from bridge.runtime_facade.store import InMemoryStore

    sessions = SessionStore(InMemoryStore())
    session = sessions.get_or_create(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        metadata={"owner_id": "owner_1"},
    )

    assert session.session_id == "edge:owner_1:supervisor:conv_abc"
    assert session.agent_profile == "edge_supervisor"
    assert session.metadata == {"owner_id": "owner_1"}

    updated = sessions.get_or_create(
        session_id=session.session_id,
        agent_profile="edge_supervisor",
        metadata={"conversation_id": "conv_abc"},
    )
    assert updated.metadata == {
        "owner_id": "owner_1",
        "conversation_id": "conv_abc",
    }
    assert updated.updated_at >= session.updated_at

    sessions.append_message(session.session_id, role="user", text="第一句")
    sessions.append_message(session.session_id, role="assistant", text="第二句")

    assert sessions.list_messages(session.session_id) == [
        {"role": "user", "text": "第一句"},
        {"role": "assistant", "text": "第二句"},
    ]


def test_run_manager_creates_runs_and_emits_lifecycle_events():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.models import RunStatus
    from bridge.runtime_facade.run_manager import RunManager
    from bridge.runtime_facade.store import InMemoryStore

    store = InMemoryStore()
    events = EventBus(store)
    runs = RunManager(store=store, event_bus=events)

    run = runs.start_run(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        input_text="帮我总结",
    )
    assert run.run_id == "run_000001"
    assert run.status == RunStatus.RUNNING
    assert run.input_text == "帮我总结"
    assert [event.type for event in events.list_by_run(run.run_id)] == ["run_started"]

    completed = runs.complete_run(
        run.run_id,
        result_text="总结完成",
        usage={"input_tokens": 12, "output_tokens": 4},
    )
    assert completed.status == RunStatus.COMPLETED
    assert completed.result_text == "总结完成"
    assert completed.usage == {"input_tokens": 12, "output_tokens": 4}
    assert [event.type for event in events.list_by_run(run.run_id)] == [
        "run_started",
        "done",
    ]

    failed = runs.start_run(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
    )
    failed = runs.fail_run(failed.run_id, error="provider failed")
    assert failed.status == RunStatus.FAILED
    assert failed.error == "provider failed"
    assert [event.type for event in events.list_by_run(failed.run_id)] == [
        "run_started",
        "error",
    ]


class FakeLegacyRuntime:
    def __init__(self):
        self.invoke_calls = []
        self.stream_calls = []

    async def invoke_raw(self, **kwargs):
        self.invoke_calls.append(kwargs)
        return {
            "final_response": "测试回复",
            "completed": True,
            "failed": False,
            "model": "deepseek-v4-pro",
            "provider": "deepseek",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }

    async def stream_raw(self, **kwargs):
        from bridge.runtime import StreamHandle

        self.stream_calls.append(kwargs)
        queue = asyncio.Queue()

        async def _run():
            await queue.put(("delta", "第一句"))
            await queue.put(("delta", "第二句"))
            await queue.put(("done", "最终回复"))

        return StreamHandle(queue=queue, task=asyncio.create_task(_run()))


async def test_facade_invoke_raw_wraps_legacy_runtime_and_records_events():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)

    result = await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="你好",
        agent_profile="edge_supervisor",
        system_prompt="你是主管",
    )

    assert legacy.invoke_calls == [
        {
            "session_id": "edge:owner_1:supervisor:conv_abc",
            "user_text": "你好",
            "agent_profile": "edge_supervisor",
            "system_prompt": "你是主管",
        }
    ]
    assert result["final_response"] == "测试回复"
    assert result["run_id"] == "run_000001"
    assert result["session_id"] == "edge:owner_1:supervisor:conv_abc"
    assert result["agent_profile"] == "edge_supervisor"

    run = facade.get_run("run_000001")
    assert run is not None
    assert run.result_text == "测试回复"
    assert [event.type for event in facade.get_run_events("run_000001")] == [
        "run_started",
        "metering",
        "done",
    ]


async def test_facade_stream_raw_wraps_legacy_stream_and_records_events():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)

    handle = await facade.stream_raw(
        session_id="edge:owner_1:supervisor:conv_stream",
        user_text="写三句朋友圈文案",
        agent_profile="edge_supervisor",
        system_prompt=None,
    )

    chunks = []
    while True:
        event_type, payload = await handle.queue.get()
        chunks.append((event_type, payload))
        if event_type in {"done", "error"}:
            break

    assert chunks == [
        ("delta", "第一句"),
        ("delta", "第二句"),
        ("done", "最终回复"),
    ]
    assert legacy.stream_calls == [
        {
            "session_id": "edge:owner_1:supervisor:conv_stream",
            "user_text": "写三句朋友圈文案",
            "agent_profile": "edge_supervisor",
            "system_prompt": None,
        }
    ]
    assert [event.type for event in facade.get_run_events("run_000001")] == [
        "run_started",
        "token",
        "token",
        "done",
    ]


async def test_run_and_session_rest_apis_read_facade_state():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)
    await app.state.runtime_facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="你好",
        agent_profile="edge_supervisor",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.get("/api/runs/run_000001")
        events_resp = await client.get("/api/runs/run_000001/events")
        sessions_resp = await client.get("/api/sessions")
        session_resp = await client.get("/api/sessions/edge:owner_1:supervisor:conv_abc")
        missing_resp = await client.get("/api/runs/run_missing")

    assert run_resp.status_code == 200
    assert run_resp.json()["run"]["run_id"] == "run_000001"
    assert events_resp.status_code == 200
    assert [event["type"] for event in events_resp.json()["events"]] == [
        "run_started",
        "metering",
        "done",
    ]
    assert sessions_resp.status_code == 200
    assert sessions_resp.json()["sessions"][0]["session_id"] == "edge:owner_1:supervisor:conv_abc"
    assert session_resp.status_code == 200
    assert session_resp.json()["session"]["agent_profile"] == "edge_supervisor"
    assert missing_resp.status_code == 404


async def test_run_event_sse_stream_replays_events_and_honors_last_event_id():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)
    await app.state.runtime_facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="你好",
        agent_profile="edge_supervisor",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        stream_resp = await client.get("/api/runs/run_000001/events/stream")
        replay_resp = await client.get(
            "/api/runs/run_000001/events/stream",
            headers={"Last-Event-ID": "evt_000001"},
        )

    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers["content-type"]
    assert "id: evt_000001" in stream_resp.text
    assert "event: run_started" in stream_resp.text
    assert "event: metering" in stream_resp.text
    assert "event: done" in stream_resp.text

    assert replay_resp.status_code == 200
    assert "id: evt_000001" not in replay_resp.text
    assert "id: evt_000002" in replay_resp.text
    assert "id: evt_000003" in replay_resp.text
