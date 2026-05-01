"""
wechat_gateway.py - 个人微信网关管理模块 (Path A: hermes-agent 原生 iLink Bot 适配器)

通过 Bridge HTTP API 暴露微信 QR 登录、连接管理和消息发送能力。
底层调用 hermes-agent 的 gateway.platforms.weixin 模块，实现：
  - QR 码扫码登录（iLink Bot API）
  - 凭证持久化与加载
  - 单次消息发送（send_weixin_direct）
  - 完整适配器生命周期管理（WeixinAdapter connect / disconnect）

设计原则：零修改 hermes-agent 源码，纯包装。
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from threading import Thread, Lock
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 状态管理
# ---------------------------------------------------------------------------

# 当前 QR 登录会话（一次只允许一个）
_qr_session: Optional[Dict[str, Any]] = None
_qr_lock = Lock()

# 当前运行中的 WeixinAdapter 实例
_adapter_instance = None
_adapter_loop: Optional[asyncio.AbstractEventLoop] = None
_adapter_thread: Optional[Thread] = None
_adapter_lock = Lock()


def _get_hermes_home() -> str:
    """获取 hermes 主目录。"""
    return str(Path.home() / ".hermes")


# ---------------------------------------------------------------------------
# 依赖检查
# ---------------------------------------------------------------------------

def check_wechat_available() -> Dict[str, Any]:
    """检查微信网关所需依赖是否就绪。"""
    result: Dict[str, Any] = {
        "available": False,
        "aiohttp": False,
        "cryptography": False,
        "weixin_module": False,
    }
    try:
        import aiohttp  # noqa: F401
        result["aiohttp"] = True
    except ImportError:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher  # noqa: F401
        result["cryptography"] = True
    except ImportError:
        pass
    try:
        from gateway.platforms.weixin import check_weixin_requirements
        result["weixin_module"] = True
        result["available"] = check_weixin_requirements()
    except ImportError:
        pass
    return result


# ---------------------------------------------------------------------------
# QR 登录流程
# ---------------------------------------------------------------------------

def start_qr_login() -> Dict[str, Any]:
    """
    发起微信 QR 扫码登录。

    直接调用 iLink Bot API 获取二维码 URL，返回给前端展示。
    后台线程轮询扫码状态直到完成/超时。
    一次只允许一个登录会话。
    """
    global _qr_session

    with _qr_lock:
        # 如果有进行中的会话且未完成，拒绝
        if _qr_session and _qr_session.get("state") == "pending":
            return {
                "status": "already_in_progress",
                "message": "已有正在进行的微信登录流程，请等待完成或取消。",
                "qr_url": _qr_session.get("qr_url", ""),
            }

        # 初始化新会话
        _qr_session = {
            "state": "pending",
            "qr_url": None,
            "session_id": None,
            "started_at": time.time(),
            "credentials": None,
            "error": None,
        }

    # 第一步：同步获取 QR 码 URL
    import uuid as _uuid
    session_id = str(_uuid.uuid4())

    try:
        import urllib.request
        import urllib.error

        qr_api_url = "https://ilinkai.weixin.qq.com/ilink/bot/get_bot_qrcode?bot_type=3"
        req = urllib.request.Request(qr_api_url, method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            qr_resp = json.loads(resp.read().decode("utf-8"))

        qrcode_value = str(qr_resp.get("qrcode") or "")
        qrcode_url = str(qr_resp.get("qrcode_img_content") or "")
        if not qrcode_value:
            with _qr_lock:
                _qr_session = {
                    "state": "error",
                    "error": "iLink API 返回空二维码",
                    "qr_url": None,
                    "session_id": None,
                    "started_at": time.time(),
                    "credentials": None,
                }
            return {"status": "error", "message": "iLink API 返回空二维码"}

        with _qr_lock:
            _qr_session["qr_url"] = qrcode_url or f"https://ilinkai.weixin.qq.com/ilink/bot/get_bot_qrcode?qrcode={qrcode_value}"
            _qr_session["session_id"] = session_id

    except Exception as e:
        logger.error(f"WeChat QR fetch error: {e}")
        with _qr_lock:
            _qr_session = {
                "state": "error",
                "error": f"获取二维码失败: {e}",
                "qr_url": None,
                "session_id": None,
                "started_at": time.time(),
                "credentials": None,
            }
        return {"status": "error", "message": f"获取二维码失败: {e}"}

    # 第二步：后台线程轮询扫码状态
    def _poll_qr_status():
        global _qr_session
        try:
            import urllib.request
            import urllib.error

            deadline = time.time() + 480
            current_base = "https://ilinkai.weixin.qq.com"
            refresh_count = 0

            while time.time() < deadline:
                with _qr_lock:
                    if not _qr_session or _qr_session.get("state") != "pending":
                        return

                try:
                    status_url = f"{current_base}/ilink/bot/get_qrcode_status?qrcode={qrcode_value}"
                    req = urllib.request.Request(status_url, method="GET")
                    req.add_header("Accept", "application/json")
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        status_resp = json.loads(resp.read().decode("utf-8"))
                except Exception as exc:
                    logger.warning(f"QR poll error: {exc}")
                    time.sleep(2)
                    continue

                status = str(status_resp.get("status") or "wait")

                if status == "scaned":
                    with _qr_lock:
                        if _qr_session:
                            _qr_session["state"] = "scanned"
                elif status == "scaned_but_redirect":
                    redirect_host = str(status_resp.get("redirect_host") or "")
                    if redirect_host:
                        current_base = f"https://{redirect_host}"
                    with _qr_lock:
                        if _qr_session:
                            _qr_session["state"] = "scanned"
                elif status == "expired":
                    refresh_count += 1
                    if refresh_count > 3:
                        with _qr_lock:
                            if _qr_session:
                                _qr_session["state"] = "expired"
                                _qr_session["error"] = "二维码多次过期"
                        return
                    # 刷新二维码
                    try:
                        refresh_url = "https://ilinkai.weixin.qq.com/ilink/bot/get_bot_qrcode?bot_type=3"
                        req = urllib.request.Request(refresh_url, method="GET")
                        req.add_header("Accept", "application/json")
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            new_qr = json.loads(resp.read().decode("utf-8"))
                        new_qrcode_value = str(new_qr.get("qrcode") or "")
                        new_qrcode_url = str(new_qr.get("qrcode_img_content") or "")
                        if new_qrcode_value:
                            # nonlocal not needed — we use _qr_session to communicate
                            with _qr_lock:
                                if _qr_session:
                                    _qr_session["qr_url"] = new_qrcode_url or _qr_session.get("qr_url", "")
                                    _qr_session["state"] = "pending"
                    except Exception as exc:
                        logger.warning(f"QR refresh error: {exc}")

                elif status == "confirmed":
                    account_id = str(status_resp.get("ilink_bot_id") or "")
                    token = str(status_resp.get("bot_token") or "")
                    base_url = str(status_resp.get("baseurl") or "https://ilinkai.weixin.qq.com")
                    user_id = str(status_resp.get("ilink_user_id") or "")

                    if not account_id or not token:
                        with _qr_lock:
                            if _qr_session:
                                _qr_session["state"] = "error"
                                _qr_session["error"] = "登录成功但凭证不完整"
                        return

                    # 保存到 hermes-agent 的账号系统
                    try:
                        from gateway.platforms.weixin import save_weixin_account
                        save_weixin_account(
                            _get_hermes_home(),
                            account_id=account_id,
                            token=token,
                            base_url=base_url,
                            user_id=user_id,
                        )
                    except Exception as exc:
                        logger.warning(f"Failed to save weixin account: {exc}")

                    credentials = {
                        "account_id": account_id,
                        "token": token,
                        "base_url": base_url,
                        "user_id": user_id,
                    }
                    with _qr_lock:
                        started = _qr_session["started_at"] if _qr_session else time.time()
                        _qr_session = {
                            "state": "success",
                            "credentials": {
                                "account_id": account_id,
                                "user_id": user_id,
                                "has_token": True,
                            },
                            "account_id": account_id,
                            "session_id": session_id,
                            "started_at": started,
                            "completed_at": time.time(),
                            "qr_url": None,
                            "error": None,
                        }
                    _save_credentials_to_env(credentials)
                    logger.info(f"WeChat login success, account_id={account_id}")

                    # 自动启动 adapter 开始接收消息
                    try:
                        result = start_adapter()
                        logger.info(f"[wechat] Auto-started adapter after login: {result}")
                    except Exception as e:
                        logger.warning(f"[wechat] Auto-start adapter failed: {e}")

                    return

                time.sleep(2)

            # 超时
            with _qr_lock:
                if _qr_session and _qr_session.get("state") == "pending":
                    _qr_session["state"] = "expired"
                    _qr_session["error"] = "登录超时"

        except Exception as e:
            logger.error(f"WeChat QR poll error: {e}")
            traceback.print_exc()
            with _qr_lock:
                if _qr_session:
                    _qr_session["state"] = "error"
                    _qr_session["error"] = str(e)

    thread = Thread(target=_poll_qr_status, daemon=True, name="wechat-qr-login")
    thread.start()

    return {
        "status": "started",
        "message": "请使用微信扫描二维码",
        "qr_url": _qr_session.get("qr_url", ""),
        "session_id": session_id,
    }


def get_qr_login_status() -> Dict[str, Any]:
    """获取当前 QR 登录会话状态。"""
    with _qr_lock:
        if not _qr_session:
            return {"state": "none", "message": "没有进行中的登录会话"}
        result = dict(_qr_session)
        # 映射 state → 前端期望的 status 字段
        state = result.get("state", "none")
        result["status"] = state
        if state == "success":
            result["connected"] = True
        elif state == "scanned":
            result["message"] = result.get("message") or "已扫码，请在微信里确认..."
        elif state == "pending":
            result["message"] = result.get("message") or "请使用微信扫描二维码"
        return result


def cancel_qr_login() -> Dict[str, Any]:
    """取消当前 QR 登录会话。"""
    global _qr_session
    with _qr_lock:
        if not _qr_session or _qr_session.get("state") != "pending":
            return {"status": "no_active_session"}
        _qr_session["state"] = "cancelled"
        _qr_session["error"] = "用户取消"
        return {"status": "cancelled"}


# ---------------------------------------------------------------------------
# 凭证管理
# ---------------------------------------------------------------------------

def _save_credentials_to_env(credentials: Dict[str, str]) -> None:
    """将 QR 登录获得的凭证写入 ~/.hermes/.env 和当前进程环境。"""
    env_updates = {}
    if credentials.get("account_id"):
        env_updates["WEIXIN_ACCOUNT_ID"] = credentials["account_id"]
    if credentials.get("token"):
        env_updates["WEIXIN_TOKEN"] = credentials["token"]
    if credentials.get("base_url"):
        env_updates["WEIXIN_BASE_URL"] = credentials["base_url"]

    if not env_updates:
        return

    # 写入 ~/.hermes/.env
    hermes_home = Path(_get_hermes_home())
    hermes_home.mkdir(parents=True, exist_ok=True)
    env_file = hermes_home / ".env"
    existing: Dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    existing.update(env_updates)
    lines = [f"{k}={v}" for k, v in existing.items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 设置到当前进程
    for k, v in env_updates.items():
        os.environ[k] = v

    logger.info(f"[wechat] Credentials saved: {list(env_updates.keys())}")


def get_wechat_credentials() -> Dict[str, Any]:
    """获取当前已保存的微信凭证摘要（不返回 token 明文）。"""
    account_id = os.environ.get("WEIXIN_ACCOUNT_ID", "")
    has_token = bool(os.environ.get("WEIXIN_TOKEN", ""))
    base_url = os.environ.get("WEIXIN_BASE_URL", "")

    # 也尝试从文件加载
    if not account_id:
        try:
            from gateway.platforms.weixin import load_weixin_account
            hermes_home = _get_hermes_home()
            accounts_dir = Path(hermes_home) / "weixin" / "accounts"
            if accounts_dir.is_dir():
                for f in accounts_dir.glob("*.json"):
                    data = json.loads(f.read_text(encoding="utf-8"))
                    account_id = data.get("account_id", f.stem)
                    has_token = bool(data.get("token"))
                    base_url = data.get("base_url", "")
                    break  # 取第一个
        except (ImportError, Exception):
            pass

    return {
        "configured": bool(account_id and has_token),
        "account_id": account_id,
        "has_token": has_token,
        "base_url": base_url,
    }


def _load_credentials_to_env():
    """从 ~/.hermes/.env 加载微信凭证到当前进程环境变量。"""
    try:
        hermes_home = Path(_get_hermes_home())
        env_file = hermes_home / ".env"

        if not env_file.exists():
            return False

        # 读取 .env 文件
        env_content = env_file.read_text(encoding="utf-8")
        for line in env_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key.startswith("WEIXIN_"):
                    os.environ[key] = value
                    logger.debug(f"[wechat] Loaded {key} from .env")

        return True
    except Exception as e:
        logger.warning(f"[wechat] Failed to load credentials from .env: {e}")
        return False



def configure_wechat(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    手动配置微信凭证和策略。

    可配置项：
    - dm_policy: open | allowlist | disabled | pairing
    - group_policy: disabled | open | allowlist
    - allowed_users: 逗号分隔的白名单
    - group_allowed_users: 逗号分隔的群聊白名单
    """
    env_updates: Dict[str, str] = {}
    if "dm_policy" in config:
        env_updates["WEIXIN_DM_POLICY"] = config["dm_policy"]
    if "group_policy" in config:
        env_updates["WEIXIN_GROUP_POLICY"] = config["group_policy"]
    if "allowed_users" in config:
        env_updates["WEIXIN_ALLOWED_USERS"] = config["allowed_users"]
    if "group_allowed_users" in config:
        env_updates["WEIXIN_GROUP_ALLOWED_USERS"] = config["group_allowed_users"]

    if not env_updates:
        return {"status": "no_changes", "message": "没有可更新的配置项"}

    # 写入环境
    _save_credentials_to_env(env_updates)

    return {
        "status": "configured",
        "updated": list(env_updates.keys()),
    }


