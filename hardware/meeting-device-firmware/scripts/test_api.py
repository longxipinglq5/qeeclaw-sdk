#!/usr/bin/env python3
"""
会议设备 HTTP API 联调脚本

默认连接本地开发地址：
- http://127.0.0.1:8000
"""

import argparse
import json
import os
import random
import struct
from pathlib import Path

import requests


def generate_test_mac() -> str:
    return ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)])


def normalize_api_base_url(value: str) -> str:
    base = value.rstrip("/")
    if base.endswith("/api"):
        return base
    return f"{base}/api"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
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


def test_connection(base_url: str) -> bool:
    print_header("测试网络连接")
    try:
        response = requests.get(base_url.replace("/api", ""), timeout=10)
        print_success(f"服务器可访问 (状态码: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError as error:
        print_error(f"无法连接到服务器: {error}")
        return False
    except requests.exceptions.Timeout:
        print_error("连接超时")
        return False


def test_register(base_url: str, mac_address: str) -> dict | None:
    print_header("1. 测试设备注册 (/meeting-device/register)")

    url = f"{base_url}/meeting-device/register"
    payload = {
        "mac_address": mac_address,
        "device_name": "API测试设备",
        "firmware_version": "1.0.0-test",
    }

    print_info(f"请求 URL: {url}")
    print_info(f"请求数据: {json.dumps(payload, ensure_ascii=False)}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        print_info(f"状态码: {response.status_code}")
        data = response.json()
        print_info(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if data.get("code") == 0:
            print_success("设备注册成功!")
            return data.get("data", {})
        print_error(f"设备注册失败: {data.get('message')}")
        return None
    except (requests.exceptions.RequestException, json.JSONDecodeError) as error:
        print_error(f"请求失败: {error}")
        return None


def test_heartbeat(base_url: str, mac_address: str) -> bool:
    print_header("2. 测试设备心跳 (/meeting-device/heartbeat)")

    url = f"{base_url}/meeting-device/heartbeat"
    payload = {
        "mac_address": mac_address,
        "status": "online",
        "local_ip": "192.168.1.36",
        "lan_ip": "192.168.1.36",
        "local_host": "192.168.1.36",
    }

    print_info(f"请求 URL: {url}")
    print_info(f"请求数据: {json.dumps(payload, ensure_ascii=False)}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        print_info(f"状态码: {response.status_code}")
        data = response.json()
        print_info(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if data.get("code") == 0:
            print_success("心跳发送成功!")
            return True
        print_error(f"心跳失败: {data.get('message')}")
        return False
    except (requests.exceptions.RequestException, json.JSONDecodeError) as error:
        print_error(f"请求失败: {error}")
        return False


def test_status(base_url: str, mac_address: str) -> dict | None:
    print_header("3. 测试设备状态查询 (/meeting-device/status)")

    url = f"{base_url}/meeting-device/status"
    params = {"mac_address": mac_address}

    print_info(f"请求 URL: {url}?mac_address={mac_address}")

    try:
        response = requests.get(url, params=params, timeout=30)
        print_info(f"状态码: {response.status_code}")
        data = response.json()
        print_info(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if data.get("code") == 0:
            print_success("状态查询成功!")
            return data.get("data", {})
        print_error(f"状态查询失败: {data.get('message')}")
        return None
    except (requests.exceptions.RequestException, json.JSONDecodeError) as error:
        print_error(f"请求失败: {error}")
        return None


def test_upload_audio(base_url: str, mac_address: str) -> dict | None:
    print_header("4. 测试音频上传 (/meeting-device/upload-audio)")

    url = f"{base_url}/meeting-device/upload-audio"
    test_audio_path = Path("/tmp/test_meeting_audio.wav")

    sample_rate = 16000
    duration_seconds = 1
    num_samples = sample_rate * duration_seconds
    wav_header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + num_samples * 2,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        num_samples * 2,
    )
    audio_data = b"\x00\x00" * num_samples

    with open(test_audio_path, "wb") as file:
        file.write(wav_header)
        file.write(audio_data)

    print_info(f"请求 URL: {url}")
    print_info(f"测试音频文件: {test_audio_path} ({test_audio_path.stat().st_size} bytes)")

    try:
        with open(test_audio_path, "rb") as audio_file:
            response = requests.post(
                url,
                files={"audio_file": ("test_audio.wav", audio_file, "audio/wav")},
                data={
                    "mac_address": mac_address,
                    "meeting_name": "API测试会议",
                    "enable_summary": "true",
                },
                timeout=60,
            )

        print_info(f"状态码: {response.status_code}")
        data = response.json()
        print_info(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if data.get("code") == 0:
            print_success("音频上传成功!")
            return data.get("data", {})
        print_error(f"音频上传失败: {data.get('message')}")
        return None
    except (requests.exceptions.RequestException, json.JSONDecodeError) as error:
        print_error(f"请求失败: {error}")
        return None
    finally:
        if test_audio_path.exists():
            test_audio_path.unlink()


def test_result(base_url: str, task_id: str) -> dict | None:
    print_header("5. 测试结果查询 (/meeting-device/result/{task_id})")

    url = f"{base_url}/meeting-device/result/{task_id}"
    print_info(f"请求 URL: {url}")

    try:
        response = requests.get(url, timeout=30)
        print_info(f"状态码: {response.status_code}")
        data = response.json()
        print_info(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
        if data.get("code") == 0:
            status = data.get("data", {}).get("status")
            print_success(f"结果查询成功! 任务状态: {status}")
            return data.get("data", {})
        print_error(f"结果查询失败: {data.get('message')}")
        return None
    except (requests.exceptions.RequestException, json.JSONDecodeError) as error:
        print_error(f"请求失败: {error}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="会议设备 HTTP API 联调脚本")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("QEECLAW_MEETING_DEVICE_API_BASE_URL", "http://127.0.0.1:8000"),
        help="平台 HTTP 地址，支持带或不带 /api，默认 http://127.0.0.1:8000",
    )
    parser.add_argument("--mac", type=str, help="指定测试 MAC 地址")
    args = parser.parse_args()

    base_url = normalize_api_base_url(args.base_url)
    test_mac = args.mac or generate_test_mac()

    print(
        f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║           会议设备 HTTP API 联调脚本                             ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.YELLOW}服务器地址: {base_url}{Colors.RESET}
{Colors.YELLOW}测试 MAC 地址: {test_mac}{Colors.RESET}
"""
    )

    results = {
        "连接测试": False,
        "设备注册": False,
        "设备心跳": False,
        "状态查询": False,
        "音频上传": False,
        "结果查询": False,
    }

    if not test_connection(base_url):
      print_error("\n网络连接失败，终止测试")
      return
    results["连接测试"] = True

    register_result = test_register(base_url, test_mac)
    if register_result:
        results["设备注册"] = True

    if test_heartbeat(base_url, test_mac):
        results["设备心跳"] = True

    if test_status(base_url, test_mac):
        results["状态查询"] = True

    upload_result = test_upload_audio(base_url, test_mac)
    task_id = None
    if upload_result:
        results["音频上传"] = True
        task_id = upload_result.get("task_id")

    if task_id and test_result(base_url, task_id):
        results["结果查询"] = True

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
    main()
