from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from bridge.tests.test_runtime_facade import FakeLegacyRuntime


async def test_typed_run_events_include_trace_id():
    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/runs",
            json={
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我总结"},
                "metadata": {"owner_id": "owner_1"},
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")

    events = events_resp.json()["events"]
    assert events
    assert {event["trace_id"] for event in events} == {"trc_000001"}
    assert all(
        {"event_id", "session_id", "run_id", "trace_id", "type", "payload", "created_at"}
        <= set(event)
        for event in events
    )


def test_child_run_inherits_parent_trace_id():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.run_manager import RunManager
    from bridge.runtime_facade.store import InMemoryStore

    store = InMemoryStore()
    events = EventBus(store)
    runs = RunManager(store=store, event_bus=events)
    parent = runs.start_run(
        session_id="session_1",
        agent_profile="edge_supervisor",
        trace_id="trc_parent",
    )
    child = runs.start_run(
        session_id="session_1",
        agent_profile="edge_supervisor",
        parent_run_id=parent.run_id,
        trace_id=parent.trace_id,
    )

    assert child.parent_run_id == parent.run_id
    assert child.trace_id == "trc_parent"


def test_structured_observability_payloads_and_metric_names_are_stable():
    from bridge.runtime_facade.observability import (
        HERMES_METRIC_NAMES,
        build_structured_log,
    )

    assert HERMES_METRIC_NAMES == {
        "hermes_run_duration_ms",
        "hermes_event_append_lag_ms",
        "hermes_sse_reconnect_total",
        "hermes_timeline_projection_lag_ms",
        "hermes_outbox_failure_total",
        "hermes_approval_wait_ms",
        "hermes_prompt_cache_hit_percent",
    }
    assert build_structured_log(
        "run_lifecycle",
        run_id="run_000001",
        trace_id="trc_000001",
        status="completed",
    ) == {
        "event": "run_lifecycle",
        "run_id": "run_000001",
        "trace_id": "trc_000001",
        "status": "completed",
    }
