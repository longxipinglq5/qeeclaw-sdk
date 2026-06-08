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
            "system_prompt": app.state.runtime_facade._supervisor_system_prompt("edge_supervisor"),
            "conversation_history": [],
        }
    ]


async def test_app_im_free_text_emits_open_skill_app_from_hermes_intent(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        {
            "final_response": (
                '{"card_type":"open_skill_app","speech":"我帮你打开工具生成。",'
                '"data":{"skill_id":"poster-generator","skill_name":"海报生成器",'
                '"summary":"生成马尔代夫朋友圈配图","auto_run":true,'
                '"prefilled":{"purpose":"朋友圈配图","theme":"马尔代夫海景"}}}'
            )
        }
    )
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    app.state.runtime_facade.skill_catalog.as_dicts = lambda: [
        {
            "name": "poster-generator",
            "description": "生成海报、朋友圈配图、小红书封面",
            "input_schema": {
                "type": "object",
                "properties": {"purpose": {}, "theme": {}},
                "required": ["purpose", "theme"],
            },
        }
    ]

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_open_skill_001", "配张海景图就行"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {"type": "free_text", "text": "配张海景图就行"},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "sync_reply"
    assert body["reply"] == {"text": "生成马尔代夫朋友圈配图"}
    timeline = app.state.runtime_facade.timeline.list_session(supervisor_session_id)
    open_skill_events = [
        event
        for event in timeline.events
        if event.card and event.card.get("card_type") == "open_skill_app"
    ]
    assert open_skill_events
    assert open_skill_events[-1].card["data"]["skill_id"] == "poster-generator"
    assert open_skill_events[-1].card["data"]["prefilled"]["theme"] == "马尔代夫海景"


async def test_app_im_toolbox_request_uses_hermes_intent_not_bridge_projection(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime({"final_response": "我需要先理解你的需求。"})
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    app.state.runtime_facade.skill_catalog.as_dicts = lambda: [
        {
            "name": "poster-generator",
            "description": "为小红书封面、公众号头图和朋友圈配图生成视觉素材。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "purpose": {},
                    "theme": {},
                    "style": {},
                    "ratio": {},
                },
                "required": ["purpose", "theme"],
            },
        }
    ]

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    user_text = "请用AI工具箱的生成海报工具，为奶茶店雨天第二杯半价活动做一张朋友圈配图海报，视觉风格真实摄影海报，比例1:1。"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_capability_toolbox_001", user_text),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {"type": "free_text", "text": user_text},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "sync_reply"
    assert body["reply"] == {"text": "我需要先理解你的需求。"}
    timeline = app.state.runtime_facade.timeline.list_session(supervisor_session_id)
    assert not [
        event
        for event in timeline.events
        if event.card and event.card.get("card_type") == "result_preview"
    ]
    open_skill_events = [
        event
        for event in timeline.events
        if event.card and event.card.get("card_type") == "open_skill_app"
    ]
    assert not open_skill_events
    assert app.state.runtime.invoke_calls == [
        {
            "session_id": supervisor_session_id,
            "user_text": user_text,
            "agent_profile": "edge_supervisor",
            "system_prompt": app.state.runtime_facade._supervisor_system_prompt("edge_supervisor"),
            "conversation_history": [],
        }
    ]


async def test_app_im_free_text_skill_intent_missing_required_field_clarifies(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        {
            "final_response": (
                '{"card_type":"open_skill_app","speech":"我帮你打开工具生成。",'
                '"data":{"skill_id":"poster-generator","skill_name":"海报生成器",'
                '"summary":"生成朋友圈配图","auto_run":true,'
                '"prefilled":{"purpose":"朋友圈配图"}}}'
            )
        }
    )
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    app.state.runtime_facade.skill_catalog.as_dicts = lambda: [
        {
            "name": "poster-generator",
            "description": "生成海报、朋友圈配图、小红书封面",
            "input_schema": {
                "type": "object",
                "properties": {"purpose": {}, "theme": {}},
                "required": ["purpose", "theme"],
            },
        }
    ]

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_skill_clarify_001", "帮我配图"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {"type": "free_text", "text": "帮我配图"},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"]["text"] == "还需要补充：theme，我才能打开「海报生成器」生成。"
    timeline = app.state.runtime_facade.timeline.list_session(supervisor_session_id)
    clarify_events = [
        event
        for event in timeline.events
        if event.source_event_type == "clarify_required"
    ]
    assert clarify_events
    assert clarify_events[-1].payload["missing_inputs"] == ["theme"]


