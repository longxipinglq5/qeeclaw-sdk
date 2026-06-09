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
        skill_dir = tmp_path / "skills" / "edge" / "weather-day-promo-generator"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: weather-day-promo-generator\n"
            "description: 为雨天生成促销话术。\n"
            "category: store\n"
            "icon: \"雨\"\n"
            "input_schema:\n"
            "  - key: weather_context\n"
            "    label: 天气/低峰情况\n"
            "    type: select\n"
            "    required: true\n"
            "    placeholder: \"选择当前情况\"\n"
            "    options: [\"雨天人少\", \"突然降温\"]\n"
            "  - key: target_item\n"
            "    label: 想推项目\n"
            "    type: textarea\n"
            "    required: true\n"
            "    placeholder: \"例如：到店消费项目\"\n"
            "output_schema:\n"
            "  - key: result\n"
            "    label: 生成结果\n"
            "    type: text\n"
            "card_template: text_only\n"
            "---\n\n# 天气低峰促销助手\n",
            encoding="utf-8",
        )
        from bridge.tools_scanner import scan_edge_skills

        scan_edge_skills(force=True)

        resp = await app_client.get("/tools/list")
        assert resp.status_code == 200
        body = resp.json()
        assert "tools" in body
        assert isinstance(body["tools"], list)
        tool = next(
            item for item in body["tools"] if item["name"] == "weather-day-promo-generator"
        )
        assert tool["icon"] == "雨"
        assert tool["category"] == "store"
        assert tool["card_template"] == "text_only"
        assert tool["output_schema"] == [
            {"key": "result", "label": "生成结果", "type": "text"}
        ]
        assert tool["input_schema"]["properties"]["weather_context"] == {
            "type": "string",
            "description": "天气/低峰情况",
            "x_input_type": "select",
            "x_placeholder": "选择当前情况",
            "enum": ["雨天人少", "突然降温"],
        }
        assert tool["input_schema"]["properties"]["target_item"] == {
            "type": "string",
            "description": "想推项目",
            "x_input_type": "textarea",
            "x_placeholder": "例如：到店消费项目",
        }
        assert tool["input_schema"]["required"] == [
            "weather_context",
            "target_item",
        ]


class TestHealthAPI:
    @pytest.mark.asyncio
    async def test_health(self, app_client):
        resp = await app_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"


class TestLLMKeysAPI:
    @pytest.mark.asyncio
    async def test_llm_keys_list(self, app_client, tmp_path, monkeypatch):
        from bridge import legacy_server as _bs

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
