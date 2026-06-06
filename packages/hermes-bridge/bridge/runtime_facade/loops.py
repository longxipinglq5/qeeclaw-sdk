from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from bridge.runtime_facade.centaur_state import LoopStage


class DigitalEmployee(BaseModel):
    employee_id: str
    owner_id: str
    title: str
    human_organizer_id: str
    loop_definition_ids: list[str] = Field(default_factory=list)
    status: Literal["active", "paused", "archived"] = "active"


class LoopDefinition(BaseModel):
    loop_id: str
    title: str
    depends_on: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    input_contract: dict[str, list[str]] = Field(default_factory=dict)
    output_contract: dict[str, list[str]] = Field(default_factory=dict)
    failure_policy: str = "pause_loop"


class LoopCycle(BaseModel):
    cycle_id: str
    run_id: str
    goal_id: str
    loop_id: str
    index: int
    stage: LoopStage = LoopStage.PLANNING

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        goal_id: str,
        loop_definition: LoopDefinition,
        index: int,
    ) -> "LoopCycle":
        return cls(
            cycle_id=f"cycle_{loop_definition.loop_id}_{index:03d}",
            run_id=run_id,
            goal_id=goal_id,
            loop_id=loop_definition.loop_id,
            index=index,
        )


class LoopRegistry:
    def __init__(self) -> None:
        self._employees: dict[str, DigitalEmployee] = {}
        self._loop_definitions: dict[str, LoopDefinition] = {}

    def register_employee(self, employee: DigitalEmployee) -> DigitalEmployee:
        self._employees[employee.employee_id] = employee
        return employee

    def get_employee(self, employee_id: str) -> DigitalEmployee | None:
        return self._employees.get(employee_id)

    def register_loop_definition(self, definition: LoopDefinition) -> LoopDefinition:
        self._loop_definitions[definition.loop_id] = definition
        return definition

    def get_loop_definition(self, loop_id: str) -> LoopDefinition | None:
        return self._loop_definitions.get(loop_id)

    def loop_definitions_for_employee(self, employee_id: str) -> list[LoopDefinition]:
        employee = self._employees[employee_id]
        return [self._loop_definitions[loop_id] for loop_id in employee.loop_definition_ids]


def create_marketing_growth_fixture(*, owner_id: str) -> LoopRegistry:
    registry = LoopRegistry()
    definitions = [
        LoopDefinition(
            loop_id="content_generation",
            title="内容生成",
            capability_ids=[
                "xiaohongshu_note_writer",
                "moments_copywriter_with_image",
                "customer_group_followup_writer",
            ],
            input_contract={"required": ["product", "campaign_goal"]},
            output_contract={
                "artifacts": [
                    "xiaohongshu_note",
                    "moments_post_with_image",
                    "customer_group_followup_script",
                ]
            },
        ),
        LoopDefinition(
            loop_id="content_publishing",
            title="内容发布",
            depends_on=["content_generation"],
            input_contract={"required": ["artifact_refs"]},
            output_contract={"outbox_refs": ["published_content"]},
        ),
        LoopDefinition(
            loop_id="customer_followup",
            title="客户跟进",
            depends_on=["content_publishing"],
            input_contract={"required": ["published_content", "followup_script"]},
            output_contract={"outbox_refs": ["customer_messages"]},
        ),
        LoopDefinition(
            loop_id="metrics_review",
            title="效果复盘",
            depends_on=["content_publishing", "customer_followup"],
            input_contract={
                "required": [
                    "published_content",
                    "customer_messages",
                    "feedback_metrics",
                ]
            },
            output_contract={"memory_candidates": ["campaign_learning"]},
        ),
    ]
    for definition in definitions:
        registry.register_loop_definition(definition)

    registry.register_employee(
        DigitalEmployee(
            employee_id="marketing_growth_v1",
            owner_id=owner_id,
            title="营销增长数字员工",
            human_organizer_id=owner_id,
            loop_definition_ids=[definition.loop_id for definition in definitions],
        )
    )
    return registry
