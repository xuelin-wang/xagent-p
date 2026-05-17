import asyncio
from typing import Any

import pytest

from xagent.agent_flow.errors import NonRetryableStepError, StepRunnerError
from xagent.agent_flow.models import AgentFlowState, StepStatus
from xagent.agent_flow.step_runner import StepRunner
from xagent.agent_persistence.memory import InMemoryStepRepository
from xagent.agent_persistence.repositories import StepRecord


def test_step_runner_persists_success_and_skips_succeeded_step() -> None:
    asyncio.run(_step_runner_persists_success_and_skips_succeeded_step())


async def _step_runner_persists_success_and_skips_succeeded_step() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    calls = 0

    async def fn(step: StepRecord) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"step_id": step.step_id, "answer": "inspect battery"}

    first = await runner.run_step(
        state=state,
        step_name="planner",
        step_type="planner",
        input_json={"query": state.user_query},
        max_attempts=2,
        fn=fn,
    )
    second = await runner.run_step(
        state=state,
        step_name="planner",
        step_type="planner",
        input_json={"query": "ignored after success"},
        max_attempts=2,
        fn=fn,
    )

    assert first == second
    assert calls == 1

    steps = await repository.get_steps_for_run_iteration("run_1", 0)
    assert len(steps) == 1
    assert steps[0].status is StepStatus.SUCCEEDED
    assert steps[0].attempt_count == 1
    assert steps[0].output_json == first


def test_step_runner_retries_failures_until_success() -> None:
    asyncio.run(_step_runner_retries_failures_until_success())


async def _step_runner_retries_failures_until_success() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    calls = 0

    async def fn(_: StepRecord) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        return {"answer": "recovered"}

    result = await runner.run_step(
        state=state,
        step_name="summary",
        step_type="summary",
        input_json={"query": state.user_query},
        max_attempts=2,
        fn=fn,
    )

    assert result == {"answer": "recovered"}
    assert calls == 2

    steps = await repository.get_steps_for_run_iteration("run_1", 0)
    assert steps[0].status is StepStatus.SUCCEEDED
    assert steps[0].attempt_count == 2
    assert steps[0].error_json is None


def test_step_runner_persists_exhausted_failure() -> None:
    asyncio.run(_step_runner_persists_exhausted_failure())


async def _step_runner_persists_exhausted_failure() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")

    async def fn(_: StepRecord) -> dict[str, Any]:
        raise RuntimeError("still failing")

    with pytest.raises(StepRunnerError) as exc_info:
        await runner.run_step(
            state=state,
            step_name="subagent:manuals",
            step_type="subagent",
            input_json={"name": "manuals"},
            max_attempts=2,
            fn=fn,
        )

    assert str(exc_info.value) == "still failing"
    assert exc_info.value.error_json == {
        "message": "still failing",
        "error_type": "RuntimeError",
        "retryable": False,
    }

    steps = await repository.get_steps_for_run_iteration("run_1", 0)
    assert steps[0].status is StepStatus.FAILED
    assert steps[0].attempt_count == 2
    assert steps[0].error_json == exc_info.value.error_json


def test_step_runner_does_not_retry_non_retryable_failure() -> None:
    asyncio.run(_step_runner_does_not_retry_non_retryable_failure())


async def _step_runner_does_not_retry_non_retryable_failure() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    calls = 0

    async def fn(_: StepRecord) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise NonRetryableStepError("invalid planner output")

    with pytest.raises(StepRunnerError) as exc_info:
        await runner.run_step(
            state=state,
            step_name="planner",
            step_type="planner",
            input_json={"query": state.user_query},
            max_attempts=3,
            fn=fn,
        )

    assert calls == 1
    assert exc_info.value.error_json == {
        "message": "invalid planner output",
        "error_type": "NonRetryableStepError",
        "retryable": False,
    }


def test_step_runner_refuses_to_resume_exhausted_failed_step() -> None:
    asyncio.run(_step_runner_refuses_to_resume_exhausted_failed_step())


async def _step_runner_refuses_to_resume_exhausted_failed_step() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    calls = 0

    async def failing_fn(_: StepRecord) -> dict[str, Any]:
        raise RuntimeError("final failure")

    with pytest.raises(StepRunnerError):
        await runner.run_step(
            state=state,
            step_name="planner",
            step_type="planner",
            input_json={"query": state.user_query},
            max_attempts=1,
            fn=failing_fn,
        )

    async def should_not_run(_: StepRecord) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"unexpected": True}

    with pytest.raises(StepRunnerError) as exc_info:
        await runner.run_step(
            state=state,
            step_name="planner",
            step_type="planner",
            input_json={"query": state.user_query},
            max_attempts=1,
            fn=should_not_run,
        )

    assert calls == 0
    assert exc_info.value.error_json["message"] == "final failure"
