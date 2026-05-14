#!/usr/bin/env python3
"""DashScope Bailian image generation helpers for Hermes bridge."""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Mapping, Optional


DEFAULT_MODEL = "wan2.7-image-pro"
DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com"
DEFAULT_SIZE = "1024*1024"
SIZE_MAP = {
    "1:1": "2048*2048",
    "16:9": "2560*1440",
    "4:3": "2048*1536",
    "3:4": "1536*2048",
    "4:5": "1440*1800",
    "1024x1024": "1024*1024",
    "1024*1024": "1024*1024",
}
ALLOWED_INPUT_MODELS = {DEFAULT_MODEL}


def _read_bool_env(name: str, fallback: bool, environ: Mapping[str, str] = os.environ) -> bool:
    value = environ.get(name)
    if value is None:
        return fallback
    normalized = str(value).strip().lower()
    if normalized in ("true", "1", "yes", "on"):
        return True
    if normalized in ("false", "0", "no", "off"):
        return False
    return fallback


def resolve_api_key(environ: Mapping[str, str] = os.environ) -> Optional[str]:
    return environ.get("DASHSCOPE_API_KEY") or environ.get("BAILIAN_API_KEY")


def resolve_endpoint(environ: Mapping[str, str] = os.environ) -> str:
    return environ.get("BAILIAN_IMAGE_ENDPOINT", DEFAULT_ENDPOINT)


def normalize_size(size: Any, environ: Mapping[str, str] = os.environ) -> str:
    value = str(size or "").strip()
    if not value:
        return environ.get("BAILIAN_IMAGE_DEFAULT_SIZE", DEFAULT_SIZE)
    return SIZE_MAP.get(value, value)


def clamp_image_count(count: Any) -> int:
    try:
        parsed = int(count)
    except (TypeError, ValueError):
        return 1
    return min(4, max(1, parsed))


def normalize_model(model: Any, environ: Mapping[str, str] = os.environ) -> str:
    env_model = environ.get("BAILIAN_IMAGE_MODEL")
    if env_model:
        return env_model
    model_value = str(model or "").strip()
    if model_value in ALLOWED_INPUT_MODELS:
        return model_value
    return DEFAULT_MODEL


def read_timeout_seconds(environ: Mapping[str, str] = os.environ) -> float:
    try:
        timeout_ms = int(environ.get("BAILIAN_IMAGE_TIMEOUT_MS", "300000"))
    except ValueError:
        timeout_ms = 300000
    if timeout_ms <= 0:
        timeout_ms = 300000
    return timeout_ms / 1000


def build_image_payload(input_body: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(input_body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Missing image prompt.")

    return {
        "model": normalize_model(input_body.get("model")),
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                },
            ],
        },
        "parameters": {
            "size": normalize_size(input_body.get("size")),
            "n": clamp_image_count(input_body.get("n")),
            "watermark": _read_bool_env("BAILIAN_IMAGE_WATERMARK", False),
            "thinking_mode": _read_bool_env("BAILIAN_IMAGE_THINKING_MODE", True),
        },
    }


def _build_error_message(status: int, raw: Dict[str, Any]) -> str:
    parts = [f"DashScope image request failed: {status}"]
    if raw.get("code"):
        parts.append(f"code={raw.get('code')}")
    request_id = raw.get("request_id") or raw.get("requestId")
    if request_id:
        parts.append(f"requestId={request_id}")
    if raw.get("message"):
        parts.append(f"message={raw.get('message')}")
    return " ".join(parts)


def normalize_image_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    choices = ((raw.get("output") or {}).get("choices") or [])
    urls: List[str] = []

    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        content = (message or {}).get("content") or []
        for item in content:
            if isinstance(item, dict) and item.get("image"):
                urls.append(str(item["image"]))

    if not urls:
        raise ValueError("百炼图片模型未返回图片地址")

    return {
        "model": raw.get("model") or DEFAULT_MODEL,
        "imageUrl": urls[0],
        "data": [{"url": url} for url in urls],
        "requestId": raw.get("request_id") or raw.get("requestId"),
        "usage": raw.get("usage") or {},
        "raw": raw,
    }


def post_image_generation(
    endpoint: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout_seconds: float,
) -> Dict[str, Any]:
    endpoint_base = endpoint.rstrip("/")
    url = f"{endpoint_base}/api/v1/services/aigc/multimodal-generation/generation"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_text = response.read().decode("utf-8")
            raw = json.loads(raw_text) if raw_text else {}
            if raw.get("code"):
                raise RuntimeError(_build_error_message(response.status, raw))
            return raw
    except urllib.error.HTTPError as exc:
        raw_text = exc.read().decode("utf-8") if exc.fp else ""
        try:
            raw = json.loads(raw_text) if raw_text else {}
        except json.JSONDecodeError:
            raw = {"message": raw_text}
        raise RuntimeError(_build_error_message(exc.code, raw)) from exc
