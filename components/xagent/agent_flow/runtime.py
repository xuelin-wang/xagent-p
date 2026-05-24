from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from xagent.agent_flow.config import AgentFlowAppConfig
from xagent.agent_flow.errors import StepRunnerError, StepWaiting
from xagent.agent_flow.messages import MessageInputStep
from xagent.agent_flow.models import (
    AgentError,
    AgentFlowState,
    ConversationMessageEvent,
    FlowStage,
    RunStatus,
    StepStatus,
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

    async def run_with_message(
        self,
        state: AgentFlowState,
        *,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> AgentFlowState:
        await self._run_repository.create_run(state)
        state = await self._record_message(
            state,
            content=content,
            metadata=metadata,
        )
        return await self._run_loop(state, create_run=False)

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
            except StepWaiting as exc:
                wait_state = (
                    exc.state.model_copy(deep=True)
                    if exc.state is not None
                    else state.model_copy(deep=True)
                )
                wait_state.pending_wait = exc.wait_spec
                wait_state.status = RunStatus.WAITING
                wait_state.current_stage = FlowStage.WAITING
                return await self._pause_state(wait_state)
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
                return await self._fail_state(
                    state_after,
                    AgentError(
                        stage=FlowStage.SUMMARIZING,
                        message="ASK_USER decision did not enter a wait step.",
                    ),
                )

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
            workflow_step,
            state,
            RuntimeContext.from_runtime_policy(
                self._config.execution_policy,
                step_type=workflow_step.step_type,
            ),
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
            checkpoint_name="wait",
            stage=state.current_stage,
            state=state,
        )
        return state

    async def resume_with_message(
        self,
        state: AgentFlowState,
        *,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> AgentFlowState:
        """Resume a waiting run by completing its wait step and recording a message."""
        if state.status not in {RunStatus.WAITING, RunStatus.WAITING_FOR_USER}:
            raise ValueError(f"Expected waiting status, got: {state.status}")

        resumed = state.model_copy(deep=True)
        await self._complete_waiting_steps(resumed)
        resumed.pending_wait = None
        resumed.pending_user_request = None
        resumed.current_iteration += 1
        resumed.current_stage = FlowStage.START
        resumed.status = RunStatus.RUNNING
        resumed = await self._record_message(
            resumed,
            content=content,
            metadata=metadata,
        )
        return await self._run_loop(resumed, create_run=False)

    async def resume_with_input(
        self,
        state: AgentFlowState,
        user_input: str,
    ) -> AgentFlowState:
        """Resume a waiting_for_user run by attaching a user input event."""
        if state.status not in {RunStatus.WAITING, RunStatus.WAITING_FOR_USER}:
            raise ValueError(f"Expected waiting status, got: {state.status}")
        request_id = "conversation_message"
        if state.pending_user_request is not None:
            request_id = state.pending_user_request.request_id
        elif state.pending_wait is not None:
            request_id = str(state.pending_wait.metadata.get("request_id", request_id))
        event = UserInputEvent(
            event_id=str(uuid4()),
            run_id=state.run_id,
            request_id=request_id,
            content=user_input,
            occurred_at=datetime.now(UTC),
        )
        new_state = state.model_copy(deep=True)
        new_state.user_input_events.append(event)
        return await self.resume_with_message(new_state, content=user_input)

    async def _record_message(
        self,
        state: AgentFlowState,
        *,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> AgentFlowState:
        message = ConversationMessageEvent(
            message_id=f"msg_{uuid4().hex}",
            conversation_id=state.conversation_id,
            run_id=state.run_id,
            role="user",
            content=content,
            occurred_at=datetime.now(UTC),
            metadata=dict(metadata or {}),
        )
        output_json = await self._step_runner.run_runtime_step(
            state=state,
            step_name=f"message_input:{message.message_id}",
            input_json=message.model_dump(mode="json"),
            step=MessageInputStep(message=message),
            context=RuntimeContext.from_runtime_policy(
                self._config.execution_policy,
                step_type="message_input",
            ),
        )
        next_state = state.model_copy(deep=True)
        next_state.conversation_messages.append(
            ConversationMessageEvent.model_validate(output_json["message"])
        )
        next_state.user_query = content
        await self._save_state(next_state, checkpoint_name="message_input")
        return next_state

    async def _complete_waiting_steps(self, state: AgentFlowState) -> None:
        steps = await self._step_repository.get_steps_for_run_iteration(
            state.run_id,
            state.current_iteration,
        )
        for step in steps:
            if step.status is StepStatus.WAITING:
                await self._step_repository.mark_step_resumed(step.step_id)
                await self._step_repository.mark_step_succeeded(
                    step.step_id,
                    step.output_json or {},
                )

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
