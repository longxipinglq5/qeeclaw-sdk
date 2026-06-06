from __future__ import annotations

import pytest


def test_json_artifact_store_creates_reads_and_lists_for_run(tmp_path):
    from bridge.runtime_facade.artifacts import JsonArtifactStore

    store = JsonArtifactStore(tmp_path)
    artifact = store.create_artifact(
        artifact_id="art_xhs_001",
        session_id="edge:owner_1:supervisor:conv_abc",
        run_id="run_000001",
        kind="xiaohongshu_note",
        title="儿童护眼台灯小红书种草文",
        content={"title": "给孩子换台灯后", "body": "..."},
        metadata={"summary": "真实分享语气"},
    )

    assert artifact.artifact_id == "art_xhs_001"
    assert store.get_artifact("art_xhs_001").title == "儿童护眼台灯小红书种草文"
    assert [item.artifact_id for item in store.list_for_run("run_000001")] == [
        "art_xhs_001"
    ]
    assert store.capabilities.durable is False
    assert store.capabilities.supports_cross_worker is False
    assert store.capabilities.supports_pagination is False
    assert store.garbage_collect() == {"deleted": 0, "reason": "gc_deferred"}


def test_json_artifact_store_does_not_silently_overwrite(tmp_path):
    from bridge.runtime_facade.artifacts import ArtifactConflictError, JsonArtifactStore

    store = JsonArtifactStore(tmp_path)
    store.create_artifact(
        artifact_id="art_xhs_001",
        session_id="session_1",
        run_id="run_000001",
        kind="note",
        title="first",
        content={"body": "first"},
    )

    with pytest.raises(ArtifactConflictError):
        store.create_artifact(
            artifact_id="art_xhs_001",
            session_id="session_1",
            run_id="run_000001",
            kind="note",
            title="second",
            content={"body": "second"},
        )


async def test_post_api_runs_skill_run_creates_artifact_and_card_events(tmp_path):
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
                "kind": "skill_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "parent_run_id": "run_sup_001",
                "capability_id": "xiaohongshu_note_writer",
                "input": {
                    "product": "儿童护眼台灯",
                    "tone": "真实种草",
                    "platform": "xiaohongshu",
                },
                "output_contract": "skill_app_card",
                "metadata": {"owner_id": "owner_1"},
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "skill_run"
    assert body["parent_run_id"] == "run_sup_001"
    assert body["artifact_id"] == "art_run_000001"

    events = events_resp.json()["events"]
    assert [event["type"] for event in events] == [
        "run_started",
        "app_started",
        "metering",
        "artifact_created",
        "app_result",
        "done",
    ]
    app_result = next(event for event in events if event["type"] == "app_result")
    assert app_result["payload"]["card"]["card_type"] == "result_preview"
    artifact = app.state.runtime_facade.artifacts.get_artifact("art_run_000001")
    assert artifact.kind == "xiaohongshu_note"
    assert artifact.content["body"] == "测试回复"


async def test_post_api_runs_skill_run_fails_closed_for_mismatched_fields(tmp_path):
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
                "kind": "skill_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "expert_id": "marketing_strategy_expert",
                "input": {"text": "帮我看看文案"},
                "metadata": {"owner_id": "owner_1"},
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RUN_KIND_UNSUPPORTED"
    assert response.json()["error"]["details"]["missing"] == ["capability_id"]
    assert response.json()["error"]["details"]["unexpected"] == ["expert_id"]


async def test_post_api_runs_skill_run_unknown_capability_returns_not_found(tmp_path):
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
                "kind": "skill_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "capability_id": "missing_capability",
                "input": {"text": "帮我写小红书"},
                "metadata": {"owner_id": "owner_1"},
            },
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CAPABILITY_NOT_FOUND"
    assert response.json()["error"]["details"] == {
        "capability_id": "missing_capability"
    }
