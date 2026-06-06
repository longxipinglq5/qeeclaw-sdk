from __future__ import annotations

import json


def test_supervisor_route_to_capability_selects_xhs_note_writer(tmp_path):
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    facade = HermesRuntimeFacade(FakeLegacyRuntime(), artifact_root_dir=tmp_path)

    selection = facade.supervisor_route_to_capability(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="帮我生成儿童护眼台灯的小红书",
        context={},
    )

    assert selection.capability_id == "xiaohongshu_note_writer"
    assert selection.input == {
        "product": "儿童护眼台灯",
        "tone": "真实种草",
        "platform": "xiaohongshu",
    }
    assert selection.output_contract == "skill_app_card"
    assert selection.requires_clarification is False
    assert selection.fallback_behavior == "run_capability"
    assert selection.source == "deterministic_rule"


async def test_supervisor_invoke_creates_child_xhs_skill_run_and_refs(tmp_path):
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
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我生成儿童护眼台灯的小红书"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        parent_events_resp = await client.get("/api/runs/run_000001/events")
        child_events_resp = await client.get("/api/runs/run_000002/events")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_000001"
    assert response.json()["artifact_id"] == "art_run_000002"

    parent_events = parent_events_resp.json()["events"]
    assert [event["type"] for event in parent_events] == [
        "run_started",
        "capability_selected",
        "done",
    ]
    selected = next(event for event in parent_events if event["type"] == "capability_selected")
    assert selected["payload"]["selection"]["capability_id"] == "xiaohongshu_note_writer"

    parent_done = parent_events[-1]["payload"]
    assert parent_done == {
        "artifact_refs": ["art_run_000002"],
        "child_run_ids": ["run_000002"],
    }
    assert "测试回复" not in json.dumps(parent_done, ensure_ascii=False)

    child_events = child_events_resp.json()["events"]
    assert [event["type"] for event in child_events] == [
        "run_started",
        "app_started",
        "metering",
        "artifact_created",
        "app_result",
        "done",
    ]

    artifact = app.state.runtime_facade.artifacts.get_artifact("art_run_000002")
    assert artifact.kind == "xiaohongshu_note"

    session = app.state.runtime_facade.sessions.get("edge:owner_1:supervisor:conv_abc")
    assert session.metadata["artifact_summaries"] == [
        {
            "artifact_id": "art_run_000002",
            "kind": "xiaohongshu_note",
            "title": "小红书种草文",
            "summary": "测试回复",
            "capability_id": "xiaohongshu_note_writer",
        }
    ]


async def test_supervisor_followup_resolves_latest_artifact_for_moments_image(tmp_path):
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
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我生成儿童护眼台灯的小红书"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        response = await client.post(
            "/api/runs",
            json={
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "再帮我生成这个产品的朋友圈，并配一张图"},
                "context_refs": ["artifact:art_run_000002"],
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        parent_events_resp = await client.get("/api/runs/run_000003/events")
        child_events_resp = await client.get("/api/runs/run_000004/events")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_000003"
    assert response.json()["artifact_id"] == "art_run_000004"

    parent_events = parent_events_resp.json()["events"]
    selected = next(event for event in parent_events if event["type"] == "capability_selected")
    selection = selected["payload"]["selection"]
    assert selection["capability_id"] == "moments_copywriter_with_image"
    assert selection["input"]["source_artifact_id"] == "art_run_000002"
    assert selection["output_contract"] == "copy_plus_image_card"

    child_events = child_events_resp.json()["events"]
    assert [event["type"] for event in child_events] == [
        "run_started",
        "app_started",
        "metering",
        "tool_started",
        "tool_completed",
        "tool_started",
        "tool_completed",
        "artifact_created",
        "app_result",
        "done",
    ]
    tool_events = [
        event["payload"]["tool_name"]
        for event in child_events
        if event["type"] in {"tool_started", "tool_completed"}
    ]
    assert tool_events == [
        "朋友圈文案生成",
        "朋友圈文案生成",
        "配图生成",
        "配图生成",
    ]

    artifact = app.state.runtime_facade.artifacts.get_artifact("art_run_000004")
    assert artifact.kind == "moments_copy"
    assert artifact.metadata["source_artifact_id"] == "art_run_000002"
    assert artifact.metadata["capability_id"] == "moments_copywriter_with_image"


async def test_supervisor_publish_followup_requires_approval_without_child_run(tmp_path):
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
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我生成儿童护眼台灯的小红书"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        response = await client.post(
            "/api/runs",
            json={
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "把这个内容发布"},
                "context_refs": ["artifact:art_run_000002"],
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        events_resp = await client.get("/api/runs/run_000003/events")
        missing_child_resp = await client.get("/api/runs/run_000004")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_000003"
    assert "artifact_id" not in response.json()

    events = events_resp.json()["events"]
    assert [event["type"] for event in events] == [
        "run_started",
        "approval_required",
        "done",
    ]
    approval = events[1]["payload"]
    assert approval["action_kind"] == "publish_content"
    assert approval["artifact_refs"] == ["art_run_000002"]
    assert missing_child_resp.status_code == 404
