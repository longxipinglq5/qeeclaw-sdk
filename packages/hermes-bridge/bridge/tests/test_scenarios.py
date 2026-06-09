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

    def test_request_context_is_not_injected(self):
        prompt = get_system_prompt(
            "supervisor",
            {
                "company_name": "测试公司",
                "owner_name": "张总",
                "ownerContext": "来自 Edge 的记忆",
                "businessContext": "来自 Edge 的企业资料",
                "pageContext": "来自 Edge 的页面上下文",
                "taskContext": "来自 Edge 的任务上下文",
                "expertRules": "来自 Edge 的专家规则",
                "expertCatalog": "来自 Edge 的专家列表",
            },
        )
        assert "测试公司" not in prompt
        assert "张总" not in prompt
        assert "来自 Edge 的记忆" not in prompt
        assert "来自 Edge 的企业资料" not in prompt
        assert "来自 Edge 的页面上下文" not in prompt
        assert "来自 Edge 的任务上下文" not in prompt
        assert "来自 Edge 的专家规则" not in prompt
        assert "来自 Edge 的专家列表" not in prompt

    def test_supervisor_suggests_toolbox_without_embedding_tool_catalog(self):
        prompt = get_system_prompt("supervisor", agent_profile="edge_supervisor")
        assert "工具箱" in prompt
        assert "标准化产出任务" in prompt
        assert "toolbox.suggest_open" in prompt
        assert "requiresConfirmation" in prompt
        assert "autoRun" in prompt
        assert "false" in prompt
        assert "scan_edge_skills" not in prompt

    def test_context_none_no_extra(self):
        prompt = get_system_prompt("general", None)
        assert "当前上下文" not in prompt
