from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from xagent.agent_flow.config import (
    AgentFlowAppConfig,
    AgentModelConfig,
    SubagentConfig,
)
from xagent.agent_flow.llm_adapter import AgentFlowLLMAdapter
from xagent.agent_flow.models import AgentFlowState, RunStatus
from xagent.agent_flow.planner import (
    FakePlannerExecutor,
    LLMPlannerExecutor,
    PlannerExecutor,
)
from xagent.agent_flow.replay import RunAuditRecord, build_audit_record
from xagent.agent_flow.runtime import AgentFlowRuntime
from xagent.agent_flow.subagents import (
    FakeFlowSubagent,
    FlowSubagent,
    LLMFlowSubagent,
)
from xagent.agent_flow.summary import (
    FakeSummaryExecutor,
    LLMSummaryExecutor,
    SummaryExecutor,
)
from xagent.agent_persistence.memory import (
    InMemoryCheckpointRepository,
    InMemoryRunRepository,
    InMemoryStepRepository,
)
from xagent.agent_persistence.repositories import (
    CheckpointRepository,
    RunRepository,
    StepRepository,
)
from xagent.llm_config import ProviderConfig
from xagent.llm_registry import LLMClientFactory, LLMProvider


class AgentFlowLLMFactory(Protocol):
    def create(self, config: ProviderConfig) -> LLMProvider: ...


class AgentFlowService:
    def __init__(
        self,
        *,
        runtime: AgentFlowRuntime,
        run_repository: RunRepository,
        step_repository: StepRepository,
        checkpoint_repository: CheckpointRepository,
    ):
        self._runtime = runtime
        self._run_repository = run_repository
        self._step_repository = step_repository
        self._checkpoint_repository = checkpoint_repository

    @classmethod
    def in_memory(
        cls,
        config: AgentFlowAppConfig,
        *,
        planner: PlannerExecutor | None = None,
        subagents: dict[str, FlowSubagent] | None = None,
        summary: SummaryExecutor | None = None,
        llm_factory: AgentFlowLLMFactory | None = None,
    ) -> AgentFlowService:
        run_repository = InMemoryRunRepository()
        step_repository = InMemoryStepRepository()
        checkpoint_repository = InMemoryCheckpointRepository()
        return cls.from_repositories(
            config,
            run_repository=run_repository,
            step_repository=step_repository,
            checkpoint_repository=checkpoint_repository,
            planner=planner,
            subagents=subagents,
            summary=summary,
            llm_factory=llm_factory,
        )

    @classmethod
    def from_repositories(
        cls,
        config: AgentFlowAppConfig,
        *,
        run_repository: RunRepository,
        step_repository: StepRepository,
        checkpoint_repository: CheckpointRepository,
        planner: PlannerExecutor | None = None,
        subagents: dict[str, FlowSubagent] | None = None,
        summary: SummaryExecutor | None = None,
        llm_factory: AgentFlowLLMFactory | None = None,
    ) -> AgentFlowService:
        executor_factory = AgentFlowExecutorFactory(
            config=config,
            llm_factory=llm_factory or LLMClientFactory(),
        )
        runtime = AgentFlowRuntime(
            config=config,
            run_repository=run_repository,
            step_repository=step_repository,
            checkpoint_repository=checkpoint_repository,
            planner=planner or executor_factory.planner(),
            subagents=subagents or executor_factory.subagents(),
            summary=summary or executor_factory.summary(),
        )
        return cls(
            runtime=runtime,
            run_repository=run_repository,
            step_repository=step_repository,
            checkpoint_repository=checkpoint_repository,
        )

    async def start_run(
        self,
        *,
        user_query: str,
        case_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AgentFlowState:
        state = AgentFlowState(
            run_id=f"run_{uuid4().hex}",
            user_query=user_query,
            case_id=case_id,
            metadata=metadata or {},
        )
        return await self._runtime.run(state)

    async def list_runs(self) -> list[AgentFlowState]:
        return await self._run_repository.list_runs()

    async def get_run(self, run_id: str) -> AgentFlowState:
        return await self._run_repository.get_run_state(run_id)

    async def get_audit_record(self, run_id: str) -> RunAuditRecord:
        return await build_audit_record(
            run_id,
            run_repository=self._run_repository,
            step_repository=self._step_repository,
        )

    async def resume_run(self, run_id: str) -> AgentFlowState:
        checkpoint = await self._checkpoint_repository.get_latest_checkpoint(run_id)
        state = checkpoint or await self._run_repository.get_run_state(run_id)
        if state.status in {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.WAITING_FOR_USER,
        }:
            return state
        return await self._runtime.resume(state)

    async def submit_user_input(self, run_id: str, user_input: str) -> AgentFlowState:
        checkpoint = await self._checkpoint_repository.get_latest_checkpoint(run_id)
        state = checkpoint or await self._run_repository.get_run_state(run_id)
        return await self._runtime.resume_with_input(state, user_input)


class AgentFlowExecutorFactory:
    def __init__(
        self,
        *,
        config: AgentFlowAppConfig,
        llm_factory: AgentFlowLLMFactory,
    ):
        self._config = config
        self._llm_factory = llm_factory

    def planner(self) -> PlannerExecutor:
        model_config = self._model_config(self._config.planner.model)
        if model_config.provider == "fake":
            return FakePlannerExecutor()
        return LLMPlannerExecutor(
            config=self._config.planner,
            llm=self._adapter(model_config),
        )

    def summary(self) -> SummaryExecutor:
        model_config = self._model_config(self._config.summary.model)
        if model_config.provider == "fake":
            return FakeSummaryExecutor()
        return LLMSummaryExecutor(
            config=self._config.summary,
            llm=self._adapter(model_config),
        )

    def subagents(self) -> dict[str, FlowSubagent]:
        return {
            name: self._subagent(config)
            for name, config in self._config.subagents.items()
        }

    def _subagent(self, config: SubagentConfig) -> FlowSubagent:
        model_config = self._model_config(config.model)
        if model_config.provider == "fake":
            return FakeFlowSubagent(
                name=config.name,
                description=config.description,
            )
        return LLMFlowSubagent(
            config=config,
            llm=self._adapter(model_config),
        )

    def _adapter(self, model_config: AgentModelConfig) -> AgentFlowLLMAdapter:
        if model_config.provider == "fake":
            raise ValueError("Fake agent-flow models do not use an LLM provider.")
        provider = self._llm_factory.create(
            ProviderConfig(
                provider=model_config.provider,
                default_model=model_config.model,
            )
        )
        return AgentFlowLLMAdapter(
            provider=provider,
            models=self._config.models,
        )

    def _model_config(self, model_name: str) -> AgentModelConfig:
        configured = self._config.models.get(model_name)
        if configured is not None:
            return configured
        if model_name == "default_reasoning":
            return AgentModelConfig()
        raise KeyError(f"Agent flow model is not configured: {model_name}")
