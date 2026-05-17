from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from xagent.agent_flow.config import AgentFlowAppConfig
from xagent.agent_flow.errors import StepRunnerError
from xagent.agent_flow.models import (
    AgentError,
    AgentFlowIteration,
    AgentFlowState,
    FlowStage,
    PlanOutput,
    RunStatus,
    SubagentResult,
    SummaryDecision,
    SummaryOutput,
)
from xagent.agent_flow.planner import PlannerExecutor
from xagent.agent_flow.step_runner import StepRunner
from xagent.agent_flow.subagents import FlowSubagent
from xagent.agent_flow.summary import SummaryExecutor
from xagent.agent_persistence.repositories import (
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
        self._checkpoint_repository = checkpoint_repository
        self._planner = planner
        self._subagents = dict(subagents)
        self._summary = summary
        self._step_runner = StepRunner(step_repository)

    async def run(self, state: AgentFlowState) -> AgentFlowState:
        return await self._run_loop(state, create_run=True)

    async def resume(self, state: AgentFlowState) -> AgentFlowState:
        if state.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
            return state
        return await self._run_loop(state, create_run=False)

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
            iteration = state.get_or_create_current_iteration()
            try:
                await self._run_planner(state, iteration)
                await self._run_subagents(state, iteration)
                await self._run_summary(state, iteration)
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

            if iteration.summary is None:
                return await self._fail_state(
                    state,
                    AgentError(
                        stage=FlowStage.SUMMARIZING,
                        message="Summary step did not produce output.",
                    ),
                )

            if iteration.summary.decision is SummaryDecision.FINAL:
                return await self._complete_state(
                    state,
                    iteration.summary.answer_draft or "",
                )

            if iteration.summary.decision is SummaryDecision.FAIL:
                return await self._fail_state(
                    state,
                    AgentError(
                        stage=FlowStage.SUMMARIZING,
                        message=iteration.summary.rationale
                        or "Summary requested run failure.",
                    ),
                )

            if state.current_iteration + 1 >= self._config.workflow.max_iterations:
                return await self._fail_state(
                    state,
                    AgentError(
                        stage=FlowStage.SUMMARIZING,
                        message="Agent flow reached the maximum iteration count.",
                        details={
                            "max_iterations": self._config.workflow.max_iterations,
                        },
                    ),
                )

            state.current_iteration += 1
            state.current_stage = FlowStage.START
            await self._save_state(state, checkpoint_name="replan")

    async def _run_planner(
        self,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> None:
        state.current_stage = FlowStage.PLANNING
        output_json = await self._step_runner.run_step(
            state=state,
            step_name="planner",
            step_type="planner",
            input_json={
                "query": state.user_query,
                "subagents": list(self._config.subagents),
            },
            max_attempts=self._config.planner.max_attempts,
            fn=lambda _: self._plan_step(state),
        )
        iteration.plan = PlanOutput.model_validate(output_json)
        await self._save_state(state, checkpoint_name="planner")

    async def _plan_step(self, state: AgentFlowState) -> dict[str, Any]:
        plan = await self._planner.plan(
            state=state,
            subagents=self._config.subagents,
            max_selections=self._config.workflow.max_subagents_per_iteration,
        )
        return plan.model_dump(mode="json")

    async def _run_subagents(
        self,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> None:
        state.current_stage = FlowStage.SUBAGENTS
        if iteration.plan is None:
            raise RuntimeError("Planner must run before subagents.")

        if self._config.workflow.subagent_execution_mode == "parallel":
            results = await asyncio.gather(
                *[
                    self._run_subagent_step(state, selection.name)
                    for selection in iteration.plan.selections
                    if selection.name in self._subagents
                ]
            )
        else:
            results = []
            for selection in iteration.plan.selections:
                if selection.name in self._subagents:
                    results.append(await self._run_subagent_step(state, selection.name))

        for result in results:
            iteration.subagent_results[result.name] = result
            if result.error is not None:
                iteration.errors.append(result.error)

        failed_results = [result for result in results if result.status == "error"]
        if failed_results and not self._config.workflow.continue_on_subagent_failure:
            first = failed_results[0]
            raise RuntimeError(first.error.message if first.error else first.content)

        await self._save_state(state, checkpoint_name="subagents")

    async def _run_subagent_step(
        self,
        state: AgentFlowState,
        subagent_name: str,
    ) -> SubagentResult:
        iteration = state.get_or_create_current_iteration()
        if iteration.plan is None:
            raise RuntimeError("Planner must run before subagents.")
        selection = next(
            selection
            for selection in iteration.plan.selections
            if selection.name == subagent_name
        )
        output_json = await self._step_runner.run_step(
            state=state,
            step_name=f"subagent:{subagent_name}",
            step_type="subagent",
            input_json=selection.model_dump(mode="json"),
            max_attempts=self._config.subagents[subagent_name].max_attempts,
            fn=lambda _: self._invoke_subagent(state, subagent_name),
        )
        return SubagentResult.model_validate(output_json)

    async def _invoke_subagent(
        self,
        state: AgentFlowState,
        subagent_name: str,
    ) -> dict[str, Any]:
        iteration = state.get_or_create_current_iteration()
        if iteration.plan is None:
            raise RuntimeError("Planner must run before subagents.")
        selection = next(
            selection
            for selection in iteration.plan.selections
            if selection.name == subagent_name
        )
        result = await self._subagents[subagent_name].ainvoke(
            state=state,
            selection=selection,
        )
        return result.model_dump(mode="json")

    async def _run_summary(
        self,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> None:
        state.current_stage = FlowStage.SUMMARIZING
        output_json = await self._step_runner.run_step(
            state=state,
            step_name="summary",
            step_type="summary",
            input_json={
                "query": state.user_query,
                "subagent_results": {
                    name: result.model_dump(mode="json")
                    for name, result in iteration.subagent_results.items()
                },
            },
            max_attempts=self._config.summary.max_attempts,
            fn=lambda _: self._summarize_step(state, iteration),
        )
        iteration.summary = SummaryOutput.model_validate(output_json)
        await self._save_state(state, checkpoint_name="summary")

    async def _summarize_step(
        self,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> dict[str, Any]:
        summary = await self._summary.summarize(state=state, iteration=iteration)
        return summary.model_dump(mode="json")

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

    async def _save_state(
        self,
        state: AgentFlowState,
        *,
        checkpoint_name: str,
    ) -> None:
        await self._run_repository.update_run_state(state)
        await self._checkpoint_repository.save_checkpoint(
            run_id=state.run_id,
            iteration=state.current_iteration,
            checkpoint_name=checkpoint_name,
            stage=state.current_stage,
            state=state,
        )
