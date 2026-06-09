from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

from bridge.expert_catalog import get_centaur_expert
from bridge.expert_workspace import (
    ensure_expert_external_dir,
    render_expert_workspace,
    sync_expert_workspaces,
)
from bridge.invocation import resolve_skill_dispatch


def test_render_expert_workspace_contains_four_files() -> None:
    expert = get_centaur_expert("professional-service-growth-strategist")

    rendered = render_expert_workspace(expert)

    assert set(rendered) == {"SKILL.md", "SOUL.md", "AGENTS.md", "IDENTITY.md"}
    assert "企业服务获客策略师" in rendered["SOUL.md"]
    assert "professional-service-growth-strategist" in rendered["IDENTITY.md"]


def test_skill_frontmatter_uses_yaml_block_scalar_description() -> None:
    expert = get_centaur_expert("professional-service-growth-strategist")

    skill_md = render_expert_workspace(expert)["SKILL.md"]

    assert "description: |-\n  企业服务获客策略师，负责企业服务增长、获客路径和线索转化。" in skill_md
    assert "1. Read and adopt the persona in `${HERMES_SKILL_DIR}/SOUL.md`." in skill_md
    assert "2. Follow operational instructions in `${HERMES_SKILL_DIR}/AGENTS.md`." in skill_md
    assert "3. Use `${HERMES_SKILL_DIR}/IDENTITY.md` for agent identity context." in skill_md


def test_sync_expert_workspaces_writes_skill_files(tmp_path: Path) -> None:
    expert = get_centaur_expert("professional-service-growth-strategist")

    root = sync_expert_workspaces(tmp_path, [expert])

    assert root == tmp_path / "centaur-experts"
    assert (root / expert.hermes_skill / "SKILL.md").is_file()
    assert (root / expert.hermes_skill / "SOUL.md").is_file()


def test_sync_expert_workspaces_is_idempotent(tmp_path: Path) -> None:
    expert = get_centaur_expert("professional-service-growth-strategist")

    root = sync_expert_workspaces(tmp_path, [expert])
    skill_path = root / expert.hermes_skill / "SKILL.md"
    first_mtime = skill_path.stat().st_mtime_ns
    sync_expert_workspaces(tmp_path, [expert])

    assert skill_path.stat().st_mtime_ns == first_mtime


def test_external_dir_registration_handles_empty_inline_list(tmp_path: Path) -> None:
    expert_dir = tmp_path / "centaur-experts"
    expert_dir.mkdir()
    (tmp_path / "config.yaml").write_text("skills:\n  external_dirs: []\n", encoding="utf-8")

    ensure_expert_external_dir(tmp_path, expert_dir)

    parsed = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert parsed["skills"]["external_dirs"] == [str(expert_dir)]
    assert "external_dirs: []" not in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_resolve_skill_dispatch_finds_generated_external_expert(tmp_path: Path, monkeypatch) -> None:
    agent_dir = Path(__file__).resolve().parents[5] / "vendor/hermes-agent"
    if not (agent_dir / "agent" / "skill_commands.py").is_file():
        agent_dir = (
            Path(__file__).resolve().parents[5]
            / "qeeclaw-server/release/qeeclaw-server-standalone/vendor/hermes-agent"
        )
    sys.path.insert(0, str(agent_dir))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    for module_name in [
        "agent.skill_commands",
        "agent.skill_utils",
        "agent.prompt_builder",
        "hermes_constants",
    ]:
        sys.modules.pop(module_name, None)

    expert = get_centaur_expert("professional-service-growth-strategist")
    expert_dir = sync_expert_workspaces(tmp_path, [expert])
    ensure_expert_external_dir(tmp_path, expert_dir)

    from agent.skill_commands import reload_skills

    reload_skills()
    dispatch = resolve_skill_dispatch(
        "hello",
        skill_command="professional-service-growth-strategist",
    )

    assert dispatch.error is None
    assert dispatch.skill_command_resolved == "/professional-service-growth-strategist"
    assert "hello" in dispatch.user_text
