from __future__ import annotations

import pytest


class TestInvokeAPI:
    @pytest.mark.asyncio
    async def test_invoke_success(self, app_client):
        resp = await app_client.post(
            "/chat/invoke",
            json={
                "scenario": "general",
                "session_id": "test-s",
                "user_text": "你好",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["final_response"] == "测试回复"
        assert body["completed"] is True
        assert body["session_id"] == "test-s"

    @pytest.mark.asyncio
    async def test_invoke_unknown_scenario(self, app_client):
        resp = await app_client.post(
            "/chat/invoke",
            json={
                "scenario": "nonexistent",
                "session_id": "test-s",
                "user_text": "你好",
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] is not None
        assert "nonexistent" in body["error"]

    @pytest.mark.asyncio
    async def test_invoke_missing_fields(self, app_client):
        resp = await app_client.post(
            "/chat/invoke",
            json={"scenario": "general"},
        )
        assert resp.status_code == 422


class TestToolsListAPI:
    @pytest.mark.asyncio
    async def test_tools_list(self, app_client, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))
        from bridge.tools_scanner import scan_edge_skills

        scan_edge_skills(force=True)

        resp = await app_client.get("/tools/list")
        assert resp.status_code == 200
        body = resp.json()
        assert "tools" in body
        assert isinstance(body["tools"], list)


class TestHealthAPI:
    @pytest.mark.asyncio
    async def test_health(self, app_client):
        resp = await app_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