# ---------------------------------------------------------------------------
# 消息发送（单次，不需要完整适配器生命周期）
# ---------------------------------------------------------------------------

def send_message(chat_id: str, message: str, media_files: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    发送微信消息（单次发送，不启动长轮询适配器）。

    使用 hermes-agent 的 send_weixin_direct() 函数。
    """
    account_id = os.environ.get("WEIXIN_ACCOUNT_ID", "")
    token = os.environ.get("WEIXIN_TOKEN", "")
    base_url = os.environ.get("WEIXIN_BASE_URL", "")

    if not account_id or not token:
        return {"error": "微信凭证未配置，请先完成 QR 登录"}

    try:
        from gateway.platforms.weixin import send_weixin_direct

        extra = {
            "account_id": account_id,
            "base_url": base_url,
        }

        # 转换 media_files 格式: List[str] -> List[Tuple[str, bool]]
        media_tuples: Optional[List[Tuple[str, bool]]] = None
        if media_files:
            media_tuples = [(f, os.path.isfile(f)) for f in media_files]

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                send_weixin_direct(
                    extra=extra,
                    token=token,
                    chat_id=chat_id,
                    message=message,
                    media_files=media_tuples,
                )
            )
        finally:
            loop.close()

        return result

    except ImportError as e:
        return {"error": f"weixin 模块不可用: {e}"}
    except Exception as e:
        logger.error(f"WeChat send error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 完整适配器生命周期管理
# ---------------------------------------------------------------------------

# 全局 AgentPool 引用（从 bridge_server 导入）
_agent_pool = None


def _get_agent_pool():
    """获取 AgentPool 实例（延迟导入避免循环依赖）。"""
    global _agent_pool
    if _agent_pool is None:
        try:
            # 从 bridge_server 导入 AgentPool
            import bridge_server
            _agent_pool = bridge_server.get_agent_pool()
        except Exception as e:
            logger.error(f"Failed to get AgentPool: {e}")
    return _agent_pool


# 消息处理回调（需要在 start_adapter 中注册）
async def _handle_incoming_message(event):
    """
    处理从 WeixinAdapter 接收到的微信消息。

    将消息转发给 AI 并返回回复。
    """
    try:
        # 提取消息信息
        sender_id = event.source.user_id or "unknown"
        chat_id = event.source.chat_id or sender_id
        text = event.text or ""

        logger.info(f"[wechat] Received message from {sender_id}: {text[:50]}")

        # 直接调用 paas.qeeshu.com 的模型 API
        try:
            import urllib.request
            import json as json_module

            api_url = "https://paas.qeeshu.com/api/platform/models/invoke"
            api_key = "mJXR0OavZjP8-unrkrDUNw"
            current_time = time.localtime()
            weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            current_date_context = (
                f"当前系统时间是 {current_time.tm_year}年{current_time.tm_mon:02d}月{current_time.tm_mday:02d}日 "
                f"{weekday_names[current_time.tm_wday]}。回答涉及今天、当前日期、星期几、现在时间等问题时，"
                f"必须以这个时间为准，不要使用训练数据中的过期日期。"
            )

            request_data = {
                "prompt": f"{current_date_context}\n\n用户消息：{text}",
                # 不指定 model，让平台根据用户选择的模型自动处理
            }

            req = urllib.request.Request(
                api_url,
                data=json_module.dumps(request_data).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json_module.loads(response.read().decode('utf-8'))

            # 提取回复文本
            if result.get("code") == 0:
                reply = result.get("data", {}).get("text", "抱歉，我无法处理您的消息。")
            else:
                reply = f"抱歉，处理您的消息时出错了：{result.get('message', '未知错误')}"

            logger.info(f"[wechat] AI reply: {reply[:100]}")

        except Exception as e:
            logger.error(f"[wechat] AI invocation error: {e}")
            traceback.print_exc()
            reply = f"抱歉，处理您的消息时出错了：{str(e)}"

        # 发送回复
        account_id = os.environ.get("WEIXIN_ACCOUNT_ID", "")
        token = os.environ.get("WEIXIN_TOKEN", "")
        base_url = os.environ.get("WEIXIN_BASE_URL", "")

        if account_id and token:
            from gateway.platforms.weixin import send_weixin_direct

            extra = {
                "account_id": account_id,
                "base_url": base_url,
            }

            result = await send_weixin_direct(
                extra=extra,
                token=token,
                chat_id=chat_id,
                message=reply,
                media_files=None,
            )

            logger.info(f"[wechat] Sent reply to {chat_id}: {result}")
        else:
            logger.warning("[wechat] Cannot send reply: credentials not configured")

    except Exception as e:
        logger.error(f"[wechat] Message handling error: {e}")
        traceback.print_exc()


def start_adapter() -> Dict[str, Any]:
    """
    启动 WeixinAdapter 长轮询适配器。

    会在后台线程中创建 asyncio 事件循环并运行 adapter.connect()。
    允许同时接收消息 + 自动回复。
    """
    global _adapter_instance, _adapter_loop, _adapter_thread

    with _adapter_lock:
        if _adapter_instance is not None and _adapter_loop is not None:
            return {"status": "already_running"}

        # 从文件加载凭证到环境变量
        _load_credentials_to_env()

        # 校验凭证
        creds = get_wechat_credentials()
        if not creds["configured"]:
            return {"error": "微信凭证未配置，请先完成 QR 登录"}

        try:
            from gateway.platforms.weixin import WeixinAdapter
            from gateway.config import PlatformConfig, Platform

            # 构建 PlatformConfig
            config = PlatformConfig(
                enabled=True,
                token=os.environ.get("WEIXIN_TOKEN", ""),
                extra={
                    "account_id": os.environ.get("WEIXIN_ACCOUNT_ID", ""),
                    "base_url": os.environ.get("WEIXIN_BASE_URL", ""),
                    "cdn_base_url": os.environ.get("WEIXIN_CDN_BASE_URL", ""),
                    "dm_policy": os.environ.get("WEIXIN_DM_POLICY", "open"),
                    "group_policy": os.environ.get("WEIXIN_GROUP_POLICY", "disabled"),
                    "allow_from": os.environ.get("WEIXIN_ALLOWED_USERS", ""),
                    "group_allow_from": os.environ.get("WEIXIN_GROUP_ALLOWED_USERS", ""),
                },
            )

            adapter = WeixinAdapter(config)

            # 注册消息处理器（关键！）
            adapter.set_message_handler(_handle_incoming_message)
            logger.info("[wechat] Message handler registered")

        except ImportError as e:
            return {"error": f"weixin 模块导入失败: {e}"}

        def _run_adapter():
            global _adapter_instance, _adapter_loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _adapter_loop = loop
            _adapter_instance = adapter
            try:
                connected = loop.run_until_complete(adapter.connect())
                if not connected:
                    logger.error("[wechat] Adapter failed to connect")
                    return
                logger.info("[wechat] Adapter connected, running event loop...")
                loop.run_forever()
            except Exception as e:
                logger.error(f"[wechat] Adapter error: {e}")
                traceback.print_exc()
            finally:
                try:
                    loop.run_until_complete(adapter.disconnect())
                except Exception:
                    pass
                loop.close()
                with _adapter_lock:
                    _adapter_instance = None
                    _adapter_loop = None

        _adapter_thread = Thread(target=_run_adapter, daemon=True, name="wechat-adapter")
        _adapter_thread.start()

        # 短暂等待让 connect() 有机会启动
        time.sleep(1.0)

        return {
            "status": "started",
            "account_id": os.environ.get("WEIXIN_ACCOUNT_ID", ""),
        }


def stop_adapter() -> Dict[str, Any]:
    """停止 WeixinAdapter 长轮询适配器。"""
    global _adapter_instance, _adapter_loop, _adapter_thread

    with _adapter_lock:
        if _adapter_instance is None or _adapter_loop is None:
            return {"status": "not_running"}

        loop = _adapter_loop
        adapter = _adapter_instance

    # 在适配器的事件循环中调度 disconnect
    future = asyncio.run_coroutine_threadsafe(adapter.disconnect(), loop)
    try:
        future.result(timeout=10)
    except Exception as e:
        logger.warning(f"[wechat] Disconnect error: {e}")

    # 停止事件循环
    loop.call_soon_threadsafe(loop.stop)

    if _adapter_thread:
        _adapter_thread.join(timeout=5)

    with _adapter_lock:
        _adapter_instance = None
        _adapter_loop = None
        _adapter_thread = None

    return {"status": "stopped"}


def get_adapter_status() -> Dict[str, Any]:
    """获取适配器运行状态。"""
    with _adapter_lock:
        running = _adapter_instance is not None and _adapter_loop is not None

    creds = get_wechat_credentials()
    return {
        "adapter_running": running,
        "credentials": creds,
    }


# ---------------------------------------------------------------------------
# 兼容旧 Webhook 接口
# ---------------------------------------------------------------------------

def parse_wechat_message(payload: dict) -> str:
    """提取任意微信消息体中的文本。"""
    if "text" in payload:
        return str(payload["text"]).strip()
    if "content" in payload:
        return str(payload["content"]).strip()
    return ""


def construct_wechat_reply(request_payload: dict, ai_response: str) -> dict:
    """依照请求构建回复。"""
    return {
        "ok": True,
        "reply": ai_response,
        "fromUser": request_payload.get("toUser", ""),
        "toUser": request_payload.get("fromUser", ""),
    }
