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
    assert app.state.runtime.invoke_calls == [
        {
            "session_id": supervisor_session_id,
            "user_text": "请用一句话回复收到",
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
