from __future__ import annotations

import pytest

from bridge.scenarios import get_system_prompt, list_scenarios


class TestScenarios:
    def test_known_scenarios(self):
        for s in list_scenarios():
            prompt = get_system_prompt(s)
            assert prompt, f"scenario {s} 返回空 prompt"

    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError, match="未知 scenario"):
            get_system_prompt("nonexistent")

    def test_general_has_default(self):
        prompt = get_system_prompt("general")
        assert "AI 助理" in prompt

    def test_context_injection(self):
        prompt = get_system_prompt(
            "general", {"company_name": "测试公司", "owner_name": "张总"}
        )
        assert "测试公司" in prompt
        assert "张总" in prompt

    def test_context_none_no_extra(self):
        prompt = get_system_prompt("general", None)
        assert "当前上下文" not in prompt
