from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from bridge.config import settings
from bridge.runtime import StreamHandle
from bridge.runtime_facade.artifacts import JsonArtifactStore
from bridge.runtime_facade.capabilities import CapabilityRegistry
from bridge.runtime_facade.cards import build_result_preview_card
from bridge.runtime_facade.event_bus import EventBus
from bridge.runtime_facade.models import (
    CapabilityManifest,
    CreateRunRequest,
    CreateRunResponse,
    PromptCacheUsage,
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

    def __init__(self, legacy_runtime: Any, artifact_root_dir: str | Path | None = None) -> None:
        self._legacy_runtime = legacy_runtime
        self.store = InMemoryStore()
        self.events = EventBus(self.store)
        self.sessions = SessionStore(self.store)
        self.runs = RunManager(store=self.store, event_bus=self.events)
        self.capabilities = CapabilityRegistry.with_builtin_capabilities()
        self.artifacts = JsonArtifactStore(
            artifact_root_dir or (settings.hermes_home_path / "bridge-state")
        )
        self._last_prompt_prefix_hash_by_session: dict[str, str] = {}

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

        usage = self._normalize_prompt_cache_usage(
            result,
            session_id=session_id,
            context_length=len(conversation_history) + 1,
        )
        previous_prompt_prefix_hash = self._last_prompt_prefix_hash_by_session.get(session_id)
        cache_prefix_changed = (
            previous_prompt_prefix_hash is not None
            and previous_prompt_prefix_hash != usage["prompt_prefix_hash"]
        )
        self._last_prompt_prefix_hash_by_session[session_id] = usage["prompt_prefix_hash"]
        self.events.append(
            session_id=session_id,
            run_id=run.run_id,
            type="metering",
            payload={
                "usage": usage,
                "cache_prefix_changed": cache_prefix_changed,
                "previous_prompt_prefix_hash": previous_prompt_prefix_hash
                if cache_prefix_changed
                else None,
            },
            trace_id=run.trace_id,
        )
        self.runs.complete_run(
            run.run_id,
            result_text=str(result.get("final_response") or ""),
            usage=usage,
            done_payload={
                "text": str(result.get("final_response") or ""),
                "usage": usage,
            },
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
        if request.kind == RunKind.SKILL_RUN:
            return await self._create_skill_run(request)

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
            parent_run_id=request.parent_run_id,
            urls=RunUrls.for_run(result["run_id"], request.session_id),
        )

    async def _create_skill_run(self, request: CreateRunRequest) -> CreateRunResponse:
        validation_error = self._validate_skill_run_fields(request)
        if validation_error:
            raise ValueError(json.dumps(validation_error))

        capability = self.capabilities.get_capability(str(request.capability_id))
        trace_id = f"trc_{self.runs.next_run_number:06d}"
        result = await self._run_skill_invocation(
            request=request,
            capability=capability,
            trace_id=trace_id,
        )
        run = self.runs.get(result["run_id"])
        return CreateRunResponse(
            run_id=result["run_id"],
            session_id=request.session_id,
            kind=request.kind,
            status=run.status if run else RunStatus.COMPLETED,
            trace_id=trace_id,
            parent_run_id=request.parent_run_id,
            artifact_id=result["artifact_id"],
            urls=RunUrls.for_run(result["run_id"], request.session_id),
        )

    def _validate_skill_run_fields(self, request: CreateRunRequest) -> dict[str, Any] | None:
        missing: list[str] = []
        unexpected: list[str] = []
        if not request.capability_id:
            missing.append("capability_id")
        for field_name in ("expert_id", "employee_id", "goal_id"):
            if getattr(request, field_name):
                unexpected.append(field_name)
        if not missing and not unexpected:
            return None
        return {
            "code": "RUN_KIND_UNSUPPORTED",
            "details": {
                "kind": request.kind.value,
                "missing": missing,
                "unexpected": unexpected,
            },
        }

    async def _run_skill_invocation(
        self,
        *,
        request: CreateRunRequest,
        capability: CapabilityManifest,
        trace_id: str,
    ) -> dict[str, Any]:
        instruction = self._skill_instruction(capability, request.input)
        self.sessions.get_or_create(
            session_id=request.session_id,
            agent_profile=capability.hermes_profile,
        )
        conversation_history = self.sessions.get_recent_messages(request.session_id)
        run = self.runs.start_run(
            session_id=request.session_id,
            agent_profile=capability.hermes_profile,
            kind=RunKind.SKILL_RUN,
            input_text=instruction,
            trace_id=trace_id,
            parent_run_id=request.parent_run_id,
            created_by=request.metadata.get("created_by"),
            source=request.metadata.get("source"),
            metadata={
                **request.metadata,
                "capability_id": capability.capability_id,
                "output_contract": request.output_contract,
            },
        )
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="app_started",
            payload={
                "capability_id": capability.capability_id,
                "title": capability.title,
                "output_contract": request.output_contract or capability.output_contract,
            },
            trace_id=run.trace_id,
        )

        try:
            result = await self._legacy_runtime.invoke_raw(
                session_id=request.session_id,
                user_text=instruction,
                agent_profile=capability.hermes_profile,
                system_prompt=None,
                conversation_history=conversation_history,
            )
        except Exception as exc:
            self.runs.fail_run(run.run_id, error=str(exc))
            raise

        usage = self._normalize_prompt_cache_usage(
            result,
            session_id=request.session_id,
            context_length=len(conversation_history) + 1,
        )
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="metering",
            payload={
                "usage": usage,
                "cache_prefix_changed": False,
                "previous_prompt_prefix_hash": None,
            },
            trace_id=run.trace_id,
        )

        final_response = str(result.get("final_response") or "")
        artifact_id = f"art_{run.run_id}"
        artifact = self.artifacts.create_artifact(
            artifact_id=artifact_id,
            session_id=request.session_id,
            run_id=run.run_id,
            kind=self._artifact_kind_for_capability(capability),
            title=capability.title,
            content={"body": final_response},
            metadata={"capability_id": capability.capability_id},
        )
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="artifact_created",
            payload={"artifact": artifact.model_dump(mode="json")},
            trace_id=run.trace_id,
        )

        card = build_result_preview_card(
            run_id=run.run_id,
            title=capability.title,
            summary=final_response,
            artifact_ids=[artifact.artifact_id],
        )
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="app_result",
            payload={"card": card.model_dump(mode="json")},
            trace_id=run.trace_id,
        )
        self.runs.complete_run(
            run.run_id,
            result_text=final_response,
            usage=usage,
            done_payload={"text": final_response, "usage": usage},
        )
        self.sessions.append_turn(
            request.session_id,
            user_text=instruction,
            assistant_text=final_response,
            metadata={"run_id": run.run_id, "capability_id": capability.capability_id},
        )
        return {
            **result,
            "run_id": run.run_id,
            "artifact_id": artifact.artifact_id,
        }

    @staticmethod
    def _skill_instruction(capability: CapabilityManifest, input_payload: Any) -> str:
        payload = input_payload.model_dump(exclude_none=True)
        return (
            f"/{capability.slash_command} "
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )

    @staticmethod
    def _artifact_kind_for_capability(capability: CapabilityManifest) -> str:
        if capability.capability_id == "xiaohongshu_note_writer":
            return "xiaohongshu_note"
        if capability.capability_id.startswith("moments_copywriter"):
            return "moments_copy"
        return capability.capability_id

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

    def _normalize_prompt_cache_usage(
        self,
        result: dict[str, Any],
        *,
        session_id: str,
        context_length: int,
    ) -> dict[str, Any]:
        prompt_details = result.get("prompt_tokens_details") or {}
        input_tokens = (
            result.get("input_tokens")
            or result.get("prompt_tokens")
            or 0
        )
        output_tokens = (
            result.get("output_tokens")
            or result.get("completion_tokens")
            or 0
        )
        cache_read_tokens = (
            result.get("cache_read_tokens")
            or result.get("cache_read_input_tokens")
            or result.get("prompt_cache_hit_tokens")
            or prompt_details.get("cached_tokens")
            or 0
        )
        cache_write_tokens = (
            result.get("cache_write_tokens")
            or result.get("cache_creation_input_tokens")
            or result.get("prompt_cache_miss_tokens")
            or 0
        )
        total_cache_tokens = cache_read_tokens + cache_write_tokens
        cache_hit_percent = (
            round(cache_read_tokens / total_cache_tokens * 100, 2)
            if total_cache_tokens
            else 0.0
        )
        usage = PromptCacheUsage(
            prompt_prefix_hash=self._prompt_prefix_hash_for_session(session_id),
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            cache_read_tokens=int(cache_read_tokens),
            cache_write_tokens=int(cache_write_tokens),
            cache_hit_percent=cache_hit_percent,
            turn_cache_hit_percent=cache_hit_percent,
            context_length=context_length,
            threshold_tokens=0,
            last_prompt_tokens=int(input_tokens),
        )
        return usage.model_dump(mode="json")

    def _prompt_prefix_hash_for_session(self, session_id: str) -> str:
        from bridge.runtime_facade.context_builder import ContextBuilder

        session = self.sessions.get(session_id)
        metadata = session.metadata if session else {}
        builder = ContextBuilder()
        prefix = builder.build_prefix(
            profile_prompt=str(metadata.get("profile_prompt", "")),
            product_boundary=str(metadata.get("product_boundary", "")),
            capability_manifest=list(metadata.get("capability_manifest", [])),
            business_summary=str(metadata.get("business_summary", "")),
            memory_summary=str(metadata.get("memory_summary", "")),
            knowledge_summary=str(metadata.get("knowledge_summary", "")),
        )
        return prefix.prompt_prefix_hash
