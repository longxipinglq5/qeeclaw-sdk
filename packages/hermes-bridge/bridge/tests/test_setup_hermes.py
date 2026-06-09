from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bridge.setup_hermes import (
    HermesAgentVersionError,
    _migrate_legacy_memories,
    _register_bundled_plugins,
    ensure_hermes_home,
    validate_hermes_agent_version,
)


class TestHermesAgentPathDetection:
    def test_uses_env_agent_dir(self, tmp_path, monkeypatch):
        agent_dir = tmp_path / "custom-agent"
        agent_dir.mkdir()

        monkeypatch.setenv("HERMES_AGENT_DIR", str(agent_dir))

        import bridge.config as config

        assert config._detect_hermes_agent_dir() == str(agent_dir)

    def test_qeeclaw_agent_dir_overrides_legacy_env(self, tmp_path, monkeypatch):
        legacy_agent_dir = tmp_path / "legacy-agent"
        release_agent_dir = tmp_path / "release-agent"
        legacy_agent_dir.mkdir()
        release_agent_dir.mkdir()

        monkeypatch.setenv("HERMES_AGENT_DIR", str(legacy_agent_dir))
        monkeypatch.setenv("QEECLAW_HERMES_AGENT_DIR", str(release_agent_dir))

        import bridge.config as config

        assert config._detect_hermes_agent_dir() == str(release_agent_dir)

    def test_detects_any_worktree_without_branch_name(self, tmp_path, monkeypatch):
        root = tmp_path / "repo"
        bridge_dir = root / "qeeclaw-sdk" / "packages" / "hermes-bridge" / "bridge"
        agent_dir = root / "vendor" / "hermes-agent" / ".worktrees" / "some-other-branch"
        bridge_dir.mkdir(parents=True)
        agent_dir.mkdir(parents=True)
        (agent_dir / "run_agent.py").write_text("", encoding="utf-8")
        (agent_dir / "hermes_constants.py").write_text("", encoding="utf-8")

        import bridge.config as config

        monkeypatch.setattr(config, "_THIS_DIR", bridge_dir)
        monkeypatch.delenv("HERMES_AGENT_DIR", raising=False)
        monkeypatch.delenv("QEECLAW_HERMES_AGENT_DIR", raising=False)

        assert config._detect_hermes_agent_dir() == str(agent_dir)

    def test_prefers_release_vendor_over_yaml_absolute_placeholder(self, tmp_path, monkeypatch):
        release_root = tmp_path / "qeeclaw-server-standalone"
        agent_dir = release_root / "vendor" / "hermes-agent"
        release_root.mkdir()
        (release_root / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        (release_root / "config.yaml").write_text(
            "hermes:\n  agent_dir: \"/opt/qeeclaw/vendor/hermes-agent\"\n",
            encoding="utf-8",
        )
        agent_dir.mkdir(parents=True)
        (agent_dir / "run_agent.py").write_text("", encoding="utf-8")
        (agent_dir / "hermes_constants.py").write_text("", encoding="utf-8")

        import bridge.config as config

        monkeypatch.setattr(config, "_CONFIG_ROOT", release_root)
        monkeypatch.setattr(config, "_RELEASE_ROOT", release_root)
        monkeypatch.setattr(
            config,
            "_YAML_CONFIG",
            {"hermes": {"agent_dir": "/opt/qeeclaw/vendor/hermes-agent"}},
        )
        monkeypatch.delenv("HERMES_AGENT_DIR", raising=False)
        monkeypatch.delenv("QEECLAW_HERMES_AGENT_DIR", raising=False)

        assert config._detect_hermes_agent_dir() == str(agent_dir)

    def test_prefers_worktree_over_vendor_root_in_development(self, tmp_path, monkeypatch):
        root = tmp_path / "repo"
        bridge_dir = root / "qeeclaw-sdk" / "packages" / "hermes-bridge" / "bridge"
        vendor_root = root / "vendor" / "hermes-agent"
        worktree = vendor_root / ".worktrees" / "locked-tag"
        bridge_dir.mkdir(parents=True)
        vendor_root.mkdir(parents=True)
        worktree.mkdir(parents=True)
        for candidate in (vendor_root, worktree):
            (candidate / "run_agent.py").write_text("", encoding="utf-8")
            (candidate / "hermes_constants.py").write_text("", encoding="utf-8")

        import bridge.config as config

        monkeypatch.setattr(config, "_THIS_DIR", bridge_dir)
        monkeypatch.setattr(config, "_CONFIG_ROOT", bridge_dir.parent)
        monkeypatch.setattr(config, "_RELEASE_ROOT", bridge_dir.parent)
        monkeypatch.setattr(config, "_YAML_CONFIG", {})
        monkeypatch.delenv("HERMES_AGENT_DIR", raising=False)
        monkeypatch.delenv("QEECLAW_HERMES_AGENT_DIR", raising=False)

        assert config._detect_hermes_agent_dir() == str(worktree)


class TestHermesHomeMigration:
    def test_migrates_legacy_memory_files_when_target_missing(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        legacy_memory = tmp_path / ".qeeclaw_hermes" / "memories"
        legacy_memory.mkdir(parents=True)
        (legacy_memory / "USER.md").write_text("用户偏好", encoding="utf-8")
        (legacy_memory / "MEMORY.md").write_text("长期观察", encoding="utf-8")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        _migrate_legacy_memories(home)

        assert (home / "memories" / "USER.md").read_text(encoding="utf-8") == "用户偏好"
        assert (home / "memories" / "MEMORY.md").read_text(encoding="utf-8") == "长期观察"

    def test_does_not_overwrite_existing_memory_files(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        target_memory = home / "memories"
        target_memory.mkdir(parents=True)
        (target_memory / "USER.md").write_text("新记忆", encoding="utf-8")

        legacy_memory = tmp_path / ".qeeclaw_hermes" / "memories"
        legacy_memory.mkdir(parents=True)
        (legacy_memory / "USER.md").write_text("旧记忆", encoding="utf-8")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        _migrate_legacy_memories(home)

        assert (target_memory / "USER.md").read_text(encoding="utf-8") == "新记忆"


class TestHermesAgentVersionLock:
    def test_accepts_required_git_tag(self, tmp_path, monkeypatch):
        agent_dir = tmp_path / "hermes-agent"
        agent_dir.mkdir()
        (agent_dir / ".git").write_text("gitdir: ../.git/worktrees/hermes-agent\n", encoding="utf-8")

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout="v2026.6.5\n", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        validate_hermes_agent_version(agent_dir)

    def test_rejects_wrong_git_tag(self, tmp_path, monkeypatch):
        agent_dir = tmp_path / "hermes-agent"
        agent_dir.mkdir()
        (agent_dir / ".git").write_text("gitdir: ../.git/worktrees/hermes-agent\n", encoding="utf-8")

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout="v2026.5.29.1\n", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(HermesAgentVersionError, match="v2026.6.5"):
            validate_hermes_agent_version(agent_dir)

    def test_allows_explicit_skip_for_local_integration_agent(self, tmp_path, monkeypatch):
        agent_dir = tmp_path / "hermes-agent"
        agent_dir.mkdir()
        (agent_dir / ".git").write_text("gitdir: ../.git/worktrees/hermes-agent\n", encoding="utf-8")

        def fail_if_called(*args, **kwargs):
            raise AssertionError("git should not be called when version lock is skipped")

        monkeypatch.setattr(subprocess, "run", fail_if_called)
        monkeypatch.setattr("bridge.setup_hermes.settings.hermes_agent_required_tag", "skip")

        validate_hermes_agent_version(agent_dir)

    def test_skips_release_directory_without_git_metadata(self, tmp_path, monkeypatch):
        agent_dir = tmp_path / "hermes-agent"
        agent_dir.mkdir()

        def fail_if_called(*args, **kwargs):
            raise AssertionError("git should not be called without .git metadata")

        monkeypatch.setattr(subprocess, "run", fail_if_called)

        validate_hermes_agent_version(agent_dir)


class TestHermesExpertWorkspaceSetup:
    def test_ensure_hermes_home_registers_expert_workspace_and_reloads_skills(self, tmp_path, monkeypatch):
        calls: dict[str, object] = {}
        expert_dir = tmp_path / "centaur-experts"

        monkeypatch.setattr("bridge.setup_hermes.validate_hermes_agent_version", lambda: None)
        monkeypatch.setattr("bridge.setup_hermes.settings.hermes_home", str(tmp_path))
        monkeypatch.setattr("bridge.setup_hermes._migrate_legacy_memories", lambda home: None)
        monkeypatch.setattr("bridge.setup_hermes._register_bundled_skills", lambda home: None)
        monkeypatch.setattr("bridge.setup_hermes.load_centaur_experts", lambda: ["expert"])

        def fake_sync(home, experts):
            calls["sync"] = (home, experts)
            return expert_dir

        def fake_register(home, registered_dir):
            calls["register"] = (home, registered_dir)

        def fake_reload():
            calls["reload"] = True

        monkeypatch.setattr("bridge.setup_hermes.sync_expert_workspaces", fake_sync)
        monkeypatch.setattr("bridge.setup_hermes.ensure_expert_external_dir", fake_register)
        monkeypatch.setitem(
            __import__("sys").modules,
            "agent.skill_commands",
            type("SkillCommands", (), {"reload_skills": staticmethod(fake_reload)}),
        )

        ensure_hermes_home()

        assert calls["sync"] == (tmp_path, ["expert"])
        assert calls["register"] == (tmp_path, expert_dir)
        assert calls["reload"] is True
