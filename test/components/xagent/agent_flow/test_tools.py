import asyncio

import pytest

from xagent.agent_flow.errors import StepRunnerError
from xagent.agent_flow.models import AgentFlowState, ToolResult
from xagent.agent_flow.step_runner import StepRunner
from xagent.agent_flow.steps import RuntimeContext
from xagent.agent_flow.tool_registry import ValidatedToolCall
from xagent.agent_flow.tools import ToolCallStep, build_execute_tools_step
from xagent.agent_persistence.memory import InMemoryStepRepository
from xagent.agent_persistence.repositories import StepStatus


def _call(
    tool_call_id: str,
    tool_name: str = "search",
    *,
    run_id: str = "run_1",
) -> ValidatedToolCall:
    return ValidatedToolCall(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        purpose="test",
        input={"query": "test"},
        idempotency_key=tool_call_id,
        timeout_ms=0,
    )


def _result(
    tool_call_id: str, tool_name: str = "search", *, status: str = "succeeded"
) -> ToolResult:
    return ToolResult(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        status=status,  # type: ignore[arg-type]
        attempt_count=1,
    )


class _FakeExecutor:
    def __init__(self, results: dict[str, ToolResult]) -> None:
        self._results = results
        self.calls: list[ValidatedToolCall] = []

    async def execute(
        self, call: ValidatedToolCall, state: AgentFlowState
    ) -> ToolResult:
        self.calls.append(call)
        return self._results[call.tool_call_id]


class _FailingExecutor:
    def __init__(self, message: str = "tool error") -> None:
        self._message = message
        self.call_count = 0

    async def execute(
        self, call: ValidatedToolCall, state: AgentFlowState
    ) -> ToolResult:
        self.call_count += 1
        raise RuntimeError(self._message)


class _RaisingExecutor:
    """Raises AssertionError if invoked — used to verify a call is skipped."""

    async def execute(
        self, call: ValidatedToolCall, state: AgentFlowState
    ) -> ToolResult:
        raise AssertionError(f"should not be invoked: {call.tool_call_id}")


# ---------------------------------------------------------------------------
# ToolCallStep
# ---------------------------------------------------------------------------


def test_tool_call_step_runs_executor_and_returns_result() -> None:
    asyncio.run(_tool_call_step_runs_executor_and_returns_result())


async def _tool_call_step_runs_executor_and_returns_result() -> None:
    call = _call("run_1:0:search:abc")
    expected = _result(call.tool_call_id)
    executor = _FakeExecutor({call.tool_call_id: expected})
    step = ToolCallStep(executor=executor, call=call)
    state = AgentFlowState(run_id="run_1", user_query="q")

    result = await step.run(state, RuntimeContext())

    assert result.output_json == expected.model_dump(mode="json")
    assert len(executor.calls) == 1
    assert executor.calls[0].tool_call_id == call.tool_call_id


# ---------------------------------------------------------------------------
# build_execute_tools_step + StepRunner integration
# ---------------------------------------------------------------------------


def test_execute_tools_runs_all_calls_and_stores_results() -> None:
    asyncio.run(_execute_tools_runs_all_calls_and_stores_results())


async def _execute_tools_runs_all_calls_and_stores_results() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="q")

    call_a = _call("run_1:0:search:aaa", "search")
    call_b = _call("run_1:0:history:bbb", "history")
    result_a = _result(call_a.tool_call_id, "search")
    result_b = _result(call_b.tool_call_id, "history")
    executor = _FakeExecutor(
        {call_a.tool_call_id: result_a, call_b.tool_call_id: result_b}
    )

    group = build_execute_tools_step(
        validated_calls=[call_a, call_b], executor=executor
    )
    step_result = await runner.execute_composite(group, state, RuntimeContext())

    assert len(executor.calls) == 2
    assert step_result.state_after is not None
    tool_results = (
        step_result.state_after.get_or_create_current_iteration().tool_results
    )
    assert tool_results[call_a.tool_call_id].status == "succeeded"
    assert tool_results[call_b.tool_call_id].status == "succeeded"


