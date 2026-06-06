from __future__ import annotations

import pytest


def test_inbox_store_dedupes_by_channel_key_and_external_message_id():
    from bridge.runtime_facade.channel_stores import InboxStore

    store = InboxStore()
    first = store.record_inbound(
        channel_key="wechat",
        external_message_id="wx_msg_001",
        session_id="edge:owner_1:channel:wechat:wechat:user:openid_123",
        content="护眼台灯现在有什么优惠？",
    )
    second = store.record_inbound(
        channel_key="wechat",
        external_message_id="wx_msg_001",
        session_id="edge:owner_1:channel:wechat:wechat:user:openid_123",
        content="护眼台灯现在有什么优惠？",
    )

    assert first.inbox_id == second.inbox_id
    assert second.deduped is True
    assert store.list_records() == [first]


def test_outbox_store_dedupes_by_run_source_event_and_channel():
    from bridge.runtime_facade.channel_stores import OutboxStore

    store = OutboxStore()
    first = store.enqueue(
        run_id="run_channel_001",
        source_event_id="evt_done_001",
        channel_key="wechat",
        conversation_key="wechat:user:openid_123",
        payload={"kind": "text_reply", "text": "目前有开学季优惠"},
    )
    second = store.enqueue(
        run_id="run_channel_001",
        source_event_id="evt_done_001",
        channel_key="wechat",
        conversation_key="wechat:user:openid_123",
        payload={"kind": "text_reply", "text": "目前有开学季优惠"},
    )

    assert first.outbox_id == second.outbox_id
    assert second.deduped is True
    assert first.dedupe_key == "run_channel_001:evt_done_001:wechat"


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "text_reply", "text": "收到"},
        {"kind": "card_reply", "card": {"card_type": "result_preview"}},
        {"kind": "publish_confirmation", "approval_id": "appr_publish_001"},
        {"kind": "contact_message", "contact_id": "openid_123", "text": "您好"},
        {"kind": "memory_write", "memory_candidate_id": "mem_001"},
    ],
)
def test_outbox_payload_variants_are_structured(payload):
    from bridge.runtime_facade.channel_stores import OutboxPayload

    parsed = OutboxPayload.model_validate(payload)

    assert parsed.kind == payload["kind"]


