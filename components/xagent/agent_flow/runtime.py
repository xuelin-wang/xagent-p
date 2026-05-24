from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from xagent.agent_flow.config import AgentFlowAppConfig
from xagent.agent_flow.errors import StepRunnerError
from xagent.agent_flow.models import (
    AgentError,
    AgentFlowState,
    FlowStage,
    RunStatus,
    SummaryDecision,
    UserInputEvent,
)
from xagent.agent_flow.planner import PlannerExecutor
from xagent.agent_flow.state_projection import derive_state
from xagent.agent_flow.step_runner import StepRunner
from xagent.agent_flow.steps import RuntimeContext
from xagent.agent_flow.subagents import FlowSubagent
from xagent.agent_flow.summary import SummaryExecutor
from xagent.agent_flow.workflow import build_iteration_step
from xagent.agent_persistence.repositories import (
    CheckpointRecord,
    CheckpointRepository,
    RunRepository,
    StepRepository,
)


class AgentFlowRuntime:
    def __init__(
        self,
        *,
        config: AgentFlowAppConfig,
        run_repository: RunRepository,
        step_repository: StepRepository,
        checkpoint_repository: CheckpointRepository,
        planner: PlannerExecutor,
        subagents: Mapping[str, FlowSubagent],
        summary: SummaryExecutor,
    ):
        self._config = config
        self._run_repository = run_repository
        self._step_repository = step_repository
        self._checkpoint_repository = checkpoint_repository
        self._planner = planner
        self._subagents = dict(subagents)
        self._summary = summary
        self._step_runner = StepRunner(step_repository)

    async def run(self, state: AgentFlowState) -> AgentFlowState:
        return await self._run_loop(state, create_run=True)

    async def resume(self, state: AgentFlowState) -> AgentFlowState:
        base = await self._checkpoint_repository.get_latest_checkpoint(state.run_id)
        if base is None:
            base = state
        if base.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
            return base
        steps = await self._step_repository.get_steps_for_run_iteration(
            base.run_id,
            base.current_iteration,
        )
        derived = derive_state(base, steps)
        return await self._run_loop(derived, create_run=False)

    async def _run_loop(
        self,
        state: AgentFlowState,
        *,
        create_run: bool,
    ) -> AgentFlowState:
        state.status = RunStatus.RUNNING
        if create_run:
            await self._run_repository.create_run(state)
        else:
            await self._run_repository.update_run_state(state)
        await self._save_state(state, checkpoint_name="start")

        while True:
            try:
                state_after = await self._run_iteration(state)
            except StepRunnerError as exc:
                return await self._fail_state(
                    state,
                    AgentError(
                        stage=state.current_stage,
                        step_name=exc.step.step_name,
                        message=str(exc),
                        error_type=exc.error_json.get("error_type"),
                        retryable=bool(exc.error_json.get("retryable", False)),
                        details=exc.error_json,
                    ),
                )
            except Exception as exc:
                return await self._fail_state(
                    state,
                    AgentError(
                        stage=state.current_stage,
                        message=str(exc),
                        error_type=type(exc).__name__,
                        retryable=False,
                    ),
                )

            current_iteration = state_after.get_or_create_current_iteration()
            failed_subagents = [
                r
                for r in current_iteration.subagent_results.values()
                if r.status == "error"
            ]
            if (
                failed_subagents
                and not self._config.workflow.continue_on_subagent_failure
            ):
                first = failed_subagents[0]
                return await self._fail_state(
                    state_after,
                    AgentError(
                        stage=FlowStage.SUBAGENTS,
                        message=first.error.message if first.error else first.content,
                    ),
                )

            if current_iteration.summary is None:
                return await self._fail_state(
                    state_after,
                    AgentError(
                        stage=FlowStage.SUMMARIZING,
                        message="Summary step did not produce output.",
                    ),
                )

            if current_iteration.summary.decision is SummaryDecision.FINAL:
                return await self._complete_state(
                    state_after,
                    current_iteration.summary.answer_draft or "",
                )

            if current_iteration.summary.decision is SummaryDecision.ASK_USER:
                user_request = current_iteration.summary.user_request
                if user_request is None:
                    return await self._fail_state(
                        state_after,
                        AgentError(
                            stage=FlowStage.SUMMARIZING,
                            message="ASK_USER decision requires user_request in SummaryOutput.",
                        ),
                    )
                wait_state = state_after.model_copy(deep=True)
                wait_state.pending_user_request = user_request
                wait_state.status = RunStatus.WAITING_FOR_USER
                wait_state.current_stage = FlowStage.WAITING_FOR_USER
                return await self._pause_state(wait_state)

            if current_iteration.summary.decision is SummaryDecision.FAIL:
                return await self._fail_state(
                    state_after,
                    AgentError(
                        stage=FlowStage.SUMMARIZING,
                        message=current_iteration.summary.rationale
                        or "Summary requested run failure.",
                    ),
                )

            if (
                state_after.current_iteration + 1
                >= self._config.workflow.max_iterations
            ):
                return await self._fail_state(
                    state_after,
                    AgentError(
                        stage=FlowStage.SUMMARIZING,
                        message="Agent flow reached the maximum iteration count.",
                        details={
                            "max_iterations": self._config.workflow.max_iterations,
                        },
                    ),
                )

            state = state_after.model_copy(deep=True)
            state.current_iteration += 1
            state.current_stage = FlowStage.START
            await self._save_state(state, checkpoint_name="replan")

    async def _run_iteration(
        self,
        state: AgentFlowState,
    ) -> AgentFlowState:
        """Build and execute the iteration workflow tree.

        Design link: Section 3.1, step hierarchy.
        Non-goal: does not contain per-phase orchestration; delegates to workflow.py.
        """
        workflow_step = build_iteration_step(
            config=self._config,
            planner=self._planner,
            subagents=self._subagents,
            summary=self._summary,
            state=state,
        )

        result = await self._step_runner.execute_composite(
            workflow_step, state, RuntimeContext()
        )
        state_after = result.state_after if result.state_after is not None else state
        await self._save_state(state_after, checkpoint_name="iteration")
        return state_after

    async def _complete_state(
        self,
        state: AgentFlowState,
        final_response: str,
    ) -> AgentFlowState:
        state.current_stage = FlowStage.FINALIZING
        state.final_response = final_response
        await self._save_state(state, checkpoint_name="final")
        await self._run_repository.mark_completed(state.run_id, final_response)
        completed = await self._run_repository.get_run_state(state.run_id)
        await self._checkpoint_repository.save_checkpoint(
            run_id=completed.run_id,
            iteration=completed.current_iteration,
            checkpoint_name="completed",
            stage=completed.current_stage,
            state=completed,
        )
        return completed

    async def _fail_state(
        self,
        state: AgentFlowState,
        error: AgentError,
    ) -> AgentFlowState:
        await self._run_repository.update_run_state(state)
        await self._run_repository.mark_failed(
            state.run_id, error.model_dump(mode="json")
        )
        failed = await self._run_repository.get_run_state(state.run_id)
        await self._checkpoint_repository.save_checkpoint(
            run_id=failed.run_id,
            iteration=failed.current_iteration,
            checkpoint_name="failed",
            stage=failed.current_stage,
            state=failed,
        )
        return failed

    async def _pause_state(self, state: AgentFlowState) -> AgentFlowState:
        await self._run_repository.update_run_state(state)
        await self._checkpoint_repository.save_checkpoint(
            run_id=state.run_id,
            iteration=state.current_iteration,
            checkpoint_name="ask_user",
            stage=state.current_stage,
            state=state,
        )
        return state

    async def resume_with_input(
        self,
        state: AgentFlowState,
        user_input: str,
    ) -> AgentFlowState:
        """Resume a waiting_for_user run by attaching a user input event."""
        if state.status is not RunStatus.WAITING_FOR_USER:
            raise ValueError(f"Expected waiting_for_user status, got: {state.status}")
        if state.pending_user_request is None:
            raise ValueError("No pending user request found in state")

        event = UserInputEvent(
            event_id=str(uuid4()),
            run_id=state.run_id,
            request_id=state.pending_user_request.request_id,
            content=user_input,
            occurred_at=datetime.now(UTC),
        )
        new_state = state.model_copy(deep=True)
        new_state.user_input_events.append(event)
        new_state.pending_user_request = None
        new_state.current_iteration += 1
        new_state.current_stage = FlowStage.START
        await self._save_state(new_state, checkpoint_name="user_input")
        return await self._run_loop(new_state, create_run=False)

    async def _save_state(
        self,
        state: AgentFlowState,
        *,
        checkpoint_name: str,
    ) -> CheckpointRecord:
        await self._run_repository.update_run_state(state)
        return await self._checkpoint_repository.save_checkpoint(
            run_id=state.run_id,
            iteration=state.current_iteration,
            checkpoint_name=checkpoint_name,
            stage=state.current_stage,
            state=state,
        )
