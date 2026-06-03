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
