import json
import urllib.request

from httpx import ASGITransport, AsyncClient


async def test_llm_images_generation_uses_configurable_timeout(monkeypatch):
    from bridge.main import create_app

    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"created": 0, "data": [{"url": "https://cdn.example/image.png"}]}).encode("utf-8")

    def fake_urlopen(req, timeout):
        calls.append({"url": req.full_url, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setenv("NEXUS_URL", "https://nexus.example")
    monkeypatch.setenv("NEXUS_API_KEY", "test-token")
    monkeypatch.setenv("NEXUS_IMAGE_TIMEOUT_SECONDS", "480")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/llm/images/generations",
            json={"prompt": "business card preview", "response_format": "url"},
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["url"] == "https://cdn.example/image.png"
    assert calls == [{"url": "https://nexus.example/api/llm/images/generations", "timeout": 480.0}]


async def test_llm_images_generation_falls_back_to_llm_timeout(monkeypatch):
    from bridge.main import create_app

    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"created": 0, "data": [{"url": "https://cdn.example/image.png"}]}).encode("utf-8")

    def fake_urlopen(req, timeout):
        calls.append(timeout)
        return FakeResponse()

    monkeypatch.setenv("NEXUS_URL", "https://nexus.example")
    monkeypatch.setenv("NEXUS_API_KEY", "test-token")
    monkeypatch.delenv("NEXUS_IMAGE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("NEXUS_LLM_TIMEOUT_SECONDS", "360")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/llm/images/generations",
            json={"prompt": "business card preview", "response_format": "url"},
        )

    assert response.status_code == 200
    assert calls == [360.0]
