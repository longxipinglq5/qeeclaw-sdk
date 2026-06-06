from __future__ import annotations


def test_digital_employee_owns_multiple_reusable_loop_definitions():
    from bridge.runtime_facade.loops import (
        DigitalEmployee,
        LoopDefinition,
        LoopRegistry,
    )

    registry = LoopRegistry()
    registry.register_loop_definition(
        LoopDefinition(
            loop_id="content_generation",
            title="内容生成",
            capability_ids=["xiaohongshu_note_writer", "moments_copywriter_with_image"],
        )
    )
    registry.register_loop_definition(
        LoopDefinition(
            loop_id="metrics_review",
            title="效果复盘",
            capability_ids=["campaign_metrics_reviewer"],
        )
    )
    employee = registry.register_employee(
        DigitalEmployee(
            employee_id="marketing_employee",
            owner_id="owner_1",
            title="营销增长数字员工",
            human_organizer_id="owner_1",
            loop_definition_ids=["content_generation", "metrics_review"],
        )
    )

    definitions = registry.loop_definitions_for_employee(employee.employee_id)

    assert [definition.loop_id for definition in definitions] == [
        "content_generation",
        "metrics_review",
    ]
    assert definitions[0].capability_ids == [
        "xiaohongshu_note_writer",
        "moments_copywriter_with_image",
    ]


def test_loop_cycles_are_per_run_while_loop_definitions_are_reusable():
    from bridge.runtime_facade.centaur_state import LoopStage
    from bridge.runtime_facade.loops import LoopCycle, LoopDefinition

    definition = LoopDefinition(
        loop_id="content_generation",
        title="内容生成",
        capability_ids=["xiaohongshu_note_writer"],
    )

    first_run_cycle = LoopCycle.create(
        run_id="run_001",
        goal_id="goal_lamp_001",
        loop_definition=definition,
        index=1,
    )
    second_run_cycle = LoopCycle.create(
        run_id="run_002",
        goal_id="goal_lamp_002",
        loop_definition=definition,
        index=1,
    )

    assert first_run_cycle.loop_id == second_run_cycle.loop_id == definition.loop_id
    assert first_run_cycle.cycle_id == "cycle_content_generation_001"
    assert second_run_cycle.cycle_id == "cycle_content_generation_001"
    assert first_run_cycle.run_id == "run_001"
    assert second_run_cycle.run_id == "run_002"
    assert first_run_cycle.stage == LoopStage.PLANNING
    assert second_run_cycle.stage == LoopStage.PLANNING


def test_marketing_growth_fixture_registers_expected_loops():
    from bridge.runtime_facade.loops import create_marketing_growth_fixture

    registry = create_marketing_growth_fixture(owner_id="owner_1")

    employee = registry.get_employee("marketing_growth_v1")
    definitions = registry.loop_definitions_for_employee("marketing_growth_v1")

    assert employee is not None
    assert employee.human_organizer_id == "owner_1"
    assert [definition.loop_id for definition in definitions] == [
        "content_generation",
        "content_publishing",
        "customer_followup",
        "metrics_review",
    ]
    assert definitions[0].input_contract == {"required": ["product", "campaign_goal"]}
    assert definitions[-1].output_contract == {
        "memory_candidates": ["campaign_learning"],
    }


def test_loop_scheduler_plans_cycles_in_dependency_order_not_registration_order():
    from bridge.runtime_facade.loops import (
        DigitalEmployee,
        LoopDefinition,
        LoopRegistry,
        LoopScheduler,
    )

    registry = LoopRegistry()
    registry.register_loop_definition(
        LoopDefinition(loop_id="metrics_review", title="复盘", depends_on=["content_publishing"])
    )
    registry.register_loop_definition(
        LoopDefinition(loop_id="content_publishing", title="发布", depends_on=["content_generation"])
    )
    registry.register_loop_definition(
        LoopDefinition(
            loop_id="content_generation",
            title="生成",
            input_contract={"required": ["product"]},
        )
    )
    registry.register_employee(
        DigitalEmployee(
            employee_id="marketing_employee",
            owner_id="owner_1",
            title="营销增长数字员工",
            human_organizer_id="owner_1",
            loop_definition_ids=[
                "metrics_review",
                "content_publishing",
                "content_generation",
            ],
        )
    )

    result = LoopScheduler(registry).plan_cycles(
        employee_id="marketing_employee",
        run_id="run_001",
        goal_id="goal_001",
        input={"product": "儿童护眼台灯"},
    )

    assert result.error_code is None
    assert [cycle.loop_id for cycle in result.cycles] == [
        "content_generation",
        "content_publishing",
        "metrics_review",
    ]
    assert [cycle.index for cycle in result.cycles] == [1, 2, 3]
    assert result.events == []


