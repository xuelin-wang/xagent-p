import asyncio

from xagent.agent_flow.config import AgentFlowAppConfig, SubagentConfig
from xagent.agent_flow.models import AgentFlowState, FlowStage, RunStatus
from xagent.agent_flow.planner import FakePlannerExecutor
from xagent.agent_flow.service import AgentFlowService
from xagent.agent_flow.summary import FakeSummaryExecutor
from xagent.agent_persistence.memory import (
    InMemoryCheckpointRepository,
    InMemoryRunRepository,
    InMemoryStepRepository,
)


def _config() -> AgentFlowAppConfig:
    return AgentFlowAppConfig(
        subagents={
            "manuals": SubagentConfig(
                name="manuals",
                description="Search service manuals.",
                prompt_template="prompts/agent_flow/subagents/manuals.md",
            ),
        }
    )


def test_service_starts_and_gets_completed_run() -> None:
    asyncio.run(_service_starts_and_gets_completed_run())


async def _service_starts_and_gets_completed_run() -> None:
    service = AgentFlowService.in_memory(
        _config(),
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        summary=FakeSummaryExecutor(),
    )

    result = await service.start_run(
        user_query="diagnose no start",
        case_id="case_123",
        metadata={"vehicle": "example"},
    )
    fetched = await service.get_run(result.run_id)

    assert result.run_id.startswith("run_")
    assert fetched == result
    assert fetched.status is RunStatus.COMPLETED
    assert fetched.case_id == "case_123"
    assert fetched.metadata == {"vehicle": "example"}


def test_service_resume_returns_terminal_checkpoint_without_rerun() -> None:
    asyncio.run(_service_resume_returns_terminal_checkpoint_without_rerun())


async def _service_resume_returns_terminal_checkpoint_without_rerun() -> None:
    service = AgentFlowService.in_memory(
        _config(),
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        summary=FakeSummaryExecutor(),
    )
    result = await service.start_run(user_query="diagnose no start")

    resumed = await service.resume_run(result.run_id)

    assert resumed == result


def test_service_resume_continues_nonterminal_checkpoint() -> None:
    asyncio.run(_service_resume_continues_nonterminal_checkpoint())


async def _service_resume_continues_nonterminal_checkpoint() -> None:
    config = _config()
    run_repository = InMemoryRunRepository()
    step_repository = InMemoryStepRepository()
    checkpoint_repository = InMemoryCheckpointRepository()
    state = AgentFlowState(
        run_id="run_existing",
        user_query="diagnose no start",
        status=RunStatus.RUNNING,
        current_stage=FlowStage.START,
    )
    await run_repository.create_run(state)
    await checkpoint_repository.save_checkpoint(
        run_id=state.run_id,
        iteration=state.current_iteration,
        checkpoint_name="start",
        stage=state.current_stage,
        state=state,
    )
    service = AgentFlowService.from_repositories(
        config,
        run_repository=run_repository,
        step_repository=step_repository,
        checkpoint_repository=checkpoint_repository,
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        summary=FakeSummaryExecutor(),
    )

    resumed = await service.resume_run("run_existing")

    assert resumed.status is RunStatus.COMPLETED
    assert resumed.final_response == (
        "manuals handled query 'diagnose no start' for iteration 0."
    )
