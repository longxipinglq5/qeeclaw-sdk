from __future__ import annotations

import asyncio
from typing import Any

from bridge.runtime import StreamHandle
from bridge.runtime_facade.event_bus import EventBus
from bridge.runtime_facade.models import (
    CreateRunRequest,
    CreateRunResponse,
    RunKind,
    RunStatus,
    RunUrls,
    RuntimeEvent,
    RuntimeRun,
)
from bridge.runtime_facade.run_manager import RunManager
from bridge.runtime_facade.session_store import SessionStore
from bridge.runtime_facade.store import InMemoryStore


class HermesRuntimeFacade:
    """Runtime facade for migrated native FastAPI routes.

    migrated_routes: Plan A migrates only native FastAPI `/invoke` and
    `/invoke/stream`; catch-all `api/legacy.py` remains legacy until a later plan
    explicitly moves each route.
    """

    def __init__(self, legacy_runtime: Any) -> None:
        self._legacy_runtime = legacy_runtime
        self.store = InMemoryStore()
        self.events = EventBus(self.store)
        self.sessions = SessionStore(self.store)
        self.runs = RunManager(store=self.store, event_bus=self.events)

    async def invoke_raw(
        self,
        *,
        session_id: str,
        user_text: str,
        agent_profile: str = "default",
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        return await self._invoke_raw_with_run_metadata(
            session_id=session_id,
            user_text=user_text,
            agent_profile=agent_profile,
            system_prompt=system_prompt,
        )

    async def _invoke_raw_with_run_metadata(
        self,
        *,
        session_id: str,
        user_text: str,
        agent_profile: str = "default",
        system_prompt: str | None = None,
        trace_id: str | None = None,
        parent_run_id: str | None = None,
        created_by: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.sessions.get_or_create(
            session_id=session_id,
            agent_profile=agent_profile,
        )
        conversation_history = self.sessions.get_recent_messages(session_id)
        run = self.runs.start_run(
            session_id=session_id,
            agent_profile=agent_profile,
            input_text=user_text,
            trace_id=trace_id,
            parent_run_id=parent_run_id,
            created_by=created_by,
            source=source,
            metadata=metadata,
        )
        try:
            result = await self._legacy_runtime.invoke_raw(
                session_id=session_id,
                user_text=user_text,
                agent_profile=agent_profile,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
            )
        except Exception as exc:
            self.runs.fail_run(run.run_id, error=str(exc))
            raise

        self.events.append(
            session_id=session_id,
            run_id=run.run_id,
            type="metering",
            payload=self._usage_from_result(result),
            trace_id=run.trace_id,
        )
        self.runs.complete_run(
            run.run_id,
            result_text=str(result.get("final_response") or ""),
            usage=self._usage_from_result(result),
        )
        self.sessions.append_turn(
            session_id,
            user_text=user_text,
            assistant_text=str(result.get("final_response") or ""),
            metadata={"run_id": run.run_id},
        )

        return {
            **result,
            "run_id": run.run_id,
            "session_id": session_id,
            "agent_profile": agent_profile,
        }

    async def create_run(self, request: CreateRunRequest) -> CreateRunResponse:
        if request.kind != RunKind.INVOKE:
            raise ValueError("RUN_KIND_UNSUPPORTED")

        trace_id = f"trc_{self.runs.next_run_number:06d}"
        result = await self._invoke_raw_with_run_metadata(
            session_id=request.session_id,
            user_text=request.input.text,
            agent_profile=request.agent_profile,
            system_prompt=None,
            trace_id=trace_id,
            created_by=request.metadata.get("created_by"),
            source=request.metadata.get("source"),
            metadata=request.metadata,
        )
        run = self.runs.get(result["run_id"])

        return CreateRunResponse(
            run_id=result["run_id"],
            session_id=request.session_id,
            kind=request.kind,
            status=run.status if run else RunStatus.COMPLETED,
            trace_id=trace_id,
            urls=RunUrls.for_run(result["run_id"], request.session_id),
        )

    def get_run(self, run_id: str) -> RuntimeRun | None:
        return self.runs.get(run_id)

    def get_run_events(self, run_id: str) -> list[RuntimeEvent]:
        return self.events.list_by_run(run_id)

    async def stream_raw(
        self,
        *,
        session_id: str,
        user_text: str,
        agent_profile: str = "default",
        system_prompt: str | None = None,
    ) -> StreamHandle:
        self.sessions.get_or_create(
            session_id=session_id,
            agent_profile=agent_profile,
        )
        conversation_history = self.sessions.get_recent_messages(session_id)
        run = self.runs.start_run(
            session_id=session_id,
            agent_profile=agent_profile,
            input_text=user_text,
        )
        try:
            legacy_handle = await self._legacy_runtime.stream_raw(
                session_id=session_id,
                user_text=user_text,
                agent_profile=agent_profile,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
            )
        except Exception as exc:
            self.runs.fail_run(run.run_id, error=str(exc))
            raise

        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def _relay() -> None:
            try:
                while True:
                    event_type, payload = await legacy_handle.queue.get()
                    if event_type == "delta":
                        self.events.append(
                            session_id=session_id,
                            run_id=run.run_id,
                            type="token",
                            payload={"text": payload},
                            trace_id=run.trace_id,
                        )
                        await queue.put((event_type, payload))
                    elif event_type == "done":
                        self.runs.complete_run(
                            run.run_id,
                            result_text=payload,
                            usage={},
                        )
                        self.sessions.append_turn(
                            session_id,
                            user_text=user_text,
                            assistant_text=payload,
                            metadata={"run_id": run.run_id},
                        )
                        await queue.put((event_type, payload))
                        break
                    elif event_type == "error":
                        self.runs.fail_run(run.run_id, error=payload)
                        await queue.put((event_type, payload))
                        break
            finally:
                if not legacy_handle.task.done():
                    legacy_handle.task.cancel()

        return StreamHandle(queue=queue, task=asyncio.create_task(_relay()))

    @staticmethod
    def _usage_from_result(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "total_tokens": result.get("total_tokens", 0),
        }
