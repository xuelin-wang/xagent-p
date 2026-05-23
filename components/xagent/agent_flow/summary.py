from __future__ import annotations

from typing import Protocol

from xagent.agent_flow.config import SummaryConfig
from xagent.agent_flow.llm_adapter import AgentFlowLLMAdapter, read_prompt_template
from xagent.agent_flow.models import (
    AgentFlowIteration,
    AgentFlowState,
    SummaryDecision,
    SummaryOutput,
)
from xagent.agent_flow.steps import RuntimeContext, StepResult


class SummaryExecutor(Protocol):
    async def summarize(
        self,
        *,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> SummaryOutput: ...


class SummaryStep:
    """RuntimeStep adapter for summary executors."""

    step_type = "summary"

    def __init__(self, *, executor: SummaryExecutor, iteration: AgentFlowIteration):
        self._executor = executor
        self._iteration = iteration

    async def run(
        self,
        state: AgentFlowState,
        context: RuntimeContext,
    ) -> StepResult:
        _ = context
        summary = await self._executor.summarize(
            state=state,
            iteration=self._iteration,
        )
        return StepResult(output_json=summary.model_dump(mode="json"))


class FakeSummaryExecutor:
    def __init__(self, *, decision: SummaryDecision = SummaryDecision.FINAL):
        self._decision = decision

    async def summarize(
        self,
        *,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> SummaryOutput:
        completed_results = [
            result
            for result in iteration.subagent_results.values()
            if result.status == "completed"
        ]
        if self._decision is SummaryDecision.FINAL:
            answer_draft = "\n".join(result.content for result in completed_results)
            if not answer_draft:
                answer_draft = f"No completed subagent results for: {state.user_query}"
            return SummaryOutput(
                decision=SummaryDecision.FINAL,
                answer_draft=answer_draft,
                rationale="Deterministic fake summary.",
            )
        if self._decision is SummaryDecision.REPLAN:
            return SummaryOutput(
                decision=SummaryDecision.REPLAN,
                rationale="Deterministic fake summary requested replan.",
                missing_information=["More fake evidence required."],
                suggested_replan={"reason": "fake_replan"},
            )
        return SummaryOutput(
            decision=SummaryDecision.FAIL,
            rationale="Deterministic fake summary requested failure.",
        )


class LLMSummaryExecutor:
    def __init__(
        self,
        *,
        config: SummaryConfig,
        llm: AgentFlowLLMAdapter,
    ):
        self._config = config
        self._llm = llm

    async def summarize(
        self,
        *,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> SummaryOutput:
        return await self._llm.generate_structured(
            model_name=self._config.model,
            system_prompt=read_prompt_template(self._config.prompt_template),
            user_prompt=self._render_user_prompt(state=state, iteration=iteration),
            output_type=SummaryOutput,
            metadata={
                "agent_flow_run_id": state.run_id,
                "agent_flow_stage": "summary",
            },
        )

    def _render_user_prompt(
        self,
        *,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> str:
        serialized_results = (
            "\n\n".join(
                (
                    f"Subagent: {result.name}\n"
                    f"Status: {result.status}\n"
                    f"Content:\n{result.content}"
                )
                for result in iteration.subagent_results.values()
            )
            or "No subagent results were available."
        )
        return (
            f"User query:\n{state.user_query}\n\n"
            f"Iteration: {iteration.iteration}\n\n"
            f"Subagent results:\n{serialized_results}"
        )
