from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, cast

from xagent.agent_flow.errors import NonRetryableStepError, StepRunnerError
from xagent.agent_flow.models import AgentFlowState, StepStatus
from xagent.agent_flow.state_projection import _apply
from xagent.agent_flow.steps import (
    ParallelStepGroup,
    RuntimeContext,
    RuntimeStep,
    SequenceStepGroup,
    StepExecutionPolicy,
    StepResult,
)
from xagent.agent_persistence.repositories import (
    StepRecord,
    StepRepository,
)

StepFunction = Callable[[StepRecord], Awaitable[dict[str, Any]]]


@dataclass
class ChildStep:
    """Bundles a step with its execution metadata for use inside composite steps.

    Design link: Section 3.1, step hierarchy.
    Non-goal: should not contain retry or checkpoint logic (that stays in the executor).

    input_json may be a static dict or a Callable[[AgentFlowState], dict] evaluated
    at execution time — useful when the input depends on prior step outputs.
    context overrides the parent's RuntimeContext for this child only (e.g., per-step
    retry policy). If None, the parent context is inherited.
    """

    step: Any  # RuntimeStep | SequenceStepGroup | ParallelStepGroup
    step_name: str
    input_json: Any = dc_field(
        default_factory=dict
    )  # dict | Callable[[AgentFlowState], dict]
    context: RuntimeContext | None = None


