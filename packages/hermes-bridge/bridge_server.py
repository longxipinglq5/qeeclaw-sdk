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
import subprocess
import sys
import time
import traceback
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
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

            _json_response(self, 200, {
                "status": "ok",
                "version": BRIDGE_VERSION,
                "hermes_available": True,
                "hermes_dir": os.path.abspath(HERMES_AGENT_DIR),
                "python_version": sys.version,
                "knowledge_base": kb_info,
            })
        except ImportError as e:
            _json_response(self, 503, {
                "status": "error",
                "version": BRIDGE_VERSION,
                "hermes_available": False,
                "message": f"Failed to import hermes-agent: {e}",
            })

    def _handle_invoke(self):
        """非流式模型调用端点。支持 session_id 实现多轮对话。"""
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

            err = _get_hermes_error()
            if err:
                _json_response(self, 503, {"error": err})
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
                if max_tokens is None and profile.max_tokens is not None:
                    max_tokens = profile.max_tokens
                if not model and profile.model:
                    model = profile.model

            # 调用 hermes-agent 的模型（带历史上下文）
            history = session.get_messages(max_turns=max_history_turns)
            result = self._invoke_hermes(
                prompt=prompt,
                model=model,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=effective_system_prompt or None,
                history=history,
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

        使用 OpenAI SDK 的 stream=True 实现真正的逐 token 流式推理。
        """
        try:
            body = _read_json_body(self)
            prompt = body.get("prompt", "")

            if not prompt:
                _json_response(self, 400, {"error": "prompt is required"})
                return

            err = _get_hermes_error()
            if err:
                _json_response(self, 503, {"error": err})
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

            # 构建流式调用
            _ensure_hermes_on_path()
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
                if max_tokens is None and profile.max_tokens is not None:
                    max_tokens = profile.max_tokens
                if not model_name and profile.model:
                    model_name = profile.model

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

            # 解析 provider 配置
            api_key = ""
            base_url = None
            _default_model = os.environ.get("HERMES_MODEL", "deepseek/deepseek-v3.2-exp")
            resolved_model = model_name or _default_model

            try:
                from hermes_cli.runtime_provider import resolve_runtime_provider
                p_name = provider_name or "openrouter"
                runtime = resolve_runtime_provider(requested=p_name)
                api_key = runtime.get("api_key", "")
                base_url = runtime.get("base_url")
                resolved_model = runtime.get("model", resolved_model)
            except ImportError:
                pass

            # 环境变量优先：OPENAI_API_KEY / OPENAI_BASE_URL 始终覆盖 runtime 配置
            env_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
            env_base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "")
            if env_key:
                api_key = env_key
            if env_base:
                base_url = env_base
            # 兜底默认
            if not base_url:
                base_url = "https://openrouter.ai/api/v1"

            import openai
            client = openai.OpenAI(api_key=api_key, base_url=base_url)

            # 构建带历史上下文的 messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            # 注入历史消息
            history = session.get_messages(max_turns=max_history_turns)
            messages.extend(history)
            # 当前用户消息
            messages.append({"role": "user", "content": prompt})

            kwargs: Dict[str, Any] = {
                "model": resolved_model,
                "messages": messages,
                "stream": True,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            if temperature is not None:
                kwargs["temperature"] = temperature

            # 真正的流式输出
            collected_text = []
            stream = client.chat.completions.create(**kwargs)
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    collected_text.append(delta.content)
                    sse_data = json.dumps({
                        "type": "text",
                        "content": delta.content,
                    }, ensure_ascii=False)
                    self.wfile.write(f"data: {sse_data}\n\n".encode("utf-8"))
                    self.wfile.flush()

                # 检查是否完成
                if chunk.choices[0].finish_reason:
                    break

            # 记录本轮对话到 session
            full_response = "".join(collected_text)
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

    # ----- Hermes 调用核心 -----

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
        """
        调用 hermes-agent 的 AIAgent 核心进行推理。

        这里采用 hermes-agent 的 Python API 方式而非 CLI，
        直接实例化 AIAgent 并调用 run_conversation。
        """
        _ensure_hermes_on_path()

        try:
            # 尝试使用 hermes-agent 的 model_tools 进行模型调用
            # hermes-agent 的架构：run_agent.py → AIAgent → model_tools.py
            from hermes_cli.runtime_provider import resolve_runtime_provider

            # 解析 provider 和模型
            provider_name = provider or "openrouter"
            model_name = model or os.environ.get("HERMES_MODEL", "deepseek/deepseek-v3.2-exp")

            # 获取运行时 provider 配置
            runtime = resolve_runtime_provider(requested=provider_name)
            api_key = runtime.get("api_key", "")
            api_base = runtime.get("base_url")

            # 环境变量优先：OPENAI_API_KEY / OPENAI_BASE_URL 始终覆盖 runtime 配置
            env_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
            env_base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL", "")
            if env_key:
                api_key = env_key
            if env_base:
                api_base = env_base
            # 兜底默认
            if not api_base:
                api_base = "https://openrouter.ai/api/v1"

            # 使用 openai 兼容接口进行调用
            import openai

            client = openai.OpenAI(
                api_key=api_key,
                base_url=api_base,
            )

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})

            kwargs: Dict[str, Any] = {
                "model": runtime.get("model", model_name),
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
                "provider": provider_name,
                "usage": usage_data,
            }

        except ImportError as e:
            # 如果 hermes-agent 的内部模块结构不可用，
            # 降级为直接使用环境变量中的 API 配置
            return self._invoke_fallback(
                prompt=prompt,
                model=model,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                history=history,
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
        """
        降级调用：如果 hermes-agent 的内部模块不可用，
        直接使用 openai SDK + 环境变量进行模型调用。
        """
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
