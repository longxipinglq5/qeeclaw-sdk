"""QeeClaw Nexus image generation backend for Hermes."""

from __future__ import annotations

import base64
import datetime
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    success_response,
)

PROVIDER_NAME = "qeeclaw-nexus"
DEFAULT_MODEL = "gpt-image-2"

_SIZES = {
    "landscape": "1536x1024",
    "square": "1024x1024",
    "portrait": "1024x1536",
}


def _cache_dir() -> Path:
    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    path = home / "cache" / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_b64_image(b64_data: str, *, prefix: str = "qeeclaw_nexus") -> Path:
    raw = base64.b64decode(b64_data)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    path = _cache_dir() / f"{prefix}_{ts}_{short}.png"
    path.write_bytes(raw)
    return path


def _request_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_error_message(exc: urllib.error.HTTPError) -> str:
    detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
    return detail or str(exc)


class QeeClawNexusImageGenProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return "QeeClaw Nexus"

    def is_available(self) -> bool:
        return bool(os.environ.get("NEXUS_URL", "").strip())

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "id": DEFAULT_MODEL,
                "display": "GPT Image 2",
                "speed": "remote",
                "strengths": "Routed through the configured Nexus image API",
                "price": "platform billing",
            }
        ]

    def default_model(self) -> str:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> dict[str, Any]:
        return {
            "name": "QeeClaw Nexus",
            "badge": "bridge",
            "tag": "Uses the existing /api/llm/images/generations endpoint",
            "env_vars": [
                {"key": "NEXUS_URL", "prompt": "Nexus API base URL"},
                {"key": "NEXUS_API_KEY", "prompt": "Nexus API key"},
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        model = str(kwargs.get("model") or os.environ.get("QEECLAW_NEXUS_IMAGE_MODEL") or DEFAULT_MODEL).strip()
        response_format = str(kwargs.get("response_format") or os.environ.get("QEECLAW_NEXUS_IMAGE_RESPONSE_FORMAT") or "url").strip()

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider=PROVIDER_NAME,
                model=model,
                aspect_ratio=aspect,
            )

        nexus_url = os.environ.get("NEXUS_URL", "").strip().rstrip("/")
        if not nexus_url:
            return error_response(
                error="NEXUS_URL is required for QeeClaw Nexus image generation",
                error_type="auth_required",
                provider=PROVIDER_NAME,
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        payload = {
            "model": model,
            "prompt": prompt,
            "size": _SIZES.get(aspect, _SIZES["landscape"]),
            "n": 1,
            "response_format": "b64_json" if response_format == "b64_json" else "url",
        }
        timeout = int(os.environ.get("NEXUS_LLM_TIMEOUT_SECONDS", "300"))

        try:
            result = _request_json(
                f"{nexus_url}/api/llm/images/generations",
                payload,
                os.environ.get("NEXUS_API_KEY", "").strip(),
                timeout,
            )
        except urllib.error.HTTPError as exc:
            return error_response(
                error=f"Nexus image generation failed: {_extract_error_message(exc)}",
                error_type="api_error",
                provider=PROVIDER_NAME,
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            return error_response(
                error=f"Nexus image generation failed: {exc}",
                error_type="api_error",
                provider=PROVIDER_NAME,
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        data = result.get("data") if isinstance(result, dict) else None
        first = data[0] if isinstance(data, list) and data else None
        if not isinstance(first, dict):
            return error_response(
                error="Nexus returned no image data",
                error_type="empty_response",
                provider=PROVIDER_NAME,
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        image = first.get("url")
        b64 = first.get("b64_json") or first.get("b64Json")
        if not image and b64:
            try:
                image = str(_save_b64_image(str(b64)))
            except Exception as exc:
                return error_response(
                    error=f"Could not save Nexus image to cache: {exc}",
                    error_type="cache_write_error",
                    provider=PROVIDER_NAME,
                    model=model,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )

        if not image:
            return error_response(
                error="Nexus image response did not include url or b64_json",
                error_type="empty_response",
                provider=PROVIDER_NAME,
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra = {}
        revised_prompt = first.get("revised_prompt") or first.get("revisedPrompt")
        if revised_prompt:
            extra["revised_prompt"] = revised_prompt

        return success_response(
            image=str(image),
            model=model,
            prompt=prompt,
            aspect_ratio=aspect,
            provider=PROVIDER_NAME,
            extra=extra,
        )


def register(ctx) -> None:
    ctx.register_image_gen_provider(QeeClawNexusImageGenProvider())