class StepRunner:
    def __init__(self, step_repository: StepRepository):
        self._step_repository = step_repository

    async def run_runtime_step(
        self,
        *,
        state: AgentFlowState,
        step_name: str,
        input_json: dict[str, Any],
        step: RuntimeStep,
        context: RuntimeContext,
        parent_step_id: str | None = None,
    ) -> dict[str, Any]:
        """Run a RuntimeStep through the existing durable step machinery."""

        return await self.run_step(
            state=state,
            step_name=step_name,
            step_type=step.step_type,
            input_json=input_json,
            max_attempts=context.execution_policy.retry.max_attempts,
            execution_policy=context.execution_policy,
            fn=lambda _: self._run_runtime_step(
                step=step,
                state=state,
                context=context,
            ),
            parent_step_id=parent_step_id,
        )

    async def run_step(
        self,
        *,
        state: AgentFlowState,
        step_name: str,
        step_type: str,
        input_json: dict[str, Any],
        max_attempts: int,
        fn: StepFunction,
        parent_step_id: str | None = None,
        execution_policy: StepExecutionPolicy | None = None,
    ) -> dict[str, Any]:
        attempts = max(max_attempts, 1)
        policy = execution_policy or StepExecutionPolicy()
        step = await self._step_repository.create_or_get_step(
            run_id=state.run_id,
            iteration=state.current_iteration,
            step_name=step_name,
            step_type=step_type,
            input_json=input_json,
            max_attempts=attempts,
            idempotency_key=f"{state.run_id}:{state.current_iteration}:{step_name}",
            parent_step_id=parent_step_id,
        )

        if step.status is StepStatus.SUCCEEDED:
            return step.output_json or {}

        if step.status is StepStatus.FAILED and step.attempt_count >= step.max_attempts:
            error_json = step.error_json or {
                "message": "Durable step failed before resume.",
                "retryable": False,
            }
            raise StepRunnerError(
                str(error_json.get("message", "Durable step failed.")),
                step=step,
                error_json=error_json,
            )

        current_step = step
        deadline_at = self._deadline_at(policy)
        while current_step.attempt_count < current_step.max_attempts:
            current_step = await self._step_repository.mark_step_running(
                current_step.step_id
            )
            try:
                output_json = await self._run_with_policy(
                    fn(current_step),
                    policy=policy,
                    deadline_at=deadline_at,
                )
            except NonRetryableStepError as exc:
                error_json = self._error_json(exc, retryable=False)
                failed_step = await self._step_repository.mark_step_failed(
                    current_step.step_id,
                    error_json,
                )
                raise StepRunnerError(
                    str(exc),
                    step=failed_step,
                    error_json=error_json,
                ) from exc
            except Exception as exc:
                retryable = self._is_retryable(
                    current_step=current_step,
                    policy=policy,
                    deadline_at=deadline_at,
                )
                error_json = self._error_json(exc, retryable=retryable)
                failed_step = await self._step_repository.mark_step_failed(
                    current_step.step_id,
                    error_json,
                )
                if not retryable:
                    raise StepRunnerError(
                        str(exc),
                        step=failed_step,
                        error_json=error_json,
                    ) from exc
                current_step = failed_step
                continue

            await self._step_repository.mark_step_succeeded(
                current_step.step_id,
                output_json,
            )
            return output_json

        error_json = current_step.error_json or {
            "message": "Durable step exhausted attempts.",
            "retryable": False,
        }
        raise StepRunnerError(
            str(error_json.get("message", "Durable step failed.")),
            step=current_step,
            error_json=error_json,
        )

    def _error_json(self, exc: Exception, *, retryable: bool) -> dict[str, Any]:
        return {
            "message": str(exc),
            "error_type": type(exc).__name__,
            "retryable": retryable,
        }

    def _deadline_at(self, policy: StepExecutionPolicy) -> float | None:
        if policy.deadline_ms is None or policy.deadline_ms == 0:
            return None
        return asyncio.get_running_loop().time() + (policy.deadline_ms / 1000)

    async def _run_with_policy(
        self,
        awaitable: Awaitable[dict[str, Any]],
        *,
        policy: StepExecutionPolicy,
        deadline_at: float | None,
    ) -> dict[str, Any]:
        wait_seconds = self._wait_seconds(policy=policy, deadline_at=deadline_at)
        if wait_seconds is None:
            return await awaitable
        if wait_seconds <= 0:
            if hasattr(awaitable, "close"):
                cast(Any, awaitable).close()
            raise TimeoutError("Step deadline expired before execution.")
        try:
            return await asyncio.wait_for(awaitable, timeout=wait_seconds)
        except TimeoutError as exc:
            raise TimeoutError(self._timeout_message(policy, deadline_at)) from exc

    def _wait_seconds(
        self,
        *,
        policy: StepExecutionPolicy,
        deadline_at: float | None,
    ) -> float | None:
        candidates: list[float] = []
        if policy.timeout_ms is not None and policy.timeout_ms > 0:
            candidates.append(policy.timeout_ms / 1000)
        if deadline_at is not None:
            candidates.append(deadline_at - asyncio.get_running_loop().time())
        if not candidates:
            return None
        return min(candidates)

    def _timeout_message(
        self,
        policy: StepExecutionPolicy,
        deadline_at: float | None,
    ) -> str:
        if deadline_at is not None and deadline_at <= asyncio.get_running_loop().time():
            return f"Step deadline exceeded after {policy.deadline_ms} ms."
        return f"Step timed out after {policy.timeout_ms} ms."

    def _is_retryable(
        self,
        *,
        current_step: StepRecord,
        policy: StepExecutionPolicy,
        deadline_at: float | None,
    ) -> bool:
        has_attempts = current_step.attempt_count < current_step.max_attempts
        if not has_attempts:
            return False
        if deadline_at is None:
            return True
        return deadline_at > asyncio.get_running_loop().time()

    async def _run_runtime_step(
        self,
        *,
        step: RuntimeStep,
        state: AgentFlowState,
        context: RuntimeContext,
    ) -> dict[str, Any]:
        result = await step.run(state=state, context=context)
        return result.output_json

    async def execute_composite(
        self,
        group: SequenceStepGroup | ParallelStepGroup,
        state: AgentFlowState,
        context: RuntimeContext,
        *,
        parent_step_id: str | None = None,
    ) -> StepResult:
        """Execute a composite step group (sequence or parallel).

        Design link: Section 3.1, step hierarchy.
        Creates its own durable step record so it appears in the event ledger.
        Children are executed with parent_step_id pointing to this group's record.
        Resume: already-succeeded composites are skipped; partially completed ones
        re-execute only incomplete children (each child handles its own idempotency).
        """
        step_record = await self._step_repository.create_or_get_step(
            run_id=state.run_id,
            iteration=state.current_iteration,
            step_name=group.step_name,
            step_type=group.step_type,
            input_json={},
            max_attempts=1,
            idempotency_key=f"{state.run_id}:{state.current_iteration}:{group.step_name}",
            parent_step_id=parent_step_id,
        )

        if step_record.status is StepStatus.SUCCEEDED:
            return StepResult(output_json=step_record.output_json or {})

        step_record = await self._step_repository.mark_step_running(step_record.step_id)

        try:
            result = await self._run_composite_with_policy(
                group=group,
                state=state,
                context=context,
                parent_step_id=step_record.step_id,
                policy=context.execution_policy,
            )
        except Exception as exc:
            error_json = self._error_json(exc, retryable=False)
            await self._step_repository.mark_step_failed(
                step_record.step_id, error_json
            )
            raise

        await self._step_repository.mark_step_succeeded(
            step_record.step_id,
            result.output_json,
        )
        return result

    async def _run_composite_with_policy(
        self,
        *,
        group: SequenceStepGroup | ParallelStepGroup,
        state: AgentFlowState,
        context: RuntimeContext,
        parent_step_id: str,
        policy: StepExecutionPolicy,
    ) -> StepResult:
        async def run_group() -> StepResult:
            if isinstance(group, SequenceStepGroup):
                return await self._execute_sequence(
                    group, state, context, parent_step_id
                )
            return await self._execute_parallel(group, state, context, parent_step_id)

        deadline_at = self._deadline_at(policy)
        wait_seconds = self._wait_seconds(policy=policy, deadline_at=deadline_at)
        if wait_seconds is None:
            return await run_group()
        if wait_seconds <= 0:
            raise TimeoutError("Step deadline expired before execution.")
        try:
            return await asyncio.wait_for(run_group(), timeout=wait_seconds)
        except TimeoutError as exc:
            raise TimeoutError(self._timeout_message(policy, deadline_at)) from exc

    async def _execute_sequence(
        self,
        group: SequenceStepGroup,
        state: AgentFlowState,
        context: RuntimeContext,
        parent_step_id: str,
    ) -> StepResult:
        current = state
        for spec in group.children:
            if callable(spec):
                child = spec(current)
                if child is None:
                    continue
            else:
                child = spec
            result = await self._execute_child(child, current, context, parent_step_id)
            if result.state_after is not None:
                current = result.state_after
        return StepResult(output_json={}, state_after=current)

    async def _execute_parallel(
        self,
        group: ParallelStepGroup,
        state: AgentFlowState,
        context: RuntimeContext,
        parent_step_id: str,
    ) -> StepResult:
        children = group.children
        if callable(children):
            children = children(state)

        results = await asyncio.gather(
            *[
                self._execute_child(child, state, context, parent_step_id)
                for child in children
            ]
        )

        merged: dict[str, Any] = {}
        merged_state = state
        for child, result in zip(children, results, strict=True):
            merged.update(result.output_json)
            if isinstance(child.step, (SequenceStepGroup, ParallelStepGroup)):
                if result.state_after is not None:
                    merged_state = result.state_after
            else:
                merged_state = _apply(merged_state, child.step_name, result.output_json)
        return StepResult(output_json=merged, state_after=merged_state)

    async def _execute_child(
        self,
        child: ChildStep,
        state: AgentFlowState,
        context: RuntimeContext,
        parent_step_id: str,
    ) -> StepResult:
        step = child.step
        step_type = step.step_type
        effective_context = context.for_child(
            step_type=step_type,
            override=child.context,
        )
        input_json = (
            child.input_json(state) if callable(child.input_json) else child.input_json
        )

        if isinstance(step, (SequenceStepGroup, ParallelStepGroup)):
            return await self.execute_composite(
                step, state, effective_context, parent_step_id=parent_step_id
            )

        output_json = await self.run_runtime_step(
            state=state,
            step_name=child.step_name,
            input_json=input_json,
            step=step,
            context=effective_context,
            parent_step_id=parent_step_id,
        )
        return StepResult(
            output_json=output_json,
            state_after=_apply(state, child.step_name, output_json),
        )
