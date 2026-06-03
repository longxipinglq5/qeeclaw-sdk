from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# 在 import bridge 模块前 mock 掉 run_agent.AIAgent
_mock_agent_module = types.ModuleType("run_agent")
_MockAIAgent = MagicMock(name="AIAgent")
_mock_agent_module.AIAgent = _MockAIAgent
sys.modules["run_agent"] = _mock_agent_module


@pytest.fixture(autouse=True)
def _ensure_settings():
    import os

    os.environ.setdefault("DEEPSEEK_API_KEY", "test-key-for-unit-tests")


@pytest.fixture()
def mock_agent_class():
    _MockAIAgent.reset_mock()
    _MockAIAgent.return_value = MagicMock(name="AIAgent-instance")
    return _MockAIAgent


@pytest.fixture()
def fresh_runtime(mock_agent_class):
    from bridge.runtime import HermesRuntime

    runtime = HermesRuntime(max_size=4)
    runtime._AIAgent = mock_agent_class
    return runtime


@pytest.fixture()
def standard_agent_response():
    return {
        "final_response": "测试回复",
        "completed": True,
        "failed": False,
        "model": "deepseek-v4-pro",
        "provider": "deepseek",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "session_id": "test-session",
    }


@pytest.fixture()
async def app_client(fresh_runtime, standard_agent_response):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app

    fresh_runtime._AIAgent.return_value.run_conversation.return_value = (
        standard_agent_response
    )

    app = create_app()
    app.state.runtime = fresh_runtime

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
