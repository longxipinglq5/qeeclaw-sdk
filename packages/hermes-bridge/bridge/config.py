from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# 自动检测 hermes-agent worktree 路径
# config.py 位于 qeeclaw-sdk/.worktrees/.../packages/hermes-bridge/bridge/
# parents[6] = qs-nexus-aos/ 根目录
_WS_ROOT = Path(__file__).resolve().parents[6]
_DEFAULT_HERMES_AGENT_DIR = (
    _WS_ROOT / "vendor" / "hermes-agent" / ".worktrees" / "feat-edge-hermes-arch"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str
    hermes_model: str = "deepseek-v4-pro"
    hermes_provider: str = "deepseek"
    bridge_port: int = 8787
    bridge_log_level: str = "INFO"
    hermes_agent_dir: str = str(_DEFAULT_HERMES_AGENT_DIR)
    hermes_home: str = str(Path.home() / ".hermes")
    cache_max_size: int = 32

    @property
    def hermes_agent_path(self) -> Path:
        return Path(self.hermes_agent_dir)

    @property
    def hermes_home_path(self) -> Path:
        return Path(self.hermes_home)


def _ensure_hermes_on_path(agent_dir: str) -> None:
    p = Path(agent_dir)
    if not p.exists():
        raise FileNotFoundError(f"hermes-agent 目录不存在: {p}")
    resolved = str(p.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
        logger.info("hermes-agent 加入 sys.path: %s", resolved)


settings = Settings()  # type: ignore[call-arg]
# hermes-agent 从 os.environ 读 API key，需显式注入
if settings.deepseek_api_key and "DEEPSEEK_API_KEY" not in os.environ:
    os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key
_ensure_hermes_on_path(settings.hermes_agent_dir)
