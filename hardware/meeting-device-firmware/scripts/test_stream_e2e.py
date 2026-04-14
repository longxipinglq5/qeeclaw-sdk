#!/usr/bin/env python3
"""
会议设备实时音频流端到端测试脚本

流程：
1. 注册设备
2. 通过 WebSocket 上传音频
3. 轮询查询任务结果
"""

import argparse
import asyncio
import json
import os
import random
import struct
import time
import wave
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    import websockets
except ImportError:
    print("请先安装 websockets: pip install websockets")
    raise SystemExit(1)


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
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


def print_summary(text: str) -> None:
    print(f"{Colors.MAGENTA}{text}{Colors.RESET}")


def generate_test_mac() -> str:
    return ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)])


def build_ws_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/meeting-device/stream"


def read_wav_file(file_path: Path) -> tuple[bytes, int, int, int]:
    with wave.open(str(file_path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        pcm_data = wav.readframes(wav.getnframes())
    return pcm_data, sample_rate, channels, sample_width


def resample_to_16k_mono(pcm_data: bytes, src_rate: int, channels: int, sample_width: int) -> bytes:
    if src_rate == 16000 and channels == 1 and sample_width == 2:
        return pcm_data

    if channels == 2:
        samples = []
        for index in range(0, len(pcm_data), sample_width * channels):
            samples.append(pcm_data[index : index + sample_width])
        pcm_data = b"".join(samples)

    if src_rate != 16000:
        samples = struct.unpack(f"<{len(pcm_data) // 2}h", pcm_data)
        ratio = 16000 / src_rate
        new_length = int(len(samples) * ratio)
        resampled = []
        for index in range(new_length):
            src_index = index / ratio
            left = int(src_index)
            right = min(left + 1, len(samples) - 1)
            frac = src_index - left
            value = int(samples[left] * (1 - frac) + samples[right] * frac)
            resampled.append(value)
        pcm_data = struct.pack(f"<{len(resampled)}h", *resampled)

    return pcm_data


def resolve_audio_file(explicit_path: str | None) -> Path | None:
    if explicit_path:
        return Path(explicit_path)

    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    env_audio = os.environ.get("QEECLAW_MEETING_DEVICE_SAMPLE_AUDIO")
    candidates = [
        Path(env_audio).expanduser() if env_audio else None,
        Path.cwd() / "sample.wav",
        project_dir / "sample.wav",
        script_dir / "sample.wav",
        script_dir / "output" / "sample.wav",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if candidate.exists():
            return candidate
    return None


async def stream_audio_file(
    ws_url: str,
    api_base_url: str,
    audio_file: Path,
    mac_address: str,
    meeting_name: str,
    silence_timeout: float,
    chunk_duration_ms: int = 100,
) -> dict:
    result = {"success": False, "task_id": None, "transcript": None, "meeting_summary": None}

    print_header("Step 1: 注册设备")
    try:
        response = requests.post(
            f"{api_base_url}/api/meeting-device/register",
            json={"mac_address": mac_address, "device_name": "E2E测试设备"},
            timeout=10,
        )
        data = response.json()
        if response.status_code != 200 or data.get("code") != 0:
            print_error(f"设备注册失败: {data.get('message')}")
            return result
        print_success(f"设备注册成功! 绑定码: {data.get('data', {}).get('bind_code')}")
    except Exception as error:
        print_error(f"设备注册失败: {error}")
        return result

    print_header("Step 2: 读取音频文件")
    print_info(f"音频文件: {audio_file}")
    if audio_file.suffix.lower() != ".wav":
        print_error(f"不支持的文件格式: {audio_file.suffix}")
        return result

    pcm_data, sample_rate, channels, sample_width = read_wav_file(audio_file)
    print_info(f"原始格式: {sample_rate}Hz, {channels}ch, {sample_width * 8}bit")
    pcm_data = resample_to_16k_mono(pcm_data, sample_rate, channels, sample_width)
    print_success(f"已转换为 16kHz 单声道, 大小: {len(pcm_data) / 1024:.1f} KB")

    print_header("Step 3: WebSocket 实时上传")
    url = f"{ws_url}?mac_address={mac_address}&meeting_name={meeting_name}&silence_timeout={silence_timeout}"
    print_info(f"连接 URL: {url}")

    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            print_recv(f"收到: {json.dumps(ready, ensure_ascii=False)}")
            if ready.get("type") != "ready":
                print_error(f"意外的消息类型: {ready.get('type')}")
                return result

            task_id = ready.get("task_id")
            result["task_id"] = task_id
            bytes_per_ms = 16000 * 2 / 1000
            chunk_size = int(bytes_per_ms * chunk_duration_ms)
            total_bytes = 0

            print_info(f"开始发送音频数据 (每块 {chunk_duration_ms}ms)...")
            started_at = time.time()
            for index in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[index : index + chunk_size]
                if not chunk:
                    continue
                await ws.send(chunk)
                total_bytes += len(chunk)
                progress = total_bytes / len(pcm_data) * 100
                print(f"\r  进度: {progress:.1f}% ({total_bytes / 1024:.1f} KB)", end="", flush=True)
                await asyncio.sleep(chunk_duration_ms / 1000 * 0.5)
                try:
                    await asyncio.wait_for(ws.recv(), timeout=0.01)
                except asyncio.TimeoutError:
                    pass

            print()
            print_success(f"音频发送完成! 共 {total_bytes / 1024:.1f} KB, 耗时 {time.time() - started_at:.1f}s")
            await ws.send(json.dumps({"type": "end"}))
            try:
                final_data = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                print_recv(f"收到: {json.dumps(final_data, ensure_ascii=False)}")
            except asyncio.TimeoutError:
                print_info("等待完成消息超时，继续查询结果...")
    except Exception as error:
        print_error(f"WebSocket 错误: {error}")
        return result

    print_header("Step 4: 等待处理完成")
    started_wait = time.time()
    while time.time() - started_wait < 120:
        try:
            response = requests.get(
                f"{api_base_url}/api/meeting-device/result/{result['task_id']}",
                timeout=10,
            )
            data = response.json()
            if response.status_code == 200 and data.get("code") == 0:
                task_data = data.get("data", {})
                status = task_data.get("status")
                elapsed = time.time() - started_wait
                print(f"\r  状态: {status} (已等待 {elapsed:.0f}s)", end="", flush=True)
                if status == "completed":
                    print()
                    print_success("任务处理完成!")
                    result["success"] = True
                    result["transcript"] = task_data.get("transcript")
                    result["meeting_summary"] = task_data.get("meeting_summary")
                    break
                if status == "failed":
                    print()
                    print_error(f"任务处理失败: {task_data.get('error_message')}")
                    break
        except Exception as error:
            print_error(f"查询失败: {error}")
        await asyncio.sleep(5)
    else:
        print()
        print_error("等待超时")

    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="会议设备实时音频流端到端测试")
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
    parser.add_argument("--audio", type=str, help="音频文件路径")
    parser.add_argument("--mac", type=str, help="指定 MAC 地址")
    parser.add_argument("--timeout", type=float, default=30, help="静默超时时间（秒）")
    args = parser.parse_args()

    api_base_url = args.api_base_url.rstrip("/")
    ws_url = args.ws_url or build_ws_url(api_base_url)
    mac_address = args.mac or generate_test_mac()
    audio_file = resolve_audio_file(args.audio)

    if not audio_file or not audio_file.exists():
        print_error("音频文件不存在，请使用 --audio 指定 WAV 文件")
        print_info("你也可以先运行: python scripts/generate_sample_wav.py")
        return

    print(
        f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║       会议设备实时音频流 - 端到端测试                             ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.YELLOW}WebSocket: {ws_url}{Colors.RESET}
{Colors.YELLOW}API: {api_base_url}{Colors.RESET}
{Colors.YELLOW}MAC 地址: {mac_address}{Colors.RESET}
{Colors.YELLOW}音频文件: {audio_file}{Colors.RESET}
"""
    )

    result = await stream_audio_file(
        ws_url=ws_url,
        api_base_url=api_base_url,
        audio_file=audio_file,
        mac_address=mac_address,
        meeting_name="E2E测试会议",
        silence_timeout=args.timeout,
    )

    print_header("测试结果")
    if result["success"]:
        print_success("端到端测试通过!")
        print()
        print_summary("转写结果:")
        transcript = result.get("transcript")
        if transcript:
            try:
                transcript_data = json.loads(transcript)
                for item in transcript_data[:5]:
                    print(f"  [{item.get('begin_time', 0) / 1000:.1f}s] {item.get('text', '')}")
                if len(transcript_data) > 5:
                    print(f"  ... (共 {len(transcript_data)} 条)")
            except Exception:
                print(f"  {str(transcript)[:500]}...")
        else:
            print("  (无)")
        print()
        print_summary("会议纪要:")
        summary = result.get("meeting_summary")
        if summary:
            print(str(summary)[:1000])
        else:
            print("  (无)")
    else:
        print_error("端到端测试失败!")
        if result.get("task_id"):
            print_info(f"任务ID: {result['task_id']}")


if __name__ == "__main__":
    asyncio.run(main())