async def test_native_skill_intent_flag_can_disable_bridge_capture(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from bridge import config
    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    monkeypatch.setattr(config.settings, "native_skill_intent_enabled", False)

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        {
            "final_response": (
                '{"card_type":"open_skill_app","data":{"skill_id":"poster-generator",'
                '"prefilled":{"purpose":"朋友圈配图","theme":"马尔代夫海景"}}}'
            )
        }
    )
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_flag_off_001", "配张海景图就行"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "action": {"type": "free_text"},
                },
            },
        )

    assert response.status_code == 200
    timeline = app.state.runtime_facade.timeline.list_session(supervisor_session_id)
    assert not [
        event
        for event in timeline.events
        if event.card and event.card.get("card_type") == "open_skill_app"
    ]


async def test_app_im_free_text_times_out_with_async_wechat_followup(tmp_path, monkeypatch):
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    sent_messages = []

    def fake_send_message(*, chat_id, message, media_files=None):
        sent_messages.append({"chat_id": chat_id, "message": message, "media_files": media_files})
        return {"success": True, "message_id": "wx_reply_001"}

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    async def slow_invoke_app_im_free_text(**kwargs):
        await asyncio.sleep(0.05)
        return {
            "run_id": "run_late_001",
            "artifact_id": None,
            "renderable_reply_text": "搞定。这是朋友圈文案和配图链接。",
            "final_response": "搞定。这是朋友圈文案和配图链接。",
        }

    monkeypatch.setattr(app.state.runtime_facade, "invoke_app_im_free_text", slow_invoke_app_im_free_text)
    monkeypatch.setattr("bridge.api.channels._send_wechat_followup_message", fake_send_message)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("app_msg_free_text_timeout_001", "帮我写一个假装在马尔代夫旅游的朋友圈，配一张图"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "sync_reply_timeout_ms": 10,
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "source_channel_key": "wechat_personal_openclaw",
                    "source_chat_id": "wx_chat_001",
                    "action": {"type": "free_text", "text": "帮我写一个假装在马尔代夫旅游的朋友圈，配一张图"},
                },
            },
        )
        await asyncio.sleep(0.08)

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "accepted_async"
    assert body["reply"] == {"text": "收到，正在生成，完成后发你。"}
    assert body["outbox_followup"] is True
    timeline_events = app.state.runtime_facade.timeline.list_session(supervisor_session_id).events
    operation_events = [
        event
        for event in timeline_events
        if event.kind == "operation_log" and event.source_event_type == "app_im_async_progress"
    ]
    assert operation_events
    assert operation_events[-1].role == "assistant"
    assert operation_events[-1].payload["status"] == "running"
    assert operation_events[-1].payload["detail"] == "收到，正在生成，完成后发你。"
    assert sent_messages == [
        {
            "chat_id": "wx_chat_001",
            "message": "搞定。这是朋友圈文案和配图链接。",
            "media_files": None,
        }
    ]


