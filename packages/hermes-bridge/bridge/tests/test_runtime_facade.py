from __future__ import annotations


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
        "input_text": None,
        "result_text": None,
        "error": None,
        "usage": {},
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
