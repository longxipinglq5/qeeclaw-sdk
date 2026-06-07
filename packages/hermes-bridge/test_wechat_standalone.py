"""
test_wechat_standalone.py
模拟局域网内微信协议抓包工具 (Wechaty / Ipad Protocol) 将数据发送至 QeeClaw 新构建的微信个人通道。
"""
import urllib.request
import urllib.error
import json

URL = "http://127.0.0.1:21747/api/wechat/webhook"

def test_wechat_webhook():
    test_payload = {
        "event_id": "wx_msg_102841",
        "message_type": "text",
        "toUser": "wxid_qeeclaw_bot",
        "fromUser": "wxid_user_test123",
        "text": "你好，能告诉我你的名字吗？我是刚刚接入 QeeClaw 微信个人通道的用户！"
    }
    encoded_data = json.dumps(test_payload).encode('utf-8')
    req = urllib.request.Request(URL, data=encoded_data, method="POST")
    req.add_header("Content-Type", "application/json")
    
    print(f"[{test_payload['fromUser']} -> {test_payload['toUser']}] 発送消息: {test_payload['text']}")
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            response = json.loads(f.read().decode('utf-8'))
            print("==== 收到大模型微信被动回复 ====")
            print(json.dumps(response, indent=2, ensure_ascii=False))
            if response.get("ok"):
                print("\n✅ 测试通过：微信通道联调成功！大模型已经可以接管局域网路由的数据！")
    except urllib.error.URLError as e:
        print(f"❌ 请求失败, 请确保 QeeClaw Bridge Server 已经启动在 127.0.0.1:21747 ! 错误: {e}")

if __name__ == "__main__":
    test_wechat_webhook()
import json
import sys
import types


