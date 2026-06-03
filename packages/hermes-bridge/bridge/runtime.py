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


@dataclass
class StreamHandle:
    queue: asyncio.Queue[tuple[str, str]]
    task: asyncio.Task[None]


class HermesRuntime:
    def __init__(self, max_size: int | None = None) -> None:
        self._max_size = max_size or settings.cache_max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._AIAgent: type | None = None

    def _get_ai_agent_class(self) -> type:
        if self._AIAgent is None:
            from run_agent import AIAgent

            self._AIAgent = AIAgent
        return self._AIAgent

    def _cache_key(self, session_id: str, scenario: str) -> str:
        return f"{session_id}:{scenario}"

    def get_or_create(
        self,
        cache_key: str,
        ephemeral_system_prompt: str | None = None,
    ) -> Any:
        with self._cache_lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

        agent = self._create_agent(
            cache_key,
            ephemeral_system_prompt=ephemeral_system_prompt,
        )

        with self._cache_lock:
            self._cache[cache_key] = agent
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.info("LRU 淘汰: %s", evicted_key)

        return agent

    def _create_agent(
        self,
        session_id: str,
        ephemeral_system_prompt: str | None = None,
        stream_delta_callback: Callable[[str], None] | None = None,
    ) -> Any:
        AIAgent = self._get_ai_agent_class()
        kwargs: dict[str, Any] = {
            "session_id": session_id,
            "platform": "edge-bridge",
            "quiet_mode": True,
            "model": settings.hermes_model,
            "provider": settings.hermes_provider,
            "api_key": settings.deepseek_api_key,
            "load_soul_identity": True,
        }
        if ephemeral_system_prompt is not None:
            kwargs["ephemeral_system_prompt"] = ephemeral_system_prompt
        if stream_delta_callback is not None:
            kwargs["stream_delta_callback"] = stream_delta_callback
        logger.info("构造 AIAgent: session=%s", session_id)
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
            conversation_history=conversation_history or [],
        )
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
                    conversation_history=conversation_history or [],
                )
                final = result.get("final_response") or ""
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
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """兼容 core-sdk HermesAdapter 的非流式调用：跳过 scenario 映射，按需注入 system_prompt。

        每次创建新 agent（不缓存，不进 LRU），调用完成后引用出作用域即被 GC。
        """
        agent = self._create_agent(
            f"compat:{session_id}",
            ephemeral_system_prompt=system_prompt,
        )
        return await asyncio.to_thread(
            agent.run_conversation,
            user_message=user_text,
            conversation_history=[],
        )

    async def stream_raw(
        self,
        session_id: str,
        user_text: str,
        system_prompt: str | None = None,
    ) -> StreamHandle:
        """兼容 core-sdk HermesAdapter 的流式调用：跳过 scenario 映射，按需注入 system_prompt。"""
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_delta(delta: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("delta", delta))

        agent = self._create_agent(
            f"compat-stream:{session_id}",
            ephemeral_system_prompt=system_prompt,
            stream_delta_callback=on_delta,
        )

        async def _run() -> None:
            try:
                result = await asyncio.to_thread(
                    agent.run_conversation,
                    user_message=user_text,
                    conversation_history=[],
                )
                final = result.get("final_response") or ""
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
