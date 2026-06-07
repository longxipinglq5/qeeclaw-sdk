from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# 将 .env 中的所有变量加载到 os.environ，供 os.environ.get() 使用
load_dotenv(override=False)

logger = logging.getLogger(__name__)

HERMES_AGENT_REQUIRED_TAG = "v2026.5.29.2"

# ---------------------------------------------------------------------------
# config.yaml 加载（与 release standalone 部署保持一致）
# 优先级: 环境变量 > config.yaml > 代码默认值
# ---------------------------------------------------------------------------

_HAS_YAML = False
try:
    import yaml

    _HAS_YAML = True
except ImportError:
    pass


def _load_yaml_config() -> dict:
    config_path = os.environ.get(
        "QEECLAW_CONFIG_FILE",
        os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
    )
    config_path = os.path.abspath(config_path)
    if os.path.isfile(config_path) and _HAS_YAML:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[hermes-bridge] WARNING: Failed to load {config_path}: {e}")
    return {}


def _config_file_path() -> Path:
    return Path(
        os.environ.get(
            "QEECLAW_CONFIG_FILE",
            os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
        )
    ).expanduser().resolve()


def _cfg(server_config: dict, section: str, key: str, default=None):
    return server_config.get(section, {}).get(key, default)


_YAML_CONFIG = _load_yaml_config()

_qos_agent_dir = os.environ.get("QEECLAW_HERMES_AGENT_DIR")
if _qos_agent_dir:
    os.environ["HERMES_AGENT_DIR"] = _qos_agent_dir

# ---------------------------------------------------------------------------
# hermes-agent 路径：standalone 包默认 vendor/hermes-agent
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_STANDALONE_ROOT = _THIS_DIR.parent  # bridge/ 的父目录（standalone 包根目录）
_CONFIG_FILE_PATH = _config_file_path()
_CONFIG_ROOT = _CONFIG_FILE_PATH.parent


def _looks_like_release_root(path: Path) -> bool:
    return (
        (path / "run.sh").is_file()
        and (path / "config.yaml").is_file()
        and (path / "vendor" / "hermes-agent").is_dir()
    )


def _detect_release_root() -> Path:
    for candidate in (
        _CONFIG_ROOT,
        _STANDALONE_ROOT,
        _STANDALONE_ROOT.parent,
        *_THIS_DIR.parents,
    ):
        if _looks_like_release_root(candidate):
            return candidate
    return _STANDALONE_ROOT


_RELEASE_ROOT = _detect_release_root()


def _is_hermes_agent_dir(path: Path) -> bool:
    return (path / "run_agent.py").is_file() and (path / "hermes_constants.py").is_file()


def _candidate_worktrees(base: Path) -> list[Path]:
    worktrees = base / ".worktrees"
    if not worktrees.is_dir():
        return []
    return sorted(
        [candidate for candidate in worktrees.iterdir() if _is_hermes_agent_dir(candidate)],
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )


def _detect_hermes_agent_dir() -> str:
    configured = (
        os.environ.get("QEECLAW_HERMES_AGENT_DIR")
        or os.environ.get("HERMES_AGENT_DIR")
    )
    if configured:
        return str(Path(configured).expanduser())

    yaml_agent_dir = _cfg(_YAML_CONFIG, "hermes", "agent_dir")
    if yaml_agent_dir and not Path(str(yaml_agent_dir)).is_absolute():
        return str((_CONFIG_ROOT / str(yaml_agent_dir)).resolve())

    release_agent = _RELEASE_ROOT / "vendor" / "hermes-agent"
    if _is_hermes_agent_dir(release_agent):
        return str(release_agent)

    candidates: list[Path] = [
        *_candidate_worktrees(release_agent),
        *_candidate_worktrees(_STANDALONE_ROOT / "vendor" / "hermes-agent"),
        *_candidate_worktrees(_STANDALONE_ROOT.parent / "vendor" / "hermes-agent"),
    ]

    for parent in _THIS_DIR.parents:
        vendor_agent = parent / "vendor" / "hermes-agent"
        candidates.extend(_candidate_worktrees(vendor_agent))

    candidates.extend(
        [
            _STANDALONE_ROOT / "vendor" / "hermes-agent",
            _STANDALONE_ROOT.parent / "vendor" / "hermes-agent",
        ]
    )

    for candidate in candidates:
        if _is_hermes_agent_dir(candidate):
            return str(candidate)

    return str(_STANDALONE_ROOT / "vendor" / "hermes-agent")


