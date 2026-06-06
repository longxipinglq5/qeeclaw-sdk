from __future__ import annotations

from typing import Literal

from bridge.runtime_facade.automation_status import AutomationRunStatus, AutomationStatusProjector
from bridge.runtime_facade.event_bus import EventBus
from bridge.runtime_facade.loops import LoopRegistry, LoopScheduler, create_marketing_growth_fixture
from bridge.runtime_facade.models import RuntimeRun
from bridge.runtime_facade.run_manager import RunManager


class CentaurLoopRuntimeAdapter:
    def __init__(
        self,
        *,
        event_bus: EventBus,
        run_manager: RunManager,
        missing_memory_decision_policy: Literal["emit_no_memory_candidate", "pause"] = "emit_no_memory_candidate",
    ) -> None:
        self._events = event_bus
        self._runs = run_manager
        self._missing_memory_decision_policy = missing_memory_decision_policy

    def start_run(
        self,
        *,
        run: RuntimeRun,
        registry: LoopRegistry | None = None,
        employee_id: str,
        goal_id: str,
        input: dict[str, object],
    ) -> None:
        registry = registry or create_marketing_growth_fixture(owner_id=str(run.metadata["owner_id"]))
        definitions = registry.loop_definitions_for_employee("marketing_growth_v1")
        self._append(run, "automation_started", {"goal_id": goal_id, "current_step": "启动营销半人马环"})
        for definition in definitions:
            self._append(run, "loop_registered", {"loop_id": definition.loop_id})

        plan = LoopScheduler(registry).plan_cycles(
            employee_id="marketing_growth_v1",
            run_id=run.run_id,
            goal_id=goal_id,
            input={
                **input,
                "artifact_refs": [],
                "published_content": [],
                "followup_script": "",
                "customer_messages": [],
                "feedback_metrics": {},
            },
        )
        for cycle in plan.cycles:
            self._append(
                run,
                "cycle_planned",
                {"cycle_id": cycle.cycle_id, "loop_id": cycle.loop_id},
            )

        if not plan.cycles:
            return

        first_cycle = plan.cycles[0]
        self._append(run, "cycle_started", {"cycle_id": first_cycle.cycle_id, "loop_id": first_cycle.loop_id})
        self._append(
            run,
            "loop_stage_changed",
            {
                "cycle_id": first_cycle.cycle_id,
                "loop_id": first_cycle.loop_id,
                "stage": "awaiting_plan_review",
            },
        )
        approval_id = "appr_plan_001"
        self._append(
            run,
            "work_plan",
            {
                "cycle_id": first_cycle.cycle_id,
                "approval_id": approval_id,
                "summary": "先确认内容生成计划，再执行后续营销环节",
            },
        )
        self._append(
            run,
            "approval_required",
            {
                "cycle_id": first_cycle.cycle_id,
                "approval_id": approval_id,
                "action_kind": "plan_review",
                "current_step": "等待确认内容生成计划",
            },
        )
        self._mark_waiting_approval(run)

    def handle_reviewer_done_without_memory_decision(
        self,
        *,
        run: RuntimeRun,
        cycle_id: str,
    ) -> None:
        self._append(
            run,
            "review_output_incomplete",
            {
                "cycle_id": cycle_id,
                "missing": ["memory_candidate", "no_memory_candidate"],
            },
        )
        if self._missing_memory_decision_policy != "emit_no_memory_candidate":
            self._mark_waiting_approval(run)
            return
        self._append(
            run,
            "no_memory_candidate",
            {
                "cycle_id": cycle_id,
                "reason": "reviewer_omitted_memory_decision",
            },
        )
        self._append(run, "learning_recorded", {"cycle_id": cycle_id})
        self._append(run, "cycle_completed", {"cycle_id": cycle_id})

    def complete_marketing_flow_with_fake_outputs(
        self,
        *,
        run: RuntimeRun,
        product: str,
        modification: dict[str, str],
        metrics: dict[str, object],
    ) -> None:
        content_cycle = "cycle_content_generation_001"
        publish_cycle = "cycle_content_publishing_002"
        followup_cycle = "cycle_customer_followup_003"
        review_cycle = "cycle_metrics_review_004"

        self._append(run, "human_review", {"approval_id": "appr_plan_001", "decision": "approved"})
        self._append(run, "loop_stage_changed", {"cycle_id": content_cycle, "stage": "generating"})
        for child_run_id, artifact_id, kind in [
            ("run_skill_xhs_001", "art_xhs_001", "xiaohongshu_note"),
            ("run_skill_moments_001", "art_moments_001", "moments_post_with_image"),
            ("run_skill_group_001", "art_group_followup_001", "customer_group_followup_script"),
        ]:
            self._append(run, "app_started", {"child_run_id": child_run_id, "parent_run_id": run.run_id})
            self._append(
                run,
                "artifact_created",
                {"artifact_id": artifact_id, "kind": kind, "product": product},
            )
        self._append(run, "loop_stage_changed", {"cycle_id": content_cycle, "stage": "awaiting_review"})
        self._append(run, "approval_required", {"cycle_id": content_cycle, "approval_id": "appr_draft_001", "action_kind": "draft_review"})
        self._append(run, "human_review", {"approval_id": "appr_draft_001", "decision": "revision_requested", **modification})
        self._append(run, "app_started", {"child_run_id": "run_skill_moments_revision_001", "parent_run_id": run.run_id})
        self._append(
            run,
            "artifact_created",
            {
                "artifact_id": "art_moments_002",
                "kind": "moments_post_with_image",
                "revision_of": modification["artifact_id"],
            },
        )
        self._append(run, "loop_stage_changed", {"cycle_id": content_cycle, "stage": "awaiting_publish"})
        self._append(run, "approval_required", {"cycle_id": content_cycle, "approval_id": "appr_publish_001", "action_kind": "publish_content"})
        self._append(run, "approval_required", {"cycle_id": content_cycle, "approval_id": "appr_contact_001", "action_kind": "contact_customer"})
        self._append(run, "human_review", {"approval_id": "appr_publish_001", "decision": "approved"})
        self._append(run, "human_review", {"approval_id": "appr_contact_001", "decision": "approved"})
        self._append(run, "loop_stage_changed", {"cycle_id": content_cycle, "stage": "cycle_complete"})

        self._complete_simple_cycle(run, publish_cycle)
        self._complete_simple_cycle(run, followup_cycle)

        self._append(run, "loop_stage_changed", {"cycle_id": review_cycle, "stage": "awaiting_feedback"})
        self._append(run, "feedback_received", {"cycle_id": review_cycle, "metrics": metrics})
        self._append(run, "loop_stage_changed", {"cycle_id": review_cycle, "stage": "reviewing_auto"})
        self._append(
            run,
            "memory_candidate",
            {
                "cycle_id": review_cycle,
                "memory_candidate_id": "mem_candidate_001",
                "summary": "真实场景型朋友圈文案带来更多咨询",
            },
        )
        self._append(run, "loop_stage_changed", {"cycle_id": review_cycle, "stage": "awaiting_memory"})
        self._append(run, "approval_required", {"cycle_id": review_cycle, "approval_id": "appr_memory_001", "action_kind": "write_memory"})
        self._append(run, "human_review", {"approval_id": "appr_memory_001", "decision": "approved"})
        self._append(
            run,
            "memory_write_requested",
            {
                "memory_candidate_id": "mem_candidate_001",
                "summary": "真实场景型朋友圈文案带来更多咨询",
            },
        )
        self._append(run, "learning_recorded", {"cycle_id": review_cycle})
        self._append(run, "loop_stage_changed", {"cycle_id": review_cycle, "stage": "cycle_complete"})
        self._append(run, "cycle_completed", {"cycle_id": review_cycle})
        self._append(run, "next_cycle_planned", {"loop_id": "content_generation", "next_wakeup_at": "2026-06-13T09:00:00+00:00"})
        self._append(run, "automation_completed", {"current_step": "自动化完成"})
        self._runs.complete_run(run.run_id, result_text="automation completed", usage={})

    def project_status(self, *, run_id: str) -> AutomationRunStatus:
        return AutomationStatusProjector().project(self._events.list_by_run(run_id))

    def _append(self, run: RuntimeRun, event_type: str, payload: dict[str, object]) -> None:
        self._events.append(
            session_id=run.session_id,
            run_id=run.run_id,
            type=event_type,
            payload=payload,
            trace_id=run.trace_id,
        )

    def _mark_waiting_approval(self, run: RuntimeRun) -> None:
        self._runs.mark_waiting_approval(run.run_id)

    def _complete_simple_cycle(self, run: RuntimeRun, cycle_id: str) -> None:
        self._append(run, "cycle_started", {"cycle_id": cycle_id})
        self._append(run, "loop_stage_changed", {"cycle_id": cycle_id, "stage": "cycle_complete"})
        self._append(run, "cycle_completed", {"cycle_id": cycle_id})
