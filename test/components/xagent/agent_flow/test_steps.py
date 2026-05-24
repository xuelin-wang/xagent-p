import asyncio

from xagent.agent_flow.models import (
    AgentFlowState,
    PlanSubagentSelection,
    SummaryDecision,
)
from xagent.agent_flow.planner import FakePlannerExecutor, PlannerStep
from xagent.agent_flow.step_runner import StepRunner
from xagent.agent_flow.steps import (
    RetryPolicy,
    RuntimeContext,
    RuntimeExecutionPolicy,
    StepExecutionPolicy,
)
from xagent.agent_flow.subagents import FakeFlowSubagent, SubagentStep
from xagent.agent_flow.summary import FakeSummaryExecutor, SummaryStep
from xagent.agent_persistence.memory import InMemoryStepRepository

from .test_executors import _subagent_configs


def test_runtime_execution_policy_uses_global_default() -> None:
    policy = RuntimeExecutionPolicy(
        default_step_policy=StepExecutionPolicy(
            timeout_ms=1_000,
            deadline_ms=5_000,
            retry=RetryPolicy(max_attempts=2, retryable_error_types=["TimeoutError"]),
            continue_on_failure=True,
        )
    )

    effective = policy.policy_for("planner")

    assert effective == StepExecutionPolicy(
        timeout_ms=1_000,
        deadline_ms=5_000,
        retry=RetryPolicy(max_attempts=2, retryable_error_types=["TimeoutError"]),
        continue_on_failure=True,
    )


def test_runtime_execution_policy_merges_step_override() -> None:
    policy = RuntimeExecutionPolicy(
        default_step_policy=StepExecutionPolicy(
            timeout_ms=1_000,
            deadline_ms=5_000,
            retry=RetryPolicy(
                max_attempts=2,
                backoff_initial_ms=100,
                retryable_error_types=["TimeoutError"],
            ),
            continue_on_failure=True,
        ),
        step_overrides={
            "planner": StepExecutionPolicy(
                timeout_ms=2_000,
                retry=RetryPolicy(max_attempts=3),
            )
        },
    )

    effective = policy.policy_for("planner")

    assert effective == StepExecutionPolicy(
        timeout_ms=2_000,
        deadline_ms=5_000,
        retry=RetryPolicy(
            max_attempts=3,
            backoff_initial_ms=100,
            retryable_error_types=["TimeoutError"],
        ),
        continue_on_failure=True,
    )


def test_runtime_context_child_inherits_parent_and_merges_override() -> None:
    parent = RuntimeContext(
        execution_policy=StepExecutionPolicy(
            timeout_ms=1_000,
            deadline_ms=5_000,
            retry=RetryPolicy(max_attempts=2, backoff_initial_ms=100),
        )
    )
    child_override = RuntimeContext(
        execution_policy=StepExecutionPolicy(
            retry=RetryPolicy(max_attempts=4),
        )
    )

    effective = parent.for_child(step_type="planner", override=child_override)

    assert effective.execution_policy == StepExecutionPolicy(
        timeout_ms=1_000,
        deadline_ms=5_000,
        retry=RetryPolicy(max_attempts=4, backoff_initial_ms=100),
    )


def test_runtime_context_child_applies_runtime_step_override() -> None:
    runtime_policy = RuntimeExecutionPolicy(
        default_step_policy=StepExecutionPolicy(timeout_ms=1_000),
        step_overrides={
            "planner": StepExecutionPolicy(deadline_ms=5_000),
        },
    )
    parent = RuntimeContext.from_runtime_policy(
        runtime_policy,
        step_type="sequence:iteration",
    )

    effective = parent.for_child(step_type="planner")

    assert effective.execution_policy == StepExecutionPolicy(
        timeout_ms=1_000,
        deadline_ms=5_000,
    )


def test_planner_step_matches_executor_output() -> None:
    asyncio.run(_planner_step_matches_executor_output())


async def _planner_step_matches_executor_output() -> None:
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    executor = FakePlannerExecutor(selection_names=["manuals"])
    step = PlannerStep(
        executor=executor,
        subagents=_subagent_configs(),
        max_selections=2,
    )

    result = await step.run(
        state=state,
        context=RuntimeContext(),
    )

    assert result.output_json == (
        await executor.plan(
            state=state,
            subagents=_subagent_configs(),
            max_selections=2,
        )
    ).model_dump(mode="json")


def test_step_runner_runs_runtime_step_with_policy_attempts() -> None:
    asyncio.run(_step_runner_runs_runtime_step_with_policy_attempts())


async def _step_runner_runs_runtime_step_with_policy_attempts() -> None:
    repository = InMemoryStepRepository()
    runner = StepRunner(repository)
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    step = PlannerStep(
        executor=FakePlannerExecutor(selection_names=["manuals"]),
        subagents=_subagent_configs(),
        max_selections=1,
    )

    result = await runner.run_runtime_step(
        state=state,
        step_name="planner",
        input_json={"query": state.user_query},
        step=step,
        context=RuntimeContext(
            execution_policy=StepExecutionPolicy(
                retry=RetryPolicy(max_attempts=3),
            )
        ),
    )

    steps = await repository.get_steps_for_run_iteration("run_1", 0)
    assert result["selections"][0]["name"] == "manuals"
    assert steps[0].step_type == "planner"
    assert steps[0].max_attempts == 3


def test_subagent_step_matches_executor_output() -> None:
    asyncio.run(_subagent_step_matches_executor_output())


async def _subagent_step_matches_executor_output() -> None:
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    selection = PlanSubagentSelection(name="manuals")
    subagent = FakeFlowSubagent(name="manuals")
    step = SubagentStep(subagent=subagent, selection=selection)

    result = await step.run(state=state, context=RuntimeContext())

    assert result.output_json == (
        await subagent.ainvoke(state=state, selection=selection)
    ).model_dump(mode="json")


def test_summary_step_matches_executor_output() -> None:
    asyncio.run(_summary_step_matches_executor_output())


async def _summary_step_matches_executor_output() -> None:
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    iteration = state.get_or_create_current_iteration()
    executor = FakeSummaryExecutor(decision=SummaryDecision.FINAL)
    step = SummaryStep(executor=executor)

    result = await step.run(state=state, context=RuntimeContext())

    assert result.output_json == (
        await executor.summarize(state=state, iteration=iteration)
    ).model_dump(mode="json")
