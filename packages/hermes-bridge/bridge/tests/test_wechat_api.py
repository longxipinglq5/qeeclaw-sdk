from __future__ import annotations

import sys
import types


async def test_fastapi_wechat_routes_delegate_to_gateway(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app

    fake_gateway = types.ModuleType("wechat_gateway")
    fake_gateway.get_wechat_credentials = lambda: {"configured": True, "account_id": "acct_001"}
    fake_gateway.get_qr_login_status = lambda: {"status": "idle"}
    fake_gateway.get_adapter_status = lambda: {"adapter_running": False}
    fake_gateway.list_recent_chat_ids = lambda: ["wx_chat_001"]
    fake_gateway.start_adapter = lambda: {"status": "started", "account_id": "acct_001"}
    fake_gateway.stop_adapter = lambda: {"status": "stopped"}
    fake_gateway.send_message = lambda chat_id, message, media_files=None: {
        "success": True,
        "chat_id": chat_id,
        "message": message,
        "media_files": media_files,
    }
    monkeypatch.setitem(sys.modules, "wechat_gateway", fake_gateway)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        credentials = await client.get("/wechat/credentials")
        status = await client.get("/wechat/status")
        started = await client.post("/wechat/adapter/start")
        sent = await client.post("/wechat/send", json={"chat_id": "wx_chat_001", "message": "Edge 发微信测试"})
        stopped = await client.post("/wechat/adapter/stop")

    assert credentials.status_code == 200
    assert credentials.json()["configured"] is True
    assert status.status_code == 200
    assert status.json()["adapter"]["adapter_running"] is False
    assert status.json()["recent_chat_ids"] == ["wx_chat_001"]
    assert started.status_code == 200
    assert started.json()["status"] == "started"
    assert sent.status_code == 200
    assert sent.json()["chat_id"] == "wx_chat_001"
    assert sent.json()["message"] == "Edge 发微信测试"
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"


async def test_wechat_send_loads_saved_credentials_before_dispatch(monkeypatch, tmp_path):
    import sys
    import types

    from httpx import ASGITransport, AsyncClient

    import wechat_gateway
    from bridge.main import create_app

    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    (hermes_home / ".env").write_text(
        "\n".join(
            [
                "WEIXIN_ACCOUNT_ID=acct_saved",
                "WEIXIN_TOKEN=token_saved",
                "WEIXIN_BASE_URL=https://weixin.saved.test",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    sent_messages = []

    async def fake_send_weixin_direct(*, extra, token, chat_id, message, media_files):
        sent_messages.append({
            "extra": extra,
            "token": token,
            "chat_id": chat_id,
            "message": message,
            "media_files": media_files,
        })
        return {"success": True}

    fake_weixin_module = types.ModuleType("gateway.platforms.weixin")
    fake_weixin_module.send_weixin_direct = fake_send_weixin_direct
    monkeypatch.setitem(sys.modules, "gateway.platforms.weixin", fake_weixin_module)
    monkeypatch.setattr(wechat_gateway, "_get_hermes_home", lambda: str(hermes_home))
    monkeypatch.delenv("WEIXIN_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("WEIXIN_TOKEN", raising=False)
    monkeypatch.delenv("WEIXIN_BASE_URL", raising=False)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/wechat/send", json={
            "chat_id": "wx_chat_001",
            "message": "Edge 发微信测试",
        })

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert sent_messages[0]["extra"]["account_id"] == "acct_saved"
    assert sent_messages[0]["token"] == "token_saved"
