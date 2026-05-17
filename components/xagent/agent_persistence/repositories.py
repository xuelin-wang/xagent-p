from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from xagent.agent_flow.models import AgentFlowState, StepStatus


class StepRecord(BaseModel):
    step_id: str
    run_id: str
    iteration: int
    step_name: str
    step_type: str
    status: StepStatus
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    attempt_count: int = 0
    max_attempts: int = 1
    idempotency_key: str


class CheckpointRecord(BaseModel):
    checkpoint_id: str
    run_id: str
    iteration: int
    checkpoint_name: str
    stage: str
    state: AgentFlowState
    sequence: int


class RunRepository(Protocol):
    async def create_run(self, state: AgentFlowState) -> None: ...

    async def get_run_state(self, run_id: str) -> AgentFlowState: ...

    async def update_run_state(self, state: AgentFlowState) -> None: ...

    async def mark_completed(self, run_id: str, final_response: str) -> None: ...

    async def mark_failed(self, run_id: str, error: dict[str, Any]) -> None: ...


class StepRepository(Protocol):
    async def create_or_get_step(
        self,
        *,
        run_id: str,
        iteration: int,
        step_name: str,
        step_type: str,
        input_json: dict[str, Any],
        max_attempts: int,
        idempotency_key: str,
    ) -> StepRecord: ...

    async def mark_step_running(self, step_id: str) -> StepRecord: ...

    async def mark_step_succeeded(
        self,
        step_id: str,
        output_json: dict[str, Any],
    ) -> StepRecord: ...

    async def mark_step_failed(
        self,
        step_id: str,
        error_json: dict[str, Any],
    ) -> StepRecord: ...

    async def get_steps_for_run_iteration(
        self,
        run_id: str,
        iteration: int,
    ) -> list[StepRecord]: ...


class CheckpointRepository(Protocol):
    async def save_checkpoint(
        self,
        *,
        run_id: str,
        iteration: int,
        checkpoint_name: str,
        stage: str,
        state: AgentFlowState,
    ) -> CheckpointRecord: ...

    async def get_latest_checkpoint(self, run_id: str) -> AgentFlowState | None: ...
