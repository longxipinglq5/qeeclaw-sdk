from __future__ import annotations

import pytest

from bridge.tests.test_runtime_facade import FakeLegacyRuntime


def test_create_run_request_accepts_invoke_contract_fields():
    from bridge.runtime_facade.models import CreateRunRequest, RunKind

    request = CreateRunRequest(
        kind="invoke",
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        input={"text": "帮我总结"},
        context_refs=["timeline:latest"],
        metadata={
            "owner_id": "owner_1",
            "created_by": "web",
            "source": "supervisor_chat",
            "correlation_id": "web_msg_001",
        },
    )

    assert request.kind == RunKind.INVOKE
    assert request.input.text == "帮我总结"
    assert request.context_refs == ["timeline:latest"]
    assert request.metadata["owner_id"] == "owner_1"
    assert request.metadata["created_by"] == "web"
    assert request.metadata["source"] == "supervisor_chat"


def test_create_run_request_rejects_conflicting_owner_metadata():
    from pydantic import ValidationError

    from bridge.runtime_facade.models import CreateRunRequest

    with pytest.raises(ValidationError, match="owner_id"):
        CreateRunRequest(
            kind="invoke",
            session_id="edge:owner_1:supervisor:conv_abc",
            agent_profile="edge_supervisor",
            input={"text": "帮我总结"},
            metadata={"owner_id": "owner_2"},
        )


def test_create_run_response_and_runtime_run_trace_fields():
    from bridge.runtime_facade.models import (
        CreateRunResponse,
        RunKind,
        RunStatus,
        RunUrls,
        RuntimeRun,
    )

    run = RuntimeRun(
        run_id="run_000001",
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        trace_id="trc_000001",
        parent_run_id="run_parent_001",
        created_by="web",
        source="supervisor_chat",
        metadata={"correlation_id": "web_msg_001"},
    )
    assert run.trace_id == "trc_000001"
    assert run.parent_run_id == "run_parent_001"
    assert run.created_by == "web"
    assert run.source == "supervisor_chat"
    assert run.metadata == {"correlation_id": "web_msg_001"}

    response = CreateRunResponse(
        run_id=run.run_id,
        session_id=run.session_id,
        kind=RunKind.INVOKE,
        status=RunStatus.RUNNING,
        trace_id=run.trace_id,
        urls=RunUrls.for_run(run.run_id, run.session_id),
    )

    assert response.model_dump(mode="json") == {
        "run_id": "run_000001",
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "kind": "invoke",
        "status": "running",
        "trace_id": "trc_000001",
        "urls": {
            "status_url": "/api/runs/run_000001",
            "events_url": "/api/runs/run_000001/events",
            "stream_url": "/api/runs/run_000001/events/stream",
            "timeline_url": "/api/sessions/edge:owner_1:supervisor:conv_abc/timeline",
        },
    }


async def test_post_api_runs_invoke_creates_readable_run_and_events():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/runs",
            json={
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我总结"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        run_resp = await client.get("/api/runs/run_000001")
        events_resp = await client.get("/api/runs/run_000001/events")

    assert create_resp.status_code == 200
    assert create_resp.json() == {
        "run_id": "run_000001",
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "kind": "invoke",
        "status": "completed",
        "trace_id": "trc_000001",
        "urls": {
            "status_url": "/api/runs/run_000001",
            "events_url": "/api/runs/run_000001/events",
            "stream_url": "/api/runs/run_000001/events/stream",
            "timeline_url": "/api/sessions/edge:owner_1:supervisor:conv_abc/timeline",
        },
    }
    assert run_resp.status_code == 200
    assert run_resp.json()["run"]["trace_id"] == "trc_000001"
    event_types = [event["type"] for event in events_resp.json()["events"]]
    assert event_types[0] == "run_started"
    assert event_types.count("message") == 2
    assert "metering" in event_types
    assert "done" in event_types


async def test_post_api_runs_rejects_unsupported_kind_until_later_plans():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/runs",
            json={
                "kind": "skill_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我写小红书"},
                "metadata": {"owner_id": "owner_1"},
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RUN_KIND_UNSUPPORTED"


def test_run_manager_cancel_and_resume_state_guards():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.models import RunStatus
    from bridge.runtime_facade.run_manager import RunManager, RunTerminalError
    from bridge.runtime_facade.store import InMemoryStore

    store = InMemoryStore()
    events = EventBus(store)
    runs = RunManager(store=store, event_bus=events)

    run = runs.start_run(session_id="session_1", agent_profile="edge_supervisor")
    cancelled = runs.cancel_run(run.run_id, reason="user_cancelled")
    assert cancelled.status == RunStatus.CANCELLED
    assert [event.type for event in events.list_by_run(run.run_id)] == [
        "run_started",
        "cancelled",
    ]

    resumed = runs.resume_run(run.run_id)
    assert resumed.status == RunStatus.RUNNING
    assert [event.type for event in events.list_by_run(run.run_id)] == [
        "run_started",
        "cancelled",
        "run_resumed",
    ]

    completed = runs.start_run(session_id="session_1", agent_profile="edge_supervisor")
    runs.complete_run(completed.run_id, result_text="done")
    with pytest.raises(RunTerminalError):
        runs.cancel_run(completed.run_id)


async def test_cancel_and_resume_run_apis_use_explicit_state_contracts():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)
    app.state.runtime_facade.runs.start_run(
        session_id="edge:owner_1:supervisor:conv_cancel",
        agent_profile="edge_supervisor",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cancel_resp = await client.post("/api/runs/run_000001/cancel")
        resume_resp = await client.post("/api/runs/run_000001/resume")
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
        terminal_cancel_resp = await client.post("/api/runs/run_000002/cancel")

    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["run"]["status"] == "cancelled"
    assert resume_resp.status_code == 200
    assert resume_resp.json()["run"]["status"] == "running"
    assert terminal_cancel_resp.status_code == 409
    assert terminal_cancel_resp.json()["error"]["code"] == "RUN_TERMINAL"


def test_in_memory_store_capabilities_are_not_production_durable():
    from bridge.runtime_facade.store import InMemoryStore

    capabilities = InMemoryStore().capabilities

    assert capabilities.durable is False
    assert capabilities.supports_retention is True
    assert capabilities.supports_replay is False
    assert capabilities.supports_cross_worker is False
    assert capabilities.safe_for_external_channels is False


def test_store_readiness_blocks_unsafe_production_external_channels():
    from bridge.runtime_facade.store import InMemoryStore, check_store_readiness

    local_result = check_store_readiness(
        InMemoryStore(),
        environment="local",
        uvicorn_workers=2,
        external_channels=True,
        outbox_retry=True,
    )
    production_result = check_store_readiness(
        InMemoryStore(),
        environment="production",
        uvicorn_workers=2,
        external_channels=True,
        outbox_retry=True,
    )

    assert local_result.ready is True
    assert local_result.warning is not None
    assert production_result.ready is False
    assert production_result.error == {
        "code": "STORE_NOT_PRODUCTION_READY",
        "message": "InMemoryStore cannot run external channels or outbox retry in production",
        "details": {
            "durable": False,
            "supports_cross_worker": False,
            "safe_for_external_channels": False,
        },
    }
