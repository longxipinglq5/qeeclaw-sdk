from __future__ import annotations

import json
import urllib.request


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"text": "测试回复"}).encode("utf-8")


def test_wechat_ai_uses_edge_supervisor_native_invoke(monkeypatch):
    import wechat_gateway

    captured = {}

    class FakeRequest:
        def __init__(self, url, data=None, headers=None, method=None):
            captured["url"] = url
            captured["payload"] = json.loads(data.decode("utf-8"))
            captured["headers"] = headers
            captured["method"] = method

    monkeypatch.delenv("WEIXIN_AI_INVOKE_URL", raising=False)
    monkeypatch.delenv("WEIXIN_AGENT_PROFILE", raising=False)
    monkeypatch.setattr(urllib.request, "Request", FakeRequest)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: _FakeResponse())

    reply = wechat_gateway._invoke_wechat_ai("你好", "user-1", "chat-1")

    assert reply == "测试回复"
    assert captured["url"] == "http://127.0.0.1:21747/invoke"
    assert captured["payload"]["prompt"] == "你好"
    assert captured["payload"]["session_id"] == "wechat:chat-1"
    assert captured["payload"]["agent_profile"] == "edge_supervisor"
    assert "system_prompt" not in captured["payload"]
