import asyncio
from pathlib import Path

from test.components.xagent.agent_flow.test_llm_adapter import FakeLLMProvider

from xagent.agent_flow.config import (
    AgentFlowAppConfig,
    AgentModelConfig,
    PlannerConfig,
    SubagentConfig,
    SummaryConfig,
)
from xagent.agent_flow.models import (
    AgentFlowState,
    FlowStage,
    RunStatus,
    SummaryDecision,
    SummaryOutput,
    UserRequest,
)
from xagent.agent_flow.planner import FakePlannerExecutor
from xagent.agent_flow.service import AgentFlowService
from xagent.agent_flow.summary import FakeSummaryExecutor
from xagent.agent_persistence.memory import (
    InMemoryCheckpointRepository,
    InMemoryRunRepository,
    InMemoryStepRepository,
)
from xagent.llm_config import ProviderConfig


class FakeLLMFactory:
    def __init__(self) -> None:
        self.configs: list[ProviderConfig] = []
        self.providers: list[FakeLLMProvider] = []

    def create(self, config: ProviderConfig) -> FakeLLMProvider:
        self.configs.append(config)
        provider = FakeLLMProvider()
        self.providers.append(provider)
        return provider


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


def test_service_uses_llm_executors_for_non_fake_model_config(
    tmp_path: Path,
) -> None:
    asyncio.run(_service_uses_llm_executors_for_non_fake_model_config(tmp_path))


async def _service_uses_llm_executors_for_non_fake_model_config(
    tmp_path: Path,
) -> None:
    planner_prompt = tmp_path / "planner.md"
    summary_prompt = tmp_path / "summary.md"
    subagent_prompt = tmp_path / "manuals.md"
    planner_prompt.write_text("planner system", encoding="utf-8")
    summary_prompt.write_text("summary system", encoding="utf-8")
    subagent_prompt.write_text("manual system", encoding="utf-8")
    llm_factory = FakeLLMFactory()
    service = AgentFlowService.in_memory(
        AgentFlowAppConfig(
            planner=PlannerConfig(
                prompt_template=str(planner_prompt),
                model="reasoning",
            ),
            summary=SummaryConfig(
                prompt_template=str(summary_prompt),
                model="reasoning",
            ),
            subagents={
                "manuals": SubagentConfig(
                    name="manuals",
                    description="Search service manuals.",
                    prompt_template=str(subagent_prompt),
                    model="reasoning",
                )
            },
            models={
                "reasoning": AgentModelConfig(
                    provider="openai",
                    model="gpt-test",
                    temperature=0.0,
                )
            },
        ),
        llm_factory=llm_factory,
    )

    result = await service.start_run(user_query="diagnose no start")

    assert result.status is RunStatus.COMPLETED
    assert result.final_response == "summary answer"
    assert [config.provider for config in llm_factory.configs] == [
        "openai",
        "openai",
        "openai",
    ]
    assert [config.default_model for config in llm_factory.configs] == [
        "gpt-test",
        "gpt-test",
        "gpt-test",
    ]
    assert len(llm_factory.providers[0].structured_requests) == 1
    assert len(llm_factory.providers[1].generate_requests) == 1
    assert len(llm_factory.providers[2].structured_requests) == 1


def test_service_resume_returns_waiting_state_without_rerun() -> None:
    asyncio.run(_service_resume_returns_waiting_state_without_rerun())


async def _service_resume_returns_waiting_state_without_rerun() -> None:
    service = AgentFlowService.in_memory(
        _config(),
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        summary=FakeSummaryExecutor(decision=SummaryDecision.ASK_USER),
    )
    waiting = await service.start_run(user_query="diagnose no start")
    assert waiting.status is RunStatus.WAITING_FOR_USER

    resumed = await service.resume_run(waiting.run_id)

    assert resumed.status is RunStatus.WAITING_FOR_USER
    assert resumed.run_id == waiting.run_id


def test_service_submit_user_input_continues_waiting_run() -> None:
    asyncio.run(_service_submit_user_input_continues_waiting_run())


async def _service_submit_user_input_continues_waiting_run() -> None:
    class _AskThenFinalSummary:
        def __init__(self) -> None:
            self._called = 0

        async def summarize(
            self,
            *,
            state: AgentFlowState,
            iteration: object,
        ) -> SummaryOutput:
            self._called += 1
            if self._called == 1:
                return SummaryOutput(
                    decision=SummaryDecision.ASK_USER,
                    user_request=UserRequest(
                        request_id="req_1",
                        prompt="What year is the vehicle?",
                    ),
                )
            return SummaryOutput(
                decision=SummaryDecision.FINAL,
                answer_draft="completed after user input",
            )

    service = AgentFlowService.in_memory(
        _config(),
        planner=FakePlannerExecutor(selection_names=["manuals"]),
        summary=_AskThenFinalSummary(),
    )

    waiting = await service.start_run(user_query="diagnose no start")
    assert waiting.status is RunStatus.WAITING_FOR_USER

    result = await service.submit_user_input(waiting.run_id, "It's a 2020 model.")

    assert result.status is RunStatus.COMPLETED
    assert result.final_response == "completed after user input"
    assert len(result.user_input_events) == 1
    assert result.user_input_events[0].content == "It's a 2020 model."
