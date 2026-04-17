#!/usr/bin/env python3
"""
QeeClaw Hermes Bridge Server

一个轻量级 HTTP 服务，充当 TypeScript SDK 与 Python hermes-agent 之间的桥梁。
SDK 侧的 HermesAdapter 通过 HTTP 调用此服务，此服务再调用 hermes-agent 的核心 AIAgent。

设计原则：
- 零修改 hermes-agent 源码
- 此文件是唯一需要理解 hermes-agent 内部结构的适配层
- 所有 hermes-agent 的 API 变更只需在此文件中适配

端口默认：21747
"""

import asyncio
import json
import os
import platform as platform_mod
import subprocess
import sys
import time
import traceback
import urllib.parse
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from threading import Thread
from typing import Any, Dict, List, Optional

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# ---------------------------------------------------------------------------
# 版本
# ---------------------------------------------------------------------------

BRIDGE_VERSION = "0.2.0"

# ---------------------------------------------------------------------------
# 配置加载（优先级：环境变量 > config.yaml > 默认值）
# ---------------------------------------------------------------------------

_server_config: Dict[str, Any] = {}

def _load_config() -> Dict[str, Any]:
    """从 config.yaml 加载配置，如文件不存在则返回空 dict。"""
    config_path = os.environ.get(
        "QEECLAW_CONFIG_FILE",
        os.path.join(os.path.dirname(__file__), "..", "..", "server", "config.yaml"),
    )
    config_path = os.path.abspath(config_path)
    if os.path.isfile(config_path) and _HAS_YAML:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[hermes-bridge] WARNING: Failed to load {config_path}: {e}")
    return {}

def _cfg(section: str, key: str, default: Any = None) -> Any:
    """从 _server_config 中按 section.key 取值。"""
    return _server_config.get(section, {}).get(key, default)

# 加载配置
_server_config = _load_config()

# 服务端监听：默认 0.0.0.0（服务端模式，接受网络连接）
BRIDGE_HOST = os.environ.get(
    "QEECLAW_HERMES_BRIDGE_HOST",
    _cfg("server", "host", "0.0.0.0"),
)
BRIDGE_PORT = int(os.environ.get(
    "QEECLAW_HERMES_BRIDGE_PORT",
    _cfg("server", "port", 21747),
))

# 日志显示地址：0.0.0.0/:: 不可在浏览器中访问，替换为 127.0.0.1
_DISPLAY_HOST = "127.0.0.1" if BRIDGE_HOST in ("0.0.0.0", "::") else BRIDGE_HOST

# hermes-agent 源码路径
HERMES_AGENT_DIR = os.environ.get(
    "QEECLAW_HERMES_AGENT_DIR",
    _cfg("hermes", "agent_dir",
         os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "hermes-agent")),
)

# HERMES_HOME: 数据/配置目录，默认 ~/.qeeclaw_hermes（避免与独立安装的 hermes-agent 冲突）
if "HERMES_HOME" not in os.environ:
    os.environ["HERMES_HOME"] = os.path.join(os.path.expanduser("~"), ".qeeclaw_hermes")

# HUD 源码路径
HUD_DIR = os.environ.get(
    "QEECLAW_HUD_DIR",
    _cfg("hud", "dir", os.path.join(os.path.dirname(__file__), "..", "vendor", "hermes-hudui")),
)
HUD_ENABLED = _cfg("hud", "enabled", True)
HUD_PORT = _cfg("hud", "port", 8134)

# ---------------------------------------------------------------------------
# API Key 鉴权
# ---------------------------------------------------------------------------

_AUTH_MODE = os.environ.get(
    "QEECLAW_AUTH_MODE",
    _cfg("auth", "mode", "none"),  # none | local | platform
)
_AUTH_API_KEYS: List[str] = _cfg("auth", "api_keys", []) or []

# 如果环境变量设置了单个 Key，也加入白名单
_env_key = os.environ.get("QEECLAW_AUTH_API_KEY", "")
if _env_key and _env_key not in _AUTH_API_KEYS:
    _AUTH_API_KEYS.append(_env_key)

# CORS 允许的来源
_CORS_ORIGINS = _cfg("cors", "allowed_origins", ["*"]) or ["*"]


def _check_api_key(handler: BaseHTTPRequestHandler) -> Optional[str]:
    """校验 API Key。返回 None 表示通过，返回错误信息表示拒绝。"""
    if _AUTH_MODE == "none":
        return None  # 不校验

    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return "Missing or invalid Authorization header. Expected: Bearer <api-key>"

    key = auth_header[7:].strip()
    if not key:
        return "Empty API key."

    if _AUTH_MODE == "local":
        if key not in _AUTH_API_KEYS:
            return "Invalid API key."
        return None

    # platform 模式（未来对接 paas.qeeshu.com）
    if _AUTH_MODE == "platform":
        # TODO: 调用平台接口校验 key 有效性
        # 暂时放行
        return None

    return None

# ---------------------------------------------------------------------------
# Hermes Agent 懒加载
# ---------------------------------------------------------------------------

_hermes_loaded = False
_hermes_error: Optional[str] = None
_agent_instance = None
_gateway_process: Optional[subprocess.Popen] = None
_gateway_thread: Optional[Thread] = None


def _ensure_hermes_on_path():
    """确保 hermes-agent 的源码在 sys.path 中。"""
    global _hermes_loaded, _hermes_error

    if _hermes_loaded:
        return

    agent_dir = os.path.abspath(HERMES_AGENT_DIR)
    if not os.path.isdir(agent_dir):
        _hermes_error = (
            f"hermes-agent directory not found: {agent_dir}. "
            f"Please set QEECLAW_HERMES_AGENT_DIR or ensure vendor/hermes-agent exists."
        )
        _hermes_loaded = True
        return

    # 将 hermes-agent 根目录加入 sys.path（hermes 的模块是顶层包）
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    _hermes_loaded = True


def _get_hermes_error() -> Optional[str]:
    """如果 hermes-agent 不可用，返回错误信息。"""
    _ensure_hermes_on_path()
    return _hermes_error


# ---------------------------------------------------------------------------
# 请求处理
# ---------------------------------------------------------------------------


def _cors_origin(handler: BaseHTTPRequestHandler) -> str:
    """根据配置返回 CORS 允许的 Origin。"""
    if "*" in _CORS_ORIGINS:
        return "*"
    request_origin = handler.headers.get("Origin", "")
    if request_origin in _CORS_ORIGINS:
        return request_origin
    return _CORS_ORIGINS[0] if _CORS_ORIGINS else ""


def _json_response(handler: BaseHTTPRequestHandler, status: int, data: Any):
    """发送 JSON 响应。"""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", _cors_origin(handler))
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    """读取请求体的 JSON。"""
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        return {}
    raw = handler.rfile.read(content_length)
    return json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# SDK 兼容层：/api/agent/* 路径映射 + 平台响应格式
# ---------------------------------------------------------------------------

_agent_id_map: Dict[str, int] = {}
_agent_id_counter = 0


def _get_agent_id(profile_name: str) -> int:
    """为 AgentProfile 分配稳定的数字 ID（进程生命周期内稳定）。"""
    global _agent_id_counter
    if profile_name not in _agent_id_map:
        _agent_id_counter += 1
        _agent_id_map[profile_name] = _agent_id_counter
    return _agent_id_map[profile_name]


def _profile_to_sdk_agent(profile) -> dict:
    """将 AgentProfile 转换为 SDK MyAgent 格式。"""
    meta = profile.metadata or {}
    return {
        "id": _get_agent_id(profile.name),
        "name": profile.display_name,
        "code": profile.name,
        "description": meta.get("description") or (
            profile.system_prompt[:200] if profile.system_prompt else None
        ),
        "avatar": meta.get("avatar"),
        "voice_id": meta.get("voice_id"),
        "runtime_type": meta.get("runtime_type", "openclaw"),
        "runtime_label": meta.get("runtime_label"),
        "model": profile.model or None,
    }


def _find_profile_by_id(sm, agent_id: int):
    """根据数字 ID 查找 AgentProfile。"""
    for profile in sm._profiles.values():
        if _get_agent_id(profile.name) == agent_id:
            return profile
    return None


def _platform_json_response(handler, status: int, data, message: str = "success"):
    """发送平台格式响应：{"code": 0, "data": ..., "message": "success"}。"""
    code_val = 0 if status < 400 else status
    _json_response(handler, status, {
        "code": code_val,
        "data": data,
        "message": message,
    })


# ---------------------------------------------------------------------------
# AgentPool：管理 AIAgent 配置，按请求创建实例
# ---------------------------------------------------------------------------

_agent_pool: Optional["AgentPool"] = None


def get_agent_pool() -> "AgentPool":
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = AgentPool()
    return _agent_pool


class AgentPool:
    """管理多个 agent_profile 到 AIAgent 配置的映射。

    采用 gateway 模式：每次请求创建新 AIAgent 实例，
    通过 session_id + conversation_history 保持状态。
    当 hermes-agent 不可用时自动降级为裸 OpenAI 调用。

    每个 agent_profile 拥有独立的 HERMES_HOME 目录，实现
    日志、config、skills 等 hermes-agent 内部状态的隔离。
    """

    def __init__(self):
        self._ai_agent_cls = None
        self._available = False
        self._init_error: Optional[str] = None
        # 保存启动时的全局 HERMES_HOME
        self._base_hermes_home: str = os.environ.get(
            "HERMES_HOME", os.path.join(os.path.expanduser("~"), ".qeeclaw_hermes")
        )
        # AIAgent 构造期间的 HERMES_HOME 切换锁
        self._creation_lock = threading.Lock()
        self._try_load()

    def _try_load(self):
        """尝试加载 hermes-agent 的 AIAgent 类。"""
        _ensure_hermes_on_path()
        err = _get_hermes_error()
        if err:
            self._init_error = err
            return
        try:
            from run_agent import AIAgent
            self._ai_agent_cls = AIAgent
            self._available = True
            print("[agent-pool] AIAgent loaded successfully — full agent mode enabled")
        except ImportError as e:
            self._init_error = f"Failed to import AIAgent: {e}"
            print(f"[agent-pool] WARNING: {self._init_error} — fallback mode")

    @property
    def profiles_home(self) -> str:
        """profiles 目录路径。"""
        return os.path.join(self._base_hermes_home, "profiles")

    def _ensure_profile_home(self, profile_name: str) -> str:
        """返回指定 profile 的 HERMES_HOME 路径，自动创建目录。

        - "default" → 全局 HERMES_HOME（不变）
        - 其他 → {base}/profiles/{name}/
        """
        if profile_name == "default":
            return self._base_hermes_home
        profile_dir = os.path.join(self._base_hermes_home, "profiles", profile_name)
        os.makedirs(profile_dir, exist_ok=True)
        return profile_dir

    @property
    def available(self) -> bool:
        return self._available

    def invoke(
        self,
        prompt: str,
        profile,
        session,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_history_turns: int = 20,
        stream_callback=None,
    ) -> dict:
        """创建 AIAgent 实例并调用 run_conversation()。

        Args:
            prompt: 用户消息
            profile: AgentProfile 实例
            session: Session 实例（提供 session_id 和历史消息）
            system_prompt: 系统提示词（含 RAG 上下文）
            model: 模型名（覆盖 profile 默认值）
            provider: provider 名
            max_tokens: 最大 token 数
            temperature: 温度
            max_history_turns: 最大历史轮数
            stream_callback: 流式回调 fn(delta_text)

        Returns:
            dict: 包含 text, model, provider, usage 等字段
        """
        if not self._available:
            return self._invoke_fallback(
                prompt=prompt,
                model=model,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                history=session.get_messages(max_turns=max_history_turns) if session else None,
                import_error=self._init_error,
            )

        # 从 profile 获取默认参数
        effective_model = model or (profile.model if profile else "") or os.environ.get("HERMES_MODEL", "")
        effective_provider = provider or ""
        effective_max_tokens = max_tokens or (profile.max_tokens if profile else None)
        effective_max_iterations = (profile.max_iterations if profile else 30) or 30

        # 构建 enabled/disabled toolsets
        enabled_ts = None
        disabled_ts = None
        if profile:
            if not profile.tools_enabled:
                # 工具被禁用 — 传空列表使 AIAgent 不加载任何工具
                enabled_ts = []
            elif profile.enabled_toolsets:
                enabled_ts = list(profile.enabled_toolsets)
            if profile.disabled_toolsets:
                disabled_ts = list(profile.disabled_toolsets)

        # 构造 AIAgent
        agent_kwargs: Dict[str, Any] = {
            "model": effective_model,
            "quiet_mode": True,
            "skip_context_files": True,
            "skip_memory": True,  # Bridge 自管理 memory，不使用 hermes 内部 memory
            "platform": "bridge",
            "session_id": session.session_id if session else None,
            "max_iterations": effective_max_iterations,
        }
        if effective_provider:
            agent_kwargs["provider"] = effective_provider
        if effective_max_tokens is not None:
            agent_kwargs["max_tokens"] = effective_max_tokens
        if enabled_ts is not None:
            agent_kwargs["enabled_toolsets"] = enabled_ts
        if disabled_ts is not None:
            agent_kwargs["disabled_toolsets"] = disabled_ts
        if stream_callback is not None:
            # stream_delta_callback is used by gateway for token-level events
            agent_kwargs["stream_delta_callback"] = stream_callback

        # 确定 per-profile HERMES_HOME
        profile_name = profile.name if profile else "default"
        profile_home = (
            profile.hermes_home if (profile and profile.hermes_home)
            else self._ensure_profile_home(profile_name)
        )

        try:
            # 在构造 AIAgent 期间切换 HERMES_HOME（线程安全）
            with self._creation_lock:
                prev_home = os.environ.get("HERMES_HOME", "")
                os.environ["HERMES_HOME"] = profile_home
                try:
                    agent = self._ai_agent_cls(**agent_kwargs)
                finally:
                    os.environ["HERMES_HOME"] = prev_home or self._base_hermes_home

            # 获取对话历史
            history = session.get_messages(max_turns=max_history_turns) if session else []

            result = agent.run_conversation(
                user_message=prompt,
                system_message=system_prompt or None,
                conversation_history=history if history else None,
                # stream_callback 控制 API 调用是否使用流式，
                # 并在每个文本 delta 时回调
                stream_callback=stream_callback,
            )

            final_text = result.get("final_response") or ""

            return {
                "text": final_text,
                "model": result.get("model", effective_model),
                "provider": result.get("provider", effective_provider),
                "usage": {
                    "input_tokens": result.get("input_tokens", 0),
                    "output_tokens": result.get("output_tokens", 0),
                    "total_tokens": result.get("total_tokens", 0),
                    "prompt_tokens": result.get("prompt_tokens", 0),
                    "completion_tokens": result.get("completion_tokens", 0),
                    "estimated_cost_usd": result.get("estimated_cost_usd"),
                },
                "api_calls": result.get("api_calls", 0),
                "completed": result.get("completed", True),
                "_agent_mode": True,
            }
        except Exception as e:
            traceback.print_exc()
            # 降级到 fallback
            print(f"[agent-pool] AIAgent invoke failed: {e} — falling back to raw LLM")
            return self._invoke_fallback(
                prompt=prompt,
                model=model,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                history=session.get_messages(max_turns=max_history_turns) if session else None,
                import_error=str(e),
            )

    def _invoke_fallback(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        import_error: Optional[str] = None,
    ) -> dict:
        """降级调用：直接使用 openai SDK 进行模型调用。"""
        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "openai package is not installed. "
                "Please run: pip install openai"
            )

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        default_model = os.environ.get("HERMES_MODEL", "deepseek/deepseek-v3.2-exp")

        client = openai.OpenAI(api_key=api_key, base_url=base_url)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": model or default_model,
            "messages": messages,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = client.chat.completions.create(**kwargs)

        choice = response.choices[0] if response.choices else None
        text = choice.message.content if choice and choice.message else ""

        usage_data = None
        if response.usage:
            usage_data = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return {
            "text": text or "",
            "model": response.model,
            "provider": provider or "fallback",
            "usage": usage_data,
            "_fallback": True,
            "_import_error": import_error,
        }

    def invoke_stream_fallback(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ):
        """降级流式调用：返回一个 chunk 生成器。"""
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package is not installed.")

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        default_model = os.environ.get("HERMES_MODEL", "deepseek/deepseek-v3.2-exp")

        client = openai.OpenAI(api_key=api_key, base_url=base_url)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": model or default_model,
            "messages": messages,
            "stream": True,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature

        return client.chat.completions.create(**kwargs)


# ---------------------------------------------------------------------------
# IAM 辅助函数（本地单用户）
# ---------------------------------------------------------------------------

_USER_PROFILE_FILE = os.path.join(os.environ.get("HERMES_HOME", os.path.expanduser("~/.qeeclaw_hermes")), "user_profile.json")

_DEFAULT_USER_PROFILE: Dict[str, Any] = {
    "id": 1,
    "username": "local-admin",
    "full_name": "本地管理员",
    "email": None,
    "phone": None,
    "role": "ADMIN",
    "is_active": True,
    "last_login_time": None,
    "created_time": "2026-01-01T00:00:00Z",
    "wallet_balance": 0,
    "is_enterprise_verified": False,
    "teams": [{"id": 1, "name": "local", "is_personal": True, "owner_id": 1}],
}


def _load_user_profile() -> Dict[str, Any]:
    """加载本地用户配置，不存在则返回默认值。"""
    if os.path.isfile(_USER_PROFILE_FILE):
        try:
            with open(_USER_PROFILE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_DEFAULT_USER_PROFILE)


