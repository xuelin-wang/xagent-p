from __future__ import annotations

from uuid import uuid4

from xagent.agent_flow.config import AgentFlowAppConfig
from xagent.agent_flow.models import AgentFlowState, RunStatus
from xagent.agent_flow.planner import FakePlannerExecutor, PlannerExecutor
from xagent.agent_flow.runtime import AgentFlowRuntime
from xagent.agent_flow.subagents import FlowSubagent, fake_subagents_from_config
from xagent.agent_flow.summary import FakeSummaryExecutor, SummaryExecutor
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


class AgentFlowService:
    def __init__(
        self,
        *,
        runtime: AgentFlowRuntime,
        run_repository: RunRepository,
        checkpoint_repository: CheckpointRepository,
    ):
        self._runtime = runtime
        self._run_repository = run_repository
        self._checkpoint_repository = checkpoint_repository

    @classmethod
    def in_memory(
        cls,
        config: AgentFlowAppConfig,
        *,
        planner: PlannerExecutor | None = None,
        subagents: dict[str, FlowSubagent] | None = None,
        summary: SummaryExecutor | None = None,
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
    ) -> AgentFlowService:
        runtime = AgentFlowRuntime(
            config=config,
            run_repository=run_repository,
            step_repository=step_repository,
            checkpoint_repository=checkpoint_repository,
            planner=planner or FakePlannerExecutor(),
            subagents=subagents or fake_subagents_from_config(config.subagents),
            summary=summary or FakeSummaryExecutor(),
        )
        return cls(
            runtime=runtime,
            run_repository=run_repository,
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

    async def get_run(self, run_id: str) -> AgentFlowState:
        return await self._run_repository.get_run_state(run_id)

    async def resume_run(self, run_id: str) -> AgentFlowState:
        checkpoint = await self._checkpoint_repository.get_latest_checkpoint(run_id)
        state = checkpoint or await self._run_repository.get_run_state(run_id)
        if state.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
            return state
        return await self._runtime.resume(state)
