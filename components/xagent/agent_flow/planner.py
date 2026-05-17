from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from xagent.agent_flow.config import PlannerConfig, SubagentConfig
from xagent.agent_flow.llm_adapter import AgentFlowLLMAdapter, read_prompt_template
from xagent.agent_flow.models import (
    AgentFlowState,
    PlanOutput,
    PlanSubagentSelection,
)


class PlannerExecutor(Protocol):
    async def plan(
        self,
        *,
        state: AgentFlowState,
        subagents: Mapping[str, SubagentConfig],
        max_selections: int,
    ) -> PlanOutput: ...


class FakePlannerRule(BaseModel):
    query_contains: str
    select: list[str]


class LLMPlannerDecision(BaseModel):
    goal: str
    selections: list[PlanSubagentSelection] = Field(default_factory=list)
    rationale: str = ""


class FakePlannerExecutor:
    def __init__(
        self,
        *,
        selection_names: Sequence[str] | None = None,
        rules: Sequence[FakePlannerRule] | None = None,
    ):
        self._selection_names = list(selection_names) if selection_names else None
        self._rules = list(rules or [])

    async def plan(
        self,
        *,
        state: AgentFlowState,
        subagents: Mapping[str, SubagentConfig],
        max_selections: int,
    ) -> PlanOutput:
        selected_names = self._select_names(state.user_query, subagents)
        bounded_names = selected_names[: max(max_selections, 0)]
        selections = [
            PlanSubagentSelection(
                name=name,
                reason=f"Selected fake subagent '{name}'.",
            )
            for name in bounded_names
            if name in subagents
        ]
        return PlanOutput(
            goal=f"Answer user query: {state.user_query}",
            selections=selections,
            rationale="Deterministic fake planner selection.",
        )

    def _select_names(
        self,
        query: str,
        subagents: Mapping[str, SubagentConfig],
    ) -> list[str]:
        normalized_query = query.casefold()
        for rule in self._rules:
            if rule.query_contains.casefold() in normalized_query:
                return rule.select
        if self._selection_names is not None:
            return self._selection_names
        return list(subagents)


class LLMPlannerExecutor:
    def __init__(
        self,
        *,
        config: PlannerConfig,
        llm: AgentFlowLLMAdapter,
    ):
        self._config = config
        self._llm = llm

    async def plan(
        self,
        *,
        state: AgentFlowState,
        subagents: Mapping[str, SubagentConfig],
        max_selections: int,
    ) -> PlanOutput:
        decision = await self._llm.generate_structured(
            model_name=self._config.model,
            system_prompt=read_prompt_template(self._config.prompt_template),
            user_prompt=self._render_user_prompt(
                state=state,
                subagents=subagents,
                max_selections=max_selections,
            ),
            output_type=LLMPlannerDecision,
            metadata={
                "agent_flow_run_id": state.run_id,
                "agent_flow_stage": "planner",
            },
        )
        selections = [
            selection
            for selection in decision.selections[: max(max_selections, 0)]
            if selection.name in subagents
        ]
        return PlanOutput(
            goal=decision.goal,
            selections=selections,
            rationale=decision.rationale,
        )

    def _render_user_prompt(
        self,
        *,
        state: AgentFlowState,
        subagents: Mapping[str, SubagentConfig],
        max_selections: int,
    ) -> str:
        catalog = "\n".join(
            f"- {name}: {config.description}" for name, config in subagents.items()
        )
        return (
            f"User query:\n{state.user_query}\n\n"
            f"Maximum subagents to select: {max_selections}\n\n"
            f"Available subagents:\n{catalog or 'No subagents configured.'}"
        )
