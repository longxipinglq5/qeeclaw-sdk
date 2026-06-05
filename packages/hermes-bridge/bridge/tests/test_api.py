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
    async def test_invoke_ignores_request_history(self, app_client, mock_agent_class):
        resp = await app_client.post(
            "/chat/invoke",
            json={
                "scenario": "general",
                "session_id": "test-s",
                "user_text": "你好",
                "conversation_history": [{"role": "user", "content": "旧历史"}],
                "context": {"businessContext": "旧上下文"},
            },
        )
        assert resp.status_code == 200

        call_kwargs = mock_agent_class.return_value.run_conversation.call_args.kwargs
        assert call_kwargs["user_message"] == "你好"
        assert call_kwargs["conversation_history"] == []

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


class TestLegacyBridgeCompatibilityAPI:
    @pytest.mark.asyncio
    async def test_channels_overview_includes_plugin_binding_enabled(self, app_client, tmp_path, monkeypatch):
        import bridge_server as _bs

        monkeypatch.setattr(_bs, "_CHANNELS_PLUGIN_CONFIG_FILE", str(tmp_path / "plugin.json"))

        resp = await app_client.get("/api/platform/channels")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        plugin = next(item for item in body["data"] if item["channel_id"] == "wechat_personal_plugin")
        assert plugin["binding_enabled"] is False
        assert plugin["bindingEnabled"] is False

    @pytest.mark.asyncio
    async def test_binding_create_accepts_openclaw_camel_case_payload(self, app_client, tmp_path, monkeypatch):
        import bridge_server as _bs

        monkeypatch.setattr(_bs, "_CHANNELS_PLUGIN_CONFIG_FILE", str(tmp_path / "plugin.json"))
        monkeypatch.setattr(_bs, "_CHANNELS_BINDINGS_FILE", str(tmp_path / "bindings.json"))

        resp = await app_client.post(
            "/api/platform/channels/bindings/create",
            json={
                "teamId": 1,
                "channelKey": "wechat_personal_openclaw",
                "bindingType": "agent",
                "bindingTargetId": "ai-assistant",
                "bindingTargetName": "AI助理",
                "expiresInHours": 72,
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["channel_key"] == "wechat_personal_openclaw"
        assert body["data"]["binding_target_id"] == "ai-assistant"

    @pytest.mark.asyncio
    async def test_binding_list_and_validate_accept_openclaw_camel_case_query(self, app_client, tmp_path, monkeypatch):
        import bridge_server as _bs

        monkeypatch.setattr(_bs, "_CHANNELS_PLUGIN_CONFIG_FILE", str(tmp_path / "plugin.json"))
        monkeypatch.setattr(_bs, "_CHANNELS_BINDINGS_FILE", str(tmp_path / "bindings.json"))

        created_resp = await app_client.post(
            "/api/platform/channels/bindings/create",
            json={
                "teamId": 1,
                "channelKey": "wechat_personal_openclaw",
                "bindingType": "agent",
                "bindingTargetId": "owner_secretary",
                "bindingTargetName": "AI助理",
            },
        )
        assert created_resp.status_code == 200
        created = created_resp.json()["data"]

        list_resp = await app_client.get(
            "/api/platform/channels/bindings",
            params={"teamId": 1, "channelKey": "wechat_personal_openclaw"},
        )
        assert list_resp.status_code == 200
        list_body = list_resp.json()
        assert list_body["success"] is True
        assert list_body["data"]["total"] == 1
        assert list_body["data"]["items"][0]["id"] == created["id"]

        validate_resp = await app_client.get(
            "/api/platform/channels/bindings/validate",
            params={"teamId": 1, "channelKey": "wechat_personal_openclaw"},
        )
        assert validate_resp.status_code == 200
        validate_body = validate_resp.json()
        assert validate_body["success"] is True
        assert validate_body["data"]["channel_key"] == "wechat_personal_openclaw"
        assert validate_body["data"]["bindings_count"] == 1

    @pytest.mark.asyncio
    async def test_gateway_status_is_available_from_fastapi_entrypoint(self, app_client):
        resp = await app_client.get("/gateway/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["running"] is False
        assert body["pid"] is None
        assert body["platforms"] == []
        assert body["activePlatformCount"] == 0
        assert body["platformDetails"] == []

    @pytest.mark.asyncio
    async def test_gateway_supported_platforms_is_available(self, app_client):
        resp = await app_client.get("/gateway/supported-platforms")

        assert resp.status_code == 200
        platforms = resp.json()["platforms"]
        assert {"id": "weixin", "name": "个人微信", "authType": "qr_login", "envVar": "WEIXIN_ACCOUNT_ID"} in platforms

    @pytest.mark.asyncio
    async def test_wechat_status_is_available_from_fastapi_entrypoint(self, app_client):
        resp = await app_client.get("/wechat/status")

        assert resp.status_code == 200
        body = resp.json()
        assert "qr_login" in body
        assert "adapter" in body

    @pytest.mark.asyncio
    async def test_conversations_history_reads_wechat_session_messages(self, app_client, tmp_path, monkeypatch):
        import session_manager as _sm

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr(_sm, "_session_manager", None)

        sm = _sm.get_session_manager()
        session = sm.get_or_create_session(
            session_id="wechat:friend-1",
            user_id="friend-1",
            agent_profile="default",
        )
        session.metadata.update({
            "source": "wechat",
            "channel_id": "wechat_personal_openclaw",
            "chat_id": "friend-1",
        })
        sm.append_turn(session.session_id, "微信消息", "微信回复")

        resp = await app_client.get(
            "/api/platform/conversations/history",
            params={"teamId": 1, "limit": 10},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"][0]["content"] == "微信回复"
        assert body["data"][0]["direction"] == "agent_to_user"
        assert body["data"][0]["channel_id"] == "wechat_personal_openclaw"
        assert body["data"][1]["content"] == "微信消息"
        assert body["data"][1]["direction"] == "user_to_agent"

    @pytest.mark.asyncio
    async def test_cloud_status_is_available_from_fastapi_entrypoint(self, app_client):
        resp = await app_client.get("/cloud/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is False


class TestConfigRuntimeDependencies:
    def test_config_module_does_not_require_pydantic_settings(self):
        import pathlib

        config_path = pathlib.Path(__file__).resolve().parents[1] / "config.py"
        source = config_path.read_text(encoding="utf-8")

        assert "pydantic_settings" not in source


class TestLLMKeysAPI:
    @pytest.mark.asyncio
    async def test_llm_keys_list(self, app_client, tmp_path, monkeypatch):
        import bridge_server as _bs

        monkeypatch.setattr(_bs, "_API_KEYS_FILE", str(tmp_path / "api_keys.json"))
        _bs._save_api_keys({
            "app_keys": [],
            "llm_keys": [
                {
                    "id": 1,
                    "provider": "deepseek",
                    "name": "default",
                    "is_active": True,
                },
            ],
        })

        resp = await app_client.get("/api/llm/keys")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == [
            {
                "id": 1,
                "provider": "deepseek",
                "name": "default",
                "is_active": True,
            },
        ]
