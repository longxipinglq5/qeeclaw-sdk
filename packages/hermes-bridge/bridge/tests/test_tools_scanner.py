from __future__ import annotations

import os
from pathlib import Path

import pytest

from bridge.tools_scanner import scan_edge_skills


class TestToolsScanner:
    def test_scan_finds_skills(self, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

        skill_dir = tmp_path / "skills" / "edge" / "echo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: echo\ndescription: 回显工具\n---\n\n# Echo\n",
            encoding="utf-8",
        )

        tools = scan_edge_skills(force=True)
        assert len(tools) == 1
        assert tools[0].name == "echo"

    def test_scan_includes_legacy_edge_skills_dir(self, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

        skill_dir = tmp_path / "edge-skills" / "legacy-note-writer"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: legacy-note-writer\ndescription: 旧 Edge 技能目录工具\n---\n\n# Legacy\n",
            encoding="utf-8",
        )

        tools = scan_edge_skills(force=True)
        assert [tool.name for tool in tools] == ["legacy-note-writer"]

    def test_empty_dir_returns_empty(self, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))
        tools = scan_edge_skills(force=True)
        assert tools == []

    def test_malformed_skill_skipped(self, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

        skill_dir = tmp_path / "skills" / "edge" / "bad"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")

        tools = scan_edge_skills(force=True)
        assert tools == []

    def test_input_schema_converted(self, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

        skill_dir = tmp_path / "skills" / "edge" / "outline"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: outline\n"
            "description: 大纲\n"
            "input_schema:\n"
            "  - key: topic\n"
            "    type: string\n"
            "    required: true\n"
            "---\n\n# 大纲\n",
            encoding="utf-8",
        )

        tools = scan_edge_skills(force=True)
        assert len(tools) == 1
        schema = tools[0].input_schema
        assert schema is not None
        assert schema["type"] == "object"
        assert "topic" in schema["properties"]
        assert "topic" in schema["required"]

    def test_skill_app_metadata_preserves_ui_and_output_schema(self, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

        skill_dir = tmp_path / "skills" / "edge" / "weather-day-promo-generator"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: weather-day-promo-generator\n"
            "description: 为雨天生成促销话术。\n"
            "category: store\n"
            "icon: \"雨\"\n"
            "input_schema:\n"
            "  - key: weather_context\n"
            "    label: 天气/低峰情况\n"
            "    type: select\n"
            "    required: true\n"
            "    placeholder: \"选择当前情况\"\n"
            "    options: [\"雨天人少\", \"突然降温\"]\n"
            "  - key: target_item\n"
            "    label: 想推项目\n"
            "    type: textarea\n"
            "    required: true\n"
            "    placeholder: \"例如：到店消费项目\"\n"
            "output_schema:\n"
            "  - key: result\n"
            "    label: 生成结果\n"
            "    type: text\n"
            "card_template: text_only\n"
            "---\n\n# 天气低峰促销助手\n",
            encoding="utf-8",
        )

        tools = scan_edge_skills(force=True)

        assert len(tools) == 1
        tool = tools[0]
        assert tool.icon == "雨"
        assert tool.category == "store"
        assert tool.card_template == "text_only"
        assert tool.output_schema == [
            {"key": "result", "label": "生成结果", "type": "text"}
        ]
        schema = tool.input_schema
        assert schema is not None
        assert schema["properties"]["weather_context"] == {
            "type": "string",
            "description": "天气/低峰情况",
            "x_input_type": "select",
            "x_placeholder": "选择当前情况",
            "enum": ["雨天人少", "突然降温"],
        }
        assert schema["properties"]["target_item"] == {
            "type": "string",
            "description": "想推项目",
            "x_input_type": "textarea",
            "x_placeholder": "例如：到店消费项目",
        }
        assert schema["required"] == ["weather_context", "target_item"]
