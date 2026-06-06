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
