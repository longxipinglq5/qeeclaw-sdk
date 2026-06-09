from __future__ import annotations


def _stable_inputs():
    return {
        "profile_prompt": "你是 Edge supervisor...",
        "product_boundary": "只执行用户授权范围内的营销、客服、运营任务...",
        "capability_manifest": [
            {"capability_id": "xiaohongshu_note_writer", "version": "2026-06-06"},
            {"capability_id": "moments_copywriter_with_image", "version": "2026-06-06"},
        ],
        "business_summary": "品牌主营儿童护眼台灯。",
        "memory_summary": "用户偏好真实、生活化、少硬广。",
        "knowledge_summary": "护眼台灯知识片段 hash=kb_lamp_v1",
    }


def test_context_builder_prefix_hash_is_stable_for_identical_inputs():
    from bridge.runtime_facade.context_builder import ContextBuilder

    builder = ContextBuilder()
    first = builder.build_prefix(**_stable_inputs())
    second = builder.build_prefix(**_stable_inputs())

    assert first.messages == second.messages
    assert builder.prefix_hash(first.messages) == builder.prefix_hash(second.messages)
    assert builder.prefix_hash(first.messages).startswith("sha256:")


def test_current_user_text_does_not_change_prompt_prefix_hash():
    from bridge.runtime_facade.context_builder import ContextBuilder

    builder = ContextBuilder()
    prefix = builder.build_prefix(**_stable_inputs())
    first_messages = builder.build_messages(
        prefix=prefix,
        session_summary="",
        recent_messages=[],
        current_user_text="帮我写一篇小红书",
        channel_metadata={"source": "web"},
    )
    second_messages = builder.build_messages(
        prefix=prefix,
        session_summary="",
        recent_messages=[],
        current_user_text="再帮我写朋友圈",
        channel_metadata={"source": "web"},
    )

    assert builder.prefix_hash(prefix.messages) == prefix.prompt_prefix_hash
    assert first_messages.prompt_prefix_hash == second_messages.prompt_prefix_hash
    assert first_messages.messages[-1] != second_messages.messages[-1]


def test_capability_manifest_version_changes_prompt_prefix_hash():
    from bridge.runtime_facade.context_builder import ContextBuilder

    builder = ContextBuilder()
    old_inputs = _stable_inputs()
    new_inputs = _stable_inputs()
    new_inputs["capability_manifest"] = [
        {"capability_id": "xiaohongshu_note_writer", "version": "2026-06-07"},
        {"capability_id": "moments_copywriter_with_image", "version": "2026-06-06"},
    ]

    old_prefix = builder.build_prefix(**old_inputs)
    new_prefix = builder.build_prefix(**new_inputs)

    assert old_prefix.prompt_prefix_hash != new_prefix.prompt_prefix_hash


def test_context_builder_injects_artifact_summaries_without_prefix_hash_change():
    from bridge.runtime_facade.context_builder import ContextBuilder

    builder = ContextBuilder()
    prefix = builder.build_prefix(**_stable_inputs())
    context = builder.build_messages(
        prefix=prefix,
        session_summary="",
        artifact_summaries=[
            {
                "artifact_id": "art_run_000002",
                "kind": "xiaohongshu_note",
                "title": "小红书种草文",
                "summary": "儿童护眼台灯的小红书种草文。",
                "capability_id": "xiaohongshu_note_writer",
            }
        ],
        recent_messages=[],
        current_user_text="再帮我生成这个产品的朋友圈",
        channel_metadata={"source": "web"},
    )

    artifact_message = context.messages[-2]
    assert artifact_message["role"] == "system"
    assert artifact_message["metadata"] == {"section": "artifact_summaries"}
    assert "art_run_000002" in artifact_message["content"]
    assert "儿童护眼台灯的小红书种草文" in artifact_message["content"]
    assert context.prompt_prefix_hash == prefix.prompt_prefix_hash
