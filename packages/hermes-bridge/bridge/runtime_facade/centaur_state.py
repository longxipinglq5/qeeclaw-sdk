from __future__ import annotations

from enum import Enum
from typing import Any


class LoopStage(str, Enum):
    PLANNING = "planning"
    AWAITING_PLAN_REVIEW = "awaiting_plan_review"
    GENERATING = "generating"
    AWAITING_REVIEW = "awaiting_review"
    AWAITING_PUBLISH = "awaiting_publish"
    AWAITING_FEEDBACK = "awaiting_feedback"
    REVIEWING_AUTO = "reviewing_auto"
    AWAITING_MEMORY = "awaiting_memory"
    CYCLE_COMPLETE = "cycle_complete"


class UserActionType(str, Enum):
    CONFIRM = "confirm"
    MODIFY = "modify"
    SKIP = "skip"
    REJECT = "reject"


class InvalidLoopTransitionError(RuntimeError):
    pass


class LoopStateGuard:
    def __init__(self) -> None:
        self._events_by_cycle: dict[str, set[str]] = {}
        self._legal_transitions = {
            LoopStage.PLANNING: {LoopStage.AWAITING_PLAN_REVIEW},
            LoopStage.AWAITING_PLAN_REVIEW: {LoopStage.GENERATING},
            LoopStage.GENERATING: {LoopStage.AWAITING_REVIEW},
            LoopStage.AWAITING_REVIEW: {LoopStage.AWAITING_PUBLISH},
            LoopStage.AWAITING_PUBLISH: {LoopStage.AWAITING_FEEDBACK},
            LoopStage.AWAITING_FEEDBACK: {LoopStage.REVIEWING_AUTO},
            LoopStage.REVIEWING_AUTO: {
                LoopStage.AWAITING_MEMORY,
                LoopStage.CYCLE_COMPLETE,
            },
            LoopStage.AWAITING_MEMORY: {LoopStage.CYCLE_COMPLETE},
        }

    def record_runtime_event(self, cycle_id: str, event_type: str) -> None:
        events = self._events_by_cycle.setdefault(cycle_id, set())
        events.add(event_type)

    def can_transition(
        self,
        cycle_id: str,
        current_stage: LoopStage,
        next_stage: LoopStage,
    ) -> bool:
        if current_stage == LoopStage.REVIEWING_AUTO and next_stage == LoopStage.CYCLE_COMPLETE:
            return "no_memory_candidate" in self._events_by_cycle.get(cycle_id, set())
        return next_stage in self._legal_transitions.get(current_stage, set())

    def require_transition(
        self,
        cycle_id: str,
        current_stage: LoopStage,
        next_stage: LoopStage,
    ) -> LoopStage:
        if not self.can_transition(cycle_id, current_stage, next_stage):
            raise InvalidLoopTransitionError(
                f"Invalid loop transition: {current_stage.value} -> {next_stage.value}"
            )
        return next_stage


def create_next_cycle(completed_cycle: dict[str, Any]) -> dict[str, Any]:
    loop_id = str(completed_cycle["loop_id"])
    next_index = int(completed_cycle["index"]) + 1
    return {
        "cycle_id": f"cycle_{loop_id}_{next_index:03d}",
        "loop_id": loop_id,
        "index": next_index,
        "stage": LoopStage.PLANNING,
    }
