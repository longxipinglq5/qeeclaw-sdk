#!/usr/bin/env python3
"""
会议设备实时音频流 WebSocket 测试脚本

默认连接本地开发地址：
- http://127.0.0.1:8000
- ws://127.0.0.1:8000/api/meeting-device/stream
"""

import argparse
import asyncio
import json
import math
import os
import random
import struct
import time
from urllib.parse import urlparse

import requests

try:
    import websockets
except ImportError:
    print("请先安装 websockets: pip install websockets")
    raise SystemExit(1)


def build_ws_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/meeting-device/stream"


def generate_test_mac() -> str:
    return ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)])


def generate_audio_data(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    num_samples = int(sample_rate * duration_seconds)
    chunks: list[bytes] = []
    frequency = 440
    for index in range(num_samples):
        if (index // (sample_rate // 2)) % 2 == 0:
            sample = int(16000 * math.sin(2 * math.pi * frequency * index / sample_rate))
        else:
            sample = 0
        sample = max(-32768, min(32767, sample))
        chunks.append(struct.pack("<h", sample))
    return b"".join(chunks)


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


def print_success(text: str) -> None:
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    print(f"{Colors.YELLOW}→ {text}{Colors.RESET}")


def print_recv(text: str) -> None:
    print(f"{Colors.CYAN}← {text}{Colors.RESET}")


def register_device(api_base_url: str, mac_address: str) -> bool:
    print_header("预备：注册测试设备")
    try:
        response = requests.post(
            f"{api_base_url.rstrip('/')}/api/meeting-device/register",
            json={"mac_address": mac_address, "device_name": "流测试设备"},
            timeout=10,
        )
        data = response.json()
        if response.status_code == 200 and data.get("code") == 0:
            print_success(f"设备注册成功! 绑定码: {data.get('data', {}).get('bind_code')}")
            return True
        print_error(f"设备注册失败: {data.get('message')}")
        return False
    except Exception as error:
        print_error(f"设备注册失败: {error}")
        return False


async def test_stream_connection(ws_url: str, mac_address: str) -> dict | None:
    print_header("测试 WebSocket 连接")
    url = f"{ws_url}?mac_address={mac_address}&meeting_name=连接测试&silence_timeout=10"
    print_info(f"连接 URL: {url}")

    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            print_success("WebSocket 连接成功!")
            message = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(message)
            print_recv(f"收到消息: {json.dumps(data, ensure_ascii=False)}")
            if data.get("type") == "ready":
                print_success(f"会话就绪! task_id: {data.get('task_id')}")
                return data
            print_error(f"意外的消息类型: {data.get('type')}")
            return None
    except Exception as error:
        print_error(f"连接失败: {error}")
        return None


async def test_stream_audio(ws_url: str, mac_address: str, duration: float) -> dict | None:
    print_header("测试实时音频流上传")
    url = f"{ws_url}?mac_address={mac_address}&meeting_name=音频流测试&silence_timeout=5"
    print_info(f"连接 URL: {url}")
    print_info(f"计划发送 {duration} 秒音频数据")

    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            print_recv(f"收到: {json.dumps(ready, ensure_ascii=False)}")
            if ready.get("type") != "ready":
                print_error(f"意外的消息类型: {ready.get('type')}")
                return None

            task_id = ready.get("task_id")
            chunk_duration = 0.5
            chunks_to_send = int(duration / chunk_duration)
            total_bytes = 0

            for index in range(chunks_to_send):
                audio_chunk = generate_audio_data(chunk_duration)
                await ws.send(audio_chunk)
                total_bytes += len(audio_chunk)
                print(f"\r  已发送: {total_bytes / 1024:.1f} KB ({index + 1}/{chunks_to_send})", end="", flush=True)
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=0.1)
                    ack_data = json.loads(message)
                    if ack_data.get("type") != "ack":
                        print_recv(json.dumps(ack_data, ensure_ascii=False))
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(0.1)

            print()
            print_success(f"音频发送完成! 共 {total_bytes / 1024:.1f} KB")
            await ws.send(json.dumps({"type": "end"}))
            try:
                final_data = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                print_recv(json.dumps(final_data, ensure_ascii=False, indent=2))
                return final_data
            except asyncio.TimeoutError:
                print_error("等待完成消息超时")
                return {"task_id": task_id}
    except Exception as error:
        print_error(f"错误: {error}")
        return None


async def test_silence_timeout(ws_url: str, mac_address: str) -> dict | None:
    print_header("测试静默超时")
    url = f"{ws_url}?mac_address={mac_address}&meeting_name=静默测试&silence_timeout=5"
    print_info(f"连接 URL: {url}")

    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            print_recv(f"收到: {json.dumps(ready, ensure_ascii=False)}")
            if ready.get("type") != "ready":
                print_error(f"意外的消息类型: {ready.get('type')}")
                return None

            audio_chunk = generate_audio_data(1.0)
            await ws.send(audio_chunk)
            print_info(f"已发送 {len(audio_chunk)} 字节音频数据")
            print_info("等待静默超时...")
            started_at = time.time()

            while True:
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                elapsed = time.time() - started_at
                if message.get("type") == "timeout":
                    print_recv(f"收到超时消息 ({elapsed:.1f}秒后): {json.dumps(message, ensure_ascii=False)}")
                    print_success("静默超时测试通过!")
                    return message
                if message.get("type") == "ack":
                    print_recv(f"收到确认: bytes_received={message.get('bytes_received')}")
                else:
                    print_recv(json.dumps(message, ensure_ascii=False))
    except Exception as error:
        print_error(f"错误: {error}")
        return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="测试会议设备实时音频流 WebSocket API")
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("QEECLAW_MEETING_DEVICE_API_BASE_URL", "http://127.0.0.1:8000"),
        help="平台 HTTP 地址",
    )
    parser.add_argument(
        "--ws-url",
        default=os.environ.get("QEECLAW_MEETING_DEVICE_WS_URL"),
        help="WebSocket 地址，未提供时自动从 api-base-url 推导",
    )
    parser.add_argument("--mac", type=str, help="指定 MAC 地址")
    parser.add_argument("--test", choices=["connect", "audio", "timeout", "all"], default="all")
    parser.add_argument("--duration", type=float, default=5.0, help="音频测试时长（秒）")
    args = parser.parse_args()

    api_base_url = args.api_base_url.rstrip("/")
    ws_url = args.ws_url or build_ws_url(api_base_url)
    mac_address = args.mac or generate_test_mac()

    print(
        f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║       会议设备实时音频流 WebSocket API 测试                       ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.YELLOW}WebSocket 地址: {ws_url}{Colors.RESET}
{Colors.YELLOW}HTTP API 地址: {api_base_url}{Colors.RESET}
{Colors.YELLOW}测试 MAC 地址: {mac_address}{Colors.RESET}
"""
    )

    if not register_device(api_base_url, mac_address):
        return

    results: dict[str, bool] = {}
    if args.test in ["connect", "all"]:
        results["连接测试"] = await test_stream_connection(ws_url, mac_address) is not None
    if args.test in ["audio", "all"]:
        results["音频流测试"] = await test_stream_audio(ws_url, mac_address, args.duration) is not None
    if args.test in ["timeout", "all"]:
        results["静默超时测试"] = await test_silence_timeout(ws_url, mac_address) is not None

    if results:
        print_header("测试结果总结")
        passed = 0
        total = len(results)
        for test_name, result in results.items():
            if result:
                print_success(f"{test_name}: 通过")
                passed += 1
            else:
                print_error(f"{test_name}: 失败")
        print(f"\n{Colors.BOLD}总计: {passed}/{total} 项测试通过{Colors.RESET}")


if __name__ == "__main__":
    asyncio.run(main())