def test_loop_scheduler_reports_missing_dependency_without_cycles():
    from bridge.runtime_facade.loops import DigitalEmployee, LoopDefinition, LoopRegistry, LoopScheduler

    registry = LoopRegistry()
    registry.register_loop_definition(
        LoopDefinition(loop_id="content_publishing", title="发布", depends_on=["content_generation"])
    )
    registry.register_employee(
        DigitalEmployee(
            employee_id="marketing_employee",
            owner_id="owner_1",
            title="营销增长数字员工",
            human_organizer_id="owner_1",
            loop_definition_ids=["content_publishing"],
        )
    )

    result = LoopScheduler(registry).plan_cycles(
        employee_id="marketing_employee",
        run_id="run_001",
        goal_id="goal_001",
        input={},
    )

    assert result.error_code == "LOOP_DEPENDENCY_NOT_FOUND"
    assert result.cycles == []
    assert result.details == {
        "loop_id": "content_publishing",
        "missing_dependency": "content_generation",
    }


def test_loop_scheduler_reports_dependency_cycle_with_path():
    from bridge.runtime_facade.loops import DigitalEmployee, LoopDefinition, LoopRegistry, LoopScheduler

    registry = LoopRegistry()
    registry.register_loop_definition(
        LoopDefinition(loop_id="content_generation", title="生成", depends_on=["metrics_review"])
    )
    registry.register_loop_definition(
        LoopDefinition(loop_id="metrics_review", title="复盘", depends_on=["content_generation"])
    )
    registry.register_employee(
        DigitalEmployee(
            employee_id="marketing_employee",
            owner_id="owner_1",
            title="营销增长数字员工",
            human_organizer_id="owner_1",
            loop_definition_ids=["content_generation", "metrics_review"],
        )
    )

    result = LoopScheduler(registry).plan_cycles(
        employee_id="marketing_employee",
        run_id="run_001",
        goal_id="goal_001",
        input={},
    )

    assert result.error_code == "LOOP_DEPENDENCY_CYCLE"
    assert result.cycles == []
    assert result.details == {
        "cycle_path": ["content_generation", "metrics_review", "content_generation"],
    }


def test_loop_scheduler_reports_input_contract_violation_event():
    from bridge.runtime_facade.loops import DigitalEmployee, LoopDefinition, LoopRegistry, LoopScheduler

    registry = LoopRegistry()
    registry.register_loop_definition(
        LoopDefinition(
            loop_id="content_generation",
            title="生成",
            input_contract={"required": ["product", "campaign_goal"]},
        )
    )
    registry.register_employee(
        DigitalEmployee(
            employee_id="marketing_employee",
            owner_id="owner_1",
            title="营销增长数字员工",
            human_organizer_id="owner_1",
            loop_definition_ids=["content_generation"],
        )
    )

    result = LoopScheduler(registry).plan_cycles(
        employee_id="marketing_employee",
        run_id="run_001",
        goal_id="goal_001",
        input={"product": "儿童护眼台灯"},
    )

    assert result.error_code == "LOOP_INPUT_INVALID"
    assert result.cycles == []
    assert result.events == [
        {
            "event_type": "loop_contract_violation",
            "loop_id": "content_generation",
            "missing_required": ["campaign_goal"],
        }
    ]


def test_failure_policy_helpers_emit_stable_policy_payloads():
    from bridge.runtime_facade.loops import pause_goal, pause_loop, skip_cycle

    assert pause_loop(loop_id="content_generation", reason="missing input") == {
        "event_type": "loop_failure_policy",
        "policy": "pause_loop",
        "loop_id": "content_generation",
        "reason": "missing input",
    }
    assert skip_cycle(cycle_id="cycle_content_generation_001", reason="operator skipped") == {
        "event_type": "loop_failure_policy",
        "policy": "skip_cycle",
        "cycle_id": "cycle_content_generation_001",
        "reason": "operator skipped",
    }
    assert pause_goal(goal_id="goal_001", reason="dependency failed") == {
        "event_type": "loop_failure_policy",
        "policy": "pause_goal",
        "goal_id": "goal_001",
        "reason": "dependency failed",
    }
