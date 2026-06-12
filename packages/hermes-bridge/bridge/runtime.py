from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from bridge.config import settings
from bridge.scenarios import get_system_prompt

logger = logging.getLogger(__name__)

EDGE_SUPERVISOR_DISABLED_TOOLSETS = [
    "browser",
    "terminal",
    "file",
    "debugging",
    "code_execution",
    "computer_use",
    "delegation",
    "todo",
    # "skills",
    "clarify",
    # "image_gen",
    "video_gen",
]


@dataclass
class StreamHandle:
    queue: asyncio.Queue[tuple[str, str]]
    task: asyncio.Task[None]


class HermesRuntime:
    def __init__(self, max_size: int | None = None) -> None:
        self._max_size = max_size or settings.cache_max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._histories: dict[str, list[dict[str, str]]] = {}
        self._cache_lock = threading.Lock()
        self._AIAgent: type | None = None

    def _get_ai_agent_class(self) -> type:
        if self._AIAgent is None:
            from run_agent import AIAgent

            self._AIAgent = AIAgent
        return self._AIAgent

    def _cache_key(self, session_id: str, scenario: str) -> str:
        return f"{session_id}:{scenario}"

    def evict_agent_profile(self, agent_profile: str) -> int:
        suffix = f":{agent_profile}"
        with self._cache_lock:
            keys = [key for key in self._cache if key.endswith(suffix)]
            for key in keys:
                self._cache.pop(key, None)
                self._histories.pop(key, None)
        if keys:
            logger.info("清理 agent_profile=%s 的缓存 agent: %d", agent_profile, len(keys))
        return len(keys)

    def get_or_create(
        self,
        cache_key: str,
        ephemeral_system_prompt: str | None = None,
        agent_profile: str | None = None,
    ) -> Any:
        with self._cache_lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

        create_kwargs: dict[str, Any] = {}
        disabled_toolsets = self._disabled_toolsets_for_profile(agent_profile)
        if disabled_toolsets is not None:
            create_kwargs["disabled_toolsets"] = disabled_toolsets
        if agent_profile == "edge_supervisor":
            create_kwargs.update(self._edge_supervisor_overrides())

        self._ensure_knowledge_mcp_for_profile(agent_profile)
        agent = self._create_agent(
            cache_key,
            ephemeral_system_prompt=ephemeral_system_prompt,
            **create_kwargs,
        )

        with self._cache_lock:
            self._cache[cache_key] = agent
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                self._histories.pop(evicted_key, None)
                logger.info("LRU 淘汰: %s", evicted_key)

        return agent

    @staticmethod
    def _disabled_toolsets_for_profile(agent_profile: str | None) -> list[str] | None:
        if agent_profile == "edge_supervisor":
            return list(EDGE_SUPERVISOR_DISABLED_TOOLSETS)
        return None

    @staticmethod
    def _edge_supervisor_overrides() -> dict[str, Any]:
        return {
            "load_soul_identity": False,
            "skip_context_files": True,
            "prefill_messages": [],
        }

    @staticmethod
    def _ensure_knowledge_mcp_for_profile(agent_profile: str | None) -> None:
        if agent_profile != "edge_supervisor":
            return
        try:
            from bridge.knowledge_mcp_config import ensure_knowledge_mcp_for_profile

            ensure_knowledge_mcp_for_profile(agent_profile)
        except Exception:
            logger.warning("edge_supervisor knowledge MCP init failed", exc_info=True)

    def _history_for(self, cache_key: str) -> list[dict[str, str]]:
        with self._cache_lock:
            return [dict(message) for message in self._histories.get(cache_key, [])]

    def _append_history(self, cache_key: str, user_text: str, result: dict[str, Any]) -> None:
        assistant_text = str(result.get("final_response") or "")
        if not assistant_text:
            return
        with self._cache_lock:
            history = self._histories.setdefault(cache_key, [])
            history.extend([
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": assistant_text},
            ])
            if len(history) > 24:
                del history[:-24]

    def _create_agent(
        self,
        session_id: str,
        ephemeral_system_prompt: str | None = None,
        stream_delta_callback: Callable[[str], None] | None = None,
        **overrides: Any,
    ) -> Any:
        AIAgent = self._get_ai_agent_class()
        kwargs: dict[str, Any] = {
            "session_id": session_id,
            "platform": "edge-bridge",
            "quiet_mode": True,
            "model": settings.hermes_model,
            "provider": settings.hermes_provider,
            "base_url": settings.deepseek_base_url,
            "load_soul_identity": True,
        }
        if settings.deepseek_api_key:
            kwargs["api_key"] = settings.deepseek_api_key
        if ephemeral_system_prompt is not None:
            kwargs["ephemeral_system_prompt"] = ephemeral_system_prompt
        if stream_delta_callback is not None:
            kwargs["stream_delta_callback"] = stream_delta_callback
        kwargs.update(overrides)
        logger.info("构造 AIAgent: session=%s overrides=%s", session_id, list(overrides.keys()))
        return AIAgent(**kwargs)

    async def invoke(
        self,
        session_id: str,
        scenario: str,
        user_text: str,
        context: dict | None = None,
        conversation_history: list[dict] | None = None,
    ) -> dict[str, Any]:
        ephemeral = get_system_prompt(scenario, context)
        key = self._cache_key(session_id, scenario)
        agent = self.get_or_create(key, ephemeral_system_prompt=ephemeral)

        result = await asyncio.to_thread(
            agent.run_conversation,
            user_message=user_text,
            conversation_history=self._history_for(key),
        )
        self._append_history(key, user_text, result)
        return result

    async def stream(
        self,
        session_id: str,
        scenario: str,
        user_text: str,
        context: dict | None = None,
        conversation_history: list[dict] | None = None,
    ) -> StreamHandle:
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_delta(delta: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("delta", delta))

        ephemeral = get_system_prompt(scenario, context)
        history_key = self._cache_key(session_id, scenario)
        # stream 每次创建新 agent，因为 stream_delta_callback 是 per-request 的
        agent = self._create_agent(
            f"stream:{session_id}:{scenario}",
            ephemeral_system_prompt=ephemeral,
            stream_delta_callback=on_delta,
        )

        async def _run() -> None:
            try:
                result = await asyncio.to_thread(
                    agent.run_conversation,
                    user_message=user_text,
                    conversation_history=self._history_for(history_key),
                )
                final = result.get("final_response") or ""
                self._append_history(history_key, user_text, result)
                await queue.put(("done", final))
            except Exception as exc:
                logger.exception("stream run_conversation 异常")
                await queue.put(("error", "流式调用失败"))

        task = asyncio.create_task(_run())
        return StreamHandle(queue=queue, task=task)

    async def invoke_raw(
        self,
        session_id: str,
        user_text: str,
        agent_profile: str = "default",
        system_prompt: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """兼容 core-sdk HermesAdapter 的非流式调用。

        Edge 只传用户输入；系统规则、记忆、skills 由 Hermes agent/profile 自主管理。
        """
        cache_key = f"compat:{session_id}:{agent_profile}"
        agent = self.get_or_create(
            cache_key,
            ephemeral_system_prompt=system_prompt,
            agent_profile=agent_profile,
        )
        result = await asyncio.to_thread(
            agent.run_conversation,
            user_message=user_text,
            conversation_history=conversation_history if conversation_history is not None else self._history_for(cache_key),
        )
        if conversation_history is None:
            self._append_history(cache_key, user_text, result)
        return result

    async def stream_raw(
        self,
        session_id: str,
        user_text: str,
        agent_profile: str = "default",
        system_prompt: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> StreamHandle:
        """兼容 core-sdk HermesAdapter 的流式调用：跳过 scenario 映射，按需注入 system_prompt。"""
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_delta(delta: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("delta", delta))

        create_kwargs: dict[str, Any] = {}
        disabled_toolsets = self._disabled_toolsets_for_profile(agent_profile)
        if disabled_toolsets is not None:
            create_kwargs["disabled_toolsets"] = disabled_toolsets
        if agent_profile == "edge_supervisor":
            create_kwargs.update(self._edge_supervisor_overrides())

        self._ensure_knowledge_mcp_for_profile(agent_profile)
        agent = self._create_agent(
            f"compat-stream:{session_id}:{agent_profile}",
            ephemeral_system_prompt=system_prompt,
            stream_delta_callback=on_delta,
            **create_kwargs,
        )

        async def _run() -> None:
            try:
                result = await asyncio.to_thread(
                    agent.run_conversation,
                    user_message=user_text,
                    conversation_history=conversation_history
                    if conversation_history is not None
                    else self._history_for(f"compat:{session_id}:{agent_profile}"),
                )
                final = result.get("final_response") or ""
                if conversation_history is None:
                    self._append_history(f"compat:{session_id}:{agent_profile}", user_text, result)
                await queue.put(("done", final))
            except Exception as exc:
                logger.exception("stream_raw run_conversation 异常")
                await queue.put(("error", "流式调用失败"))

        task = asyncio.create_task(_run())
        return StreamHandle(queue=queue, task=task)

    @property
    def cache_size(self) -> int:
        with self._cache_lock:
            return len(self._cache)