_DEFAULT_HERMES_AGENT_DIR = _detect_hermes_agent_dir()

# 端口：QEECLAW_HERMES_BRIDGE_PORT (release) > BRIDGE_PORT (dev) > config.yaml > 21747
_DEFAULT_PORT = int(
    _cfg(_YAML_CONFIG, "server", "port", 21747)
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 端口：dev 用 BRIDGE_PORT，release 用 QEECLAW_HERMES_BRIDGE_PORT
    bridge_port: int = _DEFAULT_PORT
    bridge_host: str = str(
        _cfg(_YAML_CONFIG, "server", "host", "0.0.0.0")
    )
    bridge_log_level: str = "INFO"

    # LLM provider
    deepseek_api_key: str = ""
    deepseek_base_url: str = os.environ.get(
        "DEEPSEEK_BASE_URL",
        "https://api.deepseek.com/v1",
    )
    hermes_model: str = os.environ.get("HERMES_MODEL", "deepseek-chat")
    hermes_provider: str = os.environ.get("HERMES_PROVIDER", "deepseek")

    # hermes-agent 路径
    hermes_agent_dir: str = _DEFAULT_HERMES_AGENT_DIR
    hermes_agent_required_tag: str = os.environ.get(
        "HERMES_AGENT_REQUIRED_TAG",
        HERMES_AGENT_REQUIRED_TAG,
    )

    # hermes home（standalone 包用 data/hermes）
    _standalone_hermes_home = _RELEASE_ROOT / "data" / "hermes"
    hermes_home: str = os.environ.get(
        "HERMES_HOME",
        str(_standalone_hermes_home if _standalone_hermes_home.parent.is_dir() else Path.home() / ".hermes"),
    )

    # runtime
    cache_max_size: int = 32
    context_recent_message_limit: int = 24
    context_recent_token_budget: int = 6000
    native_skill_intent_enabled: bool = os.getenv("HERMES_NATIVE_SKILL_INTENT", "1") == "1"
    headless_skill_sync_timeout_ms: int = int(
        os.getenv("HERMES_HEADLESS_SKILL_SYNC_TIMEOUT_MS", "1500")
    )

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


# release 部署通过 .env 或环境变量传入 QEECLAW_HERMES_BRIDGE_PORT
# pydantic-settings 会自动读 BRIDGE_PORT，但 QEECLAW_HERMES_BRIDGE_PORT 需要手动映射
_qos_port = os.environ.get("QEECLAW_HERMES_BRIDGE_PORT")
if _qos_port:
    os.environ.setdefault("BRIDGE_PORT", _qos_port)

_qos_host = os.environ.get("QEECLAW_HERMES_BRIDGE_HOST")
if _qos_host:
    os.environ.setdefault("BRIDGE_HOST", _qos_host)

settings = Settings()  # type: ignore[call-arg]

# hermes-agent 及其内建工具会直接读取 HERMES_HOME，且部分模块在导入时
# 缓存路径。Bridge 必须在导入 run_agent/AIAgent 前把 settings 发布到进程环境。
os.environ["HERMES_HOME"] = settings.hermes_home

# hermes-agent 从 os.environ 读 API key，需显式注入
if settings.deepseek_api_key and "DEEPSEEK_API_KEY" not in os.environ:
    os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key

try:
    _ensure_hermes_on_path(settings.hermes_agent_dir)
except FileNotFoundError:
    logger.warning("hermes-agent 目录暂不可用: %s", settings.hermes_agent_dir)
