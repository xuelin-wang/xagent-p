from __future__ import annotations

from typing import Protocol

from xagent.agent_flow.models import (
    AgentFlowIteration,
    AgentFlowState,
    SummaryDecision,
    SummaryOutput,
)


class SummaryExecutor(Protocol):
    async def summarize(
        self,
        *,
        state: AgentFlowState,
        iteration: AgentFlowIteration,
    ) -> SummaryOutput: ...


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
