from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from bridge.config import settings
from bridge.runtime import StreamHandle
from bridge.runtime_facade.approvals import ApprovalStore
from bridge.runtime_facade.artifacts import JsonArtifactStore
from bridge.runtime_facade.automation_status import AutomationRunStatus, AutomationStatusProjector
from bridge.runtime_facade.capabilities import CapabilityRegistry
from bridge.runtime_facade.cards import build_result_preview_card
from bridge.runtime_facade.centaur_adapter import CentaurLoopRuntimeAdapter
from bridge.runtime_facade.channel_stores import InboxStore, OutboxStore
from bridge.runtime_facade.event_bus import EventBus
from bridge.runtime_facade.experts import ExpertRegistry
from bridge.runtime_facade.models import (
    CapabilityManifest,
    CapabilitySelection,
    CreateRunRequest,
    CreateRunInput,
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
from bridge.runtime_facade.session_ids import SessionIdBuilder
from bridge.runtime_facade.store import InMemoryStore
from bridge.runtime_facade.timeline import TimelineStore


class HermesRuntimeFacade:
    """Runtime facade for migrated native FastAPI routes.

    migrated_routes: Plan A migrates only native FastAPI `/invoke` and
    `/invoke/stream`; catch-all `api/legacy.py` remains legacy until a later plan
    explicitly moves each route.
    """

    def __init__(self, legacy_runtime: Any, artifact_root_dir: str | Path | None = None) -> None:
        self._legacy_runtime = legacy_runtime
        self.store = InMemoryStore()
        self.timeline = TimelineStore()
        self.events = EventBus(self.store, timeline_store=self.timeline)
        self.sessions = SessionStore(self.store)
        self.runs = RunManager(store=self.store, event_bus=self.events)
        self.capabilities = CapabilityRegistry.with_builtin_capabilities()
        self.experts = ExpertRegistry.with_builtin_experts()
        self.approvals = ApprovalStore()
        self.inbox = InboxStore()
        self.outbox = OutboxStore()
        self.artifacts = JsonArtifactStore(
            artifact_root_dir or (settings.hermes_home_path / "bridge-state")
        )
        self.automation_status = AutomationStatusProjector()
        self.centaur_adapter = CentaurLoopRuntimeAdapter(
            event_bus=self.events,
            run_manager=self.runs,
            approval_store=self.approvals,
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

    async def invoke_app_im_free_text(
        self,
        *,
        session_id: str,
        user_text: str,
        agent_profile: str = "edge_supervisor",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if agent_profile == "edge_supervisor":
            selection = self.supervisor_route_to_capability(
                session_id=session_id,
                user_text=user_text,
                context={
                    "context_refs": [],
                    "metadata": metadata or {},
                },
            )
            if selection.fallback_behavior == "run_capability" and selection.capability_id:
                response = await self._create_supervisor_skill_child_run(
                    request=CreateRunRequest(
                        kind=RunKind.INVOKE,
                        session_id=session_id,
                        agent_profile=agent_profile,
                        input=CreateRunInput(text=user_text),
                        metadata=metadata or {},
                    ),
                    selection=selection,
                )
                return self._sync_reply_from_create_run_response(
                    response,
                    agent_profile=agent_profile,
                )

        return await self.invoke_raw(
            session_id=session_id,
            user_text=user_text,
            agent_profile=agent_profile,
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
        self.events.append(
            session_id=session_id,
            run_id=run.run_id,
            type="message",
            payload={"role": "user", "text": user_text},
            trace_id=run.trace_id,
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
        self.events.append(
            session_id=session_id,
            run_id=run.run_id,
            type="message",
            payload={"role": "assistant", "text": str(result.get("final_response") or "")},
            trace_id=run.trace_id,
        )
        self.sessions.append_turn(
            session_id,
            user_text=user_text,
            assistant_text=str(result.get("final_response") or ""),
            metadata={"run_id": run.run_id},
        )

        return {
            **result,
            "renderable_reply_text": self._renderable_reply_text(result),
            "run_id": run.run_id,
            "session_id": session_id,
            "agent_profile": agent_profile,
        }

    def _sync_reply_from_create_run_response(
        self,
        response: CreateRunResponse,
        *,
        agent_profile: str,
    ) -> dict[str, Any]:
        artifact = self.artifacts.get_artifact(response.artifact_id) if response.artifact_id else None
        result_text = ""
        if artifact:
            result_text = str(artifact.content.get("body") or "")
        run = self.runs.get(response.run_id)
        return {
            "final_response": result_text,
            "renderable_reply_text": self._result_preview_reply_text(
                title=artifact.title if artifact else "生成结果",
                body=result_text,
                speech="内容已生成，请查看结果。",
            ) if result_text else "",
            "run_id": response.run_id,
            "session_id": response.session_id,
            "agent_profile": agent_profile,
            "artifact_id": response.artifact_id,
            "status": (run.status.value if run else response.status.value),
        }

    async def create_run(self, request: CreateRunRequest) -> CreateRunResponse:
        if request.kind == RunKind.SKILL_RUN:
            return await self._create_skill_run(request)
        if request.kind == RunKind.EXPERT_RUN:
            return await self._create_expert_run(request)
        if request.kind == RunKind.AUTOMATION_RUN:
            return self._create_automation_run(request)

        if request.kind != RunKind.INVOKE:
            raise ValueError("RUN_KIND_UNSUPPORTED")

        if request.agent_profile == "edge_supervisor":
            selection = self.supervisor_route_to_capability(
                session_id=request.session_id,
                user_text=request.input.text or "",
                context={
                    "context_refs": request.context_refs,
                    "metadata": request.metadata,
                },
            )
            if selection.fallback_behavior == "run_capability" and selection.capability_id:
                return await self._create_supervisor_skill_child_run(
                    request=request,
                    selection=selection,
                )
            if selection.fallback_behavior == "require_approval":
                return self._create_supervisor_approval_run(
                    request=request,
                    selection=selection,
                )
            if selection.fallback_behavior == "ask_clarification":
                return self._create_supervisor_clarification_run(
                    request=request,
                    selection=selection,
                )

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

    def _create_automation_run(self, request: CreateRunRequest) -> CreateRunResponse:
        payload = request.input.model_dump(exclude_none=True)
        owner_id = self._owner_id_from_supervisor_session(request.session_id)
        metadata_owner_id = request.metadata.get("owner_id")
        if metadata_owner_id and metadata_owner_id != owner_id:
            raise ValueError("SESSION_OWNER_MISMATCH")
        employee_id = str(payload.get("employee_id") or request.employee_id or "marketing_employee")
        goal_id = str(payload.get("goal_id") or request.goal_id or f"goal_{self.runs.next_run_number:06d}")
        automation_session_id = SessionIdBuilder.automation(owner_id, employee_id, goal_id)
        trace_id = f"trc_{self.runs.next_run_number:06d}"

        self.sessions.get_or_create(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
        )
        self.sessions.get_or_create(
            session_id=automation_session_id,
            agent_profile="edge_automation",
            metadata={
                "origin_session_id": request.session_id,
                "owner_id": owner_id,
                "employee_id": employee_id,
                "goal_id": goal_id,
            },
        )
        run = self.runs.start_run(
            session_id=automation_session_id,
            agent_profile="edge_automation",
            kind=RunKind.AUTOMATION_RUN,
            input_text=str(payload.get("goal") or request.input.text or ""),
            trace_id=trace_id,
            parent_run_id=request.parent_run_id,
            created_by=request.metadata.get("created_by"),
            source=request.metadata.get("source"),
            metadata={
                **request.metadata,
                "owner_id": owner_id,
                "employee_id": employee_id,
                "goal_id": goal_id,
                "origin_session_id": request.session_id,
            },
        )
        self.centaur_adapter.start_run(
            run=run,
            employee_id=employee_id,
            goal_id=goal_id,
            input={
                "product": self._input_product_from_goal(str(payload.get("goal") or "")),
                "campaign_goal": str(payload.get("goal") or ""),
            },
        )
        run = self.runs.get(run.run_id) or run
        return CreateRunResponse(
            run_id=run.run_id,
            session_id=automation_session_id,
            kind=RunKind.AUTOMATION_RUN,
            status=run.status,
            trace_id=trace_id,
            parent_run_id=request.parent_run_id,
            urls=RunUrls(
                status_url=f"/api/runs/{run.run_id}",
                events_url=f"/api/runs/{run.run_id}/events",
                stream_url=f"/api/runs/{run.run_id}/events/stream",
                timeline_url=f"/api/sessions/{request.session_id}/timeline",
            ),
        )

    def get_automation_status_for_run(self, run_id: str) -> AutomationRunStatus | None:
        run = self.runs.get(run_id)
        if run is None:
            return None
        return self.automation_status.project(self.events.list_by_run(run_id))

    def get_automation_status_for_goal(self, goal_id: str) -> AutomationRunStatus | None:
        for run in self.store.list("runs"):
            if not isinstance(run, RuntimeRun):
                continue
            if run.metadata.get("goal_id") != goal_id:
                continue
            return self.get_automation_status_for_run(run.run_id)
        return None

    def request_automation_resume(self, goal_id: str) -> dict[str, Any] | None:
        for run in self.store.list("runs"):
            if not isinstance(run, RuntimeRun):
                continue
            if run.metadata.get("goal_id") != goal_id:
                continue
            event = self.events.append(
                session_id=run.session_id,
                run_id=run.run_id,
                type="automation_resume_requested",
                payload={"goal_id": goal_id, "manual": True},
                trace_id=run.trace_id,
            )
            return {
                "status": "resume_requested",
                "goal_id": goal_id,
                "run_id": run.run_id,
                "event_id": event.event_id,
            }
        return None

    @staticmethod
    def _owner_id_from_supervisor_session(session_id: str) -> str:
        parts = session_id.split(":")
        if len(parts) >= 2 and parts[0] == "edge":
            return parts[1]
        raise ValueError("SESSION_OWNER_MISMATCH")

    @staticmethod
    def _input_product_from_goal(goal: str) -> str:
        if "儿童护眼台灯" in goal:
            return "儿童护眼台灯"
        return "产品"

    @classmethod
    def _renderable_reply_text(cls, result: dict[str, Any]) -> str:
        final_response = str(result.get("final_response") or "").strip()
        tool_outputs = cls._extract_tool_outputs(result)
        if not tool_outputs:
            return final_response

        latest_tool = tool_outputs[-1]
        tool_text = latest_tool["content"].strip()
        title = cls._title_from_tool_output(tool_text, latest_tool["tool_name"])
        full_output = tool_text
        if final_response:
            full_output = f"{tool_text}\n\n---\n{final_response}"

        return cls._result_preview_reply_text(
            title=title,
            body=full_output,
            speech=final_response or "工具结果已生成。",
            tool_name=latest_tool["tool_name"],
        )

    @staticmethod
    def _result_preview_reply_text(
        *,
        title: str,
        body: str,
        speech: str,
        tool_name: str | None = None,
    ) -> str:
        preview = body[:220]
        return json.dumps(
            {
                "card_type": "result_preview",
                "speech": speech,
                "data": {
                    "title": title,
                    "preview": preview,
                    "full_output": body,
                    **({"tool_name": tool_name} if tool_name else {}),
                },
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _extract_tool_outputs(result: dict[str, Any]) -> list[dict[str, str]]:
        messages = result.get("messages")
        if not isinstance(messages, list):
            return []
        outputs: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") != "tool":
                continue
            content = HermesRuntimeFacade._coerce_tool_content_to_text(message.get("content"))
            if not content.strip():
                continue
            outputs.append(
                {
                    "tool_name": str(
                        message.get("tool_name")
                        or message.get("name")
                        or "tool"
                    ),
                    "content": content,
                }
            )
        return outputs

    @staticmethod
    def _coerce_tool_content_to_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        parts.append(str(text))
            return "\n".join(parts)
        if isinstance(content, dict):
            text_summary = content.get("text_summary")
            if text_summary:
                return str(text_summary)
            for key in ("text", "body", "output", "result", "content"):
                value = content.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            return json.dumps(content, ensure_ascii=False, default=str)
        return str(content)

    @staticmethod
    def _title_from_tool_output(tool_text: str, tool_name: str) -> str:
        for raw_line in tool_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            for prefix in ("标题：", "标题:", "Title:", "title:"):
                if line.startswith(prefix):
                    title = line[len(prefix):].strip()
                    if title:
                        return title[:80]
            return line[:80]
        return f"{tool_name} 结果"

    def supervisor_route_to_capability(
        self,
        *,
        session_id: str,
        user_text: str,
        context: dict[str, Any],
    ) -> CapabilitySelection:
        normalized = user_text.strip()
        if "小红书" in normalized and ("生成" in normalized or "写" in normalized):
            return CapabilitySelection(
                selection_id=f"sel_{self.runs.next_run_number:06d}",
                capability_id="xiaohongshu_note_writer",
                input={
                    "product": self._extract_product_for_xhs(normalized),
                    "tone": "真实种草",
                    "platform": "xiaohongshu",
                },
                context_refs=list(context.get("context_refs") or []),
                output_contract="skill_app_card",
                confidence=0.9,
                reasoning_summary="用户明确要求生成小红书内容。",
                requires_clarification=False,
                fallback_behavior="run_capability",
                source="deterministic_rule",
                metadata={"matched_terms": ["小红书"]},
            )
        if "发布" in normalized or "发给客户群" in normalized:
            source_artifact_id = self._latest_artifact_ref(
                session_id=session_id,
                context_refs=list(context.get("context_refs") or []),
            )
            return CapabilitySelection(
                selection_id=f"sel_{self.runs.next_run_number:06d}",
                context_refs=[f"artifact:{source_artifact_id}"] if source_artifact_id else [],
                confidence=0.88 if source_artifact_id else 0.5,
                reasoning_summary="用户请求发布或触达客户，必须先获得审批。",
                missing_inputs=[] if source_artifact_id else ["artifact"],
                requires_clarification=source_artifact_id is None,
                fallback_behavior="require_approval" if source_artifact_id else "ask_clarification",
                source="deterministic_rule",
                metadata={
                    "action_kind": "contact_customer"
                    if "客户群" in normalized
                    else "publish_content",
                    "matched_terms": ["发布"] if "发布" in normalized else ["客户群"],
                },
            )
        if "内容" in normalized:
            return CapabilitySelection(
                selection_id=f"sel_{self.runs.next_run_number:06d}",
                confidence=0.31,
                reasoning_summary="用户没有说明平台、产品或内容目标，无法可靠选择具体 Skill App。",
                missing_inputs=["product", "platform", "content_goal"],
                requires_clarification=True,
                fallback_behavior="ask_clarification",
                source="deterministic_rule",
                metadata={"matched_terms": ["内容"]},
            )
        if "朋友圈" in normalized and ("配图" in normalized or "图" in normalized):
            source_artifact_id = self._latest_artifact_ref(
                session_id=session_id,
                context_refs=list(context.get("context_refs") or []),
            )
            topic = self._extract_moments_topic(normalized)
            return CapabilitySelection(
                selection_id=f"sel_{self.runs.next_run_number:06d}",
                capability_id="moments_copywriter_with_image",
                input={
                    "topic": topic,
                    "product": "这个产品" if source_artifact_id else topic,
                    "tone": "真实、亲切、适合朋友圈",
                    "need_image": True,
                    "source_artifact_id": source_artifact_id,
                },
                context_refs=[f"artifact:{source_artifact_id}"] if source_artifact_id else [],
                output_contract="copy_plus_image_card",
                confidence=0.86 if source_artifact_id else 0.72,
                reasoning_summary="用户要求生成朋友圈并配图。",
                missing_inputs=[],
                requires_clarification=False,
                fallback_behavior="run_capability",
                source="deterministic_rule",
                metadata={"matched_terms": ["朋友圈", "配图"]},
            )
        return CapabilitySelection(
            selection_id=f"sel_{self.runs.next_run_number:06d}",
            confidence=0.0,
            reasoning_summary="未命中可确定的 Skill App 路由规则。",
            requires_clarification=False,
            fallback_behavior="invoke_default",
            source="deterministic_rule",
        )

    async def _create_supervisor_skill_child_run(
        self,
        *,
        request: CreateRunRequest,
        selection: CapabilitySelection,
    ) -> CreateRunResponse:
        trace_id = f"trc_{self.runs.next_run_number:06d}"
        self.sessions.get_or_create(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
        )
        parent_run = self.runs.start_run(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
            kind=RunKind.INVOKE,
            input_text=request.input.text,
            trace_id=trace_id,
            created_by=request.metadata.get("created_by"),
            source=request.metadata.get("source"),
            metadata=request.metadata,
        )
        self.events.append(
            session_id=request.session_id,
            run_id=parent_run.run_id,
            type="capability_selected",
            payload={"selection": selection.model_dump(mode="json", exclude_none=True)},
            trace_id=parent_run.trace_id,
        )
        child_response = await self._create_skill_run(
            CreateRunRequest(
                kind=RunKind.SKILL_RUN,
                session_id=request.session_id,
                parent_run_id=parent_run.run_id,
                capability_id=selection.capability_id,
                input=CreateRunInput.model_validate(selection.input),
                output_contract=selection.output_contract,
                context_refs=selection.context_refs,
                metadata=request.metadata,
            )
        )
        artifact_id = child_response.artifact_id
        child_run_id = child_response.run_id
        artifact_refs = [artifact_id] if artifact_id else []
        child_run_ids = [child_run_id]
        self.runs.complete_run(
            parent_run.run_id,
            result_text="",
            usage={},
            done_payload={
                "artifact_refs": artifact_refs,
                "child_run_ids": child_run_ids,
            },
        )
        if artifact_id:
            artifact = self.artifacts.get_artifact(artifact_id)
            if artifact:
                self._store_artifact_summary(
                    request.session_id,
                    {
                        "artifact_id": artifact.artifact_id,
                        "kind": artifact.kind,
                        "title": artifact.title,
                        "summary": str(artifact.content.get("body") or "")[:120],
                        "capability_id": selection.capability_id,
                    },
                )
        return CreateRunResponse(
            run_id=parent_run.run_id,
            session_id=request.session_id,
            kind=request.kind,
            status=RunStatus.COMPLETED,
            trace_id=trace_id,
            artifact_id=artifact_id,
            urls=RunUrls.for_run(parent_run.run_id, request.session_id),
        )

    def _create_supervisor_approval_run(
        self,
        *,
        request: CreateRunRequest,
        selection: CapabilitySelection,
    ) -> CreateRunResponse:
        trace_id = f"trc_{self.runs.next_run_number:06d}"
        self.sessions.get_or_create(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
        )
        run = self.runs.start_run(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
            kind=RunKind.INVOKE,
            input_text=request.input.text,
            trace_id=trace_id,
            created_by=request.metadata.get("created_by"),
            source=request.metadata.get("source"),
            metadata=request.metadata,
        )
        artifact_refs = [
            ref.removeprefix("artifact:")
            for ref in selection.context_refs
            if ref.startswith("artifact:")
        ]
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="approval_required",
            payload={
                "approval_id": f"appr_{run.run_id}",
                "action_kind": selection.metadata.get("action_kind"),
                "artifact_refs": artifact_refs,
            },
            trace_id=run.trace_id,
        )
        self.runs.complete_run(
            run.run_id,
            result_text="",
            usage={},
            done_payload={
                "approval_id": f"appr_{run.run_id}",
                "artifact_refs": artifact_refs,
            },
        )
        return CreateRunResponse(
            run_id=run.run_id,
            session_id=request.session_id,
            kind=request.kind,
            status=RunStatus.COMPLETED,
            trace_id=trace_id,
            urls=RunUrls.for_run(run.run_id, request.session_id),
        )

    async def _create_expert_run(self, request: CreateRunRequest) -> CreateRunResponse:
        validation_error = self._validate_expert_run_fields(request)
        if validation_error:
            raise ValueError(json.dumps(validation_error))

        expert = self.experts.get_expert(str(request.expert_id))
        owner_id = str(request.metadata["owner_id"])
        conversation_id = str(request.metadata["conversation_id"])
        linked_session_id = expert.session_id_for(
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        trace_id = f"trc_{self.runs.next_run_number:06d}"
        user_text = request.input.text or ""
        self.sessions.get_or_create(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
        )
        self.sessions.get_or_create(
            session_id=linked_session_id,
            agent_profile=expert.hermes_profile,
            metadata={
                "linked_session": {
                    "source_session_id": request.session_id,
                    "linked_session_id": linked_session_id,
                    "expert_id": expert.expert_id,
                    "metadata": {
                        "owner_id": owner_id,
                        "conversation_id": conversation_id,
                    },
                }
            },
        )
        conversation_history = self.sessions.get_recent_messages(linked_session_id)
        run = self.runs.start_run(
            session_id=request.session_id,
            agent_profile=expert.hermes_profile,
            kind=RunKind.EXPERT_RUN,
            input_text=user_text,
            trace_id=trace_id,
            parent_run_id=request.parent_run_id,
            created_by=request.metadata.get("created_by"),
            source=request.metadata.get("source"),
            metadata={
                **request.metadata,
                "expert_id": expert.expert_id,
                "linked_session_id": linked_session_id,
            },
        )
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="expert_selected",
            payload={
                "expert_id": expert.expert_id,
                "linked_session_id": linked_session_id,
            },
            trace_id=run.trace_id,
        )
        artifact_id = self._input_field(request.input, "artifact_id")
        required_context = [f"artifact:{artifact_id}"] if artifact_id else []
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="readiness_check",
            payload={"status": "ready", "required_context": required_context},
            trace_id=run.trace_id,
        )
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="work_plan",
            payload={"summary": "先判断语气，再给出两版修改建议"},
            trace_id=run.trace_id,
        )
        try:
            result = await self._legacy_runtime.invoke_raw(
                session_id=linked_session_id,
                user_text=user_text,
                agent_profile=expert.hermes_profile,
                system_prompt=None,
                conversation_history=conversation_history,
            )
        except Exception as exc:
            self.runs.fail_run(run.run_id, error=str(exc))
            raise

        final_response = str(result.get("final_response") or "")
        self.runs.complete_run(
            run.run_id,
            result_text=final_response,
            usage=self._usage_from_result(result),
            done_payload={"summary": final_response},
        )
        self.sessions.append_turn(
            linked_session_id,
            user_text=user_text,
            assistant_text=final_response,
            metadata={"run_id": run.run_id, "expert_id": expert.expert_id},
        )
        self._store_expert_summary(
            request.session_id,
            {
                "linked_session_id": linked_session_id,
                "expert_id": expert.expert_id,
                "expert_summary": final_response,
                "source_run_id": run.run_id,
            },
        )
        return CreateRunResponse(
            run_id=run.run_id,
            session_id=request.session_id,
            kind=request.kind,
            status=RunStatus.COMPLETED,
            trace_id=trace_id,
            urls=RunUrls.for_run(run.run_id, request.session_id),
        )

    def _validate_expert_run_fields(self, request: CreateRunRequest) -> dict[str, Any] | None:
        missing: list[str] = []
        if not request.expert_id:
            missing.append("expert_id")
        if not request.metadata.get("owner_id"):
            missing.append("owner_id")
        if not request.metadata.get("conversation_id"):
            missing.append("conversation_id")
        if not missing:
            return None
        return {
            "code": "RUN_KIND_UNSUPPORTED",
            "details": {
                "kind": request.kind.value,
                "missing": missing,
                "unexpected": [],
            },
        }

    def _store_expert_summary(
        self,
        session_id: str,
        summary: dict[str, Any],
    ) -> None:
        session = self.sessions.get(session_id)
        existing = list((session.metadata if session else {}).get("expert_summaries") or [])
        existing.append(summary)
        self.sessions.update_metadata(session_id, {"expert_summaries": existing})

    def _create_supervisor_clarification_run(
        self,
        *,
        request: CreateRunRequest,
        selection: CapabilitySelection,
    ) -> CreateRunResponse:
        trace_id = f"trc_{self.runs.next_run_number:06d}"
        self.sessions.get_or_create(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
        )
        run = self.runs.start_run(
            session_id=request.session_id,
            agent_profile=request.agent_profile,
            kind=RunKind.INVOKE,
            input_text=request.input.text,
            trace_id=trace_id,
            created_by=request.metadata.get("created_by"),
            source=request.metadata.get("source"),
            metadata=request.metadata,
        )
        self.events.append(
            session_id=request.session_id,
            run_id=run.run_id,
            type="clarify_required",
            payload={
                "missing_inputs": selection.missing_inputs,
                "selection": selection.model_dump(mode="json", exclude_none=True),
            },
            trace_id=run.trace_id,
        )
        self.runs.complete_run(
            run.run_id,
            result_text="",
            usage={},
            done_payload={
                "missing_inputs": selection.missing_inputs,
                "fallback_behavior": selection.fallback_behavior,
            },
        )
        return CreateRunResponse(
            run_id=run.run_id,
            session_id=request.session_id,
            kind=request.kind,
            status=RunStatus.COMPLETED,
            trace_id=trace_id,
            urls=RunUrls.for_run(run.run_id, request.session_id),
        )

    def _store_artifact_summary(
        self,
        session_id: str,
        summary: dict[str, Any],
    ) -> None:
        session = self.sessions.get(session_id)
        existing = list((session.metadata if session else {}).get("artifact_summaries") or [])
        existing.append(summary)
        self.sessions.update_metadata(session_id, {"artifact_summaries": existing})

    @staticmethod
    def _extract_product_for_xhs(user_text: str) -> str:
        text = user_text.strip()
        for pattern in (
            r"为(.+?)(?:生成|写|产出|做)(?:一段|一篇|一份)?(?:种草文|小红书|笔记|内容)",
            r"针对(.+?)(?:生成|写|产出|做)(?:一段|一篇|一份)?(?:种草文|小红书|笔记|内容)",
        ):
            match = re.search(pattern, text)
            if match and match.group(1).strip():
                return match.group(1).strip(" ，。、“”\"'")
        for marker in ("帮我生成", "帮我写", "生成", "写"):
            text = text.replace(marker, "")
        text = re.sub(r"请用AI工具箱的?小红书笔记生成器[，,]?", "", text)
        text = text.replace("的小红书", "").replace("小红书", "")
        return text.strip(" ，。") or "待确认产品"

    def _latest_artifact_ref(
        self,
        *,
        session_id: str,
        context_refs: list[str],
    ) -> str | None:
        for ref in reversed(context_refs):
            if ref.startswith("artifact:"):
                return ref.removeprefix("artifact:")
        session = self.sessions.get(session_id)
        summaries = list((session.metadata if session else {}).get("artifact_summaries") or [])
        for summary in reversed(summaries):
            artifact_id = summary.get("artifact_id")
            if artifact_id:
                return str(artifact_id)
        return None

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
        self._emit_skill_tool_events(request=request, capability=capability, run=run)

        final_response = self._sanitize_skill_final_response(
            str(result.get("final_response") or ""),
            capability=capability,
        )
        image_result = await self._maybe_generate_skill_image(
            request=request,
            capability=capability,
            final_response=final_response,
        )
        artifact_id = self.artifacts.next_available_artifact_id(f"art_{run.run_id}")
        artifact_content = {"body": final_response}
        artifact_metadata = {
            "capability_id": capability.capability_id,
            **self._artifact_metadata_from_input(request.input),
        }
        if image_result and image_result.get("image_url"):
            artifact_content.update(
                {
                    "imageUrl": image_result["image_url"],
                    "imagePrompt": image_result["prompt"],
                    "imageRaw": image_result.get("raw"),
                }
            )
            artifact_metadata.update(
                {
                    "image_provider": "nexus",
                    "image_model": image_result.get("model"),
                }
            )
        elif image_result:
            artifact_content.update(
                {
                    "imageStatus": image_result.get("status") or "error",
                    "imageError": image_result.get("error") or "NEXUS 生图接口暂未返回图片，文案已先生成。",
                    "imagePrompt": image_result.get("prompt"),
                }
            )
            artifact_metadata.update(
                {
                    "image_provider": "nexus",
                    "image_status": image_result.get("status") or "error",
                }
            )
        artifact = self.artifacts.create_artifact(
            artifact_id=artifact_id,
            session_id=request.session_id,
            run_id=run.run_id,
            kind=self._artifact_kind_for_capability(capability),
            title=capability.title,
            content=artifact_content,
            metadata=artifact_metadata,
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
            image_url=image_result.get("image_url") if image_result else None,
            image_prompt=image_result.get("prompt") if image_result else None,
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
        instruction = (
            f"/{capability.slash_command} "
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )
        if capability.capability_id == "moments_copywriter_with_image":
            instruction += (
                "\n系统会自动调用 NEXUS 生图接口生成配图；"
                "请直接输出朋友圈文案，不要询问是否需要出图，不要提 ComfyUI 或内部工具名。"
            )
        return instruction

    @staticmethod
    def _artifact_kind_for_capability(capability: CapabilityManifest) -> str:
        if capability.capability_id == "xiaohongshu_note_writer":
            return "xiaohongshu_note"
        if capability.capability_id.startswith("moments_copywriter"):
            return "moments_copy"
        return capability.capability_id

    @staticmethod
    def _artifact_metadata_from_input(input_payload: CreateRunInput) -> dict[str, Any]:
        payload = input_payload.model_dump(exclude_none=True)
        source_artifact_id = payload.get("source_artifact_id")
        return {"source_artifact_id": source_artifact_id} if source_artifact_id else {}

    @staticmethod
    def _sanitize_skill_final_response(text: str, *, capability: CapabilityManifest) -> str:
        if capability.capability_id != "moments_copywriter_with_image":
            return text
        sanitized = HermesRuntimeFacade._unwrap_skill_card_text(text)
        sanitized = re.sub(
            r"\n+##\s*[^\n]*(?:海报|配图)[^\n]*\n.*?(?=\n---\n|\Z)",
            "",
            sanitized,
            flags=re.S,
        )
        sanitized = re.sub(r"[^。！？\n]*ComfyUI[^。！？\n]*[。！？]?", "", sanitized)
        sanitized = re.sub(r"(?im)^.*ComfyUI.*(?:\n|$)", "", sanitized)
        sanitized = re.sub(
            r"[^。！？\n]*(?:要我|需要我|是否需要|要不要)[^。！？\n]*(?:出|生成|做|配)[^。！？\n]*(?:图|图片|配图)[^。！？\n]*[。！？]?",
            "",
            sanitized,
        )
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
        if sanitized:
            return sanitized
        return "" if "ComfyUI" in text else text

    @staticmethod
    def _unwrap_skill_card_text(text: str) -> str:
        stripped = text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.S | re.I)
        if fenced:
            stripped = fenced.group(1).strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            body = HermesRuntimeFacade._extract_loose_json_string_field(stripped, "body")
            return body or text
        if not isinstance(parsed, dict):
            return text

        data = parsed.get("data") if isinstance(parsed.get("data"), dict) else {}
        for value in (
            data.get("body"),
            data.get("full_output"),
            data.get("summary"),
            data.get("preview"),
            parsed.get("body"),
            parsed.get("summary"),
            parsed.get("speech"),
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return text

    @staticmethod
    def _extract_loose_json_string_field(text: str, field_name: str) -> str | None:
        match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"', text)
        if not match:
            return None
        index = match.end()
        chars: list[str] = []
        escaped = False
        while index < len(text):
            char = text[index]
            if escaped:
                if char == "n":
                    chars.append("\n")
                elif char == "t":
                    chars.append("\t")
                elif char == "r":
                    chars.append("\r")
                else:
                    chars.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                tail = text[index + 1 : index + 80]
                if re.match(r"\s*[,}]", tail):
                    return "".join(chars).strip()
                chars.append(char)
            else:
                chars.append(char)
            index += 1
        return None

    @staticmethod
    def _extract_moments_topic(user_text: str) -> str:
        topic = user_text.strip()
        for prefix in ("帮我写一个", "帮我写", "写一个", "生成一个", "生成"):
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        topic = re.sub(r"[，,。；;！!？?]*\s*(再)?配[一1]张图.*$", "", topic).strip()
        topic = re.sub(r"[，,。；;！!？?]*\s*朋友圈.*$", "", topic).strip()
        topic = re.sub(r"的$", "", topic).strip()
        return topic or user_text.strip()

    async def _maybe_generate_skill_image(
        self,
        *,
        request: CreateRunRequest,
        capability: CapabilityManifest,
        final_response: str,
    ) -> dict[str, Any] | None:
        if capability.capability_id != "moments_copywriter_with_image":
            return None
        payload = request.input.model_dump(exclude_none=True)
        if payload.get("need_image") is not True:
            return None

        prompt = self._image_prompt_from_skill_input(payload, final_response)
        if not prompt:
            return None
        return await asyncio.to_thread(self._call_nexus_image_generation, prompt)

    @staticmethod
    def _image_prompt_from_skill_input(payload: dict[str, Any], final_response: str) -> str:
        for key in ("image_prompt", "imagePrompt", "topic", "product"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return final_response.strip()[:500]

    @staticmethod
    def _call_nexus_image_generation(prompt: str) -> dict[str, Any] | None:
        nexus_url = os.environ.get("NEXUS_URL", "").strip().rstrip("/")
        nexus_api_key = os.environ.get("NEXUS_API_KEY", "").strip()
        if not nexus_url:
            return None

        body = {
            "prompt": prompt,
            "size": "1024x1024",
            "n": 1,
            "response_format": "url",
            "output_format": "png",
        }
        req = urllib.request.Request(
            f"{nexus_url}/api/llm/images/generations",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {nexus_api_key}",
            },
            method="POST",
        )
        timeout = int(os.environ.get("NEXUS_IMAGE_TIMEOUT_SECONDS", "120"))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except TimeoutError:
            return {
                "status": "timeout",
                "prompt": prompt,
                "error": "NEXUS 生图接口超时，文案已先生成。",
            }
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return {
                "status": "error",
                "prompt": prompt,
                "error": "NEXUS 生图接口暂未返回图片，文案已先生成。",
            }

        image_url = HermesRuntimeFacade._extract_image_url_from_generation_response(raw)
        if not image_url:
            return {
                "status": "error",
                "prompt": prompt,
                "raw": raw,
                "error": "NEXUS 生图接口未返回图片地址，文案已先生成。",
            }
        return {
            "status": "completed",
            "image_url": image_url,
            "prompt": prompt,
            "model": raw.get("model") if isinstance(raw, dict) else None,
            "raw": raw,
        }

    @staticmethod
    def _extract_image_url_from_generation_response(raw: Any) -> str | None:
        if not isinstance(raw, dict):
            return None
        for key in ("imageUrl", "url"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data = raw.get("data")
        if isinstance(data, dict):
            for key in ("imageUrl", "url"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                for key in ("imageUrl", "url"):
                    value = first.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                b64 = first.get("b64_json") or first.get("b64Json")
                if isinstance(b64, str) and b64.strip():
                    return f"data:image/png;base64,{b64.strip()}"
        return None

    @staticmethod
    def _input_field(input_payload: CreateRunInput, field_name: str) -> Any:
        return input_payload.model_dump(exclude_none=True).get(field_name)

    def _emit_skill_tool_events(
        self,
        *,
        request: CreateRunRequest,
        capability: CapabilityManifest,
        run: RuntimeRun,
    ) -> None:
        if capability.capability_id != "moments_copywriter_with_image":
            return
        for tool_name in ("朋友圈文案生成", "配图生成"):
            self.events.append(
                session_id=request.session_id,
                run_id=run.run_id,
                type="tool_started",
                payload={"tool_name": tool_name},
                trace_id=run.trace_id,
            )
            self.events.append(
                session_id=request.session_id,
                run_id=run.run_id,
                type="tool_completed",
                payload={"tool_name": tool_name},
                trace_id=run.trace_id,
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
