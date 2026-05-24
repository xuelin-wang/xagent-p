"""Common runtime-step contracts for the replay/resume migration.

Purpose: give specialized planner/tool/summary steps one small execution
contract without introducing a parallel runtime framework.
Design link: replay-resume-agent-system-design.md sections 3 and 17.
Non-goal: this module should not contain planner, tool, or LLM behavior.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from xagent.agent_flow.models import AgentFlowState
from xagent.config import StrictConfigModel


class RetryPolicy(StrictConfigModel):
    max_attempts: int = 1
    backoff_initial_ms: int = 0
    backoff_max_ms: int | None = None
    backoff_multiplier: float = 1.0
    retryable_error_types: list[str] = Field(default_factory=list)

    def merge(self, override: RetryPolicy) -> RetryPolicy:
        merged = self.model_copy(deep=True)
        return merged.model_copy(
            update={
                field: getattr(override, field) for field in override.model_fields_set
            },
            deep=True,
        )


class StepExecutionPolicy(StrictConfigModel):
    timeout_ms: int | None = None
    deadline_ms: int | None = None
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    continue_on_failure: bool = False

    def merge(self, override: StepExecutionPolicy) -> StepExecutionPolicy:
        updates: dict[str, Any] = {}
        for field in override.model_fields_set:
            if field == "retry":
                updates[field] = self.retry.merge(override.retry)
            else:
                updates[field] = getattr(override, field)
        return self.model_copy(update=updates, deep=True)


class RuntimeExecutionPolicy(StrictConfigModel):
    default_step_policy: StepExecutionPolicy = Field(
        default_factory=StepExecutionPolicy
    )
    step_overrides: dict[str, StepExecutionPolicy] = Field(default_factory=dict)

    def policy_for(self, step_type: str) -> StepExecutionPolicy:
        override = self.step_overrides.get(step_type)
        if override is None:
            return self.default_step_policy.model_copy(deep=True)
        return self.default_step_policy.merge(override)


class RuntimeContext(StrictConfigModel):
    execution_policy: StepExecutionPolicy = Field(default_factory=StepExecutionPolicy)


class StepResult(StrictConfigModel):
    output_json: dict[str, Any] = Field(default_factory=dict)
    # Populated by the executor after deriving state from events (Section 6.1).
    # None until the executor fills it in; AtomicStep.run() never sets this.
    state_after: AgentFlowState | None = None


class RuntimeStep(Protocol):
    step_type: str

    async def run(
        self,
        state: AgentFlowState,
        context: RuntimeContext,
    ) -> StepResult: ...
