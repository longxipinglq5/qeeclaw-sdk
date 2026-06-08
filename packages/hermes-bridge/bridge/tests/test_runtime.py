from __future__ import annotations

import pytest

from bridge.runtime import HermesRuntime


class TestLRUCache:
    def test_cache_miss_creates_agent(self, fresh_runtime, mock_agent_class):
        agent = fresh_runtime.get_or_create("session-1")
        mock_agent_class.assert_called_once()
        assert agent is mock_agent_class.return_value

    def test_cache_hit_returns_same_agent(self, fresh_runtime, mock_agent_class):
        a1 = fresh_runtime.get_or_create("session-1")
        mock_agent_class.reset_mock()
        a2 = fresh_runtime.get_or_create("session-1")
        mock_agent_class.assert_not_called()
        assert a1 is a2

    def test_cache_eviction(self, fresh_runtime, mock_agent_class):
        for i in range(5):
            fresh_runtime.get_or_create(f"s-{i}")
        assert fresh_runtime.cache_size == 4
        assert "s-0" not in fresh_runtime._cache

    def test_different_sessions_different_agents(self, fresh_runtime, mock_agent_class):
        fresh_runtime.get_or_create("s-a")
        fresh_runtime.get_or_create("s-b")
        assert mock_agent_class.call_count == 2


class TestInvoke:
    async def test_invoke_calls_run_conversation(
        self, fresh_runtime, mock_agent_class, standard_agent_response
    ):
        mock_agent_class.return_value.run_conversation.return_value = (
            standard_agent_response
        )

        result = await fresh_runtime.invoke(
            session_id="test-s",
            scenario="general",
            user_text="你好",
        )
        mock_agent_class.return_value.run_conversation.assert_called_once()
        call_kwargs = mock_agent_class.return_value.run_conversation.call_args
        assert call_kwargs.kwargs["user_message"] == "你好"
        assert result["final_response"] == "测试回复"

    async def test_invoke_raw_reuses_cached_agent(
        self, fresh_runtime, mock_agent_class, standard_agent_response
    ):
        mock_agent_class.return_value.run_conversation.return_value = (
            standard_agent_response
        )

        await fresh_runtime.invoke_raw(
            session_id="edge:supervisor",
            user_text="你好",
            agent_profile="edge_supervisor",
        )
        await fresh_runtime.invoke_raw(
            session_id="edge:supervisor",
            user_text="继续",
            agent_profile="edge_supervisor",
        )

        mock_agent_class.assert_called_once()
        run_calls = mock_agent_class.return_value.run_conversation.call_args_list
        assert run_calls[0].kwargs["user_message"] == "你好"
        assert run_calls[0].kwargs["conversation_history"] == []
        assert run_calls[1].kwargs["user_message"] == "继续"
        assert run_calls[1].kwargs["conversation_history"] == [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "测试回复"},
        ]

    async def test_edge_supervisor_disables_local_execution_toolsets(
        self, fresh_runtime, mock_agent_class, standard_agent_response
    ):
        mock_agent_class.return_value.run_conversation.return_value = (
            standard_agent_response
        )

        await fresh_runtime.invoke_raw(
            session_id="edge:supervisor",
            user_text="真的要生成图片看看",
            agent_profile="edge_supervisor",
        )

        disabled_toolsets = set(mock_agent_class.call_args.kwargs["disabled_toolsets"])
        assert {
            "browser",
            "terminal",
            "file",
            "debugging",
            "code_execution",
            "computer_use",
            "delegation",
            "todo",
            "skills",
        }.issubset(disabled_toolsets)
        assert mock_agent_class.call_args.kwargs["load_soul_identity"] is False
        assert mock_agent_class.call_args.kwargs["skip_context_files"] is True
        assert mock_agent_class.call_args.kwargs["request_overrides"] == {
            "response_format": {"type": "json_object"}
        }
        assert mock_agent_class.call_args.kwargs["prefill_messages"] == []

    async def test_invoke_raw_history_is_isolated_by_session(
        self, fresh_runtime, mock_agent_class, standard_agent_response
    ):
        mock_agent_class.return_value.run_conversation.return_value = (
            standard_agent_response
        )

        await fresh_runtime.invoke_raw(
            session_id="edge:a",
            user_text="A 第一轮",
            agent_profile="edge_supervisor",
        )
        await fresh_runtime.invoke_raw(
            session_id="edge:b",
            user_text="B 第一轮",
            agent_profile="edge_supervisor",
        )

        run_calls = mock_agent_class.return_value.run_conversation.call_args_list
        assert run_calls[1].kwargs["conversation_history"] == []

    async def test_invoke_uses_server_side_history(
        self, fresh_runtime, mock_agent_class, standard_agent_response
    ):
        mock_agent_class.return_value.run_conversation.return_value = (
            standard_agent_response
        )

        await fresh_runtime.invoke(
            session_id="edge:chat",
            scenario="supervisor",
            user_text="设计一个主机盒子的产品海报",
        )
        await fresh_runtime.invoke(
            session_id="edge:chat",
            scenario="supervisor",
            user_text="小红书用",
            conversation_history=[{"role": "user", "content": "外部历史"}],
        )

        run_calls = mock_agent_class.return_value.run_conversation.call_args_list
        assert run_calls[0].kwargs["conversation_history"] == []
        assert run_calls[1].kwargs["conversation_history"] == [
            {"role": "user", "content": "设计一个主机盒子的产品海报"},
            {"role": "assistant", "content": "测试回复"},
        ]
