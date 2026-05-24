"""Common runtime-step contracts for the replay/resume migration.

Purpose: give specialized planner/tool/summary steps one small execution
contract without introducing a parallel runtime framework.
Design link: replay-resume-agent-system-design.md sections 3, 3.1 and 17.
Non-goal: this module should not contain planner, tool, or LLM behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Protocol

from pydantic import Field

from xagent.agent_flow.models import AgentFlowState
from xagent.config import StrictConfigModel


class RetryPolicy(StrictConfigModel):
    max_attempts: int = Field(default=1, ge=1)
    backoff_initial_ms: int = Field(default=0, ge=0)
    backoff_max_ms: int | None = Field(default=None, ge=0)
    backoff_multiplier: float = Field(default=1.0, ge=0)
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
    timeout_ms: int | None = Field(default=None, ge=0)
    deadline_ms: int | None = Field(default=None, ge=0)
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
    runtime_policy: RuntimeExecutionPolicy | None = None

    @classmethod
    def from_runtime_policy(
        cls,
        runtime_policy: RuntimeExecutionPolicy,
        *,
        step_type: str,
    ) -> RuntimeContext:
        return cls(
            execution_policy=runtime_policy.policy_for(step_type),
            runtime_policy=runtime_policy,
        )

    def for_child(
        self,
        *,
        step_type: str,
        override: RuntimeContext | None = None,
    ) -> RuntimeContext:
        policy = self.execution_policy.model_copy(deep=True)
        if self.runtime_policy is not None:
            step_override = self.runtime_policy.step_overrides.get(step_type)
            if step_override is not None:
                policy = policy.merge(step_override)
        if override is not None:
            policy = policy.merge(override.execution_policy)
        return RuntimeContext(
            execution_policy=policy,
            runtime_policy=self.runtime_policy,
        )


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


@dataclass
class SequenceStepGroup:
    """Composite step that runs children in sequence.

    Design link: Section 3.1, step hierarchy.
    Children are ChildStep instances or lazy callables — see ChildStep in step_runner.py.
    Callables receive the current state and return a ChildStep (or None to skip).
    This defers child construction until after prior steps have mutated state
    (e.g., the subagents parallel group depends on the plan produced by the planner).
    Non-goal: not a generic graph runner; ordered sequence only.
    """

    step_type: str
    step_name: str
    children: list[Any] = dc_field(default_factory=list)


@dataclass
class ParallelStepGroup:
    """Composite step that runs children concurrently and merges results.

    Design link: Section 3.1, step hierarchy.
    Resume rule: children with a prior step_succeeded event are skipped.
    children may be a static list[ChildStep] or a factory Callable[[AgentFlowState],
    list[ChildStep]] evaluated with the current state at execution time.
    Non-goal: not a fan-out/fan-in graph; flat parallel list only.
    """

    step_type: str
    step_name: str
    children: Any = dc_field(default_factory=list)
