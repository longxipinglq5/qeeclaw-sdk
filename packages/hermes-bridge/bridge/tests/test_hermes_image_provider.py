from __future__ import annotations

import base64
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


PLUGIN_INIT = (
    Path(__file__).resolve().parents[1]
    / "hermes_plugins"
    / "image_gen"
    / "qeeclaw_nexus"
    / "__init__.py"
)
HERMES_AGENT_DIR = Path(__file__).resolve().parents[5] / "vendor" / "hermes-agent"


def _load_plugin_module():
    if str(HERMES_AGENT_DIR) not in sys.path:
        sys.path.insert(0, str(HERMES_AGENT_DIR))
    spec = importlib.util.spec_from_file_location("qeeclaw_nexus_image_plugin_under_test", PLUGIN_INIT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _NexusImageHandler(BaseHTTPRequestHandler):
    response_payload = {}
    response_status = 200
    requests: list[dict] = []

    def do_POST(self):  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(content_length).decode("utf-8")
        self.__class__.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": json.loads(body),
            }
        )
        payload = json.dumps(self.__class__.response_payload).encode("utf-8")
        self.send_response(self.__class__.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A002
        return


@pytest.fixture()
def nexus_server():
    _NexusImageHandler.requests = []
    _NexusImageHandler.response_status = 200
    _NexusImageHandler.response_payload = {}

    server = ThreadingHTTPServer(("127.0.0.1", 0), _NexusImageHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, _NexusImageHandler
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


class TestQeeClawNexusImageProvider:
    def test_generate_posts_to_existing_images_api_and_returns_url(self, nexus_server, monkeypatch):
        module = _load_plugin_module()
        server, handler = nexus_server
        handler.response_payload = {
            "data": [
                {
                    "url": "https://cdn.example.test/image.png",
                    "revised_prompt": "clean prompt",
                }
            ]
        }
        monkeypatch.setenv("NEXUS_URL", f"http://127.0.0.1:{server.server_address[1]}")
        monkeypatch.setenv("NEXUS_API_KEY", "test-nexus-key")

        provider = module.QeeClawNexusImageGenProvider()
        result = provider.generate("一张门店促销海报", aspect_ratio="portrait")

        assert result["success"] is True
        assert result["provider"] == "qeeclaw-nexus"
        assert result["model"] == "gpt-image-2"
        assert result["image"] == "https://cdn.example.test/image.png"
        assert result["revised_prompt"] == "clean prompt"
        assert handler.requests[0]["path"] == "/api/llm/images/generations"
        assert handler.requests[0]["authorization"] == "Bearer test-nexus-key"
        assert handler.requests[0]["body"] == {
            "model": "gpt-image-2",
            "prompt": "一张门店促销海报",
            "size": "1024x1536",
            "n": 1,
            "response_format": "url",
        }

    def test_generate_saves_b64_response_to_hermes_cache(self, nexus_server, monkeypatch, tmp_path):
        module = _load_plugin_module()
        server, handler = nexus_server
        png_b64 = base64.b64encode(b"fake-png").decode("ascii")
        handler.response_payload = {"data": [{"b64_json": png_b64}]}
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("NEXUS_URL", f"http://127.0.0.1:{server.server_address[1]}")

        provider = module.QeeClawNexusImageGenProvider()
        result = provider.generate(
            "一张方形Logo",
            aspect_ratio="square",
            model="seedream-4",
            response_format="b64_json",
        )

        assert result["success"] is True
        assert result["model"] == "seedream-4"
        saved = Path(result["image"])
        assert saved.is_file()
        assert saved.read_bytes() == b"fake-png"
        assert saved.parent == tmp_path / "cache" / "images"
        assert handler.requests[0]["body"]["response_format"] == "b64_json"
        assert handler.requests[0]["body"]["size"] == "1024x1024"

    def test_generate_returns_error_when_nexus_url_missing(self, monkeypatch):
        module = _load_plugin_module()
        monkeypatch.delenv("NEXUS_URL", raising=False)

        provider = module.QeeClawNexusImageGenProvider()
        result = provider.generate("一张图")

        assert result["success"] is False
        assert result["error_type"] == "auth_required"
        assert "NEXUS_URL" in result["error"]
