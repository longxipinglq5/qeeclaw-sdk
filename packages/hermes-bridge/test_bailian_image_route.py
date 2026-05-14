#!/usr/bin/env python3

import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

_BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)

os.environ["HERMES_HOME"] = tempfile.mkdtemp(prefix="qeeclaw_image_test_")

import bailian_image
import bridge_server as bs_mod


def _http_request(url, method="GET", data=None):
    body_bytes = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body_bytes, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": resp.status, "body": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": json.loads(exc.read().decode("utf-8"))}


@pytest.fixture
def bridge_server():
    server = HTTPServer(("127.0.0.1", 0), bs_mod.BridgeRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()


def test_build_bailian_image_payload_uses_env_model_and_normalizes_size(monkeypatch):
    monkeypatch.setenv("BAILIAN_IMAGE_MODEL", "env-image-model")
    monkeypatch.setenv("BAILIAN_IMAGE_WATERMARK", "yes")
    monkeypatch.setenv("BAILIAN_IMAGE_THINKING_MODE", "0")

    payload = bailian_image.build_image_payload({
        "prompt": "生成一张办公室插画",
        "model": "wan2.7-image-pro",
        "size": "16:9",
        "n": 99,
    })

    assert payload["model"] == "env-image-model"
    assert payload["input"]["messages"][0]["content"][0]["text"] == "生成一张办公室插画"
    assert payload["parameters"]["size"] == "2560*1440"
    assert payload["parameters"]["n"] == 4
    assert payload["parameters"]["watermark"] is True
    assert payload["parameters"]["thinking_mode"] is False


def test_build_bailian_image_payload_requires_prompt():
    with pytest.raises(ValueError, match="Missing image prompt"):
        bailian_image.build_image_payload({"prompt": "  "})


def test_build_openai_image_payload_fixes_response_format_in_bridge(monkeypatch):
    monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_RESPONSE_FORMAT", raising=False)

    gpt_payload = bailian_image.build_openai_image_payload({
        "model": "gpt-image-2",
        "prompt": "一张产品图",
        "response_format": "url",
        "responseFormat": "url",
        "output_format": "png",
    })
    assert gpt_payload["model"] == "gpt-image-2"
    assert "response_format" not in gpt_payload
    assert gpt_payload["output_format"] == "png"

    dalle_payload = bailian_image.build_openai_image_payload({
        "model": "dall-e-3",
        "prompt": "一张产品图",
        "response_format": "url",
    })
    assert dalle_payload["response_format"] == "b64_json"


def test_normalize_bailian_image_response_returns_edge_shape():
    raw = {
        "model": "wan2.7-image-pro",
        "request_id": "req-123",
        "usage": {"image_count": 1},
        "output": {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"text": "ok"},
                            {"image": "https://example.test/image.png"},
                        ],
                    },
                },
            ],
        },
    }

    result = bailian_image.normalize_image_response(raw)

    assert result["model"] == "wan2.7-image-pro"
    assert result["imageUrl"] == "https://example.test/image.png"
    assert result["data"] == [{"url": "https://example.test/image.png"}]
    assert result["requestId"] == "req-123"
    assert result["usage"] == {"image_count": 1}
    assert result["raw"] is raw


def test_image_generation_route_calls_dashscope_and_returns_normalized_json(monkeypatch, bridge_server):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
    monkeypatch.setenv("BAILIAN_IMAGE_ENDPOINT", "https://dashscope.unit.test")

    captured = {}

    def fake_post(endpoint, api_key, payload, timeout_seconds):
        captured["endpoint"] = endpoint
        captured["api_key"] = api_key
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return {
            "model": payload["model"],
            "request_id": "req-route",
            "usage": {},
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [{"image": "https://example.test/route.png"}],
                        },
                    },
                ],
            },
        }

    monkeypatch.setattr(bailian_image, "post_image_generation", fake_post)

    response = _http_request(
        f"{bridge_server}/api/llm/images/generations",
        "POST",
        {"prompt": "一张产品图", "size": "1:1", "n": 1},
    )

    assert response["status"] == 200
    assert response["body"]["imageUrl"] == "https://example.test/route.png"
    assert response["body"]["data"] == [{"url": "https://example.test/route.png"}]
    assert captured["endpoint"] == "https://dashscope.unit.test"
    assert captured["api_key"] == "test-dashscope-key"
    assert captured["payload"]["parameters"]["size"] == "2048*2048"


