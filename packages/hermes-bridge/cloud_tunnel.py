"""
cloud_tunnel.py - 云端 WebSocket 反连隧道

QeeClaw Server (bridge_server.py) 启动后，通过此模块主动连接到
云端后端的 /api/openclaw/ws 端点，注册为一个在线的网关。

云端后端通过此 WebSocket 隧道向本地 bridge 下发 RPC 指令（QR 二维码、
聊天消息、知识库查询等），bridge 执行后将结果通过相同的 WebSocket 返回。

协议规格：
  Request (Cloud → Bridge):
    {"type": "<request_type>", "id": "<uuid>", "traceId": "...", "payload": {...}}
  Response (Bridge → Cloud):
    {"type": "<response_type>", "id": "<uuid>", "payload": {"ok": true, "payload": {...}}}
  Heartbeat:
    Bridge → Cloud: {"type": "ping"}
    Cloud → Bridge: {"type": "pong"}
  Capabilities:
    Bridge → Cloud: {"type": "runtime.capabilities", "payload": {...}}
"""

import asyncio
import json
import logging
import os
import time
import traceback
from threading import Thread, Lock
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------
_tunnel_thread: Optional[Thread] = None
_tunnel_loop: Optional[asyncio.AbstractEventLoop] = None
_tunnel_lock = Lock()
_connected = False
_last_connect_time: Optional[float] = None
_last_disconnect_time: Optional[float] = None
_reconnect_count = 0


def get_tunnel_status() -> Dict[str, Any]:
    """返回隧道连接状态。"""
    return {
        "connected": _connected,
        "cloud_url": os.environ.get("NEXUS_URL", ""),
        "has_api_key": bool(os.environ.get("NEXUS_API_KEY", "")),
        "last_connect_time": _last_connect_time,
        "last_disconnect_time": _last_disconnect_time,
        "reconnect_count": _reconnect_count,
    }


# ---------------------------------------------------------------------------
# RPC 处理器
# ---------------------------------------------------------------------------

def _handle_qr_start(payload: dict) -> dict:
    """处理 channel.qr.start.request。"""
    try:
        from wechat_gateway import start_qr_login
        result = start_qr_login()
        # 包装为 _unwrap_gateway_rpc_payload 期望的格式
        return {"ok": True, "payload": result}
    except Exception as e:
        logger.error(f"[CloudTunnel] QR start failed: {e}")
        return {"ok": False, "error": str(e)}


def _handle_qr_status(payload: dict) -> dict:
    """处理 channel.qr.status.request。"""
    try:
        from wechat_gateway import get_qr_login_status
        result = get_qr_login_status()
        return {"ok": True, "payload": result}
    except Exception as e:
        logger.error(f"[CloudTunnel] QR status failed: {e}")
        return {"ok": False, "error": str(e)}


def _handle_chat_request(payload: dict) -> dict:
    """处理 chat.request — 调用 hermes-agent 执行对话。"""
    try:
        text = payload.get("text", "")
        if not text:
            return {"ok": True, "payload": {"text": "", "attachments": []}}

        # 尝试通过 bridge_server 的 invoke 逻辑处理
        from hermes_invoke import invoke_hermes
        result = invoke_hermes(text)
        if isinstance(result, str):
            return {"ok": True, "payload": {"text": result, "attachments": []}}
        if isinstance(result, dict):
            return {"ok": True, "payload": {
                "text": result.get("text", result.get("response", str(result))),
                "attachments": result.get("attachments", []),
            }}
        return {"ok": True, "payload": {"text": str(result), "attachments": []}}
    except ImportError:
        # hermes_invoke 不一定存在，返回提示
        return {"ok": False, "error": "Hermes invoke module not available on this bridge"}
    except Exception as e:
        logger.error(f"[CloudTunnel] Chat request failed: {e}")
        return {"ok": False, "error": str(e)}


# 请求类型 → 处理函数映射
_RPC_HANDLERS: Dict[str, Callable[[dict], dict]] = {
    "channel.qr.start.request": _handle_qr_start,
    "channel.qr.status.request": _handle_qr_status,
    "chat.request": _handle_chat_request,
}


def _get_response_type(request_type: str) -> str:
    """将 request 类型转换为 response 类型。"""
    if request_type.endswith(".request"):
        return request_type[:-len(".request")] + ".response"
    return request_type + ".response"


# ---------------------------------------------------------------------------
# WebSocket 客户端主循环
# ---------------------------------------------------------------------------

