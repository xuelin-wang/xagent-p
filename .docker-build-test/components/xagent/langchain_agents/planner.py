from collections.abc import Mapping

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from xagent.agent_app.model import PlannerStep, SubagentSelection
from xagent.langchain_agents.subagents import Subagent


class PlannerDecision(BaseModel):
    agent_names: list[str] = Field(
        default_factory=list,
        description="Names of subagents that should be invoked for this request.",
    )
    rationale: str = Field(
        default="",
        description="Short explanation for why the selected subagents are useful.",
    )


class LangChainPlanner:
    def __init__(self, model, subagents: Mapping[str, Subagent]):
        self._subagents = dict(subagents)
        self._chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        (
                            "You are a planner for a supervisor agent. "
                            "Select the subagents that should help answer the user query. "
                            "Only return subagent names from the provided catalog."
                        ),
                    ),
                    (
                        "human",
                        "User query:\n{query}\n\nAvailable subagents:\n{subagent_catalog}",
                    ),
                ]
            )
            | model.with_structured_output(PlannerDecision)
        )

    async def aplan(self, query: str) -> PlannerStep:
        catalog = "\n".join(
            f"- {subagent.name}: {subagent.description}"
            for subagent in self._subagents.values()
        )
        decision = await self._chain.ainvoke(
            {"query": query, "subagent_catalog": catalog}
        )
        selections = [
            SubagentSelection(name=name, reason=decision.rationale)
            for name in decision.agent_names
            if name in self._subagents
        ]
        if not selections and self._subagents:
            fallback_name = next(iter(self._subagents))
            selections = [
                SubagentSelection(
                    name=fallback_name,
                    reason=(
                        "Planner returned no known subagents, so the first available "
                        "subagent was selected as a fallback."
                    ),
                )
            ]
        return PlannerStep(selections=selections, notes=decision.rationale)
