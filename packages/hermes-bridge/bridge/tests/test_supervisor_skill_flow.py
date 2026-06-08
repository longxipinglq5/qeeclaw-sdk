from __future__ import annotations

import json


async def test_supervisor_invoke_delegates_tool_decision_to_hermes(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={"final_response": "我会根据你的需求判断是否需要打开工具。"}
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
                "input": {"text": "帮我生成儿童护眼台灯的小红书"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")
        missing_child_resp = await client.get("/api/runs/run_000002")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_000001"
    assert "artifact_id" not in response.json()
    assert missing_child_resp.status_code == 404

    events = events_resp.json()["events"]
    event_types = [event["type"] for event in events]
    assert "run_started" in event_types
    assert "metering" in event_types
    assert "done" in event_types
    assert not [
        event
        for event in events
        if event["type"] in {"capability_selected", "approval_required", "clarify_required"}
    ]

    assert len(app.state.runtime.invoke_calls) == 1
    invoke_call = app.state.runtime.invoke_calls[0]
    assert invoke_call["session_id"] == "edge:owner_1:supervisor:conv_abc"
    assert invoke_call["user_text"] == "帮我生成儿童护眼台灯的小红书"
    assert invoke_call["agent_profile"] == "edge_supervisor"
    assert "json object" in invoke_call["system_prompt"]
    assert invoke_call["conversation_history"] == []


async def test_supervisor_followup_keeps_context_for_hermes_instead_of_local_routing(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={"final_response": "我会结合上下文继续判断是否需要工具。"}
    )
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
        events_resp = await client.get("/api/runs/run_000002/events")
        missing_child_resp = await client.get("/api/runs/run_000003")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_000002"
    assert "artifact_id" not in response.json()
    assert missing_child_resp.status_code == 404

    events = events_resp.json()["events"]
    event_types = [event["type"] for event in events]
    assert "run_started" in event_types
    assert "metering" in event_types
    assert "done" in event_types
    assert not [
        event
        for event in events
        if event["type"] in {"capability_selected", "approval_required", "clarify_required"}
    ]
    assert app.state.runtime.invoke_calls[-1]["user_text"] == "再帮我生成这个产品的朋友圈，并配一张图"
    assert app.state.runtime.invoke_calls[-1]["conversation_history"]


async def test_supervisor_text_card_projects_readable_body_to_timeline(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={
            "final_response": (
                '{"card_type":"text","speech":"我可以帮你梳理。",'
                '"data":{"body":"我可以帮你写文案、做海报、整理客户消息。",'
                '"suggestions":["写小红书","生成海报"]}}'
            )
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
                "input": {"text": "你能帮我做什么"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        run_resp = await client.get("/api/runs/run_000001")
        timeline_resp = await client.get(
            "/api/sessions/edge:owner_1:supervisor:conv_abc/timeline"
        )

    assert response.status_code == 200
    assert run_resp.json()["run"]["result_text"] == "我可以帮你写文案、做海报、整理客户消息。"

    events = timeline_resp.json()["events"]
    assistant_messages = [
        event
        for event in events
        if event["kind"] == "message" and event["role"] == "assistant"
    ]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["text"] == "我可以帮你写文案、做海报、整理客户消息。"
    assert '"card_type"' not in assistant_messages[0]["text"]


async def test_supervisor_clarify_tool_error_projects_readable_question(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={
            "final_response": (
                "测试用户总，设计会员卡需要你定几个方向：\n\n"
                "1. 卡种：储值卡、次卡、月卡/季卡，还是权益卡？\n"
                "2. 价格和权益：比如充500送100。\n"
                "你给我几个关键词就行。"
            ),
            "messages": [
                {"role": "assistant", "content": "我需要追问几个方向。"},
                {
                    "role": "tool",
                    "tool_name": "clarify",
                    "content": {
                        "error": "Clarify tool is not available in this execution context."
                    },
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
                "input": {"text": "设计一个美甲店的会员卡"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        run_resp = await client.get("/api/runs/run_000001")
        timeline_resp = await client.get(
            "/api/sessions/edge:owner_1:supervisor:conv_abc/timeline"
        )

    assert response.status_code == 200
    assert "设计会员卡需要你定几个方向" in run_resp.json()["run"]["result_text"]

    events = timeline_resp.json()["events"]
    assistant_message = next(
        event
        for event in events
        if event["kind"] == "message" and event["role"] == "assistant"
    )
    assert "设计会员卡需要你定几个方向" in assistant_message["text"]
    assert '"card_type"' not in assistant_message["text"]
    assert "Clarify tool is not available" not in assistant_message["text"]


async def test_moments_image_skill_calls_nexus_and_attaches_image_url(tmp_path, monkeypatch):
    import urllib.request

    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    monkeypatch.setenv("NEXUS_URL", "https://nexus.example")
    monkeypatch.setenv("NEXUS_API_KEY", "test-token")
    calls = []

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {"data": [{"url": "https://cdn.example/maldives.png"}], "model": "nexus-image"}
            ).encode("utf-8")

    def fake_urlopen(req, timeout):
        calls.append(
            {
                "url": req.full_url,
                "body": json.loads(req.data.decode("utf-8")),
                "authorization": req.headers.get("Authorization"),
                "timeout": timeout,
            }
        )
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={
            "final_response": (
                "```json\n"
                "{\n"
                '  "card_type": "text",\n'
                '  "speech": "三版朋友圈文案已生成。",\n'
                '  "data": {\n'
                '    "body": "### 短版\n马尔代夫的蓝，专治加班后遗症。\n\n要我帮你直接用工具出张图吗？",\n'
                '    "suggestions": ["用短版", "用故事版"]\n'
                "  }\n"
                "}\n"
                "```"
            )
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
                "agent_profile": "edge_supervisor",
                "capability_id": "moments_copywriter_with_image",
                "input": {
                    "topic": "假装在马尔代夫旅游",
                    "tone": "轻松聊天",
                    "need_image": True,
                },
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        child_events_resp = await client.get("/api/runs/run_000001/events")

    assert response.status_code == 200
    assert calls == [
        {
            "url": "https://nexus.example/api/llm/images/generations",
            "body": {
                "prompt": "假装在马尔代夫旅游",
                "size": "1024x1024",
                "n": 1,
                "response_format": "url",
                "output_format": "png",
            },
            "authorization": "Bearer test-token",
            "timeout": 120,
        }
    ]

    artifact = app.state.runtime_facade.artifacts.get_artifact("art_run_000001")
    assert "要我帮你" not in artifact.content["body"]
    assert "```json" not in artifact.content["body"]
    assert '"card_type"' not in artifact.content["body"]
    assert "马尔代夫的蓝" in artifact.content["body"]
    assert artifact.content["imageUrl"] == "https://cdn.example/maldives.png"
    assert artifact.metadata["image_provider"] == "nexus"

    child_events = child_events_resp.json()["events"]
    app_result = next(event for event in child_events if event["type"] == "app_result")
    assert app_result["payload"]["card"]["imageUrl"] == "https://cdn.example/maldives.png"


async def test_moments_image_skill_records_nexus_timeout_without_comfy_claims(tmp_path, monkeypatch):
    import urllib.request

    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    monkeypatch.setenv("NEXUS_URL", "https://nexus.example")
    monkeypatch.setenv("NEXUS_API_KEY", "test-token")

    def fake_urlopen(_req, timeout):
        raise TimeoutError("read timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={
            "final_response": "三版朋友圈文案已生成。ComfyUI 方案不应该出现在最终结果里。"
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
                "agent_profile": "edge_supervisor",
                "capability_id": "moments_copywriter_with_image",
                "input": {
                    "topic": "假装在马尔代夫旅游",
                    "tone": "轻松聊天",
                    "need_image": True,
                },
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )

    assert response.status_code == 200

    artifact = app.state.runtime_facade.artifacts.get_artifact("art_run_000001")
    assert "ComfyUI" not in artifact.content["body"]
    assert artifact.content["imageStatus"] == "timeout"
    assert artifact.content["imageError"] == "NEXUS 生图接口超时，文案已先生成。"
    assert artifact.metadata["image_provider"] == "nexus"
    assert artifact.metadata["image_status"] == "timeout"


async def test_supervisor_publish_followup_delegates_approval_decision_to_hermes(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={"final_response": "发布前我会先判断是否需要审批。"}
    )
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
        events_resp = await client.get("/api/runs/run_000002/events")
        missing_child_resp = await client.get("/api/runs/run_000003")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_000002"
    assert "artifact_id" not in response.json()

    events = events_resp.json()["events"]
    event_types = [event["type"] for event in events]
    assert "run_started" in event_types
    assert "metering" in event_types
    assert "done" in event_types
    assert not [event for event in events if event["type"] == "approval_required"]
    assert missing_child_resp.status_code == 404


async def test_supervisor_ambiguous_content_delegates_clarification_to_hermes(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        response_overrides={"final_response": "你想做哪类内容？可以补充平台和目标。"}
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
                "input": {"text": "帮我做一篇内容"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")
        missing_child_resp = await client.get("/api/runs/run_000002")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run_000001"
    assert "artifact_id" not in response.json()

    events = events_resp.json()["events"]
    event_types = [event["type"] for event in events]
    assert "run_started" in event_types
    assert "metering" in event_types
    assert "done" in event_types
    assert not [event for event in events if event["type"] == "clarify_required"]
    assert missing_child_resp.status_code == 404
