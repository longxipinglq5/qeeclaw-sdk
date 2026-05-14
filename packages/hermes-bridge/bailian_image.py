#!/usr/bin/env python3
"""Image generation helpers for Hermes bridge.

The bridge exposes one OpenAI-compatible image endpoint while keeping provider
details here. OpenAI-compatible image APIs are the primary path, and DashScope
Bailian/Wanxiang is the fallback provider.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Mapping, Optional


DEFAULT_MODEL = "wan2.7-image-pro"
DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com"
DEFAULT_OPENAI_MODEL = "gpt-image-2"
DEFAULT_OPENAI_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_OPENAI_RESPONSE_FORMAT = "b64_json"
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


class ImageProviderError(RuntimeError):
    def __init__(self, message: str, *, provider: str, retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


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


def resolve_openai_api_key(environ: Mapping[str, str] = os.environ) -> Optional[str]:
    return environ.get("OPENAI_IMAGE_API_KEY") or environ.get("OPENAI_API_KEY")


def resolve_endpoint(environ: Mapping[str, str] = os.environ) -> str:
    return environ.get("BAILIAN_IMAGE_ENDPOINT", DEFAULT_ENDPOINT)


def resolve_openai_endpoint(environ: Mapping[str, str] = os.environ) -> str:
    return environ.get("OPENAI_IMAGE_ENDPOINT") or environ.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_ENDPOINT


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


def normalize_fallback_model(environ: Mapping[str, str] = os.environ) -> str:
    return environ.get("BAILIAN_IMAGE_MODEL") or DEFAULT_MODEL


def read_timeout_seconds(environ: Mapping[str, str] = os.environ) -> float:
    try:
        timeout_ms = int(environ.get("BAILIAN_IMAGE_TIMEOUT_MS", "300000"))
    except ValueError:
        timeout_ms = 300000
    if timeout_ms <= 0:
        timeout_ms = 300000
    return timeout_ms / 1000


def normalize_openai_model(model: Any, environ: Mapping[str, str] = os.environ) -> str:
    env_model = environ.get("OPENAI_IMAGE_MODEL")
    if env_model:
        return env_model
    model_value = str(model or "").strip()
    return model_value or DEFAULT_OPENAI_MODEL


def normalize_openai_response_format(environ: Mapping[str, str] = os.environ) -> str:
    value = str(environ.get("OPENAI_IMAGE_RESPONSE_FORMAT") or DEFAULT_OPENAI_RESPONSE_FORMAT).strip()
    return value or DEFAULT_OPENAI_RESPONSE_FORMAT


def _is_gpt_image_model(model: str) -> bool:
    return model.startswith("gpt-image-") or model in {"chatgpt-image-latest"}


def build_image_payload(input_body: Dict[str, Any], *, force_fallback_model: bool = False) -> Dict[str, Any]:
    prompt = str(input_body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Missing image prompt.")

    return {
        "model": normalize_fallback_model() if force_fallback_model else normalize_model(input_body.get("model")),
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


def build_openai_image_payload(input_body: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(input_body.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Missing image prompt.")

    model = normalize_openai_model(input_body.get("model"))
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": clamp_image_count(input_body.get("n")),
    }

    for source_key, target_key in (
        ("size", "size"),
        ("quality", "quality"),
        ("output_format", "output_format"),
        ("background", "background"),
        ("moderation", "moderation"),
        ("user", "user"),
    ):
        value = input_body.get(source_key)
        if value is not None:
            payload[target_key] = value

    if not _is_gpt_image_model(model):
        payload["response_format"] = normalize_openai_response_format()
    if "outputFormat" in input_body and "output_format" not in payload:
        payload["output_format"] = input_body["outputFormat"]

    return payload


def _build_error_message(status: int, raw: Dict[str, Any], *, provider_label: str = "DashScope") -> str:
    parts = [f"{provider_label} image request failed: {status}"]
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


def normalize_openai_image_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    data = raw.get("data") or []
    normalized_data: List[Dict[str, Any]] = []
    image_url: Optional[str] = None

    for item in data:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        if normalized.get("b64_json") and not normalized.get("b64Json"):
            normalized["b64Json"] = normalized.get("b64_json")
        if normalized.get("revised_prompt") and not normalized.get("revisedPrompt"):
            normalized["revisedPrompt"] = normalized.get("revised_prompt")
        if not image_url and normalized.get("url"):
            image_url = str(normalized.get("url"))
        normalized_data.append(normalized)

    if not normalized_data:
        raise ImageProviderError("OpenAI image provider did not return image data", provider="openai", retryable=True)

    result = {
        "model": raw.get("model") or DEFAULT_OPENAI_MODEL,
        "data": normalized_data,
        "requestId": raw.get("request_id") or raw.get("requestId") or raw.get("id"),
        "usage": raw.get("usage") or {},
        "raw": raw,
    }
    if raw.get("created") is not None:
        result["created"] = raw.get("created")
    if image_url:
        result["imageUrl"] = image_url
    return result


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
            try:
                raw = json.loads(raw_text) if raw_text else {}
            except json.JSONDecodeError as exc:
                raise ImageProviderError(
                    _build_error_message(response.status, {"message": "non-JSON response from provider"}, provider_label="DashScope"),
                    provider="bailian",
                    retryable=True,
                ) from exc
            if raw.get("code"):
                raise ImageProviderError(_build_error_message(response.status, raw), provider="bailian", retryable=True)
            return raw
    except urllib.error.HTTPError as exc:
        raw_text = exc.read().decode("utf-8") if exc.fp else ""
        try:
            raw = json.loads(raw_text) if raw_text else {}
        except json.JSONDecodeError:
            raw = {"message": raw_text}
        raise ImageProviderError(_build_error_message(exc.code, raw), provider="bailian", retryable=exc.code in (408, 409, 429) or exc.code >= 500) from exc


def post_openai_image_generation(
    endpoint: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout_seconds: float,
) -> Dict[str, Any]:
    endpoint_base = endpoint.rstrip("/")
    if endpoint_base.endswith("/images/generations"):
        url = endpoint_base
    else:
        url = f"{endpoint_base}/images/generations"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_text = response.read().decode("utf-8")
            try:
                return json.loads(raw_text) if raw_text else {}
            except json.JSONDecodeError as exc:
                raise ImageProviderError(
                    _build_error_message(response.status, {"message": "non-JSON response from provider"}, provider_label="OpenAI"),
                    provider="openai",
                    retryable=True,
                ) from exc
    except urllib.error.HTTPError as exc:
        raw_text = exc.read().decode("utf-8") if exc.fp else ""
        try:
            raw = json.loads(raw_text) if raw_text else {}
        except json.JSONDecodeError:
            raw = {"message": raw_text}
        message = _build_error_message(exc.code, raw, provider_label="OpenAI")
        raise ImageProviderError(message, provider="openai", retryable=exc.code in (408, 409, 429) or exc.code >= 500) from exc


def _with_provider_meta(
    result: Dict[str, Any],
    *,
    provider: str,
    fallback_used: bool,
    fallback_from: Optional[str] = None,
) -> Dict[str, Any]:
    merged = dict(result)
    merged["provider"] = provider
    merged["fallbackUsed"] = fallback_used
    if fallback_from:
        merged["fallbackFrom"] = fallback_from
    return merged


def generate_image(input_body: Dict[str, Any]) -> Dict[str, Any]:
    openai_key = resolve_openai_api_key()
    bailian_key = resolve_api_key()

    if not openai_key and not bailian_key:
        raise ImageProviderError("Missing image provider API key: set OPENAI_IMAGE_API_KEY/OPENAI_API_KEY or DASHSCOPE_API_KEY.", provider="image", retryable=False)

    primary_error: Optional[ImageProviderError] = None
    if openai_key:
        try:
            payload = build_openai_image_payload(input_body)
            raw = post_openai_image_generation(
                resolve_openai_endpoint(),
                openai_key,
                payload,
                read_timeout_seconds(),
            )
            return _with_provider_meta(
                normalize_openai_image_response(raw),
                provider="openai",
                fallback_used=False,
            )
        except ImageProviderError as exc:
            primary_error = exc
            if not exc.retryable:
                raise

    if bailian_key:
        payload = build_image_payload(input_body, force_fallback_model=True)
        raw = post_image_generation(
            resolve_endpoint(),
            bailian_key,
            payload,
            read_timeout_seconds(),
        )
        return _with_provider_meta(
            normalize_image_response(raw),
            provider="bailian",
            fallback_used=primary_error is not None,
            fallback_from=primary_error.provider if primary_error else None,
        )

    if primary_error:
        raise primary_error

    raise ImageProviderError("Missing image provider API key: set DASHSCOPE_API_KEY for fallback provider.", provider="image", retryable=False)
