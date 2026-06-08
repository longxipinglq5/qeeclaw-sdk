from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

KNOWLEDGE_MCP_NAME = "centaur_knowledge"
KNOWLEDGE_MCP_TOOLS = [
    "knowledge.search",
    "knowledge.stats",
    "knowledge.getDocument",
]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _server_command() -> tuple[str, list[str]]:
    script = shutil.which("qeeclaw-knowledge-mcp")
    if script:
        return script, []
    return sys.executable, ["-m", "bridge.knowledge_mcp_server"]


def resolve_profile_home(agent_profile: str) -> Path:
    try:
        from bridge.session_manager import get_session_manager

        profile = get_session_manager().get_profile(agent_profile)
        if profile and profile.hermes_home:
            return Path(profile.hermes_home).expanduser().resolve()
    except Exception:
        pass

    base_home = Path(
        os.environ.get("HERMES_HOME")
        or os.environ.get("QEECLAW_HERMES_HOME")
        or Path.home() / ".qeeclaw_hermes"
    ).expanduser().resolve()
    return base_home / "profiles" / agent_profile


def ensure_knowledge_mcp_config(hermes_home: str) -> Path:
    home = Path(hermes_home).expanduser().resolve()
    config_path = home / "config.yaml"
    data = _load_yaml(config_path)
    command, args = _server_command()
    servers = data.setdefault("mcp_servers", {})
    servers[KNOWLEDGE_MCP_NAME] = {
        "command": command,
        "args": args,
        "env": {
            "PYTHONPATH": os.pathsep.join(sys.path),
        },
        "timeout": 30,
        "connect_timeout": 10,
        "tools": {
            "include": KNOWLEDGE_MCP_TOOLS,
        },
    }
    _dump_yaml(config_path, data)
    return config_path


def discover_knowledge_mcp_tools(hermes_home: str | None = None) -> int:
    previous_home = os.environ.get("HERMES_HOME")
    try:
        if hermes_home:
            os.environ["HERMES_HOME"] = str(Path(hermes_home).expanduser().resolve())
        try:
            from tools.mcp_tool import discover_mcp_tools
        except Exception:
            return 0
        try:
            tools = discover_mcp_tools()
        except Exception:
            return 0
        return len(tools or [])
    finally:
        if hermes_home:
            if previous_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous_home


def ensure_knowledge_mcp_for_profile(agent_profile: str) -> bool:
    if agent_profile != "edge_supervisor":
        return False
    profile_home = resolve_profile_home(agent_profile)
    ensure_knowledge_mcp_config(str(profile_home))
    discover_knowledge_mcp_tools(str(profile_home))
    return True