async def test_outbox_retry_errors_and_success(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    facade = app.state.runtime_facade
    sent = facade.outbox.enqueue(
        run_id="run_channel_001",
        source_event_id="evt_done_001",
        channel_key="wechat",
        conversation_key="wechat:user:openid_123",
        payload={"kind": "text_reply", "text": "已发送"},
        status="sent",
    )
    failed = facade.outbox.enqueue(
        run_id="run_channel_002",
        source_event_id="evt_done_002",
        channel_key="wechat",
        conversation_key="wechat:user:openid_123",
        payload={"kind": "text_reply", "text": "重试消息"},
        status="failed",
        error="provider_timeout",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.post("/api/channels/outbox/out_missing/retry")
        not_retryable = await client.post(f"/api/channels/outbox/{sent.outbox_id}/retry")
        unavailable = await client.post(f"/api/channels/outbox/{failed.outbox_id}/retry?adapter_available=false")
        success = await client.post(f"/api/channels/outbox/{failed.outbox_id}/retry")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "OUTBOX_NOT_FOUND"
    assert not_retryable.status_code == 409
    assert not_retryable.json()["error"]["code"] == "OUTBOX_NOT_RETRYABLE"
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "CHANNEL_UNAVAILABLE"
    assert success.status_code == 200
    body = success.json()
    assert body["outbox_id"] == failed.outbox_id
    assert body["status"] == "sent"
    assert body["attempt_count"] == 2
    assert body["dedupe_key"] == failed.dedupe_key


async def test_openclaw_binding_create_accepts_camel_case_payload(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/platform/channels/bindings/create",
            json={
                "teamId": 1,
                "channelKey": "wechat_personal_openclaw",
                "bindingType": "agent",
                "bindingTargetId": "owner_secretary",
                "bindingTargetName": "AI助理",
                "expiresInHours": 72,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    binding = body["data"]
    assert binding["team_id"] == 1
    assert binding["channel_key"] == "wechat_personal_openclaw"
    assert binding["binding_type"] == "agent"
    assert binding["binding_target_id"] == "owner_secretary"
    assert binding["binding_target_name"] == "AI助理"
    assert binding["binding_code"].startswith("bind_")
    assert binding["status"] == "pending"


async def test_openclaw_binding_list_and_validate_accept_camel_case_query(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/platform/channels/bindings/create",
            json={
                "teamId": 1,
                "channelKey": "wechat_personal_openclaw",
                "bindingType": "agent",
                "bindingTargetId": "owner_secretary",
            },
        )
        listed = await client.get(
            "/api/platform/channels/bindings",
            params={"teamId": 1, "channelKey": "wechat_personal_openclaw"},
        )
        validated = await client.get(
            "/api/platform/channels/bindings/validate",
            params={"teamId": 1, "channelKey": "wechat_personal_openclaw"},
        )

    assert created.status_code == 200
    binding = created.json()["data"]
    assert listed.status_code == 200
    list_body = listed.json()["data"]
    assert list_body["total"] >= 1
    assert any(item["id"] == binding["id"] for item in list_body["items"])
    assert validated.status_code == 200
    validate_body = validated.json()["data"]
    assert validate_body["team_id"] == 1
    assert validate_body["channel_key"] == "wechat_personal_openclaw"
    assert validate_body["ready"] is True


async def test_channel_event_api_response_modes(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        accepted = await client.post("/api/channels/events", json=_external_event("wx_msg_async", "护眼台灯现在有什么优惠？"))
        sync = await client.post("/api/channels/events", json={**_external_event("wx_msg_sync", "ping"), "sync_reply_timeout_ms": 1000})
        duplicate = await client.post("/api/channels/events", json=_external_event("wx_msg_async", "重复消息"))
        approval = await client.post("/api/channels/events", json={**_external_event("wx_msg_approval", "请帮我发布朋友圈"), "requires_approval": True})

    assert accepted.status_code == 200
    assert accepted.json()["mode"] == "accepted_async"
    assert accepted.json()["reply"] == {"text": "收到，正在处理"}
    assert accepted.json()["outbox_followup"] is True
    assert sync.json()["mode"] == "sync_reply"
    assert sync.json()["reply"] == {"text": "pong"}
    assert duplicate.json()["mode"] == "suppressed"
    assert approval.json()["mode"] == "requires_approval"


async def test_wechat_personal_channel_message_projects_to_timeline(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    session_id = "edge:owner_default:channel:wechat_personal_openclaw:wechat:user:test_openid_001"
    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        accepted = await client.post(
            "/api/channels/events",
            json={
                "external_message_id": "wx_openclaw_msg_001",
                "channel_key": "wechat_personal_openclaw",
                "conversation_key": "wechat:user:test_openid_001",
                "sender_id": "wx_user_001",
                "direction": "inbound",
                "content": "你好，帮我看看现在能做什么",
                "metadata": {"owner_id": "owner_default", "binding_target_id": "owner_secretary"},
            },
        )
        timeline = await client.get(f"/api/sessions/{session_id}/timeline")

    assert accepted.status_code == 200
    assert accepted.json()["mode"] == "accepted_async"
    assert timeline.status_code == 200
    events = timeline.json()["events"]
    assert len(events) == 1
    assert events[0]["source_event_type"] == "channel_message"
    assert events[0]["source"] == "channel"
    assert events[0]["kind"] == "message"
    assert events[0]["role"] == "user"
    assert events[0]["text"] == "你好，帮我看看现在能做什么"


async def test_channel_event_structured_action_wins_over_conflicting_content(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        conflict = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_001", "不要发，先取消"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {"action": {"type": "confirm", "approval_id": "appr_publish_001"}},
            },
        )
        compatible = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_002", "请修改得更自然"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {"action": {"type": "modify", "approval_id": "appr_draft_001"}},
            },
        )

    assert conflict.json()["accepted_action"] == "confirm"
    assert conflict.json()["audit_note"] == "不要发，先取消"
    timeline_events = app.state.runtime_facade.timeline.list_session("edge:owner_1:channel:app_im:conv_abc").events
    assert [event.kind for event in timeline_events] == ["action_content_conflict"]
    assert compatible.json()["accepted_action"] == "modify"
    assert len(app.state.runtime_facade.timeline.list_session("edge:owner_1:channel:app_im:conv_abc").events) == 1


async def test_app_im_action_uses_supervisor_timeline_binding(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_supervisor_001", "不要发，先取消"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {"type": "confirm", "approval_id": "appr_publish_001"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["accepted_action"] == "confirm"
    supervisor_events = app.state.runtime_facade.timeline.list_session(supervisor_session_id).events
    channel_events = app.state.runtime_facade.timeline.list_session("edge:owner_1:channel:app_im:conv_abc").events
    assert [event.kind for event in supervisor_events] == ["action_content_conflict"]
    assert channel_events == []


async def test_app_im_free_text_invokes_supervisor_and_returns_renderable_reply(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime({"final_response": "收到，我会继续推进。"})
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_free_text_001", "请用一句话回复收到"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {"type": "free_text", "text": "请用一句话回复收到"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "sync_reply"
    assert response.json()["reply"] == {"text": "收到，我会继续推进。"}
    assert response.json()["run_id"] == "run_000001"
    assert "accepted_action" not in response.json()
    timeline_events = app.state.runtime_facade.timeline.list_session(supervisor_session_id).events
    assert [(event.kind, event.role, event.text) for event in timeline_events] == [
        ("message", "user", "请用一句话回复收到"),
        ("message", "assistant", "收到，我会继续推进。"),
    ]
    assert app.state.runtime.invoke_calls == [
        {
            "session_id": supervisor_session_id,
            "user_text": "请用一句话回复收到",
            "agent_profile": "edge_supervisor",
            "system_prompt": None,
            "conversation_history": [],
        }
    ]


async def test_app_im_free_text_returns_tool_output_as_renderable_result_card(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        {
            "final_response": "生成结果如上，可以直接发布。",
            "messages": [
                {"role": "user", "content": "请生成小红书笔记"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_skill_view_001",
                            "function": {"name": "skill_view", "arguments": "{}"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_name": "skill_view",
                    "name": "skill_view",
                    "content": "标题：护眼台灯真的救了我的晚间工作\n正文：这盏便携护眼台灯亮度柔和，适合睡前阅读和加班。",
                    "tool_call_id": "call_skill_view_001",
                },
                {"role": "assistant", "content": "生成结果如上，可以直接发布。"},
            ],
        }
    )
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_free_text_tool_001", "请调用工具生成内容"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {"type": "free_text", "text": "请调用工具生成内容"},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "sync_reply"
    reply_text = body["reply"]["text"]
    assert '"card_type": "result_preview"' in reply_text
    assert "护眼台灯真的救了我的晚间工作" in reply_text
    assert "生成结果如上，可以直接发布。" in reply_text


async def test_app_im_free_text_routes_clear_xhs_request_to_skill_result_card(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        {
            "final_response": "标题：护眼台灯真的救了我的晚间工作\n正文：这盏便携护眼台灯亮度柔和，适合睡前阅读和加班。",
        }
    )
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event(
                    "app_msg_free_text_xhs_001",
                    "请用AI工具箱的小红书笔记生成器，为便携护眼台灯生成一段种草文",
                ),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {
                        "type": "free_text",
                        "text": "请用AI工具箱的小红书笔记生成器，为便携护眼台灯生成一段种草文",
                    },
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "sync_reply"
    assert body["run_id"] == "run_000001"
    assert body["artifact_id"] == "art_run_000002"
    reply_text = body["reply"]["text"]
    assert '"card_type": "result_preview"' in reply_text
    assert "护眼台灯真的救了我的晚间工作" in reply_text
    assert app.state.runtime.invoke_calls == [
        {
            "session_id": supervisor_session_id,
            "user_text": '/xhs-note-generator {"platform": "xiaohongshu", "product": "便携护眼台灯", "tone": "真实种草"}',
            "agent_profile": "edge_supervisor",
            "system_prompt": None,
            "conversation_history": [],
        }
    ]


async def test_channel_status_api_reports_adapter_availability(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/channels/status")

    assert response.status_code == 200
    assert response.json() == {
        "adapters": {
            "app_im": {"available": True},
            "wechat": {"available": True},
        }
    }


def _external_event(external_message_id: str, content: str) -> dict:
    return {
        "external_message_id": external_message_id,
        "channel_key": "wechat",
        "conversation_key": "wechat:user:openid_123",
        "sender_id": "openid_123",
        "sender_name": "张女士",
        "direction": "inbound",
        "content": content,
        "timestamp": "2026-06-06T10:15:00+00:00",
    }
