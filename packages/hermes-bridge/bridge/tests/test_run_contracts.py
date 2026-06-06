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
    assert [event["type"] for event in events_resp.json()["events"]] == [
        "run_started",
        "metering",
        "done",
    ]


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