def test_partial_resume_skips_already_succeeded_tool_calls() -> None:
    asyncio.run(_partial_resume_skips_already_succeeded_tool_calls())


async def _partial_resume_skips_already_succeeded_tool_calls() -> None:
    """Core resume test: tool_A completed before crash; resume only runs tool_B."""
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="q")

    call_a = _call("run_1:0:search:aaa", "search")
    call_b = _call("run_1:0:history:bbb", "history")
    result_a = _result(call_a.tool_call_id, "search")
    result_b = _result(call_b.tool_call_id, "history")

    # Pre-seed tool_A as already succeeded (simulates partial completion before crash).
    step_a = await repository.create_or_get_step(
        run_id=state.run_id,
        iteration=state.current_iteration,
        step_name=f"tool_call:{call_a.tool_call_id}",
        step_type="tool_call",
        input_json=call_a.model_dump(mode="json"),
        max_attempts=1,
        idempotency_key=f"{state.run_id}:{state.current_iteration}:tool_call:{call_a.tool_call_id}",
    )
    await repository.mark_step_running(step_a.step_id)
    await repository.mark_step_succeeded(
        step_a.step_id, result_a.model_dump(mode="json")
    )

    # tool_A executor raises — it should never be called.
    executor_a = _RaisingExecutor()
    executor_b = _FakeExecutor({call_b.tool_call_id: result_b})

    class _SplitExecutor:
        async def execute(
            self, call: ValidatedToolCall, s: AgentFlowState
        ) -> ToolResult:
            if call.tool_call_id == call_a.tool_call_id:
                return await executor_a.execute(call, s)
            return await executor_b.execute(call, s)

    group = build_execute_tools_step(
        validated_calls=[call_a, call_b], executor=_SplitExecutor()
    )
    step_result = await runner.execute_composite(group, state, RuntimeContext())

    # tool_B ran, tool_A was skipped.
    assert len(executor_b.calls) == 1
    assert step_result.state_after is not None
    tool_results = (
        step_result.state_after.get_or_create_current_iteration().tool_results
    )
    assert tool_results[call_a.tool_call_id].status == "succeeded"
    assert tool_results[call_b.tool_call_id].status == "succeeded"

    # Verify only one new step record was created for tool_B.
    steps = await repository.get_steps_for_run_iteration("run_1", 0)
    tool_call_steps = [s for s in steps if s.step_name.startswith("tool_call:")]
    assert all(s.status is StepStatus.SUCCEEDED for s in tool_call_steps)


def test_failed_tool_raises_step_runner_error() -> None:
    asyncio.run(_failed_tool_raises_step_runner_error())


async def _failed_tool_raises_step_runner_error() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="q")

    call = _call("run_1:0:search:aaa")
    group = build_execute_tools_step(
        validated_calls=[call],
        executor=_FailingExecutor("tool exploded"),
    )

    with pytest.raises(StepRunnerError) as exc_info:
        await runner.execute_composite(group, state, RuntimeContext())

    assert "tool exploded" in str(exc_info.value)


def test_tool_call_retries_on_transient_failure() -> None:
    asyncio.run(_tool_call_retries_on_transient_failure())


async def _tool_call_retries_on_transient_failure() -> None:
    from xagent.agent_flow.steps import RetryPolicy

    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="q")

    attempt_count = 0

    class _TransientExecutor:
        async def execute(self, c: ValidatedToolCall, s: AgentFlowState) -> ToolResult:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise RuntimeError("transient")
            return _result(c.tool_call_id)

    call = ValidatedToolCall(
        tool_call_id="run_1:0:search:aaa",
        tool_name="search",
        purpose="test",
        input={"query": "test"},
        idempotency_key="run_1:0:search:aaa",
        timeout_ms=0,
        retry_policy=RetryPolicy(max_attempts=3),
    )
    group = build_execute_tools_step(
        validated_calls=[call], executor=_TransientExecutor()
    )
    step_result = await runner.execute_composite(group, state, RuntimeContext())

    assert attempt_count == 2
    assert step_result.state_after is not None
    results = step_result.state_after.get_or_create_current_iteration().tool_results
    assert results[call.tool_call_id].status == "succeeded"
