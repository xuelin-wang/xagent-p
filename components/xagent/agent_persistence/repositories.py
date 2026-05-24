from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from xagent.agent_flow.models import AgentFlowState, StepStatus


class StepEventType(StrEnum):
    CREATED = "step_created"
    STARTED = "step_started"
    SUCCEEDED = "step_succeeded"
    FAILED = "step_failed"


class StepEvent(BaseModel):
    """Append-only execution event used to derive StepRecord projections."""

    event_id: str
    run_id: str
    step_id: str
    sequence_index: int
    iteration_index: int
    step_name: str
    step_type: str
    attempt_index: int
    event_type: StepEventType
    occurred_at: datetime
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    error_ref: str | None = None
    state_before_ref: str | None = None
    state_after_ref: str | None = None
    checkpoint_id: str | None = None
    max_attempts: int = 1
    idempotency_key: str
    parent_step_id: str | None = None
    tool_call_id: str | None = None
    snapshot_id: str | None = None
    flow_decision: str | None = None
    next_step_type: str | None = None


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
    checkpoint_id: str | None = None
    # Set when this step is a child of a composite step (Section 3.1).
    parent_step_id: str | None = None


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
        parent_step_id: str | None = None,
    ) -> StepRecord: ...

    async def mark_step_running(self, step_id: str) -> StepRecord: ...

    async def mark_step_succeeded(
        self,
        step_id: str,
        output_json: dict[str, Any],
        checkpoint_id: str | None = None,
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

    async def get_children_for_step(
        self,
        parent_step_id: str,
    ) -> list[StepRecord]: ...

    async def append_step_event(self, event: StepEvent) -> StepEvent: ...

    async def get_step_events_for_run(self, run_id: str) -> list[StepEvent]: ...

    async def get_step_events_for_step(self, step_id: str) -> list[StepEvent]: ...

    async def get_latest_succeeded_event(self, run_id: str) -> StepEvent | None: ...

    async def rebuild_step_projection(self) -> list[StepRecord]: ...


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

    async def get_checkpoint(self, checkpoint_id: str) -> CheckpointRecord | None: ...
