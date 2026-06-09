from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from bridge.tests.test_runtime_facade import FakeLegacyRuntime


async def _client():
    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_run_not_found_uses_shared_error_envelope():
    async with await _client() as client:
        response = await client.get("/api/runs/run_missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RUN_NOT_FOUND",
            "message": "Run not found",
            "details": {"run_id": "run_missing"},
        }
    }


async def test_run_kind_unsupported_uses_shared_error_envelope():
    async with await _client() as client:
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
    assert response.json()["error"]["details"] == {
        "kind": "skill_run",
        "missing": ["capability_id"],
        "unexpected": [],
    }


async def test_session_owner_mismatch_uses_shared_error_envelope():
    async with await _client() as client:
        response = await client.post(
            "/api/runs",
            json={
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我总结"},
                "metadata": {"owner_id": "owner_2"},
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SESSION_OWNER_MISMATCH"


async def test_event_cursor_expired_uses_shared_error_envelope():
    async with await _client() as client:
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
        response = await client.get(
            "/api/runs/run_000001/events/stream",
            headers={"Last-Event-ID": "evt_999999"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EVENT_CURSOR_EXPIRED"
