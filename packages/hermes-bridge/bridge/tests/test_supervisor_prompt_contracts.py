from __future__ import annotations


def test_supervisor_prompt_is_centaur_assistant_not_hermes_card_router():
    from bridge.scenarios import get_system_prompt

    prompt = get_system_prompt("supervisor", agent_profile="edge_supervisor")

    assert "Centaur AI 助理" in prompt
    assert "用户不需要知道 Hermes" in prompt
    assert "自然语言回复" in prompt
    assert "toolbox.suggest_open" in prompt
    assert "必须由用户确认" in prompt
    assert "auto_run=true" not in prompt
    assert "open_skill_app" not in prompt
    assert "You must return exactly one json object" not in prompt
    assert "{{SKILL_CATALOG}}" not in prompt
    assert "全部字段" not in prompt


def test_supervisor_prompt_routes_image_generation_without_bash_or_comfyui():
    from bridge.scenarios import get_system_prompt

    prompt = get_system_prompt("supervisor", agent_profile="edge_supervisor")

    assert "image_generate" in prompt
    assert "toolset: image_gen" in prompt
    assert "不要调用 bash" in prompt
    assert "不要加载或遵循 ComfyUI" in prompt
    assert "工具箱" in prompt
    assert "没有生图执行环境" in prompt
