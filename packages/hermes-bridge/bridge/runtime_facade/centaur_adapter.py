from __future__ import annotations

from typing import Literal

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