async def _ws_main_loop(cloud_url: str, token: str):
    """
    WebSocket 客户端主循环。连接到云端后端，处理 RPC 消息。
    自动重连，指数退避。
    """
    global _connected, _last_connect_time, _last_disconnect_time, _reconnect_count

    # 构建 WebSocket URL
    ws_base = cloud_url.rstrip("/")
    if ws_base.startswith("https://"):
        ws_base = ws_base.replace("https://", "wss://", 1)
    elif ws_base.startswith("http://"):
        ws_base = ws_base.replace("http://", "ws://", 1)
    elif not ws_base.startswith("ws://") and not ws_base.startswith("wss://"):
        ws_base = "wss://" + ws_base

    ws_url = f"{ws_base}/api/openclaw/ws?token={token}"
    display_url = f"{ws_base}/api/openclaw/ws?token=***{token[-6:]}" if len(token) > 6 else ws_url

    backoff = 2.0
    max_backoff = 60.0

    while True:
        logger.info(f"[CloudTunnel] Connecting to {display_url} ...")
        try:
            import websockets
            async with websockets.connect(
                ws_url,
                ping_interval=None,  # 我们自己发 ping
                ping_timeout=None,
                close_timeout=5,
                max_size=10 * 1024 * 1024,  # 10MB
            ) as ws:
                _connected = True
                _last_connect_time = time.time()
                backoff = 2.0
                logger.info(f"[CloudTunnel] Connected to cloud backend")

                # 发送能力声明
                await ws.send(json.dumps({
                    "type": "runtime.capabilities",
                    "payload": {
                        "official_wechat_plugin_available": True,
                        "hermes_bridge": True,
                        "bridge_version": "0.2.0",
                    },
                }, ensure_ascii=False))

                # 启动心跳任务
                heartbeat_task = asyncio.create_task(_heartbeat_loop(ws))
                try:
                    await _message_loop(ws)
                finally:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

        except ImportError:
            logger.error("[CloudTunnel] websockets module not installed. Run: pip install websockets")
            _connected = False
            return  # 不重连，缺依赖没法用
        except Exception as e:
            logger.warning(f"[CloudTunnel] Connection lost: {type(e).__name__}: {e}")
        finally:
            _connected = False
            _last_disconnect_time = time.time()
            _reconnect_count += 1

        logger.info(f"[CloudTunnel] Reconnecting in {backoff:.0f}s ... (attempt #{_reconnect_count})")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.5, max_backoff)


async def _heartbeat_loop(ws):
    """每 20 秒发一次 ping。"""
    try:
        while True:
            await asyncio.sleep(20)
            await ws.send(json.dumps({"type": "ping"}))
    except asyncio.CancelledError:
        raise
    except Exception:
        pass


async def _message_loop(ws):
    """接收并处理云端消息。"""
    async for raw_data in ws:
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.warning(f"[CloudTunnel] Invalid JSON: {str(raw_data)[:200]}")
            continue

        msg_type = data.get("type", "")

        # 忽略心跳回复
        if msg_type == "pong":
            continue

        # 处理 RPC 请求
        request_id = data.get("id", "")
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        handler = _RPC_HANDLERS.get(msg_type)
        if handler:
            # 在线程池中执行（避免阻塞 event loop）
            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(None, handler, payload)
            except Exception as e:
                logger.error(f"[CloudTunnel] Handler error for {msg_type}: {e}")
                result = {"ok": False, "error": str(e)}

            response_type = _get_response_type(msg_type)
            response_frame = json.dumps({
                "type": response_type,
                "id": request_id,
                "payload": result,
            }, ensure_ascii=False)
            await ws.send(response_frame)
        else:
            if msg_type and not msg_type.endswith(".response"):
                logger.debug(f"[CloudTunnel] Unhandled message type: {msg_type}")


# ---------------------------------------------------------------------------
# 启动 / 停止
# ---------------------------------------------------------------------------

def start_tunnel():
    """
    启动云端隧道（后台线程）。

    需要以下环境变量：
      NEXUS_URL     - 云端平台地址，例如 https://paas.qeeshu.com
      NEXUS_API_KEY - 平台上创建的 API Key（同聊天接口使用的 Key）
    """
    global _tunnel_thread, _tunnel_loop

    cloud_url = os.environ.get("NEXUS_URL", "").strip()
    token = os.environ.get("NEXUS_API_KEY", "").strip()

    if not cloud_url or not token:
        logger.info("[CloudTunnel] NEXUS_URL or NEXUS_API_KEY not set, cloud tunnel disabled")
        return False

    with _tunnel_lock:
        if _tunnel_thread is not None and _tunnel_thread.is_alive():
            logger.info("[CloudTunnel] Tunnel already running")
            return True

    def _run():
        global _tunnel_loop
        _tunnel_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_tunnel_loop)
        try:
            _tunnel_loop.run_until_complete(_ws_main_loop(cloud_url, token))
        except Exception as e:
            logger.error(f"[CloudTunnel] Fatal error: {e}")
            traceback.print_exc()
        finally:
            _tunnel_loop.close()
            _tunnel_loop = None

    with _tunnel_lock:
        _tunnel_thread = Thread(target=_run, daemon=True, name="cloud-tunnel")
        _tunnel_thread.start()

    logger.info(f"[CloudTunnel] Tunnel started → {cloud_url}")
    return True


def stop_tunnel():
    """停止云端隧道。"""
    global _tunnel_thread, _tunnel_loop

    with _tunnel_lock:
        if _tunnel_loop is not None:
            _tunnel_loop.call_soon_threadsafe(_tunnel_loop.stop)
        _tunnel_thread = None
        _tunnel_loop = None
    logger.info("[CloudTunnel] Tunnel stopped")
