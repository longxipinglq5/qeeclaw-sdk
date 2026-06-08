from __future__ import annotations


def test_supervisor_prompt_routes_image_confirmation_to_poster_skill():
    from bridge.scenarios import get_system_prompt

    prompt = get_system_prompt("supervisor", agent_profile="edge_supervisor")

    assert "真的要生成图片看看" in prompt
    assert "poster-generator" in prompt
    assert "open_skill_app" in prompt
    assert "json object" in prompt
    assert "ComfyUI" in prompt
    assert "不要解释本机 ComfyUI" in prompt
    assert "不要声称上下文压缩、历史丢失或找不回上一轮内容" in prompt
    assert "用户当前消息里复述的上一轮内容就是可用上下文" in prompt
    assert '"purpose":"朋友圈配图"' in prompt
    assert '"style":"真实摄影海报"' in prompt
    assert '"ratio":"3:4"' in prompt
