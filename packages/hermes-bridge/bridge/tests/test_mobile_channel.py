from __future__ import annotations

import json

from httpx import ASGITransport, AsyncClient


async def test_mobile_channel_snapshot_projects_local_state(tmp_path, monkeypatch):
    from bridge import legacy_server as _bs
    from bridge.main import create_app

    monkeypatch.setattr(_bs, "_APPROVALS_FILE", str(tmp_path / "approvals.json"))
    (tmp_path / "approvals.json").write_text(
        json.dumps(
            [
                {
                    "approval_id": "apr_mobile_1",
                    "status": "pending",
                    "title": "确认视频号脚本",
                    "reason": "发布前确认",
                    "risk_level": "medium",
                    "payload": {"summary": "脚本已生成，需要确认是否发布。"},
                    "created_at": "2026-06-09T08:00:00Z",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/platform/mobile-channel/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["device"]["displayName"] == "CentaurOS Edge"
    assert data["device"]["online"] is True
    assert data["conversation"]["id"] == "mobile-default"
    assert data["approvals"][0]["id"] == "apr_mobile_1"
    assert data["approvals"][0]["status"] == "pending"
    assert data["approvals"][0]["risk"] == "medium"
    assert data["tasks"] == []
    assert data["nextCursor"].startswith("evt_")


async def test_mobile_channel_message_records_messages_and_events(tmp_path, monkeypatch):
    from bridge import config
    from bridge.main import create_app

    monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sent = await client.post(
            "/api/platform/mobile-channel/messages",
            json={"conversationId": "mobile-default", "content": "今天我应该先做什么？"},
        )
        events = await client.get(
            "/api/platform/mobile-channel/events",
            params={"cursor": "evt_000000000000"},
        )

    assert sent.status_code == 200
    sent_body = sent.json()["data"]
    assert sent_body["conversationId"] == "mobile-default"
    assert sent_body["userMessage"]["role"] == "user"
    assert sent_body["userMessage"]["content"] == "今天我应该先做什么？"
    assert sent_body["assistantMessage"]["role"] == "assistant"
    assert sent_body["assistantMessage"]["content"]
    assert sent_body["createdApprovals"] == []
    assert sent_body["createdTasks"] == []

    event_body = events.json()["data"]
    assert [item["type"] for item in event_body["items"]] == [
        "message.created",
        "message.created",
    ]
    assert event_body["nextCursor"] == event_body["items"][-1]["cursor"]


async def test_mobile_channel_message_uses_runtime_facade_when_available(tmp_path, monkeypatch):
    from bridge import config
    from bridge.main import create_app

    monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

    calls: list[dict] = []

    class FakeFacade:
        async def invoke_app_im_free_text(self, **kwargs):
            calls.append(kwargs)
            return {
                "final_response": "这是来自智能体的建议。",
                "renderable_reply_text": "这是来自智能体的建议。",
            }

    app = create_app()
    app.state.runtime_facade = FakeFacade()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/platform/mobile-channel/messages",
            json={"conversationId": "mobile-default", "content": "帮我安排今天的内容任务"},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["assistantMessage"]["content"] == "这是来自智能体的建议。"
    assert calls[0]["session_id"] == "mobile-default"
    assert calls[0]["user_text"] == "帮我安排今天的内容任务"
    assert calls[0]["agent_profile"] == "edge_supervisor"


async def test_mobile_channel_resolves_approval_idempotently(tmp_path, monkeypatch):
    from bridge import config
    from bridge import legacy_server as _bs
    from bridge.main import create_app

    monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))
    monkeypatch.setattr(_bs, "_APPROVALS_FILE", str(tmp_path / "approvals.json"))
    _bs._save_approvals(
        [
            {
                "approval_id": "apr_mobile_1",
                "status": "pending",
                "title": "确认脚本",
                "reason": "发布前确认",
                "risk_level": "low",
                "payload": {"summary": "脚本待确认"},
            }
        ]
    )

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/platform/mobile-channel/approvals/apr_mobile_1/resolve",
            json={"action": "approve", "comment": "确认发布"},
        )
        second = await client.post(
            "/api/platform/mobile-channel/approvals/apr_mobile_1/resolve",
            json={"action": "approve", "comment": "确认发布"},
        )
        conflict = await client.post(
            "/api/platform/mobile-channel/approvals/apr_mobile_1/resolve",
            json={"action": "reject", "comment": "不要发布"},
        )
        events = await client.get(
            "/api/platform/mobile-channel/events",
            params={"cursor": "evt_000000000000"},
        )

    assert first.status_code == 200
    assert first.json()["data"]["status"] == "approved"
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "approved"
    assert conflict.status_code == 409
    assert conflict.json()["success"] is False
    assert any(item["type"] == "approval.updated" for item in events.json()["data"]["items"])


async def test_mobile_channel_task_action_is_idempotent(tmp_path, monkeypatch):
    from bridge import config
    from bridge.main import create_app

    monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/platform/mobile-channel/tasks/task_daily_check/action",
            json={"action": "done", "comment": "已处理"},
        )
        second = await client.post(
            "/api/platform/mobile-channel/tasks/task_daily_check/action",
            json={"action": "done", "comment": "已处理"},
        )
        snapshot = await client.get("/api/platform/mobile-channel/snapshot")

    assert first.status_code == 200
    assert first.json()["data"]["id"] == "task_daily_check"
    assert first.json()["data"]["status"] == "done"
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "done"
    assert snapshot.json()["data"]["tasks"][0]["id"] == "task_daily_check"
    assert snapshot.json()["data"]["tasks"][0]["status"] == "done"
