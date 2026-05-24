"""Tool execution: EXECUTE_TOOLS parent step and tool_call child steps.

Each validated tool call runs as its own durable child step inside a
ParallelStepGroup so partial tool execution is safe to resume without
duplicate execution.

Design link: Section 11, per-call tool execution durability.
Simplifications (deferred):
  - timeout_ms / deadline_ms enforcement
  - output_ref / error_ref artifact storage
  - write-side actuator special handling
Non-goal: validation belongs in tool_registry.py; persistence in repositories.
"""

from __future__ import annotations

from typing import Protocol

from xagent.agent_flow.models import AgentFlowState, ToolResult
from xagent.agent_flow.step_runner import ChildStep
from xagent.agent_flow.steps import (
    ParallelStepGroup,
    RetryPolicy,
    RuntimeContext,
    StepExecutionPolicy,
    StepResult,
)
from xagent.agent_flow.tool_registry import ValidatedToolCall


class ToolExecutor(Protocol):
    async def execute(
        self,
        call: ValidatedToolCall,
        state: AgentFlowState,
    ) -> ToolResult: ...


class ToolCallStep:
    """Durable step for a single validated tool call.

    step_type = "tool_call"
    The idempotency_key from the ValidatedToolCall ensures that a
    succeeded call is never re-executed on resume.
    Design link: Section 11.
    """

    step_type = "tool_call"

    def __init__(self, *, executor: ToolExecutor, call: ValidatedToolCall) -> None:
        self._executor = executor
        self._call = call

    async def run(self, state: AgentFlowState, context: RuntimeContext) -> StepResult:
        result = await self._executor.execute(self._call, state)
        return StepResult(output_json=result.model_dump(mode="json"))


def build_execute_tools_step(
    *,
    validated_calls: list[ValidatedToolCall],
    executor: ToolExecutor,
) -> ParallelStepGroup:
    """Build a ParallelStepGroup of durable tool_call child steps.

    step_name per child is "tool_call:{tool_call_id}" so the StepRunner
    idempotency key is "{run_id}:{iteration}:tool_call:{tool_call_id}".
    On resume, already-succeeded calls are skipped automatically.
    Design link: Section 11.
    """
    children = [
        ChildStep(
            step=ToolCallStep(executor=executor, call=call),
            step_name=f"tool_call:{call.tool_call_id}",
            input_json=call.model_dump(mode="json"),
            context=_context_for_call(call),
        )
        for call in validated_calls
    ]
    return ParallelStepGroup(
        step_type="parallel:execute_tools",
        step_name="execute_tools",
        children=children,
    )


def _context_for_call(call: ValidatedToolCall) -> RuntimeContext:
    retry = (
        call.retry_policy
        if call.retry_policy is not None
        else RetryPolicy(max_attempts=1)
    )
    return RuntimeContext(
        execution_policy=StepExecutionPolicy(
            timeout_ms=call.timeout_ms,
            deadline_ms=call.deadline_ms,
            retry=retry,
        )
    )