def test_image_generation_route_uses_openai_primary(monkeypatch, bridge_server):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_IMAGE_ENDPOINT", "https://openai.unit.test/v1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")

    captured = {}

    def fake_openai_post(endpoint, api_key, payload, timeout_seconds):
        captured["endpoint"] = endpoint
        captured["api_key"] = api_key
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return {
            "created": 123,
            "data": [{"url": "https://example.test/openai.png"}],
        }

    def fail_bailian_post(*_args, **_kwargs):
        raise AssertionError("fallback provider should not be called")

    monkeypatch.setattr(bailian_image, "post_openai_image_generation", fake_openai_post)
    monkeypatch.setattr(bailian_image, "post_image_generation", fail_bailian_post)

    response = _http_request(
        f"{bridge_server}/api/llm/images/generations",
        "POST",
        {"prompt": "一张产品图", "model": "gpt-image-2", "size": "16:9", "n": 1},
    )

    assert response["status"] == 200
    assert response["body"]["imageUrl"] == "https://example.test/openai.png"
    assert response["body"]["provider"] == "openai"
    assert response["body"]["fallbackUsed"] is False
    assert captured["endpoint"] == "https://openai.unit.test/v1"
    assert captured["api_key"] == "test-openai-key"
    assert captured["payload"]["model"] == "gpt-image-2"
    assert captured["payload"]["prompt"] == "一张产品图"
    assert captured["payload"]["size"] == "16:9"


def test_image_generation_route_falls_back_to_bailian_when_openai_unavailable(monkeypatch, bridge_server):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")

    calls = []

    def fake_openai_post(*_args, **_kwargs):
        calls.append("openai")
        raise bailian_image.ImageProviderError("OpenAI image unavailable", provider="openai", retryable=True)

    def fake_bailian_post(endpoint, api_key, payload, timeout_seconds):
        calls.append("bailian")
        assert payload["model"] == "wan2.7-image-pro"
        return {
            "model": payload["model"],
            "request_id": "req-fallback",
            "usage": {},
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [{"image": "https://example.test/fallback.png"}],
                        },
                    },
                ],
            },
        }

    monkeypatch.setattr(bailian_image, "post_openai_image_generation", fake_openai_post)
    monkeypatch.setattr(bailian_image, "post_image_generation", fake_bailian_post)

    response = _http_request(
        f"{bridge_server}/api/llm/images/generations",
        "POST",
        {"prompt": "一张产品图", "model": "gpt-image-2", "size": "1:1", "n": 1},
    )

    assert response["status"] == 200
    assert calls == ["openai", "bailian"]
    assert response["body"]["imageUrl"] == "https://example.test/fallback.png"
    assert response["body"]["provider"] == "bailian"
    assert response["body"]["fallbackUsed"] is True
    assert response["body"]["fallbackFrom"] == "openai"


def test_openai_non_json_success_is_retryable_for_fallback(monkeypatch):
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"<html>not json</html>"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    with pytest.raises(bailian_image.ImageProviderError) as exc_info:
        bailian_image.post_openai_image_generation(
            "https://openai.unit.test/v1",
            "test-openai-key",
            {"model": "gpt-image-2", "prompt": "一张产品图"},
            1,
        )

    assert exc_info.value.provider == "openai"
    assert exc_info.value.retryable is True
    assert "OpenAI image request failed: 200" in str(exc_info.value)


def test_image_generation_route_requires_at_least_one_provider_key(monkeypatch, bridge_server):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)

    response = _http_request(
        f"{bridge_server}/api/llm/images/generations",
        "POST",
        {"prompt": "一张产品图"},
    )

    assert response["status"] == 502
    assert response["body"]["code"] == "IMAGE_GENERATION_FAILED"
    assert "Missing image provider API key" in response["body"]["message"]
