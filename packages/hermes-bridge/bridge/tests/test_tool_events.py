from __future__ import annotations


def test_extract_tool_call_events_pairs_calls_with_results():
    from bridge.runtime_facade.tool_events import extract_tool_call_events

    events = extract_tool_call_events(
        {
            "messages": [
                {"role": "user", "content": "生成一条朋友圈"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_copy_001",
                            "function": {
                                "name": "skill_view",
                                "arguments": '{"topic":"雨天到店满99减20"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "skill_view",
                    "tool_call_id": "call_copy_001",
                    "content": "雨天不想出门？到店项目满99减20。",
                },
                {"role": "assistant", "content": "生成结果如上。"},
            ]
        }
    )

    assert [event["type"] for event in events] == [
        "tool_call.started",
        "tool_call.completed",
    ]
    assert events[0]["payload"] == {
        "tool_call_id": "call_copy_001",
        "tool_name": "skill_view",
        "arguments": {"topic": "雨天到店满99减20"},
        "raw_arguments": '{"topic":"雨天到店满99减20"}',
    }
    assert events[1]["payload"] == {
        "tool_call_id": "call_copy_001",
        "tool_name": "skill_view",
        "arguments": {"topic": "雨天到店满99减20"},
        "raw_arguments": '{"topic":"雨天到店满99减20"}',
        "result": {
            "content": "雨天不想出门？到店项目满99减20。",
            "raw_content": "雨天不想出门？到店项目满99减20。",
        },
    }


async def test_skill_run_emits_stable_tool_call_events(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={
            "final_response": "生成结果如上。",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_copy_001",
                            "function": {
                                "name": "skill_view",
                                "arguments": '{"topic":"雨天到店满99减20"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "skill_view",
                    "tool_call_id": "call_copy_001",
                    "content": "雨天不想出门？到店项目满99减20。",
                },
                {"role": "assistant", "content": "生成结果如上。"},
            ],
        }
    )
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
                "capability_id": "xiaohongshu_note_writer",
                "input": {
                    "product": "雨天到店项目",
                    "tone": "轻松",
                    "platform": "moments",
                },
                "metadata": {"owner_id": "owner_1"},
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")

    assert response.status_code == 200
    event_types = [event["type"] for event in events_resp.json()["events"]]
    assert "tool_call.started" in event_types
    assert "tool_call.completed" in event_types
    completed = next(
        event
        for event in events_resp.json()["events"]
        if event["type"] == "tool_call.completed"
    )
    assert completed["payload"]["tool_call_id"] == "call_copy_001"
    assert completed["payload"]["tool_name"] == "skill_view"
    assert completed["payload"]["result"]["content"] == "雨天不想出门？到店项目满99减20。"


async def test_invoke_run_emits_stable_tool_call_events(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={
            "final_response": "我建议打开工具箱。",
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_open_001",
                            "function": {
                                "name": "open_skill_app",
                                "arguments": '{"skill_id":"xiaohongshu_note_writer"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "name": "open_skill_app",
                    "tool_call_id": "call_open_001",
                    "content": '{"status":"accepted"}',
                },
            ],
        }
    )
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
                "input": {"text": "帮我写小红书"},
                "metadata": {"owner_id": "owner_1"},
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")

    assert response.status_code == 200
    events = events_resp.json()["events"]
    started = next(event for event in events if event["type"] == "tool_call.started")
    assert started["payload"]["tool_name"] == "open_skill_app"
    assert started["payload"]["arguments"] == {"skill_id": "xiaohongshu_note_writer"}