def _save_user_profile(profile: Dict[str, Any]):
    """保存用户配置到磁盘。"""
    try:
        os.makedirs(os.path.dirname(_USER_PROFILE_FILE), exist_ok=True)
        with open(_USER_PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[bridge] WARNING: Failed to save user profile: {e}")


# ---------------------------------------------------------------------------
# Models 辅助函数
# ---------------------------------------------------------------------------

_model_id_counter = 0
_model_id_map: Dict[str, int] = {}


def _get_model_id(model_name: str) -> int:
    """为模型名分配稳定的数字 ID。"""
    global _model_id_counter
    if model_name not in _model_id_map:
        _model_id_counter += 1
        _model_id_map[model_name] = _model_id_counter
    return _model_id_map[model_name]


def _infer_provider_from_url(base_url: str) -> str:
    """从 OPENAI_BASE_URL 推断 provider 名。"""
    if not base_url:
        return "openai"
    base_url = base_url.lower()
    if "openrouter" in base_url:
        return "openrouter"
    if "deepseek" in base_url:
        return "deepseek"
    if "dashscope" in base_url or "aliyun" in base_url:
        return "dashscope"
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return "local"
    if "openai" in base_url:
        return "openai"
    return "custom"


def _discover_models() -> List[Dict[str, Any]]:
    """从环境变量和 AgentProfile 枚举可用模型。"""
    models: Dict[str, Dict[str, Any]] = {}
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "")
    provider = _infer_provider_from_url(base_url)
    default_model = os.environ.get("HERMES_MODEL", "deepseek/deepseek-v3.2-exp")

    # 主模型
    models[default_model] = {
        "id": _get_model_id(default_model),
        "provider_name": provider,
        "model_name": default_model,
        "provider_model_id": default_model,
        "label": default_model,
        "is_preferred": True,
        "availability_status": "available",
        "unit_price": 0,
        "output_unit_price": 0,
        "currency": "CNY",
        "billing_mode": "token",
        "text_unit_chars": 1000,
        "text_min_amount": 0,
    }

    # 从 AgentProfile 收集额外模型
    try:
        from session_manager import get_session_manager
        sm = get_session_manager()
        for p in sm._profiles.values():
            m = p.model
            if m and m not in models:
                models[m] = {
                    "id": _get_model_id(m),
                    "provider_name": provider,
                    "model_name": m,
                    "provider_model_id": m,
                    "label": m,
                    "is_preferred": False,
                    "availability_status": "available",
                    "unit_price": 0,
                    "output_unit_price": 0,
                    "currency": "CNY",
                    "billing_mode": "token",
                    "text_unit_chars": 1000,
                    "text_min_amount": 0,
                }
    except Exception:
        pass

    return list(models.values())


def _get_preferred_model() -> str:
    """获取当前 preferred model：优先用户偏好 > 环境变量默认。"""
    profile = _load_user_profile()
    pref = (profile.get("preference") or {}).get("preferred_model")
    if pref:
        return pref
    return os.environ.get("HERMES_MODEL", "deepseek/deepseek-v3.2-exp")


# ---------------------------------------------------------------------------
# Workflow 辅助函数
# ---------------------------------------------------------------------------

_HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.qeeclaw_hermes"))
_WORKFLOWS_FILE = os.path.join(_HERMES_HOME, "workflows.json")


