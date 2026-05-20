import importlib.util
import json
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class _BackendHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8") or "{}")
        self.__class__.received.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "payload": payload,
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "code": 0,
            "data": {
                "text": "backend text ok",
                "model": "backend-default-chat",
            },
            "message": "success",
        }).encode("utf-8"))

    def log_message(self, _format, *_args):
        return


def _start_server(handler_class):
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _load_bridge(monkeypatch, tmp_path, backend_url):
    bridge_dir = Path(__file__).parent
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    monkeypatch.setenv("HERMES_BRIDGE_API_KEY", "")
    monkeypatch.setenv("QEECLAW_HERMES_AGENT_DIR", str(tmp_path))
    monkeypatch.setenv("NEXUS_URL", backend_url)
    monkeypatch.setenv("NEXUS_API_KEY", "backend-key")
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    spec = importlib.util.spec_from_file_location(
        "bridge_backend_proxy_under_test",
        bridge_dir / "bridge_server.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bridge_backend_proxy_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_platform_models_invoke_proxies_to_nexus_backend_without_model(tmp_path, monkeypatch):
    _BackendHandler.received = []
    backend = _start_server(_BackendHandler)
    backend_url = f"http://127.0.0.1:{backend.server_address[1]}"
    bridge = _load_bridge(monkeypatch, tmp_path, backend_url)
    bridge_server = _start_server(bridge.BridgeRequestHandler)

    try:
        status, body = _post_json(
            f"http://127.0.0.1:{bridge_server.server_address[1]}/api/platform/models/invoke",
            {"prompt": "ping backend"},
        )
    finally:
        bridge_server.shutdown()
        backend.shutdown()

    assert status == 200
    assert body["text"] == "backend text ok"
    assert body["model"] == "backend-default-chat"
    assert body["raw"]["data"]["text"] == "backend text ok"
    assert _BackendHandler.received == [{
        "path": "/api/platform/models/invoke",
        "authorization": "Bearer backend-key",
        "payload": {"prompt": "ping backend"},
    }]
