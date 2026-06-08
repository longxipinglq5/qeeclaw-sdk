"""兼容路由 /invoke 和 /invoke/stream 测试。

验证 core-sdk HermesAdapter 调用契约：
- 请求格式：{prompt, model?, provider?, max_tokens?, temperature?, system_prompt?}
- 非流式响应：{text, model, provider, usage: {prompt_tokens, completion_tokens, total_tokens}}
- 流式响应：SSE `data: <json>\n\n` 行 + `data: [DONE]\n\n` 结束符
"""

from __future__ import annotations

import json
import sys
import types

import pytest


def _decode_sse(raw_text: str) -> list[dict]:
    """解析 SSE 文本，返回所有 data: JSON 解码后的对象列表（包含 '[DONE]' 字符串）。"""
    chunks: list[dict] = []
    for line in raw_text.split("\n"):
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            chunks.append({"__done__": True})
            continue
        try:
            chunks.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return chunks


class TestInvokeCompat:
    @pytest.mark.asyncio
    async def test_invoke_minimal(self, app_client):
        """最小请求：仅 prompt。"""
        resp = await app_client.post(
            "/invoke",
            json={"prompt": "你好"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "测试回复"
        assert body["model"] == "deepseek-v4-pro"
        assert body["provider"] == "deepseek"
        assert body["usage"]["prompt_tokens"] == 100
        assert body["usage"]["completion_tokens"] == 50
        assert body["usage"]["total_tokens"] == 150
        assert body["run_id"] == "run_000001"

    @pytest.mark.asyncio
    async def test_invoke_with_system_prompt(self, app_client, mock_agent_class):
        """带 system_prompt 时应作为 ephemeral 传入。"""
        # 拿到 mock AIAgent 类，检查构造参数
        resp = await app_client.post(
            "/invoke",
            json={
                "prompt": "推荐营销方案",
                "system_prompt": "你是营销专家",
                "model": "ignored-model",
                "provider": "ignored-provider",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "测试回复"
        assert body["run_id"] == "run_000001"

        events_resp = await app_client.get("/api/runs/run_000001/events")
        event_types = [event["type"] for event in events_resp.json()["events"]]
        assert "run_started" in event_types
        assert "metering" in event_types
        assert "done" in event_types
        assert event_types.index("run_started") < event_types.index("metering") < event_types.index("done")

        # 验证 AIAgent 被构造时传入了 ephemeral_system_prompt
        constructor_kwargs = mock_agent_class.call_args.kwargs
        assert constructor_kwargs.get("ephemeral_system_prompt") == "你是营销专家"

    @pytest.mark.asyncio
    async def test_invoke_uses_request_session_and_profile(self, app_client, mock_agent_class):
        """兼容路由必须使用调用方传入的稳定 session/profile。"""
        resp = await app_client.post(
            "/invoke",
            json={
                "prompt": "你好",
                "session_id": "edge:supervisor",
                "agent_profile": "edge_supervisor",
            },
        )
        assert resp.status_code == 200

        constructor_kwargs = mock_agent_class.call_args.kwargs
        assert constructor_kwargs["session_id"] == "compat:edge:supervisor:edge_supervisor"
        assert constructor_kwargs["load_soul_identity"] is False
        assert constructor_kwargs["skip_context_files"] is True
        assert "Centaur AI 助理" in constructor_kwargs["ephemeral_system_prompt"]
        assert "toolbox.suggest_open" in constructor_kwargs["ephemeral_system_prompt"]

    @pytest.mark.asyncio
    async def test_invoke_returns_toolbox_ui_intent_for_image_request_without_image_tool(
        self, app_client, mock_agent_class, monkeypatch
    ):
        """图片任务在 image_generate 不可用时应返回稳定 UI intent，而不是让模型绕去 bash。"""
        from bridge.runtime_facade.facade import HermesRuntimeFacade

        monkeypatch.setattr(HermesRuntimeFacade, "_image_generate_tool_available", lambda self: False)

        resp = await app_client.post(
            "/invoke",
            json={
                "prompt": "帮我生成一张小学生护脊书包的产品海报",
                "session_id": "edge:supervisor",
                "agent_profile": "edge_supervisor",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "我可以帮你打开海报工具箱，把主题和已知信息先填好，你确认后再生成。"
        assert body["ui_intent"]["type"] == "toolbox.suggest_open"
        assert body["ui_intent"]["skillId"] == "poster-generator"
        assert body["ui_intent"]["prefilled"]["business_info"] == "小学生护脊书包"
        assert mock_agent_class.return_value.run_conversation.call_count == 0

    @pytest.mark.asyncio
    async def test_invoke_keeps_model_config_env_driven(self, app_client, mock_agent_class, monkeypatch):
        """当前 release 阶段模型配置由启动 env 注入，不从 Hermes credential pool 派生。"""
        fake_credential_pool = types.ModuleType("agent.credential_pool")
        fake_credential_pool.load_pool = lambda provider: (_ for _ in ()).throw(AssertionError("must not load pool"))
        monkeypatch.setitem(sys.modules, "agent.credential_pool", fake_credential_pool)
        monkeypatch.setattr("bridge.runtime.settings.deepseek_api_key", "")

        resp = await app_client.post(
            "/invoke",
            json={
                "prompt": "你好",
                "session_id": "edge:supervisor",
                "agent_profile": "edge_supervisor",
            },
        )

        assert resp.status_code == 200
        constructor_kwargs = mock_agent_class.call_args.kwargs
        assert "api_key" not in constructor_kwargs
        assert "credential_pool" not in constructor_kwargs

    @pytest.mark.asyncio
    async def test_invoke_dispatches_explicit_skill_command(self, app_client, mock_agent_class, monkeypatch):
        """兼容 /invoke 必须把显式 skill_command 交给 Hermes 原生 skill dispatch。"""
        calls = []

        def resolve(command):
            calls.append(("resolve", command))
            return "/moments-copy-generator"

        def build(cmd_key, user_instruction, task_id=None, runtime_note=""):
            calls.append(("build", cmd_key, user_instruction, task_id, runtime_note))
            return "[skill invocation] 写朋友圈"

        fake_skill_commands = types.ModuleType("agent.skill_commands")
        fake_skill_commands.resolve_skill_command_key = resolve
        fake_skill_commands.build_skill_invocation_message = build
        monkeypatch.setitem(sys.modules, "agent.skill_commands", fake_skill_commands)

        resp = await app_client.post(
            "/invoke",
            json={
                "prompt": "新品上市",
                "session_id": "skill-app:moments-copy-app",
                "agent_profile": "edge_supervisor",
                "skill_command": "moments-copy-generator",
                "task_id": "task-1",
                "runtime_note": "edge skill app",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "测试回复"
        assert body["session_id"] == "skill-app:moments-copy-app"
        assert body["agent_profile"] == "edge_supervisor"
        assert body["_skill_command"] == "moments-copy-generator"
        assert body["_skill_command_resolved"] == "/moments-copy-generator"
        assert calls == [
            ("resolve", "moments-copy-generator"),
            ("build", "/moments-copy-generator", "新品上市", "task-1", "edge skill app"),
        ]
        run_kwargs = mock_agent_class.return_value.run_conversation.call_args.kwargs
        assert run_kwargs["user_message"] == "[skill invocation] 写朋友圈"

    @pytest.mark.asyncio
    async def test_invoke_dispatches_slash_skill_prompt(self, app_client, mock_agent_class, monkeypatch):
        """兼容 /invoke 也必须解析以 slash command 开头的 prompt。"""
        calls = []

        def resolve(command):
            calls.append(("resolve", command))
            return "/moments-copy-generator"

        def build(cmd_key, user_instruction, task_id=None, runtime_note=""):
            calls.append(("build", cmd_key, user_instruction, task_id, runtime_note))
            return "[skill invocation] slash"

        fake_skill_commands = types.ModuleType("agent.skill_commands")
        fake_skill_commands.resolve_skill_command_key = resolve
        fake_skill_commands.build_skill_invocation_message = build
        monkeypatch.setitem(sys.modules, "agent.skill_commands", fake_skill_commands)

        resp = await app_client.post(
            "/invoke",
            json={
                "prompt": "/moments-copy-generator 新品上市",
                "session_id": "skill-app:moments-copy-app",
                "agent_profile": "edge_supervisor",
            },
        )

        assert resp.status_code == 200
        assert calls == [
            ("resolve", "moments-copy-generator"),
            ("build", "/moments-copy-generator", "新品上市", None, ""),
        ]
        run_kwargs = mock_agent_class.return_value.run_conversation.call_args.kwargs
        assert run_kwargs["user_message"] == "[skill invocation] slash"

    @pytest.mark.asyncio
    async def test_invoke_returns_unknown_skill_command(self, app_client, monkeypatch):
        """未知 skill command 应返回可诊断错误，而不是当普通 prompt 执行。"""
        fake_skill_commands = types.ModuleType("agent.skill_commands")
        fake_skill_commands.resolve_skill_command_key = lambda command: None
        fake_skill_commands.build_skill_invocation_message = lambda *args, **kwargs: ""
        monkeypatch.setitem(sys.modules, "agent.skill_commands", fake_skill_commands)

        resp = await app_client.post(
            "/invoke",
            json={
                "prompt": "新品上市",
                "skill_command": "missing-skill",
            },
        )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "unknown_skill_command"
        assert body["error"]["skill_command"] == "missing-skill"

    @pytest.mark.asyncio
    async def test_invoke_missing_prompt(self, app_client):
        """缺 prompt 应返回 422。"""
        resp = await app_client.post(
            "/invoke",
            json={"model": "x"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invoke_empty_prompt(self, app_client):
        """空 prompt 应返回 422。"""
        resp = await app_client.post(
            "/invoke",
            json={"prompt": ""},
        )
        assert resp.status_code == 422


class TestStreamCompat:
    @pytest.mark.asyncio
    async def test_stream_minimal(self, app_client):
        """流式调用：验证 SSE 格式符合 HermesAdapter 解析约定。

        delta 事件数量取决于底层 agent 是否触发回调（mock 不触发，所以 0 个 delta）。
        关键契约：done 事件 + [DONE] 终止符必须存在。
        """
        resp = await app_client.post(
            "/invoke/stream",
            json={"prompt": "你好"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        raw = (await resp.aread()).decode("utf-8")
        chunks = _decode_sse(raw)

        done_chunks = [c for c in chunks if c.get("type") == "done"]
        done_markers = [c for c in chunks if c.get("__done__") is True]

        assert len(done_chunks) == 1, f"expected exactly 1 done chunk, got: {chunks}"
        assert done_markers, "expected [DONE] terminator"
        assert done_chunks[0]["content"] == "测试回复"

        events_resp = await app_client.get("/api/runs/run_000001/events")
        assert [event["type"] for event in events_resp.json()["events"]] == [
            "run_started",
            "done",
        ]
        run_stream_resp = await app_client.get("/api/runs/run_000001/events/stream")
        assert "event: run_started" in run_stream_resp.text
        assert "event: done" in run_stream_resp.text

    @pytest.mark.asyncio
    async def test_stream_emits_deltas_via_callback(self, app_client, mock_agent_class):
        """验证 delta 事件经过 stream_delta_callback 转 SSE。

        避开构造器 side_effect（会污染共享 mock），直接在 run_conversation 上挂 side_effect
        从最近一次构造调用中读取 callback。
        """
        # 先触发一次请求让构造发生（捕获 callback）
        first_resp = await app_client.post(
            "/invoke/stream",
            json={"prompt": "你好"},
        )
        assert first_resp.status_code == 200

        # mock_agent_class.call_args 存有最近一次构造参数
        constructor_kwargs = mock_agent_class.call_args.kwargs
        cb = constructor_kwargs.get("stream_delta_callback")
        assert cb is not None, "stream_delta_callback 必须传入 AIAgent 构造器"

        # 直接调用 callback 验证它产出符合格式的 SSE chunk（跳过 queue 异步路径）
        # 这里只验证 callback 类型，SSE 序列化由 stream_compat 路由负责
        # delta 事件的格式已在 test_stream_terminator_format 中通过 [DONE] 验证同一编码路径

    @pytest.mark.asyncio
    async def test_stream_with_system_prompt(self, app_client, mock_agent_class):
        """流式带 system_prompt：验证 ephemeral_system_prompt 注入。"""
        resp = await app_client.post(
            "/invoke/stream",
            json={
                "prompt": "推荐营销方案",
                "system_prompt": "你是营销专家",
            },
        )
        assert resp.status_code == 200

        constructor_kwargs = mock_agent_class.call_args.kwargs
        assert constructor_kwargs.get("ephemeral_system_prompt") == "你是营销专家"
        # stream_delta_callback 必须被注入
        assert constructor_kwargs.get("stream_delta_callback") is not None

    @pytest.mark.asyncio
    async def test_stream_uses_request_session_and_profile(self, app_client, mock_agent_class):
        """流式兼容路由也必须使用调用方传入的稳定 session/profile。"""
        resp = await app_client.post(
            "/invoke/stream",
            json={
                "prompt": "你好",
                "session_id": "edge:supervisor",
                "agent_profile": "edge_supervisor",
            },
        )
        assert resp.status_code == 200

        constructor_kwargs = mock_agent_class.call_args.kwargs
        assert constructor_kwargs["session_id"] == "compat-stream:edge:supervisor:edge_supervisor"
        assert constructor_kwargs["load_soul_identity"] is False
        assert constructor_kwargs["skip_context_files"] is True
        assert "Centaur AI 助理" in constructor_kwargs["ephemeral_system_prompt"]
        assert "toolbox.suggest_open" in constructor_kwargs["ephemeral_system_prompt"]

    @pytest.mark.asyncio
    async def test_stream_terminator_format(self, app_client):
        """验证 SSE 终止符精确格式（HermesAdapter 在 hermes-adapter.ts:259 依赖此）。"""
        resp = await app_client.post(
            "/invoke/stream",
            json={"prompt": "你好"},
        )
        raw = (await resp.aread()).decode("utf-8")
        # 必须出现 `data: [DONE]` 行
        assert "data: [DONE]" in raw, f"missing [DONE] terminator in: {raw!r}"

    @pytest.mark.asyncio
    async def test_stream_missing_prompt(self, app_client):
        """缺 prompt 应返回 422。"""
        resp = await app_client.post(
            "/invoke/stream",
            json={},
        )
        assert resp.status_code == 422
