from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"


class FlowStage(StrEnum):
    START = "start"
    PLANNING = "planning"
    SUBAGENTS = "subagents"
    SUMMARIZING = "summarizing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SummaryDecision(StrEnum):
    FINAL = "final"
    REPLAN = "replan"
    FAIL = "fail"


class AgentError(BaseModel):
    stage: str
    step_name: str | None = None
    message: str
    error_type: str | None = None
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class PlanSubagentSelection(BaseModel):
    name: str
    reason: str = ""
    input_hint: str | None = None


class PlanOutput(BaseModel):
    goal: str
    selections: list[PlanSubagentSelection] = Field(default_factory=list)
    rationale: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    duration_seconds: float | None = None


class SubagentResult(BaseModel):
    name: str
    status: Literal["completed", "timeout", "error", "skipped"]
    content: str
    duration_seconds: float | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    error: AgentError | None = None


class SummaryOutput(BaseModel):
    decision: SummaryDecision
    answer_draft: str | None = None
    rationale: str = ""
    missing_information: list[str] = Field(default_factory=list)
    suggested_replan: dict[str, Any] | None = None


class AgentFlowIteration(BaseModel):
    iteration: int
    plan: PlanOutput | None = None
    subagent_results: dict[str, SubagentResult] = Field(default_factory=dict)
    summary: SummaryOutput | None = None
    errors: list[AgentError] = Field(default_factory=list)


class AgentFlowState(BaseModel):
    run_id: str
    user_query: str
    case_id: str | None = None

    status: RunStatus = RunStatus.PENDING
    current_stage: FlowStage = FlowStage.START
    current_iteration: int = 0

    iterations: list[AgentFlowIteration] = Field(default_factory=list)
    final_response: str | None = None

    errors: list[AgentError] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def should_stop_replanning(self, max_iterations: int) -> bool:
        return self.current_iteration >= max_iterations

    def get_or_create_current_iteration(self) -> AgentFlowIteration:
        for iteration_state in self.iterations:
            if iteration_state.iteration == self.current_iteration:
                return iteration_state
        iteration_state = AgentFlowIteration(iteration=self.current_iteration)
        self.iterations.append(iteration_state)
        return iteration_state
