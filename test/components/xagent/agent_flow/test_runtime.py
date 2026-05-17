import asyncio

from xagent.agent_flow.config import (
    AgentFlowAppConfig,
    AgentWorkflowConfig,
    SubagentConfig,
)
from xagent.agent_flow.models import (
    AgentFlowIteration,
    AgentFlowState,
    PlanOutput,
    PlanSubagentSelection,
    RunStatus,
    SubagentResult,
    SummaryDecision,
    SummaryOutput,
)
from xagent.agent_flow.planner import FakePlannerExecutor
from xagent.agent_flow.runtime import AgentFlowRuntime
from xagent.agent_flow.subagents import fake_subagents_from_config
from xagent.agent_flow.summary import FakeSummaryExecutor
from xagent.agent_persistence.memory import (
    InMemoryCheckpointRepository,
    InMemoryRunRepository,
    InMemoryStepRepository,
)


class RaisingSubagent:
    name = "manuals"
    description = "Raises if invoked."

    async def ainvoke(
        self,
        *,
        state: AgentFlowState,
        selection: PlanSubagentSelection,
    ) -> SubagentResult:
        _ = (state, selection)
        raise AssertionError("succeeded subagent step should have been skipped")


class SequencedSummaryExecutor:
    def __init__(self, decisions: list[SummaryDecision]):
        self._decisions = decisions
        self._index = 0

    async def summarize(
        self,
        *,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> SummaryOutput:
        decision = self._decisions[min(self._index, len(self._decisions) - 1)]
        self._index += 1
        if decision is SummaryDecision.REPLAN:
            return SummaryOutput(
                decision=SummaryDecision.REPLAN,
                rationale="need another pass",
                missing_information=["more evidence"],
            )
        return SummaryOutput(
            decision=SummaryDecision.FINAL,
            answer_draft=f"final from iteration {iteration.iteration}",
        )


def _config(*, max_iterations: int = 3) -> AgentFlowAppConfig:
    return AgentFlowAppConfig(
        workflow=AgentWorkflowConfig(max_iterations=max_iterations),
        subagents={
            "manuals": SubagentConfig(
                name="manuals",
                description="Search service manuals.",
                prompt_template="prompts/agent_flow/subagents/manuals.md",
            ),
            "history": SubagentConfig(
                name="history",
                description="Search repair history.",
                prompt_template="prompts/agent_flow/subagents/history.md",
            ),
        },
    )


def test_runtime_completes_memory_backed_happy_path() -> None:
    asyncio.run(_runtime_completes_memory_backed_happy_path())


async def _runtime_completes_memory_backed_happy_path() -> None:
    config = _config()
    run_repository = InMemoryRunRepository()
    checkpoint_repository = InMemoryCheckpointRepository()
    runtime = AgentFlowRuntime(
        config=config,
        run_repository=run_repository,
        step_repository=InMemoryStepRepository(),
        checkpoint_repository=checkpoint_repository,
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        subagents=fake_subagents_from_config(config.subagents),
        summary=FakeSummaryExecutor(),
    )

    result = await runtime.run(
        AgentFlowState(run_id="run_1", user_query="diagnose no start")
    )

    assert result.status is RunStatus.COMPLETED
    assert result.final_response == (
        "manuals handled query 'diagnose no start' for iteration 0."
    )
    assert result.current_iteration == 0
    assert len(result.iterations) == 1
    assert result.iterations[0].plan is not None
    assert [selection.name for selection in result.iterations[0].plan.selections] == [
        "manuals"
    ]
    assert sorted(result.iterations[0].subagent_results) == ["manuals"]
    latest = await checkpoint_repository.get_latest_checkpoint("run_1")
    assert latest is not None
    assert latest.status is RunStatus.COMPLETED


def test_runtime_replans_then_completes_next_iteration() -> None:
    asyncio.run(_runtime_replans_then_completes_next_iteration())


async def _runtime_replans_then_completes_next_iteration() -> None:
    config = _config(max_iterations=2)
    runtime = AgentFlowRuntime(
        config=config,
        run_repository=InMemoryRunRepository(),
        step_repository=InMemoryStepRepository(),
        checkpoint_repository=InMemoryCheckpointRepository(),
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        subagents=fake_subagents_from_config(config.subagents),
        summary=SequencedSummaryExecutor(
            [SummaryDecision.REPLAN, SummaryDecision.FINAL]
        ),
    )

    result = await runtime.run(
        AgentFlowState(run_id="run_1", user_query="diagnose no start")
    )

    assert result.status is RunStatus.COMPLETED
    assert result.current_iteration == 1
    assert [iteration.iteration for iteration in result.iterations] == [0, 1]
    assert result.iterations[0].summary is not None
    assert result.iterations[0].summary.decision is SummaryDecision.REPLAN
    assert result.iterations[1].summary is not None
    assert result.iterations[1].summary.decision is SummaryDecision.FINAL
    assert result.final_response == "final from iteration 1"


def test_runtime_fails_when_replan_exhausts_iteration_budget() -> None:
    asyncio.run(_runtime_fails_when_replan_exhausts_iteration_budget())


async def _runtime_fails_when_replan_exhausts_iteration_budget() -> None:
    config = _config(max_iterations=1)
    runtime = AgentFlowRuntime(
        config=config,
        run_repository=InMemoryRunRepository(),
        step_repository=InMemoryStepRepository(),
        checkpoint_repository=InMemoryCheckpointRepository(),
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        subagents=fake_subagents_from_config(config.subagents),
        summary=SequencedSummaryExecutor([SummaryDecision.REPLAN]),
    )

    result = await runtime.run(
        AgentFlowState(run_id="run_1", user_query="diagnose no start")
    )

    assert result.status is RunStatus.FAILED
    assert result.current_iteration == 0
    assert result.errors[-1].message == (
        "Agent flow reached the maximum iteration count."
    )
    assert result.errors[-1].details == {"max_iterations": 1}


def test_runtime_resume_reconciles_succeeded_steps_from_stale_checkpoint() -> None:
    asyncio.run(_runtime_resume_reconciles_succeeded_steps_from_stale_checkpoint())


async def _runtime_resume_reconciles_succeeded_steps_from_stale_checkpoint() -> None:
    config = _config()
    run_repository = InMemoryRunRepository()
    step_repository = InMemoryStepRepository()
    checkpoint_repository = InMemoryCheckpointRepository()
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    await run_repository.create_run(state)
    await checkpoint_repository.save_checkpoint(
        run_id=state.run_id,
        iteration=state.current_iteration,
        checkpoint_name="start",
        stage=state.current_stage,
        state=state,
    )
    plan = PlanOutput(
        goal="Answer user query: diagnose no start",
        selections=[PlanSubagentSelection(name="manuals")],
    )
    plan_step = await step_repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={"query": state.user_query},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await step_repository.mark_step_succeeded(
        plan_step.step_id,
        plan.model_dump(mode="json"),
    )
    subagent_step = await step_repository.create_or_get_step(
        run_id=state.run_id,
        iteration=0,
        step_name="subagent:manuals",
        step_type="subagent",
        input_json={"name": "manuals"},
        max_attempts=1,
        idempotency_key="run_1:0:subagent:manuals",
    )
    await step_repository.mark_step_succeeded(
        subagent_step.step_id,
        SubagentResult(
            name="manuals",
            status="completed",
            content="recovered manual result",
        ).model_dump(mode="json"),
    )
    runtime = AgentFlowRuntime(
        config=config,
        run_repository=run_repository,
        step_repository=step_repository,
        checkpoint_repository=checkpoint_repository,
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        subagents={"manuals": RaisingSubagent()},
        summary=FakeSummaryExecutor(),
    )

    result = await runtime.resume(state)

    assert result.status is RunStatus.COMPLETED
    assert result.final_response == "recovered manual result"
    assert result.iterations[0].plan == plan
    assert result.iterations[0].subagent_results["manuals"].content == (
        "recovered manual result"
    )
