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


def test_image_generation_route_requires_dashscope_key(monkeypatch, bridge_server):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)

    response = _http_request(
        f"{bridge_server}/api/llm/images/generations",
        "POST",
        {"prompt": "一张产品图"},
    )

    assert response["status"] == 502
    assert response["body"]["code"] == "BAILIAN_IMAGE_FAILED"
    assert "Missing DASHSCOPE_API_KEY" in response["body"]["message"]
