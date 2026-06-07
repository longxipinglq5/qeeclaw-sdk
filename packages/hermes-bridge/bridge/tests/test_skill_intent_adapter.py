from __future__ import annotations


def test_skill_catalog_provider_preloads_and_serves_cached_tools(monkeypatch):
    from bridge.runtime_facade.skill_catalog_provider import EdgeSkillCatalogProvider

    calls = []

    class Tool:
        def __init__(self, name):
            self.name = name

        def model_dump(self, mode="json"):
            return {"name": self.name, "description": "测试工具"}

    def fake_scan(force=False):
        calls.append(force)
        return [Tool("poster-generator")]

    provider = EdgeSkillCatalogProvider(scanner=fake_scan, ttl_seconds=60)
    provider.preload()

    assert provider.as_dicts() == [{"name": "poster-generator", "description": "测试工具"}]
    assert provider.as_dicts() == [{"name": "poster-generator", "description": "测试工具"}]
    assert calls == [True]


def test_extract_open_skill_app_card_intent():
    from bridge.runtime_facade.skill_intent_adapter import extract_skill_use_intent

    text = (
        '{"card_type":"open_skill_app","speech":"我帮你打开工具生成。",'
        '"data":{"skill_id":"poster-generator","skill_name":"海报生成器",'
        '"summary":"为当前朋友圈文案生成配图","auto_run":true,'
        '"prefilled":{"purpose":"朋友圈配图","theme":"马尔代夫旅游海景"}}}'
    )

    intent = extract_skill_use_intent({"final_response": text})

    assert intent is not None
    assert intent.skill_id == "poster-generator"
    assert intent.skill_name == "海报生成器"
    assert intent.auto_run is True
    assert intent.prefilled == {
        "purpose": "朋友圈配图",
        "theme": "马尔代夫旅游海景",
    }


def test_extract_legacy_intent_confirm_toolbox_intent():
    from bridge.runtime_facade.skill_intent_adapter import extract_skill_use_intent

    text = (
        '{"card_type":"intent_confirm","speech":"打开工具箱。",'
        '"data":{"skill_id":"weather-day-promo-generator",'
        '"execution_mode":"toolbox",'
        '"prefilled":{"weather_context":"雨天人少","target_item":"到店项目"},'
        '"summary":"生成雨天促销朋友圈"}}'
    )

    intent = extract_skill_use_intent({"final_response": text})

    assert intent is not None
    assert intent.skill_id == "weather-day-promo-generator"
    assert intent.prefilled["weather_context"] == "雨天人少"


def test_ignore_plain_text_without_skill_intent():
    from bridge.runtime_facade.skill_intent_adapter import extract_skill_use_intent

    assert extract_skill_use_intent({"final_response": "你好，我可以帮你。"}) is None


def test_extract_json_does_not_greedily_merge_multiple_objects():
    from bridge.runtime_facade.skill_intent_adapter import _parse_json_object

    parsed = _parse_json_object(
        '前置说明 {"ignored": true} '
        '{"card_type":"open_skill_app","data":{"skill_id":"poster-generator"}}'
    )

    assert parsed == {"ignored": True}


def test_validate_skill_intent_rejects_unknown_skill():
    from bridge.runtime_facade.skill_intent_adapter import SkillUseIntent, validate_skill_use_intent

    intent = SkillUseIntent(skill_id="missing-tool", prefilled={})
    validated = validate_skill_use_intent(intent, tools=[{"name": "poster-generator"}])

    assert validated.status == "rejected"
    assert "不存在" in validated.reason


def test_validate_skill_intent_keeps_only_schema_fields():
    from bridge.runtime_facade.skill_intent_adapter import SkillUseIntent, validate_skill_use_intent

    intent = SkillUseIntent(
        skill_id="poster-generator",
        prefilled={
            "purpose": "朋友圈配图",
            "theme": "马尔代夫海景",
            "unknown": "不要传递",
        },
    )
    validated = validate_skill_use_intent(
        intent,
        tools=[
            {
                "name": "poster-generator",
                "input_schema": {
                    "type": "object",
                    "properties": {"purpose": {}, "theme": {}},
                    "required": ["purpose", "theme"],
                },
            }
        ],
    )

    assert validated.status == "accepted"
    assert validated.intent.prefilled == {
        "purpose": "朋友圈配图",
        "theme": "马尔代夫海景",
    }


def test_validate_skill_intent_missing_required_field_needs_clarification():
    from bridge.runtime_facade.skill_intent_adapter import SkillUseIntent, validate_skill_use_intent

    intent = SkillUseIntent(
        skill_id="poster-generator",
        prefilled={"purpose": "朋友圈配图"},
    )
    validated = validate_skill_use_intent(
        intent,
        tools=[
            {
                "name": "poster-generator",
                "input_schema": {
                    "type": "object",
                    "properties": {"purpose": {}, "theme": {}},
                    "required": ["purpose", "theme"],
                },
            }
        ],
    )

    assert validated.status == "needs_clarification"
    assert validated.missing_inputs == ["theme"]
