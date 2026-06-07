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

    def test_supervisor_routes_internal_tool_matches_to_toolbox_form(self):
        prompt = get_system_prompt("supervisor", agent_profile="edge_supervisor")
        assert "命中内部 AI工具箱工具" in prompt
        assert "禁止直接返回 result_preview" in prompt
        assert "open_skill_app" in prompt
        assert "skill_id" in prompt
        assert "不要直接返回最终生成结果" in prompt
        assert "短回复" in prompt
        assert "马尔代夫" in prompt
        assert "雨天人少" in prompt
        assert 'execution_mode 必须设为 "toolbox"' in prompt
        assert "前端会导航到对应工具表单页" in prompt

    def test_context_none_no_extra(self):
        prompt = get_system_prompt("general", None)
        assert "当前上下文" not in prompt
