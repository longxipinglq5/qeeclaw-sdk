from __future__ import annotations

import yaml


def test_ensure_knowledge_mcp_writes_profile_config(tmp_path):
    from bridge.knowledge_mcp_config import ensure_knowledge_mcp_config

    ensure_knowledge_mcp_config(str(tmp_path))
    config_path = tmp_path / "config.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    server = data["mcp_servers"]["centaur_knowledge"]
    assert server["command"]
    command_line = " ".join([server["command"], *server["args"]])
    assert (
        "qeeclaw-knowledge-mcp" in command_line
        or "bridge.knowledge_mcp_server" in command_line
    )
    assert server["tools"]["include"] == [
        "knowledge.search",
        "knowledge.stats",
        "knowledge.getDocument",
    ]
    assert "knowledge.upload" not in str(server)
    assert "knowledge.delete" not in str(server)


def test_ensure_knowledge_mcp_is_idempotent(tmp_path):
    from bridge.knowledge_mcp_config import ensure_knowledge_mcp_config

    ensure_knowledge_mcp_config(str(tmp_path))
    first = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    ensure_knowledge_mcp_config(str(tmp_path))
    second = (tmp_path / "config.yaml").read_text(encoding="utf-8")

    assert first == second