async def test_wechat_source_skill_intent_runs_headless_skill_when_fast(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        {
            "final_response": (
                '{"card_type":"open_skill_app","data":{"skill_id":"poster-generator",'
                '"skill_name":"海报生成器","summary":"生成马尔代夫朋友圈配图",'
                '"prefilled":{"purpose":"朋友圈配图","theme":"马尔代夫海景"}}}'
            )
        }
    )
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    app.state.runtime_facade.skill_catalog.as_dicts = lambda: [
        {
            "name": "poster-generator",
            "description": "生成海报",
            "input_schema": {
                "type": "object",
                "properties": {"purpose": {}, "theme": {}},
                "required": ["purpose", "theme"],
            },
        }
    ]
    calls = []

    async def fake_run_headless_skill_intent(*, intent, metadata, parent_run_id=None, trace_id=None):
        calls.append(
            {
                "skill_id": intent.skill_id,
                "prefilled": intent.prefilled,
                "metadata": metadata,
                "parent_run_id": parent_run_id,
            }
        )
        return {
            "run_id": "run_skill_001",
            "artifact_id": "art_skill_001",
            "renderable_reply_text": "朋友圈文案和配图已生成：https://cdn.example/maldives.png",
            "final_response": "朋友圈文案和配图已生成：https://cdn.example/maldives.png",
        }

    monkeypatch.setattr(app.state.runtime_facade, "run_headless_skill_intent", fake_run_headless_skill_intent)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("wx_skill_intent_001", "帮我写一个假装在马尔代夫旅游的朋友圈，配一张图"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "source_channel_key": "wechat_personal_openclaw",
                    "source_chat_id": "wx_chat_001",
                    "action": {"type": "free_text"},
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "sync_reply"
    assert body["artifact_id"] == "art_skill_001"
    assert body["reply"]["text"] == "朋友圈文案和配图已生成：https://cdn.example/maldives.png"
    assert calls == [
        {
            "skill_id": "poster-generator",
            "prefilled": {"purpose": "朋友圈配图", "theme": "马尔代夫海景"},
            "metadata": {
                "owner_id": "owner_1",
                "conversation_id": "conv_abc",
                "channel_key": "app_im",
                "external_message_id": "wx_skill_intent_001",
                "supervisor_session_id": supervisor_session_id,
                "source_channel_key": "wechat_personal_openclaw",
                "source_chat_id": "wx_chat_001",
                "action": {"type": "free_text"},
            },
            "parent_run_id": "run_000001",
        }
    ]


async def test_wechat_source_skill_intent_times_out_and_schedules_headless_followup(
    tmp_path,
    monkeypatch,
):
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    sent_messages = []
    app = create_app()
    app.state.runtime = FakeLegacyRuntime(
        {
            "final_response": (
                '{"card_type":"open_skill_app","data":{"skill_id":"poster-generator",'
                '"skill_name":"海报生成器","summary":"生成马尔代夫朋友圈配图",'
                '"prefilled":{"purpose":"朋友圈配图","theme":"马尔代夫海景"}}}'
            )
        }
    )
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    app.state.runtime_facade.skill_catalog.as_dicts = lambda: [
        {
            "name": "poster-generator",
            "description": "生成海报",
            "input_schema": {
                "type": "object",
                "properties": {"purpose": {}, "theme": {}},
                "required": ["purpose", "theme"],
            },
        }
    ]

    async def slow_run_headless_skill_intent(*, intent, metadata, parent_run_id=None, trace_id=None):
        await asyncio.sleep(0.05)
        return {
            "run_id": "run_skill_late_001",
            "artifact_id": "art_skill_late_001",
            "renderable_reply_text": "朋友圈配图已生成：https://cdn.example/maldives.png",
            "final_response": "朋友圈配图已生成：https://cdn.example/maldives.png",
        }

    def fake_send_message(*, chat_id, message, media_files=None):
        sent_messages.append({"chat_id": chat_id, "message": message, "media_files": media_files})
        return {"success": True, "message_id": "wx_reply_001"}

    monkeypatch.setattr(app.state.runtime_facade, "run_headless_skill_intent", slow_run_headless_skill_intent)
    monkeypatch.setattr("bridge.api.channels._send_wechat_followup_message", fake_send_message)

    supervisor_session_id = "edge:owner_1:supervisor:conv_abc"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/channels/events",
            json={
                **_external_event("wx_skill_timeout_001", "帮我配张马尔代夫海景图"),
                "channel_key": "app_im",
                "conversation_key": "conv_abc",
                "sender_id": "owner_1",
                "sync_reply_timeout_ms": 30,
                "metadata": {
                    "supervisor_session_id": supervisor_session_id,
                    "source_channel_key": "wechat_personal_openclaw",
                    "source_chat_id": "wx_chat_001",
                    "action": {"type": "free_text"},
                },
            },
        )
        await asyncio.sleep(0.08)

    assert response.status_code == 200
    assert response.json()["mode"] == "accepted_async"
    assert response.json()["reply"]["text"] == "收到，正在生成，完成后发你。"
    assert sent_messages == [
        {
            "chat_id": "wx_chat_001",
            "message": "朋友圈配图已生成：https://cdn.example/maldives.png",
            "media_files": None,
        }
    ]