def test_incoming_wechat_message_routes_through_edge_app_im(monkeypatch):
    import wechat_gateway

    captured_requests = []
    sent_messages = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({
                "mode": "sync_reply",
                "run_id": "run_001",
                "reply": {"text": "Edge 已收到微信消息"},
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured_requests.append({
            "url": request.full_url,
            "body": json.loads(request.data.decode("utf-8")),
            "timeout": timeout,
        })
        return FakeResponse()

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
    monkeypatch.setenv("WEIXIN_ACCOUNT_ID", "acct_001")
    monkeypatch.setenv("WEIXIN_TOKEN", "token_001")
    monkeypatch.setenv("WEIXIN_BASE_URL", "https://weixin.example.test")
    monkeypatch.setenv("WEIXIN_AI_INVOKE_URL", "http://127.0.0.1:21748/api/channels/events")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    event = types.SimpleNamespace(
        source=types.SimpleNamespace(user_id="wx_user_001", chat_id="wx_chat_001"),
        text="测试微信到 Edge",
    )

    asyncio_run = __import__("asyncio").run
    asyncio_run(wechat_gateway._handle_incoming_message(event))

    assert captured_requests == [
        {
            "url": "http://127.0.0.1:21748/api/channels/events",
            "body": {
                "channel_key": "app_im",
                "conversation_key": "main",
                "external_message_id": "wechat:wx_chat_001:wx_user_001:测试微信到 Edge",
                "sender_id": "owner_default",
                "sender_name": "wx_user_001",
                "direction": "inbound",
                "content": "测试微信到 Edge",
                "sync_reply_timeout_ms": 55000,
                "metadata": {
                    "supervisor_session_id": "edge:owner_default:supervisor:main",
                    "source_channel_key": "wechat_personal_openclaw",
                    "source_chat_id": "wx_chat_001",
                    "source_sender_id": "wx_user_001",
                    "action": {"type": "free_text", "text": "测试微信到 Edge"},
                },
            },
            "timeout": 60.0,
        }
    ]
    assert sent_messages[0]["chat_id"] == "wx_chat_001"
    assert sent_messages[0]["message"] == "Edge 已收到微信消息"


def test_send_message_loads_saved_weixin_credentials(monkeypatch, tmp_path):
    import wechat_gateway

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

    result = wechat_gateway.send_message("wx_chat_001", "Edge 发微信测试")

    assert result == {"success": True}
    assert sent_messages == [
        {
            "extra": {
                "account_id": "acct_saved",
                "base_url": "https://weixin.saved.test",
            },
            "token": "token_saved",
            "chat_id": "wx_chat_001",
            "message": "Edge 发微信测试",
            "media_files": None,
        }
    ]


def test_list_recent_chat_ids_returns_context_token_keys(monkeypatch, tmp_path):
    import wechat_gateway

    hermes_home = tmp_path / "hermes"
    accounts_dir = hermes_home / "weixin" / "accounts"
    accounts_dir.mkdir(parents=True)
    (hermes_home / ".env").write_text(
        "WEIXIN_ACCOUNT_ID=acct_saved\nWEIXIN_TOKEN=token_saved\n",
        encoding="utf-8",
    )
    (accounts_dir / "acct_saved.context-tokens.json").write_text(
        json.dumps({
            "wx_chat_001": "token_value_001",
            "wx_chat_002": "token_value_002",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(wechat_gateway, "_get_hermes_home", lambda: str(hermes_home))
    monkeypatch.delenv("WEIXIN_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("WEIXIN_TOKEN", raising=False)

    assert wechat_gateway.list_recent_chat_ids(limit=1) == ["wx_chat_001"]


def test_wechat_sync_reply_suppresses_result_preview_json_for_outbound(monkeypatch):
    import wechat_gateway

    captured_requests = []
    sent_messages = []

    result_preview = {
        "card_type": "result_preview",
        "speech": "工具结果已生成。",
        "data": {
            "title": "长报告",
            "preview": "这是一段预览",
            "full_output": "{\"team_id\":1,\"agent_prompt\":\"内部上下文\"}\n" + ("very long internal text\n" * 120),
            "tool_name": "internal-tool",
        },
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({
                "mode": "sync_reply",
                "run_id": "run_001",
                "reply": {"text": json.dumps(result_preview, ensure_ascii=False)},
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured_requests.append(request)
        return FakeResponse()

    async def fake_send_weixin_direct(*, extra, token, chat_id, message, media_files):
        sent_messages.append(message)
        return {"success": True}

    fake_weixin_module = types.ModuleType("gateway.platforms.weixin")
    fake_weixin_module.send_weixin_direct = fake_send_weixin_direct
    monkeypatch.setitem(sys.modules, "gateway.platforms.weixin", fake_weixin_module)
    monkeypatch.setenv("WEIXIN_ACCOUNT_ID", "acct_001")
    monkeypatch.setenv("WEIXIN_TOKEN", "token_001")
    monkeypatch.setenv("WEIXIN_BASE_URL", "https://weixin.example.test")
    monkeypatch.setenv("WEIXIN_AI_INVOKE_URL", "http://127.0.0.1:21748/api/channels/events")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    event = types.SimpleNamespace(
        source=types.SimpleNamespace(user_id="wx_user_001", chat_id="wx_chat_001"),
        text="生成一份长报告",
    )

    asyncio_run = __import__("asyncio").run
    asyncio_run(wechat_gateway._handle_incoming_message(event))

    assert captured_requests
    assert sent_messages == ["已收到，结果已在 Edge 主对话里生成。"]


def test_wechat_sync_reply_keeps_long_natural_language_question(monkeypatch):
    import wechat_gateway

    text = (
        "文案先出，ComfyUI 还在启动中。\n\n"
        "给你三个版本挑：\n"
        "版本一｜短平快：落地第一口空气是咸的。\n"
        "版本二｜沉浸式：早上被海浪声吵醒。\n"
        "版本三｜反转版：印度洋的日落真太绝了。\n\n"
        "图的话，ComfyUI 正在后台启动。你想先定哪个文案版本？还是三个都要？"
    )

    sanitized = wechat_gateway._sanitize_wechat_outbound_reply(text + "\n" + ("补充说明。\n" * 220))

    assert "你想先定哪个文案版本" in sanitized
    assert "已收到，结果已在 Edge 主对话里生成。" not in sanitized


def test_wechat_sync_reply_unwraps_safe_result_preview_card():
    import wechat_gateway

    result_preview = {
        "card_type": "result_preview",
        "speech": "内容已生成。",
        "data": {
            "title": "朋友圈文案",
            "preview": "预览文本",
            "full_output": "朋友圈文案：\n马尔代夫的蓝，专治加班后遗症。\n\n配图：https://example.test/image.jpg",
        },
    }

    sanitized = wechat_gateway._sanitize_wechat_outbound_reply(json.dumps(result_preview, ensure_ascii=False))

    assert sanitized == "朋友圈文案：\n马尔代夫的蓝，专治加班后遗症。\n\n配图：https://example.test/image.jpg"


def test_wechat_sync_reply_unwraps_result_preview_with_nexus_image_url():
    import wechat_gateway

    result_preview = {
        "card_type": "result_preview",
        "title": "朋友圈文案",
        "summary": "朋友圈文案：\n马尔代夫的蓝，专治加班后遗症。",
        "imageUrl": "https://cdn.example.test/maldives.png",
        "imagePrompt": "假装在马尔代夫旅游",
    }

    sanitized = wechat_gateway._sanitize_wechat_outbound_reply(json.dumps(result_preview, ensure_ascii=False))

    assert sanitized == (
        "朋友圈文案：\n马尔代夫的蓝，专治加班后遗症。"
        "\n\n配图：https://cdn.example.test/maldives.png"
    )


def test_wechat_sync_reply_removes_terminal_json_before_user_summary():
    import wechat_gateway

    text = (
        '{"output":"{\\n  \\"os\\": \\"Darwin\\",\\n  \\"arch\\": \\"x86_64\\",\\n'
        '  \\"system_ram_gb\\": 36.0,\\n  \\"verdict\\": \\"cloud\\"\\n}",'
        '"exit_code":2,"error":null}\n\n'
        "林总，图这块有点情况——这台机器是 Intel Mac 跑 Rosetta，本地跑不了 ComfyUI。\n"
        "有两个方案：\n"
        "1. Comfy Cloud：云端生成。\n"
        "2. 我帮你找现成的：搜一张高清马尔代夫无水印图。"
    )

    sanitized = wechat_gateway._sanitize_wechat_outbound_reply(text)

    assert sanitized.startswith("林总，图这块有点情况")
    assert '"output"' not in sanitized
    assert '"exit_code"' not in sanitized
    assert "system_ram_gb" not in sanitized
