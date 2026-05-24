from __future__ import annotations

import asyncio

from xagent.agent_flow.models import (
    AgentFlowState,
    PlanOutput,
    PlanSubagentSelection,
    SubagentResult,
    SummaryDecision,
    SummaryOutput,
)
from xagent.agent_flow.state_projection import _apply, derive_state
from xagent.agent_persistence.memory import InMemoryStepRepository


def _base_state() -> AgentFlowState:
    return AgentFlowState(run_id="run_1", user_query="diagnose no start")


def _plan() -> PlanOutput:
    return PlanOutput(
        goal="Answer user query: diagnose no start",
        selections=[PlanSubagentSelection(name="manuals")],
    )


def _subagent_result() -> SubagentResult:
    return SubagentResult(
        name="manuals",
        status="completed",
        content="manual result",
    )


def _summary_output() -> SummaryOutput:
    return SummaryOutput(
        decision=SummaryDecision.FINAL,
        answer_draft="the answer",
        rationale="done",
    )


def test_apply_returns_unchanged_state_for_unknown_step_name() -> None:
    state = _base_state()
    result = _apply(state, "unknown_step", {})
    iteration = result.get_or_create_current_iteration()
    assert iteration.plan is None
    assert iteration.summary is None
    assert iteration.subagent_results == {}


def test_apply_planner_sets_iteration_plan() -> None:
    state = _base_state()
    plan = _plan()
    result = _apply(state, "planner", plan.model_dump(mode="json"))
    iteration = result.get_or_create_current_iteration()
    assert iteration.plan == plan


def test_apply_subagent_adds_to_subagent_results() -> None:
    state = _base_state()
    subagent_result = _subagent_result()
    result = _apply(state, "subagent:manuals", subagent_result.model_dump())
    iteration = result.get_or_create_current_iteration()
    assert "manuals" in iteration.subagent_results
    assert iteration.subagent_results["manuals"] == subagent_result


def test_apply_summary_sets_iteration_summary() -> None:
    state = _base_state()
    summary_output = _summary_output()
    result = _apply(state, "summary", summary_output.model_dump())
    iteration = result.get_or_create_current_iteration()
    assert iteration.summary == summary_output


def test_apply_does_not_mutate_input_state() -> None:
    state = _base_state()
    plan = _plan()
    _apply(state, "planner", plan.model_dump(mode="json"))
    iteration = state.get_or_create_current_iteration()
    assert iteration.plan is None


def test_derive_state_empty_steps_returns_base() -> None:
    state = _base_state()
    result = derive_state(state, [])
    assert result == state


def test_derive_state_skips_non_succeeded_steps() -> None:
    asyncio.run(_test_derive_state_skips_non_succeeded_steps())


async def _test_derive_state_skips_non_succeeded_steps() -> None:
    repository = InMemoryStepRepository()
    state = _base_state()

    # Create a FAILED step and a RUNNING step
    failed_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await repository.mark_step_running(failed_step.step_id)
    await repository.mark_step_failed(failed_step.step_id, {"message": "error"})

    steps = await repository.get_steps_for_run_iteration(state.run_id, 0)
    result = derive_state(state, steps)
    iteration = result.get_or_create_current_iteration()
    assert iteration.plan is None


def test_derive_state_applies_all_succeeded_steps() -> None:
    asyncio.run(_test_derive_state_applies_all_succeeded_steps())


async def _test_derive_state_applies_all_succeeded_steps() -> None:
    repository = InMemoryStepRepository()
    state = _base_state()
    plan = _plan()
    subagent_result = _subagent_result()
    summary_output = _summary_output()

    # Create and succeed planner step
    planner_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await repository.mark_step_running(planner_step.step_id)
    await repository.mark_step_succeeded(
        planner_step.step_id, plan.model_dump(mode="json")
    )

    # Create and succeed subagent step
    subagent_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="subagent:manuals",
        step_type="subagent",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:subagent:manuals",
    )
    await repository.mark_step_running(subagent_step.step_id)
    await repository.mark_step_succeeded(
        subagent_step.step_id, subagent_result.model_dump()
    )

    # Create and succeed summary step
    summary_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="summary",
        step_type="summary",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:summary",
    )
    await repository.mark_step_running(summary_step.step_id)
    await repository.mark_step_succeeded(
        summary_step.step_id, summary_output.model_dump()
    )

    steps = await repository.get_steps_for_run_iteration(state.run_id, 0)
    result = derive_state(state, steps)
    iteration = result.get_or_create_current_iteration()
    assert iteration.plan == plan
    assert "manuals" in iteration.subagent_results
    assert iteration.subagent_results["manuals"] == subagent_result
    assert iteration.summary == summary_output


def test_derive_state_does_not_mutate_base() -> None:
    asyncio.run(_test_derive_state_does_not_mutate_base())


async def _test_derive_state_does_not_mutate_base() -> None:
    repository = InMemoryStepRepository()
    state = _base_state()
    plan = _plan()

    planner_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await repository.mark_step_running(planner_step.step_id)
    await repository.mark_step_succeeded(
        planner_step.step_id, plan.model_dump(mode="json")
    )

    steps = await repository.get_steps_for_run_iteration(state.run_id, 0)
    derive_state(state, steps)
    iteration = state.get_or_create_current_iteration()
    assert iteration.plan is None


def test_derive_state_identical_to_on_success_path() -> None:
    asyncio.run(_test_derive_state_identical_to_on_success_path())


async def _test_derive_state_identical_to_on_success_path() -> None:
    repository = InMemoryStepRepository()
    state = _base_state()
    plan = _plan()
    subagent_result = _subagent_result()
    summary_output = _summary_output()

    # Build expected state via manual on_success application
    expected = state.model_copy(deep=True)
    expected_iter = expected.get_or_create_current_iteration()
    expected_iter.plan = plan
    expected_iter.subagent_results["manuals"] = subagent_result
    expected_iter.summary = summary_output

    # Build actual state via derive_state
    planner_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await repository.mark_step_running(planner_step.step_id)
    await repository.mark_step_succeeded(
        planner_step.step_id, plan.model_dump(mode="json")
    )

    subagent_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="subagent:manuals",
        step_type="subagent",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:subagent:manuals",
    )
    await repository.mark_step_running(subagent_step.step_id)
    await repository.mark_step_succeeded(
        subagent_step.step_id, subagent_result.model_dump()
    )

    summary_step = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="summary",
        step_type="summary",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:summary",
    )
    await repository.mark_step_running(summary_step.step_id)
    await repository.mark_step_succeeded(
        summary_step.step_id, summary_output.model_dump()
    )

    steps = await repository.get_steps_for_run_iteration(state.run_id, 0)
    actual = derive_state(state, steps)

    actual_iter = actual.get_or_create_current_iteration()
    assert actual_iter.plan == expected_iter.plan
    assert actual_iter.subagent_results == expected_iter.subagent_results
    assert actual_iter.summary == expected_iter.summary