def _load_workflows() -> List[Dict[str, Any]]:
    if os.path.isfile(_WORKFLOWS_FILE):
        try:
            with open(_WORKFLOWS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_workflows(workflows: List[Dict[str, Any]]):
    try:
        os.makedirs(os.path.dirname(_WORKFLOWS_FILE), exist_ok=True)
        with open(_WORKFLOWS_FILE, "w", encoding="utf-8") as f:
            json.dump(workflows, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[bridge] WARNING: Failed to save workflows: {e}")


# ---------------------------------------------------------------------------
# Device 辅助函数
# ---------------------------------------------------------------------------

_DEVICE_INFO_FILE = os.path.join(_HERMES_HOME, "device_info.json")


def _load_device_info() -> Dict[str, Any]:
    if os.path.isfile(_DEVICE_INFO_FILE):
        try:
            with open(_DEVICE_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    import platform as _platform
    return {
        "id": 1,
        "device_name": _platform.node() or "local-device",
        "hostname": _platform.node(),
        "os_info": f"{_platform.system()} {_platform.release()}",
        "status": "online",
        "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "created_time": "2026-01-01T00:00:00Z",
        "team_id": 1,
        "registration_mode": "local",
        "installation_id": f"local-{uuid.uuid4().hex[:8]}",
    }


def _save_device_info(info: Dict[str, Any]):
    try:
        os.makedirs(os.path.dirname(_DEVICE_INFO_FILE), exist_ok=True)
        with open(_DEVICE_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[bridge] WARNING: Failed to save device info: {e}")


# ---------------------------------------------------------------------------
# Approval 辅助函数
# ---------------------------------------------------------------------------

_APPROVALS_FILE = os.path.join(_HERMES_HOME, "approvals.json")


def _load_approvals() -> List[Dict[str, Any]]:
    if os.path.isfile(_APPROVALS_FILE):
        try:
            with open(_APPROVALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_approvals(items: List[Dict[str, Any]]):
    try:
        os.makedirs(os.path.dirname(_APPROVALS_FILE), exist_ok=True)
        with open(_APPROVALS_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[bridge] WARNING: Failed to save approvals: {e}")


# ---------------------------------------------------------------------------
# Audit 辅助函数
# ---------------------------------------------------------------------------

_AUDIT_EVENTS_FILE = os.path.join(_HERMES_HOME, "audit_events.json")


def _load_audit_events() -> List[Dict[str, Any]]:
    if os.path.isfile(_AUDIT_EVENTS_FILE):
        try:
            with open(_AUDIT_EVENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_audit_events(events: List[Dict[str, Any]]):
    try:
        os.makedirs(os.path.dirname(_AUDIT_EVENTS_FILE), exist_ok=True)
        with open(_AUDIT_EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[bridge] WARNING: Failed to save audit events: {e}")


# ---------------------------------------------------------------------------
# ApiKey 辅助函数
# ---------------------------------------------------------------------------

_API_KEYS_FILE = os.path.join(_HERMES_HOME, "api_keys.json")


def _load_api_keys() -> Dict[str, Any]:
    if os.path.isfile(_API_KEYS_FILE):
        try:
            with open(_API_KEYS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"app_keys": [], "llm_keys": []}


def _save_api_keys(data: Dict[str, Any]):
    try:
        os.makedirs(os.path.dirname(_API_KEYS_FILE), exist_ok=True)
        with open(_API_KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[bridge] WARNING: Failed to save api keys: {e}")


# ---------------------------------------------------------------------------
# Knowledge Config 辅助函数
# ---------------------------------------------------------------------------

_KNOWLEDGE_CONFIG_FILE = os.path.join(_HERMES_HOME, "knowledge_config.json")


def _load_knowledge_config() -> Dict[str, Any]:
    if os.path.isfile(_KNOWLEDGE_CONFIG_FILE):
        try:
            with open(_KNOWLEDGE_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"watch_dir": "", "auto_index": False}


def _save_knowledge_config(config: Dict[str, Any]):
    try:
        os.makedirs(os.path.dirname(_KNOWLEDGE_CONFIG_FILE), exist_ok=True)
        with open(_KNOWLEDGE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[bridge] WARNING: Failed to save knowledge config: {e}")


# ---------------------------------------------------------------------------
# Skills / Cron 辅助函数（Bridge 原生实现）
# ---------------------------------------------------------------------------

def _parse_yaml_frontmatter(text: str) -> dict:
    """从 SKILL.md 解析 YAML frontmatter，返回 metadata dict。"""
    if not text.startswith("---"):
        return {}
    import re
    match = re.search(r'\n---\s*\n', text[3:])
    if not match:
        return {}
    yaml_str = text[3:match.start() + 3]
    try:
        if _HAS_YAML:
            return yaml.safe_load(yaml_str) or {}
        # 简易解析 fallback（无 PyYAML 时）
        result = {}
        for line in yaml_str.splitlines():
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, _, val = line.partition(":")
                result[key.strip()] = val.strip().strip('"').strip("'")
        return result
    except Exception:
        return {}


def _list_skills_from_dir(skills_dir: str) -> list:
    """扫描 skills_dir 下所有 SKILL.md，提取 name + description。"""
    if not os.path.isdir(skills_dir):
        return []
    results = []
    for root, dirs, files in os.walk(skills_dir):
        if "SKILL.md" in files:
            skill_md = os.path.join(root, "SKILL.md")
            try:
                with open(skill_md, "r", encoding="utf-8") as f:
                    content = f.read()
                meta = _parse_yaml_frontmatter(content)
                dir_name = os.path.basename(root)
                # 判断 category：如果 parent 不是 skills_dir 自身，则 parent 名即 category
                parent = os.path.dirname(root)
                category = None
                if parent != skills_dir:
                    category = os.path.basename(parent)
                results.append({
                    "name": meta.get("name", dir_name),
                    "description": meta.get("description", ""),
                    "category": category,
                    "path": root,
                })
            except Exception:
                pass
    results.sort(key=lambda s: (s.get("category") or "", s["name"]))
    return results


def _find_skill_dir(skills_dir: str, name: str):
    """在 skills_dir 中搜索匹配 name 的技能目录，返回路径或 None。"""
    if not os.path.isdir(skills_dir):
        return None
    # 直接匹配
    direct = os.path.join(skills_dir, name)
    if os.path.isdir(direct) and os.path.isfile(os.path.join(direct, "SKILL.md")):
        return direct
    # 递归搜索
    for root, dirs, files in os.walk(skills_dir):
        if os.path.basename(root) == name and "SKILL.md" in files:
            return root
    return None


def _read_skill_from_dir(skills_dir: str, name: str):
    """读取指定技能的完整 SKILL.md 内容，返回 dict 或 None。"""
    skill_dir = _find_skill_dir(skills_dir, name)
    if not skill_dir:
        return None
    skill_md = os.path.join(skill_dir, "SKILL.md")
    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
        meta = _parse_yaml_frontmatter(content)
        # 列出辅助文件
        linked_files = []
        for subdir in ("references", "templates", "scripts", "assets"):
            subpath = os.path.join(skill_dir, subdir)
            if os.path.isdir(subpath):
                for fn in os.listdir(subpath):
                    linked_files.append(f"{subdir}/{fn}")
        return {
            "name": meta.get("name", os.path.basename(skill_dir)),
            "description": meta.get("description", ""),
            "content": content,
            "path": skill_dir,
            "linked_files": linked_files,
            "metadata": meta,
        }
    except Exception:
        return None


def _load_cron_jobs_for_profile(profile_name: str) -> list:
    """从指定 profile 的 cron/jobs.json 加载任务列表。"""
    pool = get_agent_pool()
    profile_home = pool._ensure_profile_home(profile_name)
    jobs_file = os.path.join(profile_home, "cron", "jobs.json")
    if not os.path.isfile(jobs_file):
        return []
    try:
        with open(jobs_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_cron_jobs_for_profile(profile_name: str, jobs: list):
    """保存任务列表到指定 profile 的 cron/jobs.json。"""
    pool = get_agent_pool()
    profile_home = pool._ensure_profile_home(profile_name)
    cron_dir = os.path.join(profile_home, "cron")
    os.makedirs(cron_dir, exist_ok=True)
    jobs_file = os.path.join(cron_dir, "jobs.json")
    with open(jobs_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


class BridgeRequestHandler(BaseHTTPRequestHandler):
    """桥接服务的 HTTP 请求处理器。"""

    def log_message(self, format, *args):
        """覆盖默认日志格式。"""
        sys.stderr.write(
            f"[hermes-bridge] {self.client_address[0]} - {format % args}\n"
        )

    def do_OPTIONS(self):
        """处理 CORS 预检请求。"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", _cors_origin(self))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _check_auth(self) -> bool:
        """检查 API Key。返回 True 表示通过/继续，False 表示已拒绝。"""
        # /health 端点免鉴权
        if self.path == "/health":
            return True
        err = _check_api_key(self)
        if err:
            _json_response(self, 401, {"error": "Unauthorized", "message": err})
            return False
        return True

    def do_GET(self):
        if not self._check_auth():
            return
        # 去掉 query string 以便路由匹配
        _path = urllib.parse.urlparse(self.path).path
        if _path == "/health":
            self._handle_health()
        elif self.path == "/knowledge/list" or self.path == "/knowledge/documents":
            self._handle_kb_list()
        elif self.path.startswith("/knowledge/document/"):
            self._handle_kb_get_document()
        elif self.path == "/knowledge/stats":
            self._handle_kb_stats()
        elif self.path == "/gateway/status":
            self._handle_gateway_status()
        elif self.path == "/gateway/platforms":
            self._handle_gateway_platforms()
        elif self.path == "/gateway/supported-platforms":
            self._handle_supported_platforms()
        elif self.path == "/wechat/status":
            self._handle_wechat_status()
        elif self.path == "/wechat/credentials":
            self._handle_wechat_credentials()
        elif self.path == "/wechat/check":
            self._handle_wechat_check()
        elif self.path == "/cloud/status":
            self._handle_cloud_status()
        # --- Session & Agent ---
        elif _path == "/sessions" or _path == "/sessions/":
            self._handle_sessions_list()
        elif _path == "/sessions/stats":
            self._handle_sessions_stats()
        elif _path.startswith("/sessions/") and _path.count("/") == 2:
            self._handle_session_get()
        elif _path == "/agents" or _path == "/agents/":
            self._handle_agents_list()
        elif _path.startswith("/agents/") and _path.count("/") == 2:
            self._handle_agent_get()
        # --- SDK 兼容路径 (/api/agent/*) ---
        elif _path == "/api/agent/my-agents":
            self._handle_api_agent_list()
        elif _path == "/api/agent/tools":
            self._handle_api_agent_tools()
        elif _path == "/api/platform/memory/stats":
            self._handle_memory_stats()
        # --- Phase 2: Memory / Skills / Tools / Cron ---
        elif _path == "/memory/stats":
            self._handle_memory_stats_v2()
        elif _path == "/tools" or _path == "/tools/":
            self._handle_tools_list()
        elif _path == "/skills" or _path == "/skills/":
            self._handle_skills_list()
        elif _path.startswith("/skills/") and _path.count("/") == 2:
            self._handle_skill_get()
        elif _path == "/cron" or _path == "/cron/":
            self._handle_cron_list()
        # --- Agent Templates ---
        elif _path == "/agent_config/default":
            self._handle_agent_config_default()
        elif _path.startswith("/agent_config/") and _path.count("/") == 2:
            self._handle_agent_config_get()
        # --- IAM ---
        elif _path == "/api/users/me":
            self._handle_iam_get_profile()
        elif _path == "/api/users/products":
            self._handle_iam_list_products()
        elif _path == "/api/users" or _path == "/api/users/":
            self._handle_iam_list_users()
        # --- Models ---
        elif _path == "/api/platform/models/providers":
            self._handle_models_providers()
        elif _path == "/api/platform/models/runtimes":
            self._handle_models_runtimes()
        elif _path == "/api/platform/models/resolve":
            self._handle_models_resolve()
        elif _path == "/api/platform/models/route":
            self._handle_models_route_get()
        elif _path == "/api/platform/models/usage":
            self._handle_models_usage()
        elif _path == "/api/platform/models/cost":
            self._handle_models_cost()
        elif _path == "/api/platform/models/quota":
            self._handle_models_quota()
        elif _path == "/api/platform/models" or _path == "/api/platform/models/":
            self._handle_models_list()
        # --- Conversations ---
        elif _path == "/api/platform/conversations/stats":
            self._handle_conversations_stats()
        elif _path == "/api/platform/conversations/groups" or _path == "/api/platform/conversations/groups/":
            self._handle_conversations_groups()
        elif _path.startswith("/api/platform/conversations/groups/") and _path.endswith("/messages"):
            self._handle_conversations_group_messages()
        elif _path == "/api/platform/conversations/history":
            self._handle_conversations_history()
        elif _path == "/api/platform/conversations" or _path == "/api/platform/conversations/":
            self._handle_conversations_home()
        # --- Billing ---
        elif _path == "/api/billing/wallet":
            self._handle_billing_wallet()
        elif _path == "/api/billing/records":
            self._handle_billing_records()
        elif _path == "/api/billing/summary":
            self._handle_billing_summary()
        # --- Channels ---
        elif _path.startswith("/api/platform/channels/wechat-work/config"):
            self._handle_channel_wechat_work_config()
        elif _path.startswith("/api/platform/channels/feishu/config"):
            self._handle_channel_feishu_config()
        elif _path.startswith("/api/platform/channels/wechat-personal-plugin/config"):
            self._handle_channel_wechat_personal_plugin_config()
        elif _path == "/api/platform/channels/wechat-personal-openclaw/qr/status":
            self._handle_channel_openclaw_qr_status()
        elif _path.startswith("/api/platform/channels/wechat-personal-openclaw/config"):
            self._handle_channel_wechat_personal_openclaw_config()
        elif _path == "/api/platform/channels/bindings":
            self._handle_channel_bindings_list()
        elif _path == "/api/platform/channels" or _path == "/api/platform/channels/":
            self._handle_channels_overview()
        # --- Tenant ---
        elif _path == "/api/users/me/context":
            self._handle_tenant_context()
        elif _path == "/api/company/verification":
            self._handle_company_verification_get()
        # --- Devices ---
        elif _path == "/api/platform/devices/account-state":
            self._handle_devices_account_state()
        elif _path == "/api/platform/devices/online":
            self._handle_devices_online()
        elif _path == "/api/platform/devices" or _path == "/api/platform/devices/":
            self._handle_devices_list()
        # --- Knowledge new paths ---
        elif _path == "/api/platform/knowledge/config":
            self._handle_platform_knowledge_config()
        elif _path == "/api/platform/knowledge/search":
            self._handle_platform_knowledge_search()
        elif _path == "/api/platform/knowledge/download":
            self._handle_platform_knowledge_download()
        elif _path == "/api/platform/knowledge/stats":
            self._handle_platform_knowledge_stats()
        elif _path == "/api/platform/knowledge/list":
            self._handle_platform_knowledge_list()
        # --- Approval ---
        elif _path.startswith("/api/platform/approvals/") and _path.count("/") == 4:
            self._handle_approval_get()
        elif _path == "/api/platform/approvals" or _path == "/api/platform/approvals/":
            self._handle_approvals_list()
        # --- Audit ---
        elif _path == "/api/platform/audit/summary":
            self._handle_audit_summary()
        elif _path == "/api/platform/audit/events":
            self._handle_audit_events_list()
        # --- App Keys ---
        elif _path == "/api/users/app-keys":
            self._handle_app_keys_list()
        # --- LLM Keys ---
        elif _path == "/api/llm/keys":
            self._handle_llm_keys_list()
        # --- Workflows ---
        elif _path.startswith("/api/workflows/executions/") and _path.endswith("/logs"):
            self._handle_workflow_execution_logs()
        elif _path.startswith("/api/workflows/") and _path.count("/") == 3:
            self._handle_workflow_get()
        elif _path == "/api/workflows" or _path == "/api/workflows/":
            self._handle_workflows_list()
        # --- Documents ---
        elif _path.startswith("/api/products/") and _path.endswith("/documents"):
            self._handle_product_documents()
        elif _path.startswith("/api/documents/") and _path.count("/") == 3:
            self._handle_document_get()
        elif _path == "/api/documents" or _path == "/api/documents/":
            self._handle_documents_list()
        else:
            _json_response(self, 404, {"error": "Not found"})

    def do_POST(self):
        if not self._check_auth():
            return
        if self.path == "/invoke":
            self._handle_invoke()
        elif self.path == "/invoke/stream":
            self._handle_invoke_stream()
        elif self.path == "/knowledge/upload":
            self._handle_kb_upload()
        elif self.path == "/knowledge/search":
            self._handle_kb_search()
        elif self.path.startswith("/knowledge/delete/"):
            self._handle_kb_delete()
        elif self.path == "/gateway/start":
            self._handle_gateway_start()
        elif self.path == "/gateway/stop":
            self._handle_gateway_stop()
        elif self.path == "/gateway/configure":
            self._handle_gateway_configure()
        elif self.path == "/wechat/webhook":
            self._handle_wechat_webhook()
        elif self.path == "/wechat/qr-login":
            self._handle_wechat_qr_login()
        elif self.path == "/wechat/qr-cancel":
            self._handle_wechat_qr_cancel()
        elif self.path == "/wechat/configure":
            self._handle_wechat_configure()
        elif self.path == "/wechat/send":
            self._handle_wechat_send()
        elif self.path == "/wechat/adapter/start":
            self._handle_wechat_adapter_start()
        elif self.path == "/wechat/adapter/stop":
            self._handle_wechat_adapter_stop()
        # --- Session & Agent ---
        elif self.path == "/sessions":
            self._handle_session_create()
        elif self.path.startswith("/sessions/") and self.path.endswith("/clear"):
            self._handle_session_clear()
        elif self.path.startswith("/sessions/") and self.path.endswith("/delete"):
            self._handle_session_delete()
        elif self.path == "/agents":
            self._handle_agent_create()
        elif self.path.startswith("/agents/") and self.path.endswith("/delete"):
            self._handle_agent_delete()
        # --- SDK 兼容路径 (/api/agent/*) ---
        elif self.path == "/api/agent/create":
            self._handle_api_agent_create()
        elif self.path == "/api/platform/memory/store":
            self._handle_memory_store()
        elif self.path == "/api/platform/memory/search":
            self._handle_memory_search()
        # --- Phase 2: Memory / Skills / Cron ---
        elif self.path == "/memory/store":
            self._handle_memory_store_v2()
        elif self.path == "/memory/search":
            self._handle_memory_search_v2()
        elif self.path == "/memory/clear":
            self._handle_memory_clear_v2()
        elif self.path == "/skills/install":
            self._handle_skill_install()
        elif self.path == "/skills/uninstall":
            self._handle_skill_uninstall()
        elif self.path == "/cron":
            self._handle_cron_create()
        # --- Conversations ---
        elif self.path == "/api/platform/conversations/messages":
            self._handle_conversations_send()
        # --- Channels ---
        elif self.path == "/api/platform/channels/wechat-work/config":
            self._handle_channel_wechat_work_config_update()
        elif self.path == "/api/platform/channels/feishu/config":
            self._handle_channel_feishu_config_update()
        elif self.path == "/api/platform/channels/wechat-personal-plugin/config":
            self._handle_channel_wechat_personal_plugin_config_update()
        elif self.path == "/api/platform/channels/bindings/create":
            self._handle_channel_binding_create()
        elif self.path == "/api/platform/channels/bindings/disable":
            self._handle_channel_binding_disable()
        elif self.path == "/api/platform/channels/bindings/regenerate-code":
            self._handle_channel_binding_regenerate_code()
        elif self.path == "/api/platform/channels/wechat-personal-openclaw/qr/start":
            self._handle_channel_openclaw_qr_start()
        # --- Knowledge new paths ---
        elif self.path == "/api/platform/knowledge/config/update":
            self._handle_platform_knowledge_config_update()
        elif self.path == "/api/platform/knowledge/upload":
            self._handle_platform_knowledge_upload()
        elif self.path == "/api/platform/knowledge/delete":
            self._handle_platform_knowledge_delete()
        # --- Approval ---
        elif self.path.startswith("/api/platform/approvals/") and self.path.endswith("/resolve"):
            self._handle_approval_resolve()
        elif self.path == "/api/platform/approvals/request":
            self._handle_approval_request()
        # --- Audit ---
        elif self.path == "/api/platform/audit/events":
            self._handle_audit_record()
        # --- Company ---
        elif self.path == "/api/company/verification/approve":
            self._handle_company_verification_approve()
        elif self.path == "/api/company/verification":
            self._handle_company_verification_submit()
        # --- Devices ---
        elif self.path == "/api/platform/devices/bootstrap":
            self._handle_devices_bootstrap()
        elif self.path == "/api/platform/devices/pair-code":
            self._handle_devices_pair_code()
        elif self.path == "/api/platform/devices/claim":
            self._handle_devices_claim()
        # --- Workflow ---
        elif self.path.startswith("/api/workflows/") and self.path.endswith("/run"):
            self._handle_workflow_run()
        elif self.path == "/api/workflows":
            self._handle_workflow_save()
        # --- ApiKey ---
        elif self.path == "/api/users/app-keys/default/token":
            self._handle_app_key_issue_token()
        elif self.path == "/api/users/app-keys":
            self._handle_app_key_create()
        elif self.path == "/api/llm/keys":
            self._handle_llm_key_create()
        # --- Policy ---
        elif self.path == "/api/platform/policy/tool-access/check":
            self._handle_policy_check()
        elif self.path == "/api/platform/policy/data-access/check":
            self._handle_policy_check()
        elif self.path == "/api/platform/policy/exec-access/check":
            self._handle_policy_check()
        # --- Voice ---
        elif self.path == "/api/asr":
            self._handle_voice_not_implemented()
        elif self.path == "/api/tts":
            self._handle_voice_not_implemented()
        elif self.path == "/api/audio/speech":
            self._handle_voice_not_implemented()
        else:
            _json_response(self, 404, {"error": "Not found"})

    def do_PUT(self):
        if not self._check_auth():
            return
        _path = urllib.parse.urlparse(self.path).path
        # PUT /api/agent/{id}
        if _path.startswith("/api/agent/") and _path.count("/") == 3:
            self._handle_api_agent_update()
        # --- Phase 2: Tools ---
        elif _path == "/tools":
            self._handle_tools_update()
        # --- IAM ---
        elif _path == "/api/users/me/preference":
            self._handle_iam_update_preference()
        elif _path == "/api/users/me":
            self._handle_iam_update_profile()
        # --- Models ---
        elif _path == "/api/platform/models/route":
            self._handle_models_route_set()
        # --- App Keys ---
        elif _path.startswith("/api/users/app-keys/") and _path.endswith("/name"):
            self._handle_app_key_rename()
        # --- Devices ---
        elif _path.startswith("/api/platform/devices/") and _path.count("/") == 4:
            self._handle_device_update()
        # --- LLM Keys ---
        elif _path.startswith("/api/llm/keys/") and _path.count("/") == 4:
            self._handle_llm_key_update()
        else:
            _json_response(self, 404, {"error": "Not found"})

    def do_DELETE(self):
        if not self._check_auth():
            return
        _path = urllib.parse.urlparse(self.path).path
        # DELETE /api/agent/{id}
        if _path.startswith("/api/agent/") and _path.count("/") == 3:
            self._handle_api_agent_delete()
        # DELETE /api/platform/memory/agent/{agentId}
        elif _path.startswith("/api/platform/memory/agent/"):
            self._handle_memory_clear_agent()
        # DELETE /api/platform/memory/{entryId}
        elif _path.startswith("/api/platform/memory/"):
            self._handle_memory_delete()
        # --- Phase 2: Cron ---
        elif _path.startswith("/cron/") and _path.count("/") == 2:
            self._handle_cron_delete()
        # --- App Keys ---
        elif _path.startswith("/api/users/app-keys/"):
            self._handle_app_key_delete()
        # --- LLM Keys ---
        elif _path.startswith("/api/llm/keys/"):
            self._handle_llm_key_delete()
        # --- Devices ---
        elif _path.startswith("/api/platform/devices/") and _path.count("/") == 4:
            self._handle_device_delete()
        else:
            _json_response(self, 404, {"error": "Not found"})

    def do_PATCH(self):
        if not self._check_auth():
            return
        _path = urllib.parse.urlparse(self.path).path
        if _path.startswith("/api/users/app-keys/"):
            self._handle_app_key_set_active()
        else:
            _json_response(self, 404, {"error": "Not found"})

    # ----- Endpoints -----

    def _handle_health(self):
        """健康检查端点。"""
        err = _get_hermes_error()
        if err:
            _json_response(self, 503, {
                "status": "error",
                "version": BRIDGE_VERSION,
                "hermes_available": False,
                "message": err,
            })
            return

        # 尝试导入 hermes-agent 核心模块来验证可用性
        try:
            _ensure_hermes_on_path()
            import agent  # noqa: F401 — hermes-agent 的核心包

            # 知识库状态
            kb_info = {"available": False}
            try:
                from knowledge_store import get_kb_stats
                kb_info = get_kb_stats()
            except ImportError:
                kb_info = {"available": False, "error": "chromadb not installed"}
            except Exception:
                pass

            # AgentPool 信息
            pool = get_agent_pool()
            pool_info = {
                "available": pool.available,
                "base_hermes_home": pool._base_hermes_home,
                "profiles_home": pool.profiles_home,
            }

            _json_response(self, 200, {
                "status": "ok",
                "version": BRIDGE_VERSION,
                "hermes_available": True,
                "hermes_dir": os.path.abspath(HERMES_AGENT_DIR),
                "python_version": sys.version,
                "knowledge_base": kb_info,
                "agent_pool": pool_info,
            })
        except ImportError as e:
            _json_response(self, 503, {
                "status": "error",
                "version": BRIDGE_VERSION,
                "hermes_available": False,
                "message": f"Failed to import hermes-agent: {e}",
            })

    def _handle_invoke(self):
        """非流式模型调用端点。支持 session_id 实现多轮对话。

        使用 AgentPool 调用 AIAgent.run_conversation()，
        获得完整的 Tool Calling / Memory / Delegate 能力。
        当 AIAgent 不可用时自动降级为裸 LLM 调用。
        """
        try:
            body = _read_json_body(self)
            prompt = body.get("prompt", "")
            model = body.get("model")
            provider = body.get("provider")
            max_tokens = body.get("max_tokens")
            temperature = body.get("temperature")
            system_prompt = body.get("system_prompt")
            use_knowledge = body.get("use_knowledge", True)  # 默认启用 RAG
            kb_scope = body.get("kb_scope")
            # 多轮对话 + 多智体参数
            session_id = body.get("session_id")
            user_id = body.get("user_id", "anonymous")
            agent_profile = body.get("agent_profile", "default")
            max_history_turns = body.get("max_history_turns", 20)

            if not prompt:
                _json_response(self, 400, {"error": "prompt is required"})
                return

            # RAG: 自动检索知识库并注入上下文
            rag_context = ""
            if use_knowledge:
                try:
                    from knowledge_store import build_rag_context, is_kb_available
                    if is_kb_available():
                        rag_context = build_rag_context(prompt, scope=kb_scope)
                except ImportError:
                    pass
                except Exception as e:
                    print(f"[hermes-bridge] KB retrieval warning: {e}")

            # 将 RAG 上下文注入到 system prompt
            effective_system_prompt = system_prompt or ""
            if rag_context:
                effective_system_prompt = (
                    (effective_system_prompt + "\n\n" if effective_system_prompt else "")
                    + rag_context
                )

            # 获取/创建 session（支持多轮对话）
            from session_manager import get_session_manager
            sm = get_session_manager()
            session = sm.get_or_create_session(
                session_id=session_id,
                user_id=user_id,
                agent_profile=agent_profile,
            )
            actual_session_id = session.session_id

            # 获取 agent profile 的默认参数
            profile = sm.get_profile(session.agent_profile)
            if profile:
                if not effective_system_prompt and profile.system_prompt:
                    effective_system_prompt = profile.system_prompt
                if temperature is None and profile.temperature is not None:
                    temperature = profile.temperature

            # 通过 AgentPool 调用（AIAgent 或 fallback）
            pool = get_agent_pool()
            result = pool.invoke(
                prompt=prompt,
                profile=profile,
                session=session,
                system_prompt=effective_system_prompt or None,
                model=model,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
                max_history_turns=max_history_turns,
            )

            # 记录本轮对话到 session
            assistant_text = result.get("text", "")
            if assistant_text:
                sm.append_turn(actual_session_id, prompt, assistant_text)

            # 在响应中标记会话信息
            result["session_id"] = actual_session_id
            result["agent_profile"] = session.agent_profile
            result["turn_count"] = session.turn_count
            if rag_context:
                result["_rag_used"] = True

            _json_response(self, 200, result)

        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {
                "error": f"Internal bridge error: {e}",
            })

    def _handle_wechat_webhook(self):
        """轻量个人微信网关集成回调"""
        try:
            body = _read_json_body(self)
            from wechat_gateway import parse_wechat_message, construct_wechat_reply
            prompt = parse_wechat_message(body)

            if not prompt:
                _json_response(self, 200, {"status": "ignored", "reason": "no text"})
                return

            # 调用内部的抽象流转 (非流式，保证拿到全文本)
            ans = self._invoke_hermes(
                prompt=prompt,
                system_prompt="你是由 QeeClaw 部署在微信内的私域助理，请用简洁亲和的语调回答。"
            )

            if "error" in ans:
                reply_payload = construct_wechat_reply(body, f"抱歉，大模型处理失败: {ans['error']}")
                _json_response(self, 200, reply_payload)
            else:
                reply_payload = construct_wechat_reply(body, ans.get("text", "（空）"))
                _json_response(self, 200, reply_payload)

        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # ----- Session & Agent Management Endpoints -----

    def _handle_sessions_list(self):
        """GET /sessions — 列出会话 (可按 user_id / agent_profile 过滤)。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            user_id = params.get("user_id", [None])[0]
            agent_profile = params.get("agent_profile", [None])[0]
            sessions = sm.list_sessions(user_id=user_id, agent_profile=agent_profile)
            _json_response(self, 200, {"sessions": sessions})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_sessions_stats(self):
        """GET /sessions/stats — 会话统计信息。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            total = len(sm._sessions)
            users = set()
            profiles_used: Dict[str, int] = {}
            total_turns = 0
            for s in sm._sessions.values():
                users.add(s.user_id)
                profiles_used[s.agent_profile] = profiles_used.get(s.agent_profile, 0) + 1
                total_turns += s.turn_count
            _json_response(self, 200, {
                "total_sessions": total,
                "unique_users": len(users),
                "total_turns": total_turns,
                "profiles_used": profiles_used,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_session_get(self):
        """GET /sessions/{session_id} — 获取单个会话详情。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            parts = self.path.strip("/").split("/")
            # /sessions/{id}
            session_id = parts[1] if len(parts) >= 2 else None
            if not session_id:
                _json_response(self, 400, {"error": "session_id is required"})
                return
            session = sm.get_session(session_id)
            if not session:
                _json_response(self, 404, {"error": f"session {session_id} not found"})
                return
            _json_response(self, 200, session.to_dict())
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_session_create(self):
        """POST /sessions — 手动创建会话。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            body = _read_json_body(self)
            user_id = body.get("user_id", "anonymous")
            agent_profile = body.get("agent_profile", "default")
            session = sm.create_session(user_id=user_id, agent_profile=agent_profile)
            _json_response(self, 200, {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "agent_profile": session.agent_profile,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_session_clear(self):
        """POST /sessions/{session_id}/clear — 清空会话历史。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            parts = self.path.strip("/").split("/")
            session_id = parts[1] if len(parts) >= 2 else None
            if not session_id:
                _json_response(self, 400, {"error": "session_id is required"})
                return
            session = sm.get_session(session_id)
            if not session:
                _json_response(self, 404, {"error": f"session {session_id} not found"})
                return
            session.clear_messages()
            _json_response(self, 200, {"status": "cleared", "session_id": session_id})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_session_delete(self):
        """POST /sessions/{session_id}/delete — 删除会话。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            parts = self.path.strip("/").split("/")
            session_id = parts[1] if len(parts) >= 2 else None
            if not session_id:
                _json_response(self, 400, {"error": "session_id is required"})
                return
            ok = sm.delete_session(session_id)
            if not ok:
                _json_response(self, 404, {"error": f"session {session_id} not found"})
                return
            _json_response(self, 200, {"status": "deleted", "session_id": session_id})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_agents_list(self):
        """GET /agents — 列出所有可用智体 (Agent Profile)。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            profiles = sm.list_profiles()
            _json_response(self, 200, {"agents": profiles})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_agent_get(self):
        """GET /agents/{name} — 获取单个智体详情。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            parts = self.path.strip("/").split("/")
            agent_name = parts[1] if len(parts) >= 2 else None
            if not agent_name:
                _json_response(self, 400, {"error": "agent name is required"})
                return
            profile = sm.get_profile(agent_name)
            if not profile:
                _json_response(self, 404, {"error": f"agent '{agent_name}' not found"})
                return
            _json_response(self, 200, profile.to_dict())
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_agent_create(self):
        """POST /agents — 创建/更新自定义智体。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            body = _read_json_body(self)
            name = body.get("name")
            if not name:
                _json_response(self, 400, {"error": "name is required"})
                return
            profile = sm.create_profile(body)
            _json_response(self, 200, {"status": "created", "agent": profile.to_dict()})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_agent_delete(self):
        """POST /agents/{name}/delete — 删除自定义智体。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            parts = self.path.strip("/").split("/")
            agent_name = parts[1] if len(parts) >= 2 else None
            if not agent_name:
                _json_response(self, 400, {"error": "agent name is required"})
                return
            ok = sm.delete_profile(agent_name)
            if not ok:
                _json_response(self, 404, {"error": f"agent '{agent_name}' not found or is builtin"})
                return
            _json_response(self, 200, {"status": "deleted", "agent": agent_name})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # ----- SDK 兼容接口 (/api/agent/*) -----

    def _handle_api_agent_list(self):
        """GET /api/agent/my-agents — SDK 兼容：列出智体（平台响应格式）。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            agents = [_profile_to_sdk_agent(p) for p in sm._profiles.values()]
            _platform_json_response(self, 200, agents)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_api_agent_tools(self):
        """GET /api/agent/tools — SDK 兼容：列出系统工具。

        从 hermes-agent 的 toolsets 中获取真实工具列表。
        支持 ?agent_id= 查询参数按 profile 过滤工具集。
        """
        try:
            _ensure_hermes_on_path()
            tools: List[Dict[str, Any]] = []

            # 解析 query string 中的 agent_id（可选）
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            agent_id_str = (params.get("agent_id") or [None])[0]

            # 尝试获取 profile 以支持 per-agent toolset 过滤
            enabled_ts = None
            disabled_ts = None
            if agent_id_str:
                try:
                    from session_manager import get_session_manager
                    sm = get_session_manager()
                    profile = _find_profile_by_id(sm, int(agent_id_str))
                    if profile:
                        if not profile.tools_enabled:
                            _platform_json_response(self, 200, [])
                            return
                        enabled_ts = profile.enabled_toolsets
                        disabled_ts = profile.disabled_toolsets
                except (ValueError, TypeError):
                    pass

            try:
                from model_tools import get_tool_definitions
                raw_tools = get_tool_definitions(
                    enabled_toolsets=enabled_ts,
                    disabled_toolsets=disabled_ts,
                    quiet_mode=True,
                )
                for t in raw_tools:
                    fn = t.get("function", {})
                    tools.append({
                        "name": fn.get("name", ""),
                        "description": fn.get("description", ""),
                        "parameters": fn.get("parameters", {}),
                    })
            except ImportError:
                pass  # hermes-agent 不可用，返回空列表

            _platform_json_response(self, 200, tools)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_api_agent_create(self):
        """POST /api/agent/create — SDK 兼容：创建智体（平台响应格式）。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            body = _read_json_body(self)

            name = body.get("name", "")
            description = body.get("description", "")
            model = body.get("model", "")
            runtime_type = body.get("runtime_type", "openclaw")

            if not name:
                _platform_json_response(self, 400, None, "name is required")
                return

            # 生成唯一 code（作为 profile name）
            code = "".join(
                c if c.isalnum() or c in "_-" else "_"
                for c in name.lower()
            ).strip("_")
            if not code:
                code = f"agent_{int(time.time())}"
            # 避免 code 冲突
            base_code = code
            counter = 1
            while sm.get_profile(code):
                code = f"{base_code}_{counter}"
                counter += 1

            profile_data = {
                "name": code,
                "display_name": name,
                "system_prompt": description,
                "model": model,
                "metadata": {
                    "description": description,
                    "runtime_type": runtime_type,
                },
            }
            profile = sm.create_profile(profile_data)
            agent_id = _get_agent_id(profile.name)

            _platform_json_response(self, 200, {
                "id": agent_id,
                "code": profile.name,
                "runtime_type": runtime_type,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_api_agent_update(self):
        """PUT /api/agent/{id} — SDK 兼容：更新智体（平台响应格式）。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()

            # 从路径提取 agent_id: /api/agent/{id}
            _path = urllib.parse.urlparse(self.path).path
            parts = _path.strip("/").split("/")
            try:
                agent_id = int(parts[-1])
            except (IndexError, ValueError):
                _platform_json_response(self, 400, None, "invalid agent id")
                return

            profile = _find_profile_by_id(sm, agent_id)
            if not profile:
                _platform_json_response(self, 404, None, f"agent {agent_id} not found")
                return

            body = _read_json_body(self)
            name = body.get("name", profile.display_name)
            description = body.get("description", "")
            model = body.get("model", profile.model)
            runtime_type = body.get("runtime_type",
                                    profile.metadata.get("runtime_type", "openclaw"))

            # 更新 profile 字段
            profile.display_name = name
            if description:
                profile.system_prompt = description
                profile.metadata["description"] = description
            if model:
                profile.model = model
            profile.metadata["runtime_type"] = runtime_type
            sm._save_custom_profiles()

            _platform_json_response(self, 200, _profile_to_sdk_agent(profile))
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_api_agent_delete(self):
        """DELETE /api/agent/{id} — SDK 兼容：删除智体（平台响应格式）。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()

            _path = urllib.parse.urlparse(self.path).path
            parts = _path.strip("/").split("/")
            try:
                agent_id = int(parts[-1])
            except (IndexError, ValueError):
                _platform_json_response(self, 400, None, "invalid agent id")
                return

            profile = _find_profile_by_id(sm, agent_id)
            if not profile:
                _platform_json_response(self, 404, None, f"agent {agent_id} not found")
                return

            # 内建 profile 不允许删除
            from session_manager import _BUILTIN_PROFILES
            if profile.name in _BUILTIN_PROFILES:
                _platform_json_response(self, 400, None,
                                        f"cannot delete built-in agent '{profile.display_name}'")
                return

            sm.delete_profile(profile.name)
            _platform_json_response(self, 200, {"id": agent_id, "deleted": True})
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Memory 接口 (/api/platform/memory/*) -----

    def _handle_memory_store(self):
        """POST /api/platform/memory/store — 存入记忆。"""
        try:
            from memory_store import store_memory
            body = _read_json_body(self)
            entry = store_memory(
                content=body.get("content", ""),
                category=body.get("category", "other"),
                importance=body.get("importance", 0.5),
                team_id=body.get("team_id"),
                runtime_type=body.get("runtime_type", "openclaw"),
                device_id=body.get("device_id"),
                agent_id=body.get("agent_id"),
                source_session=body.get("source_session"),
                skip_duplicate_check=body.get("skip_duplicate_check", False),
            )
            _platform_json_response(self, 200, entry)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_memory_search(self):
        """POST /api/platform/memory/search — 搜索记忆。"""
        try:
            from memory_store import search_memory
            body = _read_json_body(self)
            scope = {}
            for key in ("team_id", "runtime_type", "device_id", "agent_id"):
                val = body.get(key)
                if val is not None:
                    scope[key] = val
            results = search_memory(
                query=body.get("query", ""),
                limit=body.get("limit", 5),
                threshold=body.get("threshold", 0.0),
                scope=scope,
            )
            _platform_json_response(self, 200, results)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_memory_delete(self):
        """DELETE /api/platform/memory/{entryId} — 删除单条记忆。"""
        try:
            from memory_store import delete_memory
            _path = urllib.parse.urlparse(self.path).path
            entry_id = _path.replace("/api/platform/memory/", "").strip("/")
            entry_id = urllib.parse.unquote(entry_id)

            # scope 从 query string 获取
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            scope = {}
            for key in ("team_id", "agent_id", "runtime_type"):
                vals = params.get(key)
                if vals:
                    scope[key] = vals[0]

            deleted = delete_memory(entry_id, scope=scope)
            _platform_json_response(self, 200, {"deleted": deleted})
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_memory_clear_agent(self):
        """DELETE /api/platform/memory/agent/{agentId} — 清除 agent 全部记忆。"""
        try:
            from memory_store import clear_agent_memory
            _path = urllib.parse.urlparse(self.path).path
            agent_id = _path.replace("/api/platform/memory/agent/", "").strip("/")
            agent_id = urllib.parse.unquote(agent_id)

            # scope 从 query string 获取
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            scope = {}
            for key in ("team_id", "runtime_type"):
                vals = params.get(key)
                if vals:
                    scope[key] = vals[0]

            cleared_count = clear_agent_memory(agent_id, scope=scope)
            _platform_json_response(self, 200, {"cleared_count": cleared_count})
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_memory_stats(self):
        """GET /api/platform/memory/stats — 记忆统计。"""
        try:
            from memory_store import get_memory_stats
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            scope = {}
            for key in ("team_id", "agent_id", "runtime_type"):
                vals = params.get(key)
                if vals:
                    scope[key] = vals[0]
            stats = get_memory_stats(scope=scope)
            _platform_json_response(self, 200, stats)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- WeChat Native Gateway (Path A) Endpoints -----

    def _handle_wechat_check(self):
        """检查微信网关依赖是否就绪。"""
        try:
            _ensure_hermes_on_path()
            from wechat_gateway import check_wechat_available
            result = check_wechat_available()
            _json_response(self, 200, result)
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_wechat_qr_login(self):
        """发起微信 QR 扫码登录。"""
        try:
            _ensure_hermes_on_path()
            from wechat_gateway import start_qr_login
            result = start_qr_login()
            _json_response(self, 200, result)
        except ImportError as e:
            _json_response(self, 503, {"error": f"微信模块不可用: {e}"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_cloud_status(self):
        """获取云端隧道连接状态。"""
        try:
            from cloud_tunnel import get_tunnel_status
            _json_response(self, 200, get_tunnel_status())
        except ImportError:
            _json_response(self, 200, {"connected": False, "error": "cloud_tunnel module not available"})
        except Exception as e:
            _json_response(self, 200, {"connected": False, "error": str(e)})

    def _handle_wechat_status(self):
        """获取 QR 登录状态和适配器运行状态。"""
        try:
            _ensure_hermes_on_path()
            from wechat_gateway import get_qr_login_status, get_adapter_status
            qr_status = get_qr_login_status()
            adapter_status = get_adapter_status()
            _json_response(self, 200, {
                "qr_login": qr_status,
                "adapter": adapter_status,
            })
        except ImportError as e:
            _json_response(self, 200, {
                "qr_login": {"state": "unavailable"},
                "adapter": {"adapter_running": False, "credentials": {"configured": False}},
                "_error": str(e),
            })
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_wechat_qr_cancel(self):
        """取消当前 QR 登录会话。"""
        try:
            _ensure_hermes_on_path()
            from wechat_gateway import cancel_qr_login
            result = cancel_qr_login()
            _json_response(self, 200, result)
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_wechat_credentials(self):
        """获取当前微信凭证摘要。"""
        try:
            _ensure_hermes_on_path()
            from wechat_gateway import get_wechat_credentials
            result = get_wechat_credentials()
            _json_response(self, 200, result)
        except Exception as e:
            _json_response(self, 200, {
                "configured": False,
                "account_id": "",
                "has_token": False,
                "_error": str(e),
            })

    def _handle_wechat_configure(self):
        """配置微信策略（DM / 群聊策略、白名单等）。"""
        try:
            body = _read_json_body(self)
            _ensure_hermes_on_path()
            from wechat_gateway import configure_wechat
            result = configure_wechat(body)
            _json_response(self, 200, result)
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_wechat_send(self):
        """发送微信消息（单次直发，不需要启动完整适配器）。"""
        try:
            body = _read_json_body(self)
            chat_id = body.get("chat_id", "")
            message = body.get("message", "")
            media_files = body.get("media_files")

            if not chat_id:
                _json_response(self, 400, {"error": "chat_id is required"})
                return
            if not message and not media_files:
                _json_response(self, 400, {"error": "message or media_files is required"})
                return

            _ensure_hermes_on_path()
            from wechat_gateway import send_message
            result = send_message(chat_id=chat_id, message=message, media_files=media_files)
            status = 200 if "error" not in result else 400
            _json_response(self, status, result)
        except ImportError as e:
            _json_response(self, 503, {"error": f"微信模块不可用: {e}"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_wechat_adapter_start(self):
        """启动微信长轮询适配器（持续接收和回复消息）。"""
        try:
            _ensure_hermes_on_path()
            from wechat_gateway import start_adapter
            result = start_adapter()
            status = 200 if "error" not in result else 400
            _json_response(self, status, result)
        except ImportError as e:
            _json_response(self, 503, {"error": f"微信模块不可用: {e}"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_wechat_adapter_stop(self):
        """停止微信长轮询适配器。"""
        try:
            _ensure_hermes_on_path()
            from wechat_gateway import stop_adapter
            result = stop_adapter()
            _json_response(self, 200, result)
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_invoke_stream(self):
        """流式模型调用端点 (SSE)。支持 session_id 实现多轮对话。

        优先使用 AIAgent 的 stream_callback 实现流式输出；
        当 AIAgent 不可用时降级为 OpenAI SDK stream=True。
        """
        try:
            body = _read_json_body(self)
            prompt = body.get("prompt", "")

            if not prompt:
                _json_response(self, 400, {"error": "prompt is required"})
                return

            # 多轮对话 + 多智体参数
            session_id = body.get("session_id")
            user_id = body.get("user_id", "anonymous")
            agent_profile = body.get("agent_profile", "default")
            max_history_turns = body.get("max_history_turns", 20)

            # 设置 SSE 响应头
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            model_name = body.get("model")
            provider_name = body.get("provider")
            system_prompt = body.get("system_prompt")
            max_tokens = body.get("max_tokens")
            temperature = body.get("temperature")
            use_knowledge = body.get("use_knowledge", True)
            kb_scope = body.get("kb_scope")

            # 获取/创建 session
            from session_manager import get_session_manager
            sm = get_session_manager()
            session = sm.get_or_create_session(
                session_id=session_id,
                user_id=user_id,
                agent_profile=agent_profile,
            )
            actual_session_id = session.session_id

            # 获取 agent profile 的默认参数
            profile = sm.get_profile(session.agent_profile)
            if profile:
                if not system_prompt and profile.system_prompt:
                    system_prompt = profile.system_prompt
                if temperature is None and profile.temperature is not None:
                    temperature = profile.temperature

            # RAG: 自动检索知识库并注入上下文
            if use_knowledge:
                try:
                    from knowledge_store import build_rag_context, is_kb_available
                    if is_kb_available():
                        rag_context = build_rag_context(prompt, scope=kb_scope)
                        if rag_context:
                            system_prompt = (
                                (system_prompt + "\n\n" if system_prompt else "")
                                + rag_context
                            )
                except ImportError:
                    pass
                except Exception as e:
                    print(f"[hermes-bridge] KB stream retrieval warning: {e}")

            # 发送 session 元信息（首个 SSE 事件）
            meta_event = json.dumps({
                "type": "session",
                "session_id": actual_session_id,
                "agent_profile": session.agent_profile,
            }, ensure_ascii=False)
            self.wfile.write(f"data: {meta_event}\n\n".encode("utf-8"))
            self.wfile.flush()

            pool = get_agent_pool()
            collected_text: List[str] = []
            wfile = self.wfile

            def _sse_stream_callback(delta: str):
                """将 AIAgent 的文本 delta 写入 SSE。"""
                if delta:
                    collected_text.append(delta)
                    sse_data = json.dumps({
                        "type": "text",
                        "content": delta,
                    }, ensure_ascii=False)
                    wfile.write(f"data: {sse_data}\n\n".encode("utf-8"))
                    wfile.flush()

            if pool.available:
                # --- AIAgent 流式模式 ---
                result = pool.invoke(
                    prompt=prompt,
                    profile=profile,
                    session=session,
                    system_prompt=system_prompt or None,
                    model=model_name,
                    provider=provider_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    max_history_turns=max_history_turns,
                    stream_callback=_sse_stream_callback,
                )
                full_response = result.get("text", "")
            else:
                # --- Fallback 流式模式（裸 OpenAI streaming）---
                history = session.get_messages(max_turns=max_history_turns)
                stream = pool.invoke_stream_fallback(
                    prompt=prompt,
                    model=model_name,
                    provider=provider_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system_prompt=system_prompt,
                    history=history,
                )
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        _sse_stream_callback(delta.content)
                    if chunk.choices[0].finish_reason:
                        break
                full_response = "".join(collected_text)

            # 记录本轮对话到 session
            if full_response:
                sm.append_turn(actual_session_id, prompt, full_response)

            # 发送完成信号
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

        except Exception as e:
            traceback.print_exc()
            try:
                error_chunk = json.dumps({
                    "type": "error",
                    "error": str(e),
                }, ensure_ascii=False)
                self.wfile.write(f"data: {error_chunk}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

    # ----- Knowledge Base Endpoints -----

    def _handle_kb_upload(self):
        """上传文档到知识库。"""
        try:
            body = _read_json_body(self)
            content = body.get("content", "")
            filename = body.get("filename", "")
            doc_type = body.get("doc_type", "text")
            scope = body.get("scope", "default")
            tags = body.get("tags", [])

            if not content:
                _json_response(self, 400, {"error": "content is required"})
                return

            from knowledge_store import add_document
            result = add_document(
                content=content,
                filename=filename,
                doc_type=doc_type,
                scope=scope,
                tags=tags,
            )

            status = 200 if result.get("success") else 400
            _json_response(self, status, result)

        except ImportError:
            _json_response(self, 503, {"error": "Knowledge base module not available. Install: pip install chromadb"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_kb_list(self):
        """列出知识库中的所有文档。"""
        try:
            # 从 query string 获取 scope 参数
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            scope = params.get("scope", [None])[0]

            from knowledge_store import list_documents
            docs = list_documents(scope=scope)
            _json_response(self, 200, {"documents": docs})

        except ImportError:
            _json_response(self, 503, {"error": "Knowledge base module not available"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_kb_get_document(self):
        """获取单个文档的元数据。"""
        try:
            # 从 URL 中提取 doc_id: /knowledge/document/<doc_id>
            doc_id = self.path.split("/knowledge/document/")[-1].strip("/")
            if not doc_id:
                _json_response(self, 400, {"error": "doc_id is required"})
                return

            from knowledge_store import get_document
            doc = get_document(doc_id)
            if doc:
                _json_response(self, 200, {"document": doc})
            else:
                _json_response(self, 404, {"error": f"Document not found: {doc_id}"})

        except ImportError:
            _json_response(self, 503, {"error": "Knowledge base module not available"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_kb_delete(self):
        """删除知识库中的文档。"""
        try:
            # /knowledge/delete/<doc_id>
            doc_id = self.path.split("/knowledge/delete/")[-1].strip("/")
            if not doc_id:
                _json_response(self, 400, {"error": "doc_id is required"})
                return

            from knowledge_store import delete_document
            result = delete_document(doc_id)
            status = 200 if result.get("success") else 404
            _json_response(self, status, result)

        except ImportError:
            _json_response(self, 503, {"error": "Knowledge base module not available"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_kb_search(self):
        """在知识库中进行向量检索。"""
        try:
            body = _read_json_body(self)
            query = body.get("query", "")
            top_k = body.get("top_k", 5)
            scope = body.get("scope")
            min_score = body.get("min_score", 0.3)

            if not query:
                _json_response(self, 400, {"error": "query is required"})
                return

            from knowledge_store import search_knowledge
            results = search_knowledge(
                query=query,
                top_k=top_k,
                scope=scope,
                min_score=min_score,
            )
            _json_response(self, 200, {"results": results, "count": len(results)})

        except ImportError:
            _json_response(self, 503, {"error": "Knowledge base module not available. Install: pip install chromadb"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_kb_stats(self):
        """返回知识库统计信息。"""
        try:
            from knowledge_store import get_kb_stats
            stats = get_kb_stats()
            _json_response(self, 200, stats)
        except ImportError:
            _json_response(self, 200, {
                "available": False,
                "error": "Knowledge base module not available. Install: pip install chromadb",
                "document_count": 0,
            })
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_gateway_status(self):
        """Gateway 运行状态查询端点。"""
        global _gateway_process

        running = False
        pid = None
        if _gateway_process is not None:
            poll = _gateway_process.poll()
            if poll is None:
                running = True
                pid = _gateway_process.pid
            else:
                _gateway_process = None

        # 尝试从 hermes 的 status.json 获取平台连接信息
        platforms_info: List[Dict[str, Any]] = []
        try:
            _ensure_hermes_on_path()
            from hermes_cli.config import get_hermes_home
            status_file = get_hermes_home() / "gateway-status.json"
            if status_file.exists():
                import json as _json
                status_data = _json.loads(status_file.read_text())
                if isinstance(status_data, dict):
                    for plat_name, plat_state in status_data.get("platforms", {}).items():
                        platforms_info.append({
                            "name": plat_name,
                            "state": plat_state.get("state", "unknown"),
                            "error": plat_state.get("error_message"),
                        })
        except Exception:
            pass

        active_count = sum(1 for p in platforms_info if p.get("state") == "connected")
        platform_names = [p["name"] for p in platforms_info]

        _json_response(self, 200, {
            "running": running,
            "pid": pid,
            "platforms": platform_names,
            "activePlatformCount": active_count,
            "platformDetails": platforms_info,
        })

    def _handle_supported_platforms(self):
        """返回 hermes-agent 支持的所有消息平台。"""
        # 这些信息直接从 hermes gateway/config.py 的 Platform enum 中提取
        supported = [
            {"id": "telegram",      "name": "Telegram",        "authType": "bot_token", "envVar": "TELEGRAM_BOT_TOKEN"},
            {"id": "discord",       "name": "Discord",         "authType": "bot_token", "envVar": "DISCORD_BOT_TOKEN"},
            {"id": "dingtalk",      "name": "钉钉",             "authType": "app_credentials", "envVar": "DINGTALK_APP_KEY"},
            {"id": "feishu",        "name": "飞书",             "authType": "app_credentials", "envVar": "FEISHU_APP_ID"},
            {"id": "weixin",        "name": "个人微信",          "authType": "qr_login",       "envVar": "WEIXIN_ACCOUNT_ID"},
            {"id": "wecom",         "name": "企业微信",          "authType": "bot_credentials", "envVar": "WECOM_BOT_ID"},
            {"id": "whatsapp",      "name": "WhatsApp",        "authType": "bridge",    "envVar": "WHATSAPP_ENABLED"},
            {"id": "slack",         "name": "Slack",           "authType": "bot_token", "envVar": "SLACK_BOT_TOKEN"},
            {"id": "signal",        "name": "Signal",          "authType": "http_url",  "envVar": "SIGNAL_HTTP_URL"},
            {"id": "matrix",        "name": "Matrix",          "authType": "access_token", "envVar": "MATRIX_ACCESS_TOKEN"},
            {"id": "mattermost",    "name": "Mattermost",      "authType": "bot_token", "envVar": "MATTERMOST_TOKEN"},
            {"id": "email",         "name": "Email",           "authType": "imap_smtp", "envVar": "EMAIL_ADDRESS"},
            {"id": "sms",           "name": "SMS (Twilio)",    "authType": "api_key",   "envVar": "TWILIO_ACCOUNT_SID"},
            {"id": "homeassistant", "name": "Home Assistant",  "authType": "api_key",   "envVar": "HA_BASE_URL"},
            {"id": "webhook",       "name": "Webhook",         "authType": "none",      "envVar": ""},
            {"id": "api_server",    "name": "API Server",      "authType": "none",      "envVar": ""},
        ]
        _json_response(self, 200, {"platforms": supported})

    def _handle_gateway_platforms(self):
        """返回当前已配置（已有凭证）的活跃平台。"""
        err = _get_hermes_error()
        if err:
            _json_response(self, 200, {"configured": []})
            return

        try:
            _ensure_hermes_on_path()
            from gateway.config import load_gateway_config
            gw_config = load_gateway_config()
            connected = gw_config.get_connected_platforms()
            configured = []
            for plat in connected:
                pconfig = gw_config.platforms.get(plat)
                configured.append({
                    "id": plat.value,
                    "enabled": pconfig.enabled if pconfig else False,
                    "hasToken": bool(pconfig.token) if pconfig else False,
                    "hasHomeChannel": bool(pconfig.home_channel) if pconfig else False,
                })
            _json_response(self, 200, {"configured": configured})
        except ImportError:
            _json_response(self, 200, {"configured": [], "_note": "gateway module not available"})
        except Exception as e:
            _json_response(self, 200, {"configured": [], "_error": str(e)})

    def _handle_gateway_start(self):
        """启动 hermes Gateway 进程。"""
        global _gateway_process

        # 检查是否已在运行
        if _gateway_process is not None and _gateway_process.poll() is None:
            _json_response(self, 200, {
                "status": "already_running",
                "pid": _gateway_process.pid,
            })
            return

        err = _get_hermes_error()
        if err:
            _json_response(self, 503, {"error": err})
            return

        try:
            _ensure_hermes_on_path()
            agent_dir = os.path.abspath(HERMES_AGENT_DIR)

            # 通过 hermes_cli.gateway.run_gateway() 启动
            # hermes_cli.gateway 没有 __main__.py，不能用 python -m 直接运行
            # 需要用 -c 调用 run_gateway() 函数
            python_path = sys.executable
            gateway_cmd = [
                python_path, "-c",
                "import sys; sys.path.insert(0, '{}'); from hermes_cli.gateway import run_gateway; run_gateway()".format(
                    agent_dir.replace("'", "\\'")
                ),
            ]

            _gateway_process = subprocess.Popen(
                gateway_cmd,
                cwd=agent_dir,
                env={**os.environ, "PYTHONPATH": agent_dir},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # 短暂等待检测是否立即崩溃
            import time as _time
            _time.sleep(0.5)
            if _gateway_process.poll() is not None:
                stderr_out = ""
                if _gateway_process.stderr:
                    stderr_out = _gateway_process.stderr.read()[:500]
                _gateway_process = None
                _json_response(self, 500, {
                    "error": f"Gateway exited immediately. {stderr_out}".strip(),
                })
                return

            _json_response(self, 200, {
                "status": "started",
                "pid": _gateway_process.pid,
            })

            # 启动线程异步消费 Gateway stdout/stderr，防止管道死锁
            def _consume_gateway_output():
                proc = _gateway_process
                if not proc:
                    return
                for stream, tag in [(proc.stdout, "stdout"), (proc.stderr, "stderr")]:
                    if not stream:
                        continue
                    def _drain(s=stream, t=tag):
                        for line in s:
                            sys.stderr.write(f"[gateway] {line}")
                    Thread(target=_drain, daemon=True).start()
            _consume_gateway_output()

        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {
                "error": f"Failed to start gateway: {e}",
            })

    def _handle_gateway_stop(self):
        """停止 hermes Gateway 进程。"""
        global _gateway_process

        if _gateway_process is None or _gateway_process.poll() is not None:
            _gateway_process = None
            _json_response(self, 200, {"status": "not_running"})
            return

        try:
            pid = _gateway_process.pid
            _gateway_process.terminate()
            try:
                _gateway_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _gateway_process.kill()
            _gateway_process = None
            _json_response(self, 200, {"status": "stopped", "pid": pid})
        except Exception as e:
            _json_response(self, 500, {"error": f"Failed to stop gateway: {e}"})

    def _handle_gateway_configure(self):
        """配置 Gateway 平台凭证。

        接收平台配置，写入 hermes 的 config.yaml。
        不修改 hermes 源码，只操作其配置文件。
        """
        try:
            body = _read_json_body(self)
            platform_id = body.get("platform")
            credentials = body.get("credentials", {})

            if not platform_id:
                _json_response(self, 400, {"error": "platform is required"})
                return

            _ensure_hermes_on_path()

            # 环境变量映射
            env_mapping = {
                "telegram": {"token": "TELEGRAM_BOT_TOKEN"},
                "discord":  {"token": "DISCORD_BOT_TOKEN"},
                "dingtalk": {"app_key": "DINGTALK_APP_KEY", "app_secret": "DINGTALK_APP_SECRET"},
                "feishu":   {"app_id": "FEISHU_APP_ID", "app_secret": "FEISHU_APP_SECRET"},
                "weixin":   {"token": "WEIXIN_TOKEN", "account_id": "WEIXIN_ACCOUNT_ID", "app_id": "WEIXIN_APP_ID", "app_secret": "WEIXIN_APP_SECRET"},
                "wecom":    {"bot_id": "WECOM_BOT_ID", "bot_secret": "WECOM_BOT_SECRET"},
                "slack":    {"token": "SLACK_BOT_TOKEN", "app_token": "SLACK_APP_TOKEN"},
            }

            mapping = env_mapping.get(platform_id, {})
            env_updates = {}
            for cred_key, env_key in mapping.items():
                if cred_key in credentials:
                    env_updates[env_key] = credentials[cred_key]

            # 同时写入 hermes 的 .env 文件
            if env_updates:
                try:
                    from pathlib import Path
                    hermes_home = Path.home() / ".qeeclaw_hermes"
                    hermes_home.mkdir(parents=True, exist_ok=True)
                    env_file = hermes_home / ".env"
                    existing = {}
                    if env_file.exists():
                        for line in env_file.read_text().splitlines():
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, _, v = line.partition("=")
                                existing[k.strip()] = v.strip()

                    existing.update(env_updates)
                    lines = [f"{k}={v}" for k, v in existing.items()]
                    env_file.write_text("\n".join(lines) + "\n")

                    # 也设置到当前进程环境
                    for k, v in env_updates.items():
                        os.environ[k] = v

                except Exception as e:
                    _json_response(self, 500, {"error": f"Failed to write config: {e}"})
                    return

            _json_response(self, 200, {
                "status": "configured",
                "platform": platform_id,
                "envVarsSet": list(env_updates.keys()),
            })

        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # =====================================================================
    # Phase 2: Memory / Skills / Tools / Cron 新增接口
    # =====================================================================

    # ----- Memory /memory/* (v2 路由，干净路径别名) -----

    def _handle_memory_store_v2(self):
        """POST /memory/store — 存入记忆。"""
        try:
            from memory_store import store_memory
            body = _read_json_body(self)
            entry = store_memory(
                content=body.get("content", ""),
                category=body.get("category", "other"),
                importance=body.get("importance", 0.5),
                agent_id=body.get("agent_profile") or body.get("agent_id"),
                runtime_type=body.get("runtime_type", "openclaw"),
                source_session=body.get("source_session"),
            )
            _json_response(self, 200, {"success": True, "entry": entry})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_memory_search_v2(self):
        """POST /memory/search — 搜索记忆。"""
        try:
            from memory_store import search_memory
            body = _read_json_body(self)
            scope = {}
            agent_profile = body.get("agent_profile")
            if agent_profile:
                scope["agent_id"] = agent_profile
            for key in ("team_id", "runtime_type", "device_id"):
                val = body.get(key)
                if val is not None:
                    scope[key] = val
            results = search_memory(
                query=body.get("query", ""),
                limit=body.get("limit", body.get("top_k", 5)),
                threshold=body.get("threshold", 0.0),
                scope=scope,
            )
            _json_response(self, 200, {"success": True, "results": results})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_memory_stats_v2(self):
        """GET /memory/stats — 记忆统计。"""
        try:
            from memory_store import get_memory_stats
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            scope = {}
            agent_profile = params.get("agent_profile")
            if agent_profile:
                scope["agent_id"] = agent_profile[0]
            stats = get_memory_stats(scope=scope)
            _json_response(self, 200, {"success": True, **stats})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_memory_clear_v2(self):
        """POST /memory/clear — 清除指定 agent_profile 的全部记忆。"""
        try:
            from memory_store import clear_agent_memory
            body = _read_json_body(self)
            agent_profile = body.get("agent_profile")
            if not agent_profile:
                _json_response(self, 400, {"error": "agent_profile is required"})
                return
            cleared = clear_agent_memory(agent_profile)
            _json_response(self, 200, {"success": True, "cleared_count": cleared})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # ----- Tools /tools/* -----

    def _handle_tools_list(self):
        """GET /tools — 列出所有工具集，标注当前 profile 的启用状态。"""
        try:
            _ensure_hermes_on_path()
            from toolsets import get_all_toolsets, resolve_toolset
            from session_manager import get_session_manager

            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            profile_name = (params.get("agent_profile") or [None])[0]

            sm = get_session_manager()
            profile = sm.get_profile(profile_name) if profile_name else None

            all_toolsets = get_all_toolsets()
            result = []
            for ts_name, ts_def in all_toolsets.items():
                tools = resolve_toolset(ts_name)
                entry = {
                    "name": ts_name,
                    "description": ts_def.get("description", ""),
                    "tools": sorted(tools),
                    "tool_count": len(tools),
                }
                # 标注 profile 级别启用状态
                if profile:
                    if profile.enabled_toolsets is not None:
                        entry["enabled"] = ts_name in profile.enabled_toolsets
                    elif profile.disabled_toolsets is not None:
                        entry["enabled"] = ts_name not in profile.disabled_toolsets
                    else:
                        entry["enabled"] = True
                result.append(entry)

            result.sort(key=lambda x: x["name"])
            _json_response(self, 200, {
                "success": True,
                "toolsets": result,
                "count": len(result),
                "agent_profile": profile_name,
            })
        except ImportError:
            _json_response(self, 200, {
                "success": True,
                "toolsets": [],
                "count": 0,
                "message": "hermes-agent not available, toolsets unavailable",
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_tools_update(self):
        """PUT /tools — 更新 profile 的 enabled/disabled toolsets 配置。"""
        try:
            from session_manager import get_session_manager
            body = _read_json_body(self)
            agent_profile = body.get("agent_profile")
            if not agent_profile:
                _json_response(self, 400, {"error": "agent_profile is required"})
                return

            sm = get_session_manager()
            profile = sm.get_profile(agent_profile)
            if not profile:
                _json_response(self, 404, {"error": f"agent '{agent_profile}' not found"})
                return

            # 构建更新数据
            profile_data = profile.to_dict()
            if "enabled" in body:
                profile_data["enabled_toolsets"] = body["enabled"]
                profile_data.pop("disabled_toolsets", None)
            elif "disabled" in body:
                profile_data["disabled_toolsets"] = body["disabled"]
                profile_data.pop("enabled_toolsets", None)
            else:
                _json_response(self, 400, {"error": "Either 'enabled' or 'disabled' toolset list is required"})
                return

            sm.create_profile(profile_data)
            _json_response(self, 200, {
                "success": True,
                "message": f"Toolsets updated for agent '{agent_profile}'",
                "enabled_toolsets": profile_data.get("enabled_toolsets"),
                "disabled_toolsets": profile_data.get("disabled_toolsets"),
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # ----- Skills /skills/* (Bridge 原生文件操作) -----

    def _handle_skills_list(self):
        """GET /skills — 列出指定 profile 的技能。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            profile_name = (params.get("agent_profile") or ["default"])[0]

            pool = get_agent_pool()
            profile_home = pool._ensure_profile_home(profile_name)
            skills_dir = os.path.join(profile_home, "skills")

            skills = _list_skills_from_dir(skills_dir)
            _json_response(self, 200, {
                "success": True,
                "skills": skills,
                "count": len(skills),
                "agent_profile": profile_name,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_skill_get(self):
        """GET /skills/{name} — 查看技能内容。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            parts = _path.strip("/").split("/")
            skill_name = parts[1] if len(parts) >= 2 else None
            if not skill_name:
                _json_response(self, 400, {"error": "skill name is required"})
                return

            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            profile_name = (params.get("agent_profile") or ["default"])[0]

            pool = get_agent_pool()
            profile_home = pool._ensure_profile_home(profile_name)
            skills_dir = os.path.join(profile_home, "skills")

            result = _read_skill_from_dir(skills_dir, skill_name)
            if result is None:
                _json_response(self, 404, {"error": f"skill '{skill_name}' not found"})
                return
            _json_response(self, 200, {"success": True, **result})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_skill_install(self):
        """POST /skills/install — 创建/安装技能。"""
        try:
            body = _read_json_body(self)
            name = body.get("name") or body.get("skill_name")
            content = body.get("content")
            profile_name = body.get("agent_profile", "default")

            if not name:
                _json_response(self, 400, {"error": "name is required"})
                return
            if not content:
                _json_response(self, 400, {"error": "content (SKILL.md text) is required"})
                return

            pool = get_agent_pool()
            profile_home = pool._ensure_profile_home(profile_name)
            skills_dir = os.path.join(profile_home, "skills")
            category = body.get("category")

            # 构建目标目录
            if category:
                skill_dir = os.path.join(skills_dir, category, name)
            else:
                skill_dir = os.path.join(skills_dir, name)

            if os.path.isdir(skill_dir) and os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
                _json_response(self, 409, {"error": f"skill '{name}' already exists"})
                return

            os.makedirs(skill_dir, exist_ok=True)
            skill_md_path = os.path.join(skill_dir, "SKILL.md")
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(content)

            _json_response(self, 200, {
                "success": True,
                "message": f"Skill '{name}' installed.",
                "path": skill_dir,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_skill_uninstall(self):
        """POST /skills/uninstall — 删除/卸载技能。"""
        try:
            import shutil
            body = _read_json_body(self)
            name = body.get("name") or body.get("skill_name")
            profile_name = body.get("agent_profile", "default")

            if not name:
                _json_response(self, 400, {"error": "name is required"})
                return

            pool = get_agent_pool()
            profile_home = pool._ensure_profile_home(profile_name)
            skills_dir = os.path.join(profile_home, "skills")

            # 在 skills_dir 中搜索匹配的技能
            skill_dir = _find_skill_dir(skills_dir, name)
            if not skill_dir:
                _json_response(self, 404, {"error": f"skill '{name}' not found"})
                return

            shutil.rmtree(skill_dir)

            # 清理空的 category 目录
            parent = os.path.dirname(skill_dir)
            if parent != skills_dir and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)

            _json_response(self, 200, {
                "success": True,
                "message": f"Skill '{name}' uninstalled.",
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # ----- Cron /cron/* (Bridge 原生 JSON 存储) -----

    def _handle_cron_list(self):
        """GET /cron — 列出指定 profile 的定时任务。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            profile_name = (params.get("agent_profile") or ["default"])[0]

            jobs = _load_cron_jobs_for_profile(profile_name)
            _json_response(self, 200, {
                "success": True,
                "jobs": jobs,
                "count": len(jobs),
                "agent_profile": profile_name,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_cron_create(self):
        """POST /cron — 创建定时任务。"""
        try:
            body = _read_json_body(self)
            profile_name = body.get("agent_profile", "default")
            prompt = body.get("prompt")
            schedule = body.get("schedule")
            name = body.get("name")

            if not schedule:
                _json_response(self, 400, {"error": "schedule is required"})
                return
            if not prompt:
                _json_response(self, 400, {"error": "prompt is required"})
                return

            import uuid as _uuid
            job = {
                "id": f"cron_{_uuid.uuid4().hex[:12]}",
                "name": name or prompt[:50],
                "prompt": prompt,
                "schedule": schedule,
                "agent_profile": profile_name,
                "enabled": True,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "next_run_at": None,
            }

            jobs = _load_cron_jobs_for_profile(profile_name)
            jobs.append(job)
            _save_cron_jobs_for_profile(profile_name, jobs)

            _json_response(self, 200, {
                "success": True,
                "job": job,
                "message": f"Cron job '{job['name']}' created.",
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_cron_delete(self):
        """DELETE /cron/{job_id} — 删除定时任务。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            parts = _path.strip("/").split("/")
            job_id = parts[1] if len(parts) >= 2 else None
            if not job_id:
                _json_response(self, 400, {"error": "job_id is required"})
                return

            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            profile_name = (params.get("agent_profile") or ["default"])[0]

            jobs = _load_cron_jobs_for_profile(profile_name)
            original_count = len(jobs)
            jobs = [j for j in jobs if j.get("id") != job_id]

            if len(jobs) == original_count:
                _json_response(self, 404, {"error": f"job '{job_id}' not found"})
                return

            _save_cron_jobs_for_profile(profile_name, jobs)
            _json_response(self, 200, {
                "success": True,
                "message": f"Cron job '{job_id}' removed.",
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # ----- Agent Templates (/agent_config/*) -----

    def _handle_agent_config_default(self):
        """GET /agent_config/default — 列出默认智体模板。"""
        try:
            from session_manager import get_session_manager, _BUILTIN_PROFILES
            sm = get_session_manager()
            templates = []
            idx = 0
            for name, profile in _BUILTIN_PROFILES.items():
                idx += 1
                templates.append({
                    "id": idx,
                    "code": name,
                    "name": profile.display_name,
                    "description": profile.system_prompt[:200] if profile.system_prompt else None,
                    "avatar": None,
                    "allowed_tools": ["web_search", "memory"],
                })
            _json_response(self, 200, templates)
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _handle_agent_config_get(self):
        """GET /agent_config/{code} — 获取指定模板。"""
        try:
            from session_manager import get_session_manager, _BUILTIN_PROFILES
            _path = urllib.parse.urlparse(self.path).path
            code = urllib.parse.unquote(_path.split("/")[-1])

            sm = get_session_manager()
            profile = sm.get_profile(code)
            if not profile:
                _json_response(self, 404, {"error": f"template '{code}' not found"})
                return
            template = {
                "id": _get_agent_id(profile.name),
                "code": profile.name,
                "name": profile.display_name,
                "description": profile.system_prompt[:200] if profile.system_prompt else None,
                "avatar": (profile.metadata or {}).get("avatar"),
                "allowed_tools": ["web_search", "memory"],
            }
            _json_response(self, 200, template)
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    # ----- IAM / Users (/api/users/*) -----

    def _handle_iam_get_profile(self):
        """GET /api/users/me — 返回本地用户 profile。"""
        try:
            profile = _load_user_profile()
            _platform_json_response(self, 200, profile)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_iam_update_profile(self):
        """PUT /api/users/me — 更新用户 profile。"""
        try:
            body = _read_json_body(self)
            profile = _load_user_profile()
            if "full_name" in body:
                profile["full_name"] = body["full_name"]
            if "email" in body:
                profile["email"] = body["email"]
            if "phone" in body:
                profile["phone"] = body["phone"]
            _save_user_profile(profile)
            _platform_json_response(self, 200, profile)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_iam_update_preference(self):
        """PUT /api/users/me/preference — 更新偏好（preferred_model）。"""
        try:
            body = _read_json_body(self)
            preferred_model = body.get("preferred_model", "")
            profile = _load_user_profile()
            if "preference" not in profile:
                profile["preference"] = {}
            profile["preference"]["preferred_model"] = preferred_model
            _save_user_profile(profile)
            _platform_json_response(self, 200, {
                "preferred_model": preferred_model,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_iam_list_users(self):
        """GET /api/users — 用户列表（边缘设备返回单用户）。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            page = int((params.get("page") or ["1"])[0])
            page_size = int((params.get("page_size") or ["20"])[0])
            profile = _load_user_profile()
            _platform_json_response(self, 200, {
                "total": 1,
                "page": page,
                "page_size": page_size,
                "items": [profile],
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_iam_list_products(self):
        """GET /api/users/products — 产品列表（边缘设备返回空）。"""
        try:
            _platform_json_response(self, 200, [])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Models (/api/platform/models/*) -----

    def _handle_models_list(self):
        """GET /api/platform/models — 列出可用模型。"""
        try:
            models = _discover_models()
            _platform_json_response(self, 200, models)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_providers(self):
        """GET /api/platform/models/providers — 模型供应商概览。"""
        try:
            models = _discover_models()
            base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "")
            provider = _infer_provider_from_url(base_url)
            preferred = _get_preferred_model()
            model_names = [m["model_name"] for m in models]
            summary = {
                "provider_name": provider,
                "configured": True,
                "provider_status": "active",
                "visible_count": len(models),
                "hidden_count": 0,
                "disabled_count": 0,
                "models": model_names,
                "preferred_model_supported": preferred in model_names,
                "is_default_route_provider": True,
                "default_route_model": preferred,
                "default_route_provider_model_id": preferred,
            }
            _platform_json_response(self, 200, [summary])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_runtimes(self):
        """GET /api/platform/models/runtimes — 运行时列表。"""
        try:
            runtime = {
                "runtime_type": "openclaw",
                "runtime_label": "OpenClaw",
                "runtime_status": "active",
                "runtime_stage": "production",
                "is_default": True,
                "adapter_registered": True,
                "bridge_registered": True,
                "online_team_count": 1,
                "supports_im_relay": True,
                "supports_device_bridge": True,
                "supports_managed_download": False,
                "notes": "Local Hermes Bridge runtime",
            }
            _platform_json_response(self, 200, [runtime])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_resolve(self):
        """GET /api/platform/models/resolve?model_name=X — 解析模型。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            model_name = (params.get("model_name") or [""])[0]
            if not model_name:
                _platform_json_response(self, 400, None, "model_name is required")
                return

            models = _discover_models()
            selected = None
            for m in models:
                if m["model_name"] == model_name:
                    selected = m
                    break
            if not selected:
                selected = models[0] if models else None

            if not selected:
                _platform_json_response(self, 404, None, f"no models available to resolve '{model_name}'")
                return

            base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "")
            provider = _infer_provider_from_url(base_url)
            _platform_json_response(self, 200, {
                "requested_model": model_name,
                "resolved_model": selected["model_name"],
                "provider_name": provider,
                "provider_model_id": selected["provider_model_id"],
                "candidate_count": len(models),
                "selected": selected,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_route_get(self):
        """GET /api/platform/models/route — 获取当前模型路由。"""
        try:
            models = _discover_models()
            preferred = _get_preferred_model()
            base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "")
            provider = _infer_provider_from_url(base_url)

            selected = None
            for m in models:
                if m["model_name"] == preferred:
                    selected = m
                    break
            if not selected and models:
                selected = models[0]

            _platform_json_response(self, 200, {
                "preferred_model": preferred,
                "preferred_model_available": selected is not None,
                "resolved_model": selected["model_name"] if selected else None,
                "resolved_provider_name": provider,
                "resolved_provider_model_id": selected["provider_model_id"] if selected else None,
                "candidate_count": len(models),
                "configured_provider_count": 1,
                "available_model_count": len(models),
                "resolution_reason": "preferred_model_match" if selected else "fallback",
                "selected": selected,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_route_set(self):
        """PUT /api/platform/models/route — 设置默认模型路由。"""
        try:
            body = _read_json_body(self)
            preferred_model = body.get("preferred_model", "")
            if not preferred_model:
                _platform_json_response(self, 400, None, "preferred_model is required")
                return

            # 保存到用户偏好
            profile = _load_user_profile()
            if "preference" not in profile:
                profile["preference"] = {}
            profile["preference"]["preferred_model"] = preferred_model
            _save_user_profile(profile)

            # 返回更新后的路由 profile
            models = _discover_models()
            base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "")
            provider = _infer_provider_from_url(base_url)
            selected = None
            for m in models:
                if m["model_name"] == preferred_model:
                    selected = m
                    break
            if not selected and models:
                selected = models[0]

            _platform_json_response(self, 200, {
                "preferred_model": preferred_model,
                "preferred_model_available": selected is not None,
                "resolved_model": selected["model_name"] if selected else None,
                "resolved_provider_name": provider,
                "resolved_provider_model_id": selected["provider_model_id"] if selected else None,
                "candidate_count": len(models),
                "configured_provider_count": 1,
                "available_model_count": len(models),
                "resolution_reason": "preferred_model_match" if selected else "fallback",
                "selected": selected,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_usage(self):
        """GET /api/platform/models/usage — 用量统计（边缘设备 stub）。"""
        try:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _platform_json_response(self, 200, {
                "window_days": 30,
                "period_start": now,
                "period_end": now,
                "attribution_mode": "local",
                "record_count": 0,
                "total_calls": 0,
                "total_input_chars": 0,
                "total_output_chars": 0,
                "total_duration_seconds": 0,
                "last_used_at": None,
                "breakdown": [],
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_cost(self):
        """GET /api/platform/models/cost — 费用统计（边缘设备 stub）。"""
        try:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _platform_json_response(self, 200, {
                "window_days": 30,
                "period_start": now,
                "period_end": now,
                "attribution_mode": "local",
                "record_count": 0,
                "total_amount": 0,
                "primary_currency": "CNY",
                "currency_breakdown": [],
                "last_billed_at": None,
                "breakdown": [],
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_models_quota(self):
        """GET /api/platform/models/quota — 配额查询（边缘设备无限额）。"""
        try:
            _platform_json_response(self, 200, {
                "wallet_balance": 0,
                "currency": "CNY",
                "daily_limit": None,
                "daily_spent": 0,
                "daily_remaining": None,
                "daily_unlimited": True,
                "monthly_limit": None,
                "monthly_spent": 0,
                "monthly_remaining": None,
                "monthly_unlimited": True,
                "updated_time": None,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Conversations (/api/platform/conversations/*) -----

    def _session_to_group(self, session) -> dict:
        """将 Session 转为 ConversationGroup 格式。"""
        from session_manager import get_session_manager
        sm = get_session_manager()
        profile = sm.get_profile(session.agent_profile)
        room_name = profile.display_name if profile else session.agent_profile
        return {
            "room_id": session.session_id,
            "room_name": room_name,
            "last_active": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(session.updated_at)),
            "msg_count": len(session.messages),
            "member_count": 2,
        }

    def _message_to_history(self, msg: dict, idx: int, session) -> dict:
        """将 session message 转为 ConversationHistoryMessage 格式。"""
        role = msg.get("role", "user")
        return {
            "id": idx,
            "sender_id": 1 if role == "user" else None,
            "agent_id": _get_agent_id(session.agent_profile) if role == "assistant" else None,
            "channel_id": None,
            "direction": "user_to_agent" if role == "user" else "agent_to_user",
            "content": msg.get("content", ""),
            "created_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(session.updated_at)),
        }

    def _handle_conversations_home(self):
        """GET /api/platform/conversations — 会话首页。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            group_limit = int((params.get("group_limit") or ["10"])[0])
            history_limit = int((params.get("history_limit") or ["20"])[0])

            sessions_data = sm.list_sessions()
            groups = []
            all_messages = []
            for sd in sessions_data[:group_limit]:
                session = sm.get_session(sd["session_id"])
                if session:
                    groups.append(self._session_to_group(session))
                    for idx, msg in enumerate(session.messages):
                        all_messages.append(self._message_to_history(msg, idx, session))

            # 按时间倒序取最近 history_limit 条
            all_messages.sort(key=lambda m: m.get("id", 0), reverse=True)
            history = all_messages[:history_limit]

            total_msgs = sum(sd.get("turn_count", 0) * 2 for sd in sessions_data)
            stats = {
                "group_count": len(sessions_data),
                "msg_count": total_msgs,
                "entity_count": 0,
                "history_count": len(all_messages),
            }
            _platform_json_response(self, 200, {
                "stats": stats,
                "groups": groups,
                "history": history,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_conversations_stats(self):
        """GET /api/platform/conversations/stats — 对话统计。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            sessions_data = sm.list_sessions()
            total_msgs = sum(sd.get("turn_count", 0) * 2 for sd in sessions_data)
            _platform_json_response(self, 200, {
                "group_count": len(sessions_data),
                "msg_count": total_msgs,
                "entity_count": 0,
                "history_count": total_msgs,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_conversations_groups(self):
        """GET /api/platform/conversations/groups — 会话分组列表。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            limit = int((params.get("limit") or ["50"])[0])

            sessions_data = sm.list_sessions()
            groups = []
            for sd in sessions_data[:limit]:
                session = sm.get_session(sd["session_id"])
                if session:
                    groups.append(self._session_to_group(session))
            _platform_json_response(self, 200, groups)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_conversations_group_messages(self):
        """GET /api/platform/conversations/groups/{roomId}/messages — 分组消息。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            _path = urllib.parse.urlparse(self.path).path
            # 路径: /api/platform/conversations/groups/{roomId}/messages
            parts = _path.strip("/").split("/")
            # parts = ['api', 'platform', 'conversations', 'groups', '{roomId}', 'messages']
            room_id = urllib.parse.unquote(parts[4]) if len(parts) > 4 else ""

            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            limit = int((params.get("limit") or ["50"])[0])

            session = sm.get_session(room_id)
            if not session:
                _platform_json_response(self, 200, [])
                return

            messages = session.get_messages()
            result = []
            for idx, msg in enumerate(messages[-limit:]):
                role = msg.get("role", "user")
                result.append({
                    "id": idx,
                    "sender_name": "用户" if role == "user" else session.agent_profile,
                    "sender_role": role,
                    "msg_type": "text",
                    "content": msg.get("content", ""),
                    "created_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(session.updated_at)),
                    "entities": [],
                })
            _platform_json_response(self, 200, result)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_conversations_history(self):
        """GET /api/platform/conversations/history — 跨会话消息历史。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            limit = int((params.get("limit") or ["50"])[0])

            sessions_data = sm.list_sessions()
            all_messages = []
            msg_id = 0
            for sd in sessions_data:
                session = sm.get_session(sd["session_id"])
                if not session:
                    continue
                for msg in session.messages:
                    msg_id += 1
                    all_messages.append(self._message_to_history(msg, msg_id, session))
            # 最近的排前面
            all_messages.reverse()
            _platform_json_response(self, 200, all_messages[:limit])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_conversations_send(self):
        """POST /api/platform/conversations/messages — 发送消息。"""
        try:
            from session_manager import get_session_manager
            sm = get_session_manager()
            body = _read_json_body(self)
            content = body.get("content", "")
            agent_id = body.get("agent_id")
            direction = body.get("direction", "user_to_agent")

            # 尝试找到对应的 session 或创建新的
            # 如果有 agent_id，找对应 profile
            profile_name = "default"
            if agent_id:
                profile = _find_profile_by_id(sm, int(agent_id))
                if profile:
                    profile_name = profile.name

            # 获取或创建 session
            sessions = sm.list_sessions(agent_profile=profile_name)
            if sessions:
                session = sm.get_session(sessions[0]["session_id"])
            else:
                session = sm.create_session(agent_profile=profile_name)

            if not session:
                session = sm.create_session(agent_profile=profile_name)

            role = "user" if direction == "user_to_agent" else "assistant"
            session.add_message(role, content)

            msg_id = len(session.messages)
            result = {
                "id": msg_id,
                "sender_id": 1 if role == "user" else None,
                "agent_id": _get_agent_id(profile_name) if role == "assistant" else None,
                "channel_id": None,
                "direction": direction,
                "content": content,
                "created_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _platform_json_response(self, 200, result)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Billing (/api/billing/*) — 边缘设备 stub -----

    def _handle_billing_wallet(self):
        """GET /api/billing/wallet — 钱包余额（stub）。"""
        try:
            _platform_json_response(self, 200, {
                "balance": 0,
                "currency": "CNY",
                "total_spent": 0,
                "total_recharge": 0,
                "current_month_spent": 0,
                "updated_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_billing_records(self):
        """GET /api/billing/records — 消费记录（stub 空列表）。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            page = int((params.get("page") or ["1"])[0])
            page_size = int((params.get("page_size") or ["20"])[0])
            _platform_json_response(self, 200, {
                "total": 0,
                "page": page,
                "page_size": page_size,
                "items": [],
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_billing_summary(self):
        """GET /api/billing/summary — 消费汇总（stub）。"""
        try:
            _platform_json_response(self, 200, {
                "total_spent": 0,
                "total_recharge": 0,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Channels (/api/platform/channels/*) -----

    def _make_channel_item(self, key, name, group, kernel, configured=False, enabled=False):
        """构建单个渠道配置项。"""
        return {
            "channel_key": key,
            "channel_name": name,
            "channel_group": group,
            "channel_kernel": kernel,
            "configured": configured,
            "enabled": enabled,
            "binding_enabled": False,
            "callback_url": "",
            "risk_level": "low",
            "updated_time": None,
        }

    def _handle_channels_overview(self):
        """GET /api/platform/channels — 渠道总览。"""
        try:
            # 检查 OpenClaw/微信状态
            openclaw_configured = False
            openclaw_enabled = False
            try:
                # 尝试获取 gateway 状态
                _ensure_hermes_on_path()
                from gateway.gateway_manager import GatewayManager
                gm = GatewayManager()
                openclaw_configured = True
                openclaw_enabled = gm.is_running() if hasattr(gm, "is_running") else False
            except Exception:
                pass

            items = [
                self._make_channel_item(
                    "wechat_work", "企业微信", "enterprise_collab", "wechat_work",
                ),
                self._make_channel_item(
                    "feishu", "飞书", "enterprise_collab", "feishu",
                ),
                self._make_channel_item(
                    "wechat_personal_plugin", "微信个人号(插件)", "personal_reach", "wechat_work_plugin",
                ),
                self._make_channel_item(
                    "wechat_personal_openclaw", "微信个人号(OpenClaw)", "personal_reach",
                    "openclaw_wechat_plugin",
                    configured=openclaw_configured,
                    enabled=openclaw_enabled,
                ),
            ]
            configured_count = sum(1 for i in items if i["configured"])
            active_count = sum(1 for i in items if i["enabled"])
            _platform_json_response(self, 200, {
                "supported_count": len(items),
                "configured_count": configured_count,
                "active_count": active_count,
                "items": items,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_wechat_work_config(self):
        """GET /api/platform/channels/wechat-work/config — 企业微信配置（stub）。"""
        try:
            config = self._make_channel_item(
                "wechat_work", "企业微信", "enterprise_collab", "wechat_work",
            )
            config.update({
                "corp_id": "",
                "agent_id": "",
                "secret": "",
                "secret_configured": False,
                "verify_token": "",
                "aes_key": "",
            })
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_wechat_work_config_update(self):
        """POST /api/platform/channels/wechat-work/config — 更新企业微信配置（stub）。"""
        try:
            body = _read_json_body(self)
            config = self._make_channel_item(
                "wechat_work", "企业微信", "enterprise_collab", "wechat_work",
                configured=True,
            )
            config.update({
                "corp_id": body.get("corp_id", ""),
                "agent_id": body.get("agent_id", ""),
                "secret": "",
                "secret_configured": bool(body.get("secret")),
                "verify_token": "",
                "aes_key": "",
            })
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_feishu_config(self):
        """GET /api/platform/channels/feishu/config — 飞书配置（stub）。"""
        try:
            config = self._make_channel_item(
                "feishu", "飞书", "enterprise_collab", "feishu",
            )
            config.update({
                "app_id": "",
                "app_secret": "",
                "verification_token": "",
                "encrypt_key": "",
                "secret_configured": False,
            })
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_feishu_config_update(self):
        """POST /api/platform/channels/feishu/config — 更新飞书配置（stub）。"""
        try:
            body = _read_json_body(self)
            config = self._make_channel_item(
                "feishu", "飞书", "enterprise_collab", "feishu",
                configured=True,
            )
            config.update({
                "app_id": body.get("app_id", ""),
                "app_secret": "",
                "verification_token": "",
                "encrypt_key": "",
                "secret_configured": bool(body.get("app_secret")),
            })
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_wechat_personal_plugin_config(self):
        """GET /api/platform/channels/wechat-personal-plugin/config — 个人微信插件配置（stub）。"""
        try:
            config = self._make_channel_item(
                "wechat_personal_plugin", "微信个人号(插件)", "personal_reach", "wechat_work_plugin",
            )
            config.update({
                "display_name": "微信个人号(插件)",
                "kernel_source": "unconfigured",
                "kernel_configured": False,
                "kernel_isolated": False,
                "kernel_corp_id": "",
                "kernel_agent_id": "",
                "kernel_secret": "",
                "kernel_secret_configured": False,
                "kernel_verify_token": "",
                "kernel_aes_key": "",
                "effective_kernel_corp_id": "",
                "effective_kernel_agent_id": "",
                "effective_kernel_verify_token": "",
                "effective_kernel_aes_key": "",
                "setup_status": "planned",
                "assistant_name": "",
                "welcome_message": "",
                "capability_stage": "planned",
            })
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_wechat_personal_plugin_config_update(self):
        """POST /api/platform/channels/wechat-personal-plugin/config — 更新（stub）。"""
        try:
            body = _read_json_body(self)
            config = self._make_channel_item(
                "wechat_personal_plugin", "微信个人号(插件)", "personal_reach", "wechat_work_plugin",
                configured=True,
            )
            config.update({
                "display_name": body.get("display_name", "微信个人号(插件)"),
                "kernel_source": "independent",
                "kernel_configured": False,
                "kernel_isolated": False,
                "kernel_corp_id": body.get("kernel_corp_id", ""),
                "kernel_agent_id": body.get("kernel_agent_id", ""),
                "kernel_secret": "",
                "kernel_secret_configured": False,
                "kernel_verify_token": "",
                "kernel_aes_key": "",
                "effective_kernel_corp_id": body.get("kernel_corp_id", ""),
                "effective_kernel_agent_id": body.get("kernel_agent_id", ""),
                "effective_kernel_verify_token": "",
                "effective_kernel_aes_key": "",
                "setup_status": "planned",
                "assistant_name": body.get("assistant_name", ""),
                "welcome_message": body.get("welcome_message", ""),
                "capability_stage": "planned",
            })
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_wechat_personal_openclaw_config(self):
        """GET /api/platform/channels/wechat-personal-openclaw/config — OpenClaw 微信配置。"""
        try:
            gateway_online = False
            try:
                _ensure_hermes_on_path()
                from gateway.gateway_manager import GatewayManager
                gm = GatewayManager()
                gateway_online = gm.is_running() if hasattr(gm, "is_running") else False
            except Exception:
                pass

            config = self._make_channel_item(
                "wechat_personal_openclaw", "微信个人号(OpenClaw)", "personal_reach",
                "openclaw_wechat_plugin",
                configured=True,
                enabled=gateway_online,
            )
            config.update({
                "display_name": "微信个人号(OpenClaw)",
                "channel_mode": "official_openclaw_plugin",
                "setup_status": "ready" if gateway_online else "waiting_gateway",
                "manual_cli_required": False,
                "preinstall_supported": True,
                "qr_supported": True,
                "gateway_online": gateway_online,
                "official_plugin_available": None,
                "install_hint": "请通过 /wechat/qr-login 发起扫码登录",
                "capability_stage": "production",
            })
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_bindings_list(self):
        """GET /api/platform/channels/bindings — 绑定列表（stub 空）。"""
        try:
            _platform_json_response(self, 200, {
                "items": [],
                "total": 0,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_binding_create(self):
        """POST /api/platform/channels/bindings/create — 创建绑定（stub）。"""
        try:
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            binding = {
                "id": int(time.time()),
                "team_id": body.get("team_id", 1),
                "channel_key": body.get("channel_key", "wechat_personal_plugin"),
                "binding_type": body.get("binding_type", ""),
                "binding_target_id": body.get("binding_target_id", ""),
                "binding_target_name": body.get("binding_target_name"),
                "binding_code": f"bind_{int(time.time())}",
                "code_expires_at": None,
                "status": "pending",
                "created_by_user_id": 1,
                "bound_by_user_id": None,
                "binding_enabled_snapshot": True,
                "notes": body.get("notes"),
                "bound_at": None,
                "created_time": now,
                "updated_time": now,
                "identity": None,
            }
            _platform_json_response(self, 200, binding)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # =====================================================================
    # Phase 2: 剩余 SDK 模块全覆盖
    # =====================================================================

    # ----- Step 1: Channels 补全 -----

    def _handle_channel_binding_disable(self):
        """POST /api/platform/channels/bindings/disable — 禁用绑定。"""
        try:
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            binding = {
                "id": body.get("binding_id", 0),
                "team_id": 1,
                "channel_key": "wechat_personal_plugin",
                "binding_type": "user",
                "binding_target_id": "",
                "binding_target_name": None,
                "binding_code": "",
                "code_expires_at": None,
                "status": "disabled",
                "created_by_user_id": 1,
                "bound_by_user_id": None,
                "binding_enabled_snapshot": False,
                "notes": None,
                "bound_at": None,
                "created_time": now,
                "updated_time": now,
                "identity": None,
            }
            _platform_json_response(self, 200, binding)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_binding_regenerate_code(self):
        """POST /api/platform/channels/bindings/regenerate-code — 重新生成绑定码。"""
        try:
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            expires_hours = body.get("expires_in_hours", 72)
            binding = {
                "id": body.get("binding_id", 0),
                "team_id": 1,
                "channel_key": "wechat_personal_plugin",
                "binding_type": "user",
                "binding_target_id": "",
                "binding_target_name": None,
                "binding_code": f"bind_{uuid.uuid4().hex[:12]}",
                "code_expires_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() + expires_hours * 3600),
                ),
                "status": "pending",
                "created_by_user_id": 1,
                "bound_by_user_id": None,
                "binding_enabled_snapshot": True,
                "notes": None,
                "bound_at": None,
                "created_time": now,
                "updated_time": now,
                "identity": None,
            }
            _platform_json_response(self, 200, binding)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_openclaw_qr_start(self):
        """POST /api/platform/channels/wechat-personal-openclaw/qr/start — QR 扫码登录。"""
        try:
            _platform_json_response(self, 200, {
                "status": "waiting_scan",
                "message": "请使用微信扫描二维码",
                "qr_data_url": "",
                "qr_url": "",
                "session_id": f"qr_{uuid.uuid4().hex[:12]}",
                "account_id": "",
                "expires_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() + 300),
                ),
                "connected": False,
                "binding": None,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_channel_openclaw_qr_status(self):
        """GET /api/platform/channels/wechat-personal-openclaw/qr/status — QR 状态。"""
        try:
            _platform_json_response(self, 200, {
                "status": "waiting_scan",
                "message": "等待扫码",
                "qr_data_url": "",
                "qr_url": "",
                "session_id": "",
                "account_id": "",
                "expires_at": None,
                "connected": False,
                "binding": None,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 2: Tenant -----

    def _handle_tenant_context(self):
        """GET /api/users/me/context — 租户工作空间上下文。"""
        try:
            profile = _load_user_profile()
            teams = profile.get("teams", [{"id": 1, "name": "local", "is_personal": True, "owner_id": 1}])
            first_team = teams[0] if teams else {}
            data = {
                "id": profile.get("id", 1),
                "username": profile.get("username", "local-admin"),
                "role": profile.get("role", "ADMIN"),
                "is_enterprise_verified": profile.get("is_enterprise_verified", False),
                "default_team_id": first_team.get("id", 1),
                "default_team_name": first_team.get("name", "local"),
                "default_team_is_personal": first_team.get("is_personal", True),
                "teams": teams,
            }
            _platform_json_response(self, 200, data)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_company_verification_get(self):
        """GET /api/company/verification — 企业认证状态。"""
        try:
            _platform_json_response(self, 200, {
                "status": "none",
                "company_name": None,
                "tax_number": None,
                "address": None,
                "phone": None,
                "bank_name": None,
                "bank_account": None,
                "license_url": None,
                "rejection_reason": None,
                "updated_time": None,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_company_verification_submit(self):
        """POST /api/company/verification — 提交企业认证。"""
        try:
            _platform_json_response(self, 200, {
                "status": "pending",
                "company_name": None,
                "updated_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_company_verification_approve(self):
        """POST /api/company/verification/approve — 审批企业认证。"""
        try:
            _platform_json_response(self, 200, {
                "status": "approved",
                "company_name": "已认证企业",
                "updated_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 3: File / Documents -----

    def _handle_documents_list(self):
        """GET /api/documents — 列出本地文档。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            skip = int((params.get("skip") or ["0"])[0])
            limit = int((params.get("limit") or ["100"])[0])

            docs_dir = os.path.join(_HERMES_HOME, "documents")
            docs: List[Dict[str, Any]] = []
            if os.path.isdir(docs_dir):
                for idx, fname in enumerate(sorted(os.listdir(docs_dir))):
                    fpath = os.path.join(docs_dir, fname)
                    if os.path.isfile(fpath):
                        stat = os.stat(fpath)
                        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))
                        docs.append({
                            "id": idx + 1,
                            "document_title": fname,
                            "document_detail": None,
                            "sort_num": idx,
                            "labels": None,
                            "create_time": ts,
                            "update_time": ts,
                        })
            result = docs[skip:skip + limit]
            _platform_json_response(self, 200, result)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_document_get(self):
        """GET /api/documents/{id} — 获取单个文档。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            doc_id = int(_path.split("/")[-1])

            docs_dir = os.path.join(_HERMES_HOME, "documents")
            if os.path.isdir(docs_dir):
                files = sorted(os.listdir(docs_dir))
                idx = doc_id - 1
                if 0 <= idx < len(files):
                    fname = files[idx]
                    fpath = os.path.join(docs_dir, fname)
                    stat = os.stat(fpath)
                    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime))
                    detail = None
                    try:
                        if stat.st_size < 100000:
                            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                                detail = f.read()[:2000]
                    except Exception:
                        pass
                    _platform_json_response(self, 200, {
                        "id": doc_id,
                        "document_title": fname,
                        "document_detail": detail,
                        "sort_num": idx,
                        "labels": None,
                        "create_time": ts,
                        "update_time": ts,
                    })
                    return
            _platform_json_response(self, 404, None, "Document not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_product_documents(self):
        """GET /api/products/{productId}/documents — 产品文档（边缘设备返回空）。"""
        try:
            _platform_json_response(self, 200, [])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 4: Workflow -----

    def _handle_workflows_list(self):
        """GET /api/workflows — 列出 workflow。"""
        try:
            workflows = _load_workflows()
            _platform_json_response(self, 200, workflows)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_workflow_save(self):
        """POST /api/workflows — 保存 workflow 定义。"""
        try:
            body = _read_json_body(self)
            wf_id = body.get("id") or f"wf_{uuid.uuid4().hex[:12]}"
            workflows = _load_workflows()
            found = False
            for i, wf in enumerate(workflows):
                if wf.get("id") == wf_id:
                    workflows[i] = body
                    workflows[i]["id"] = wf_id
                    found = True
                    break
            if not found:
                body["id"] = wf_id
                body.setdefault("enabled", True)
                workflows.append(body)
            _save_workflows(workflows)
            _platform_json_response(self, 200, body)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_workflow_get(self):
        """GET /api/workflows/{id} — 获取单个 workflow。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            wf_id = _path.split("/")[-1]
            workflows = _load_workflows()
            for wf in workflows:
                if str(wf.get("id")) == wf_id:
                    _platform_json_response(self, 200, wf)
                    return
            _platform_json_response(self, 404, None, "Workflow not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_workflow_run(self):
        """POST /api/workflows/{id}/run — 运行 workflow（stub）。"""
        try:
            exec_id = f"exec_{uuid.uuid4().hex[:12]}"
            _platform_json_response(self, 200, {"execution_id": exec_id})
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_workflow_execution_logs(self):
        """GET /api/workflows/executions/{id}/logs — 执行日志（stub 空）。"""
        try:
            _platform_json_response(self, 200, [])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 5: Devices -----

    def _handle_devices_list(self):
        """GET /api/platform/devices — 列出设备。"""
        try:
            info = _load_device_info()
            info["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _platform_json_response(self, 200, [info])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_devices_account_state(self):
        """GET /api/platform/devices/account-state — 设备账号状态。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            installation_id = (params.get("installation_id") or [""])[0]
            info = _load_device_info()
            _platform_json_response(self, 200, {
                "installation_id": installation_id or info.get("installation_id", ""),
                "state": "current_user",
                "can_register_current_account": False,
                "current_user_device_id": info.get("id", 1),
                "current_user_has_devices": True,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_devices_online(self):
        """GET /api/platform/devices/online — 设备在线状态。"""
        try:
            _platform_json_response(self, 200, {
                "runtime_type": "openclaw",
                "runtime_label": "OpenClaw",
                "runtime_status": "running",
                "runtime_stage": "phase_device_bridge_only",
                "supports_device_bridge": True,
                "supports_managed_download": False,
                "online_team_ids": [1],
                "notes": "当前设备中心仅管理 OpenClaw device bridge。",
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_devices_bootstrap(self):
        """POST /api/platform/devices/bootstrap — 设备注册。"""
        try:
            body = _read_json_body(self)
            info = _load_device_info()
            if body.get("device_name"):
                info["device_name"] = body["device_name"]
            if body.get("hostname"):
                info["hostname"] = body["hostname"]
            if body.get("os_info"):
                info["os_info"] = body["os_info"]
            if body.get("installation_id"):
                info["installation_id"] = body["installation_id"]
            _save_device_info(info)
            port = os.environ.get("BRIDGE_PORT", "21747")
            _platform_json_response(self, 200, {
                "api_key": "local-bridge-key",
                "base_url": f"http://127.0.0.1:{port}",
                "ws_url": f"ws://127.0.0.1:{port}",
                "device_id": info.get("id", 1),
                "device_name": info.get("device_name", ""),
                "installation_id": info.get("installation_id", ""),
                "registration_mode": "local",
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_devices_pair_code(self):
        """POST /api/platform/devices/pair-code — 生成配对码（stub）。"""
        try:
            _platform_json_response(self, 200, {
                "pair_code": f"PAIR-{uuid.uuid4().hex[:6].upper()}",
                "expires_in_seconds": 600,
                "expires_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() + 600),
                ),
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_devices_claim(self):
        """POST /api/platform/devices/claim — 认领设备。"""
        try:
            self._handle_devices_bootstrap()
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_device_update(self):
        """PUT /api/platform/devices/{id} — 更新设备名称。"""
        try:
            body = _read_json_body(self)
            info = _load_device_info()
            if body.get("device_name"):
                info["device_name"] = body["device_name"]
            _save_device_info(info)
            _platform_json_response(self, 200, None)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_device_delete(self):
        """DELETE /api/platform/devices/{id} — 删除设备（stub）。"""
        try:
            _platform_json_response(self, 200, None)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 6: Knowledge 新路径 -----

    def _handle_platform_knowledge_list(self):
        """GET /api/platform/knowledge/list — 代理到现有知识库列表。"""
        try:
            self._handle_kb_list()
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_platform_knowledge_search(self):
        """GET /api/platform/knowledge/search — 从 query params 检索知识库。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            query = (params.get("query") or [""])[0]
            filename = (params.get("filename") or [None])[0]
            limit = int((params.get("limit") or ["5"])[0])

            try:
                from knowledge_store import search_knowledge
                results = search_knowledge(query=query or "", top_k=limit)
                if filename:
                    results = [r for r in results if filename.lower() in (r.get("filename") or "").lower()]
                _platform_json_response(self, 200, results)
            except ImportError:
                _platform_json_response(self, 200, [])
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_platform_knowledge_upload(self):
        """POST /api/platform/knowledge/upload — 代理到现有上传。"""
        try:
            self._handle_kb_upload()
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_platform_knowledge_delete(self):
        """POST /api/platform/knowledge/delete — 从 query params 删除。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            source_name = (params.get("source_name") or [""])[0]
            if not source_name:
                body = _read_json_body(self)
                source_name = body.get("source_name", "")
            if not source_name:
                _platform_json_response(self, 400, None, "source_name is required")
                return
            try:
                from knowledge_store import delete_document
                ok = delete_document(source_name)
                _platform_json_response(self, 200, {"deleted": ok})
            except ImportError:
                _platform_json_response(self, 200, {"deleted": False})
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_platform_knowledge_download(self):
        """GET /api/platform/knowledge/download — 下载文档（返回路径）。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            source_name = (params.get("source_name") or [""])[0]
            mode = (params.get("mode") or ["path"])[0]
            if not source_name:
                _platform_json_response(self, 400, None, "source_name is required")
                return
            kb_dir = os.path.join(_HERMES_HOME, "knowledge")
            file_path = os.path.join(kb_dir, source_name)
            if os.path.isfile(file_path) and mode == "path":
                _platform_json_response(self, 200, {"path": file_path, "source_name": source_name})
            else:
                _platform_json_response(self, 404, None, "File not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_platform_knowledge_stats(self):
        """GET /api/platform/knowledge/stats — 代理到现有统计。"""
        try:
            self._handle_kb_stats()
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_platform_knowledge_config(self):
        """GET /api/platform/knowledge/config — 知识库配置。"""
        try:
            config = _load_knowledge_config()
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_platform_knowledge_config_update(self):
        """POST /api/platform/knowledge/config/update — 更新知识库配置。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            watch_dir = (params.get("watchDir") or (params.get("watch_dir") or [""]))[0]
            config = _load_knowledge_config()
            if watch_dir:
                config["watch_dir"] = watch_dir
            _save_knowledge_config(config)
            _platform_json_response(self, 200, config)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 7: Approval -----

    def _handle_approvals_list(self):
        """GET /api/platform/approvals — 审批列表。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            page = int((params.get("page") or ["1"])[0])
            page_size = int((params.get("page_size") or ["20"])[0])
            status_filter = (params.get("status") or [None])[0]

            items = _load_approvals()
            if status_filter:
                items = [a for a in items if a.get("status") == status_filter]
            total = len(items)
            start = (page - 1) * page_size
            page_items = items[start:start + page_size]
            _platform_json_response(self, 200, {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": page_items,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_approval_request(self):
        """POST /api/platform/approvals/request — 创建审批请求。"""
        try:
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            expires_seconds = body.get("expires_in_seconds", 86400)
            approval = {
                "approval_id": f"apr_{uuid.uuid4().hex[:12]}",
                "status": "pending",
                "approval_type": body.get("approval_type", "custom"),
                "title": body.get("title", ""),
                "reason": body.get("reason", ""),
                "risk_level": body.get("risk_level", "medium"),
                "payload": body.get("payload", {}),
                "requested_by": {"user_id": 1, "username": "local-admin"},
                "resolved_by": None,
                "resolution_comment": None,
                "created_at": now,
                "expires_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() + expires_seconds),
                ),
                "resolved_at": None,
            }
            items = _load_approvals()
            items.insert(0, approval)
            _save_approvals(items)
            _platform_json_response(self, 200, approval)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_approval_get(self):
        """GET /api/platform/approvals/{id} — 审批详情。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            approval_id = _path.split("/")[-1]
            items = _load_approvals()
            for item in items:
                if item.get("approval_id") == approval_id:
                    _platform_json_response(self, 200, item)
                    return
            _platform_json_response(self, 404, None, "Approval not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_approval_resolve(self):
        """POST /api/platform/approvals/{id}/resolve — 审批/拒绝。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            # path: /api/platform/approvals/{id}/resolve
            parts = _path.strip("/").split("/")
            approval_id = parts[3] if len(parts) >= 5 else ""
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            items = _load_approvals()
            for item in items:
                if item.get("approval_id") == approval_id:
                    action = body.get("action", "")
                    if action == "approved" or body.get("approved"):
                        item["status"] = "approved"
                    else:
                        item["status"] = "rejected"
                    item["resolved_at"] = now
                    item["resolved_by"] = {"user_id": 1, "username": "local-admin"}
                    item["resolution_comment"] = body.get("comment")
                    _save_approvals(items)
                    _platform_json_response(self, 200, item)
                    return
            _platform_json_response(self, 404, None, "Approval not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 8: Audit -----

    def _handle_audit_events_list(self):
        """GET /api/platform/audit/events — 审计事件列表。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            page = int((params.get("page") or ["1"])[0])
            page_size = int((params.get("page_size") or ["50"])[0])

            events = _load_audit_events()
            total = len(events)
            start = (page - 1) * page_size
            page_items = events[start:start + page_size]
            _platform_json_response(self, 200, {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": page_items,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_audit_summary(self):
        """GET /api/platform/audit/summary — 审计汇总。"""
        try:
            events = _load_audit_events()
            approvals = _load_approvals()
            _platform_json_response(self, 200, {
                "total": len(events) + len(approvals),
                "operation_count": len(events),
                "approval_count": len(approvals),
                "pending_approval_count": sum(1 for a in approvals if a.get("status") == "pending"),
                "approved_approval_count": sum(1 for a in approvals if a.get("status") == "approved"),
                "rejected_approval_count": sum(1 for a in approvals if a.get("status") == "rejected"),
                "expired_approval_count": sum(1 for a in approvals if a.get("status") == "expired"),
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_audit_record(self):
        """POST /api/platform/audit/events — 记录审计事件。"""
        try:
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            event = {
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "category": body.get("category", "operation"),
                "event_type": body.get("event_type") or body.get("action_type", "unknown"),
                "title": body.get("title", ""),
                "summary": body.get("summary"),
                "module": body.get("module", "SDK"),
                "path": body.get("path"),
                "status": body.get("status", "completed"),
                "risk_level": body.get("risk_level", "low"),
                "actor": {"user_id": 1, "username": "local-admin"},
                "metadata": body.get("metadata", {}),
                "created_at": now,
            }
            events = _load_audit_events()
            events.insert(0, event)
            events = events[:1000]
            _save_audit_events(events)
            _platform_json_response(self, 200, event)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 9: ApiKey -----

    def _handle_app_keys_list(self):
        """GET /api/users/app-keys — App Key 列表。"""
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            page = int((params.get("page") or ["1"])[0])
            page_size = int((params.get("page_size") or ["20"])[0])

            data = _load_api_keys()
            items = data.get("app_keys", [])
            total = len(items)
            start = (page - 1) * page_size
            _platform_json_response(self, 200, {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items[start:start + page_size],
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_app_key_create(self):
        """POST /api/users/app-keys — 创建 App Key。"""
        try:
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            key_id = int(time.time() * 1000) % 1000000
            app_key = f"ak_{uuid.uuid4().hex[:16]}"
            app_secret = f"sk_{uuid.uuid4().hex}"
            key_name = body.get("name", "")
            entry = {
                "id": key_id,
                "name": key_name,
                "app_key": app_key,
                "app_secret": app_secret,
                "role": "USER",
                "is_active": True,
                "expire_time": None,
                "create_time": now,
            }
            data = _load_api_keys()
            data.setdefault("app_keys", []).append(entry)
            _save_api_keys(data)
            _platform_json_response(self, 200, entry)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_app_key_delete(self):
        """DELETE /api/users/app-keys/{id} — 删除 App Key。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            key_id = int(_path.split("/")[-1])
            data = _load_api_keys()
            data["app_keys"] = [k for k in data.get("app_keys", []) if k.get("id") != key_id]
            _save_api_keys(data)
            _platform_json_response(self, 200, None)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_app_key_set_active(self):
        """PATCH /api/users/app-keys/{id} — 设置 is_active。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            key_id = int(_path.split("/")[-1])
            body = _read_json_body(self)
            data = _load_api_keys()
            for k in data.get("app_keys", []):
                if k.get("id") == key_id:
                    k["is_active"] = body.get("is_active", True)
                    _save_api_keys(data)
                    _platform_json_response(self, 200, k)
                    return
            _platform_json_response(self, 404, None, "Key not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_app_key_rename(self):
        """PUT /api/users/app-keys/{id}/name — 重命名 App Key。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            # /api/users/app-keys/{id}/name → id = parts[-2]
            parts = _path.strip("/").split("/")
            key_id = int(parts[-2])
            body = _read_json_body(self)
            new_name = body.get("name") or body.get("key_name", "")
            data = _load_api_keys()
            for k in data.get("app_keys", []):
                if k.get("id") == key_id:
                    k["name"] = new_name
                    k["key_name"] = new_name
                    _save_api_keys(data)
                    _platform_json_response(self, 200, k)
                    return
            _platform_json_response(self, 404, None, "Key not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_app_key_issue_token(self):
        """POST /api/users/app-keys/default/token — 签发 token。"""
        try:
            data = _load_api_keys()
            keys = data.get("app_keys", [])
            if not keys:
                # 自动创建一个默认 key
                key_id = 1
                app_key = f"ak_default_{uuid.uuid4().hex[:8]}"
                keys.append({
                    "id": key_id,
                    "app_key": app_key,
                    "key_name": "default",
                    "role": "ADMIN",
                    "is_active": True,
                    "expire_time": None,
                    "create_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
                data["app_keys"] = keys
                _save_api_keys(data)
            first = keys[0]
            token = f"tok_{uuid.uuid4().hex}"
            _platform_json_response(self, 200, {
                "token": token,
                "expires_in": 86400,
                "app_key": first.get("app_key", ""),
                "app_key_id": first.get("id", 1),
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_llm_keys_list(self):
        """GET /api/llm/keys — LLM Key 列表。"""
        try:
            data = _load_api_keys()
            _platform_json_response(self, 200, data.get("llm_keys", []))
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_llm_key_create(self):
        """POST /api/llm/keys — 创建 LLM Key。"""
        try:
            body = _read_json_body(self)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            key_id = int(time.time() * 1000) % 1000000
            record = {
                "id": key_id,
                "key": f"llm_{uuid.uuid4().hex[:24]}",
                "provider": body.get("provider", ""),
                "api_key": body.get("api_key", ""),
                "name": body.get("name", ""),
                "description": body.get("description"),
                "limit_config": body.get("limit_config"),
                "expire_time": body.get("expire_time"),
                "is_active": True,
                "created_time": now,
            }
            data = _load_api_keys()
            data.setdefault("llm_keys", []).append(record)
            _save_api_keys(data)
            _platform_json_response(self, 200, record)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_llm_key_update(self):
        """PUT /api/llm/keys/{id} — 更新 LLM Key。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            key_id = int(_path.split("/")[-1])
            body = _read_json_body(self)
            data = _load_api_keys()
            for k in data.get("llm_keys", []):
                if k.get("id") == key_id:
                    if "name" in body:
                        k["name"] = body["name"]
                    if "description" in body:
                        k["description"] = body["description"]
                    if "expire_time" in body:
                        k["expire_time"] = body["expire_time"]
                    if "is_active" in body:
                        k["is_active"] = body["is_active"]
                    _save_api_keys(data)
                    _platform_json_response(self, 200, k)
                    return
            _platform_json_response(self, 404, None, "LLM key not found")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    def _handle_llm_key_delete(self):
        """DELETE /api/llm/keys/{id} — 删除 LLM Key。"""
        try:
            _path = urllib.parse.urlparse(self.path).path
            key_id = int(_path.split("/")[-1])
            data = _load_api_keys()
            data["llm_keys"] = [k for k in data.get("llm_keys", []) if k.get("id") != key_id]
            _save_api_keys(data)
            _platform_json_response(self, 200, None)
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 10: Policy -----

    def _handle_policy_check(self):
        """POST /api/platform/policy/*/check — 策略检查（边缘设备全部放行）。"""
        try:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _platform_json_response(self, 200, {
                "allowed": True,
                "requires_approval": False,
                "checked_at": now,
            })
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Step 11: Voice (stub) -----

    def _handle_voice_not_implemented(self):
        """POST /api/asr, /api/tts, /api/audio/speech — 语音服务未实现。"""
        try:
            _platform_json_response(self, 501, None, "Voice service not available on this edge device")
        except Exception as e:
            traceback.print_exc()
            _platform_json_response(self, 500, None, str(e))

    # ----- Hermes 调用核心 (委托给 AgentPool) -----

    def _invoke_hermes(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> dict:
        """兼容旧调用签名 — 委托给 AgentPool._invoke_fallback()。

        仅供不走 session/profile 的遗留调用路径使用（如微信 webhook）。
        新代码应直接使用 get_agent_pool().invoke()。
        """
        pool = get_agent_pool()
        return pool._invoke_fallback(
            prompt=prompt,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            history=history,
        )


# ---------------------------------------------------------------------------
# HUD 子进程管理
# ---------------------------------------------------------------------------

_hud_process: Optional[subprocess.Popen] = None

def _start_hud():
    """后台启动 hermes-hudui。"""
    global _hud_process
    if not HUD_ENABLED:
        return
    main_py_path = os.path.join(HUD_DIR, "backend", "main.py")
    if not os.path.isfile(main_py_path):
        print(f"[hermes-bridge] ⚠️ HUD disabled: 'backend/main.py' not found at {HUD_DIR}")
        return

    # 准备环境变量
    env = os.environ.copy()
    env["HERMES_HOME"] = os.path.abspath(HERMES_AGENT_DIR)

    _hud_host = os.environ.get("QEECLAW_HUD_HOST", _cfg("hud", "host", "127.0.0.1"))
    print(f"[hermes-bridge] Starting HUD Dashboard on http://{_hud_host}:{HUD_PORT} ...")
    try:
        _hud_process = subprocess.Popen(
            [sys.executable, "-m", "backend.main",
             "--host", _hud_host, "--port", str(HUD_PORT)],
            cwd=HUD_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )

        # 启动一个线程异步消费 HUD stderr，防止死锁
        def _consume_hud_stderr():
            if not _hud_process or not _hud_process.stderr:
                return
            for line in _hud_process.stderr:
                # 脱敏或直接输出
                sys.stderr.write(f"[hudui] {line}")
        Thread(target=_consume_hud_stderr, daemon=True).start()

    except Exception as e:
        print(f"[hermes-bridge] ❌ Failed to start HUD: {e}")


def _stop_hud():
    """停止 hermes-hudui。"""
    global _hud_process
    if _hud_process:
        print("[hermes-bridge] Stopping HUD Dashboard...")
        _hud_process.terminate()
        try:
            _hud_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _hud_process.kill()
        _hud_process = None


def main():
    """启动 bridge HTTP 服务。"""
    print(f"[hermes-bridge] ======================================")
    print(f"[hermes-bridge] QeeClaw Hermes Bridge v{BRIDGE_VERSION}")
    print(f"[hermes-bridge] ======================================")
    print(f"[hermes-bridge] Host: {_DISPLAY_HOST}")
    print(f"[hermes-bridge] Port: {BRIDGE_PORT}")
    print(f"[hermes-bridge] Auth mode: {_AUTH_MODE}")
    if _AUTH_MODE == "local":
        print(f"[hermes-bridge] API keys loaded: {len(_AUTH_API_KEYS)}")
    print(f"[hermes-bridge] CORS origins: {_CORS_ORIGINS}")
    print(f"[hermes-bridge] Hermes agent dir: {os.path.abspath(HERMES_AGENT_DIR)}")
    print(f"[hermes-bridge] Hermes hud dir: {os.path.abspath(HUD_DIR)}")
    print(f"[hermes-bridge] Python: {sys.version}")
    print(f"[hermes-bridge] Config file: {os.environ.get('QEECLAW_CONFIG_FILE', '(default)')}")

    _ensure_hermes_on_path()
    if _hermes_error:
        print(f"[hermes-bridge] WARNING: {_hermes_error}")
    else:
        print("[hermes-bridge] Hermes agent directory found.")

    # 初始化 AgentPool（加载 AIAgent 类）
    pool = get_agent_pool()
    if pool.available:
        print("[hermes-bridge] AgentPool: AIAgent mode ENABLED (full tool calling)")
    else:
        print(f"[hermes-bridge] AgentPool: FALLBACK mode (raw LLM) — {pool._init_error or 'unknown'}")
    print(f"[hermes-bridge] AgentPool: base HERMES_HOME = {pool._base_hermes_home}")
    print(f"[hermes-bridge] AgentPool: profiles dir = {pool.profiles_home}")

    # 初始化知识库
    try:
        from knowledge_store import init_knowledge_store, get_kb_stats
        kb_err = init_knowledge_store()
        if kb_err:
            print(f"[hermes-bridge] Knowledge base: UNAVAILABLE ({kb_err})")
        else:
            stats = get_kb_stats()
            print(f"[hermes-bridge] Knowledge base: OK ({stats['document_count']} docs, {stats['chunk_count']} chunks)")
            print(f"[hermes-bridge] KB storage: {stats['storage_dir']}")
    except ImportError:
        print("[hermes-bridge] Knowledge base: UNAVAILABLE (chromadb not installed)")
    except Exception as e:
        print(f"[hermes-bridge] Knowledge base: ERROR ({e})")

    # 启动云端反连隧道
    try:
        from cloud_tunnel import start_tunnel, get_tunnel_status
        tunnel_started = start_tunnel()
        if tunnel_started:
            print(f"[hermes-bridge] Cloud tunnel: CONNECTING → {os.environ.get('NEXUS_URL', '')}")
        else:
            print("[hermes-bridge] Cloud tunnel: DISABLED (set NEXUS_URL + NEXUS_API_KEY to enable)")
    except ImportError:
        print("[hermes-bridge] Cloud tunnel: UNAVAILABLE (websockets not installed)")
    except Exception as e:
        print(f"[hermes-bridge] Cloud tunnel: ERROR ({e})")

    # 启动 HUD 子服务
    _start_hud()

    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True

    server = ReusableThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), BridgeRequestHandler)
    print(f"[hermes-bridge] Listening at http://{_DISPLAY_HOST}:{BRIDGE_PORT}")
    print("[hermes-bridge] Endpoints:")
    print("  GET  /health                     - 健康检查 (免鉴权)")
    print("  POST /invoke                     - 非流式模型调用 (自动 RAG)")
    print("  POST /invoke/stream              - 流式模型调用 (SSE, 自动 RAG)")
    print("  --- Sessions (多人多轮对话) ---")
    print("  GET  /sessions                   - 列出会话")
    print("  GET  /sessions/stats             - 会话统计")
    print("  GET  /sessions/{id}              - 获取会话详情")
    print("  POST /sessions                   - 创建会话")
    print("  POST /sessions/{id}/clear        - 清空会话历史")
    print("  POST /sessions/{id}/delete       - 删除会话")
    print("  --- Agents (多智体) ---")
    print("  GET  /agents                     - 列出智体")
    print("  GET  /agents/{name}              - 获取智体详情")
    print("  POST /agents                     - 创建/更新智体")
    print("  POST /agents/{name}/delete       - 删除智体")
    print("  --- Knowledge Base ---")
    print("  POST /knowledge/upload           - 上传文档到知识库")
    print("  GET  /knowledge/list             - 列出所有文档")
    print("  GET  /knowledge/document/<id>    - 获取文档详情")
    print("  POST /knowledge/search           - 向量检索")
    print("  POST /knowledge/delete/<id>      - 删除文档")
    print("  GET  /knowledge/stats            - 知识库统计")
    print("  --- Gateway ---")
    print("  GET  /gateway/status             - Gateway 运行状态")
    print("  GET  /gateway/platforms          - 已配置的平台列表")
    print("  GET  /gateway/supported-platforms - 支持的全部平台")
    print("  POST /gateway/start              - 启动 Gateway")
    print("  POST /gateway/stop               - 停止 Gateway")
    print("  POST /gateway/configure          - 配置平台凭证")
    print("  --- WeChat (个人微信) ---")
    print("  GET  /wechat/check               - 检查微信依赖")
    print("  GET  /wechat/status               - 微信状态总览")
    print("  GET  /wechat/credentials          - 凭证摘要")
    print("  POST /wechat/qr-login             - 发起 QR 扫码登录")
    print("  POST /wechat/qr-cancel            - 取消 QR 登录")
    print("  POST /wechat/configure            - 配置 DM/群聊策略")
    print("  POST /wechat/send                 - 发送微信消息")
    print("  POST /wechat/adapter/start        - 启动长轮询适配器")
    print("  POST /wechat/adapter/stop         - 停止长轮询适配器")
    print("  --- SDK 兼容 (/api/agent/*) ---")
    print("  GET  /api/agent/my-agents          - 列出智体 (SDK 格式)")
    print("  GET  /api/agent/tools              - 列出系统工具")
    print("  POST /api/agent/create             - 创建智体 (SDK 格式)")
    print("  PUT  /api/agent/{id}               - 更新智体 (SDK 格式)")
    print("  --- SDK 兼容 (/api/platform/memory/*) ---")
    print("  POST /api/platform/memory/store      - 存入记忆")
    print("  POST /api/platform/memory/search     - 搜索记忆")
    print("  GET  /api/platform/memory/stats      - 记忆统计")
    print("  DELETE /api/platform/memory/{id}      - 删除单条记忆")
    print("  DELETE /api/platform/memory/agent/{id} - 清除 agent 全部记忆")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[hermes-bridge] Shutting down.")
        try:
            from cloud_tunnel import stop_tunnel
            stop_tunnel()
        except Exception:
            pass
        _stop_hud()
        server.server_close()


if __name__ == "__main__":
    main()
