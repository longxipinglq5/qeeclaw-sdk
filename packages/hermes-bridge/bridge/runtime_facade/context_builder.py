from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextPrefix:
    messages: list[dict[str, Any]]
    prompt_prefix_hash: str


@dataclass(frozen=True)
class BuiltContext:
    messages: list[dict[str, Any]]
    prompt_prefix_hash: str


class ContextBuilder:
    def build_prefix(
        self,
        *,
        profile_prompt: str,
        product_boundary: str,
        capability_manifest: list[dict[str, Any]],
        business_summary: str,
        memory_summary: str,
        knowledge_summary: str,
    ) -> ContextPrefix:
        messages = [
            {
                "role": "system",
                "content": profile_prompt,
                "metadata": {"section": "profile_prompt"},
            },
            {
                "role": "system",
                "content": product_boundary,
                "metadata": {"section": "product_boundary"},
            },
            {
                "role": "system",
                "content": json.dumps(
                    capability_manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "metadata": {"section": "capability_manifest"},
            },
            {
                "role": "system",
                "content": business_summary,
                "metadata": {"section": "business_summary"},
            },
            {
                "role": "system",
                "content": memory_summary,
                "metadata": {"section": "memory_summary"},
            },
            {
                "role": "system",
                "content": knowledge_summary,
                "metadata": {"section": "knowledge_summary"},
            },
        ]
        return ContextPrefix(
            messages=messages,
            prompt_prefix_hash=self.prefix_hash(messages),
        )

    def build_messages(
        self,
        *,
        prefix: ContextPrefix,
        session_summary: str,
        artifact_summaries: list[dict[str, Any]] | None = None,
        recent_messages: list[dict[str, Any]],
        current_user_text: str,
        channel_metadata: dict[str, Any] | None = None,
    ) -> BuiltContext:
        messages = list(prefix.messages)
        if session_summary:
            messages.append(
                {
                    "role": "system",
                    "content": session_summary,
                    "metadata": {"section": "session_summary"},
                }
            )
        if artifact_summaries:
            messages.append(
                {
                    "role": "system",
                    "content": json.dumps(
                        artifact_summaries,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "metadata": {"section": "artifact_summaries"},
                }
            )
        messages.extend(recent_messages)
        messages.append(
            {
                "role": "user",
                "content": current_user_text,
                "metadata": channel_metadata or {},
            }
        )
        return BuiltContext(
            messages=messages,
            prompt_prefix_hash=prefix.prompt_prefix_hash,
        )

    def prefix_hash(self, prefix_messages: list[dict[str, Any]]) -> str:
        canonical = json.dumps(
            prefix_messages,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
