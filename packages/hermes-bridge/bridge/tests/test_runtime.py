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
