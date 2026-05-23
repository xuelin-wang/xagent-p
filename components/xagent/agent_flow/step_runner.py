from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from xagent.agent_flow.errors import NonRetryableStepError, StepRunnerError
from xagent.agent_flow.models import AgentFlowState, StepStatus
from xagent.agent_flow.steps import RuntimeContext, RuntimeStep
from xagent.agent_persistence.repositories import StepRecord, StepRepository

StepFunction = Callable[[StepRecord], Awaitable[dict[str, Any]]]


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
    ) -> dict[str, Any]:
        """Run a RuntimeStep through the existing durable step machinery."""

        return await self.run_step(
            state=state,
            step_name=step_name,
            step_type=step.step_type,
            input_json=input_json,
            max_attempts=context.execution_policy.retry.max_attempts,
            fn=lambda _: self._run_runtime_step(
                step=step,
                state=state,
                context=context,
            ),
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
    ) -> dict[str, Any]:
        attempts = max(max_attempts, 1)
        step = await self._step_repository.create_or_get_step(
            run_id=state.run_id,
            iteration=state.current_iteration,
            step_name=step_name,
            step_type=step_type,
            input_json=input_json,
            max_attempts=attempts,
            idempotency_key=f"{state.run_id}:{state.current_iteration}:{step_name}",
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
        while current_step.attempt_count < current_step.max_attempts:
            current_step = await self._step_repository.mark_step_running(
                current_step.step_id
            )
            try:
                output_json = await fn(current_step)
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
                retryable = current_step.attempt_count < current_step.max_attempts
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

    async def _run_runtime_step(
        self,
        *,
        step: RuntimeStep,
        state: AgentFlowState,
        context: RuntimeContext,
    ) -> dict[str, Any]:
        result = await step.run(state=state, context=context)
        return result.output_json