def test_wechat_followup_text_unwraps_result_preview_json():
    from bridge.api.channels import _wechat_followup_text_from_result

    result = {
        "renderable_reply_text": (
            '{"card_type":"result_preview","speech":"内容已生成。",'
            '"data":{"title":"朋友圈文案","preview":"预览文本",'
            '"full_output":"朋友圈文案：\\n马尔代夫的蓝，专治加班后遗症。\\n\\n配图：https://example.test/image.jpg"}}'
        ),
        "final_response": "内容已生成。",
    }

    assert _wechat_followup_text_from_result(result) == (
        "朋友圈文案：\n马尔代夫的蓝，专治加班后遗症。\n\n配图：https://example.test/image.jpg"
    )


def test_wechat_followup_text_removes_terminal_json_before_user_summary():
    from bridge.api.channels import _wechat_followup_text_from_result

    result = {
        "renderable_reply_text": (
            '{"card_type":"result_preview","speech":"内容已生成。",'
            '"data":{"title":"工具结果","preview":"预览",'
            '"full_output":"{\\"output\\":\\"{\\\\n  \\\\\\"os\\\\\\": \\\\\\"Darwin\\\\\\",\\\\n  \\\\\\"arch\\\\\\": \\\\\\"x86_64\\\\\\",\\\\n'
            '  \\\\\\"system_ram_gb\\\\\\": 36.0,\\\\n  \\\\\\"verdict\\\\\\": \\\\\\"cloud\\\\\\"\\\\n}\\",'
            '\\"exit_code\\":2,\\"error\\":null}\\n\\n'
            "林总，图这块有点情况——这台机器是 Intel Mac 跑 Rosetta，本地跑不了 ComfyUI。"
            "\\n有两个方案：\\n1. Comfy Cloud：云端生成。\\n2. 我帮你找现成的高清图。\"}}"
        ),
        "final_response": "内容已生成。",
    }

    text = _wechat_followup_text_from_result(result)

    assert text.startswith("林总，图这块有点情况")
    assert '"output"' not in text
    assert '"exit_code"' not in text
    assert "system_ram_gb" not in text


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


async def test_app_im_free_text_delegates_xhs_toolbox_request_to_hermes_intent(tmp_path):
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
    assert body["artifact_id"] is None
    reply_text = body["reply"]["text"]
    assert "护眼台灯真的救了我的晚间工作" in reply_text
    timeline = app.state.runtime_facade.timeline.list_session(supervisor_session_id)
    assert not [
        event
        for event in timeline.events
        if event.card and event.card.get("card_type") in {"result_preview", "open_skill_app"}
    ]
    assert app.state.runtime.invoke_calls == [
        {
            "session_id": supervisor_session_id,
            "user_text": "请用AI工具箱的小红书笔记生成器，为便携护眼台灯生成一段种草文",
            "agent_profile": "edge_supervisor",
            "system_prompt": app.state.runtime_facade._supervisor_system_prompt("edge_supervisor"),
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
