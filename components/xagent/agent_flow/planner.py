from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel

from xagent.agent_flow.config import SubagentConfig
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
