from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from xagent.agent_flow.config import SubagentConfig
from xagent.agent_flow.models import (
    AgentError,
    AgentFlowState,
    PlanSubagentSelection,
    SubagentResult,
)


class FlowSubagent(Protocol):
    name: str
    description: str

    async def ainvoke(
        self,
        *,
        state: AgentFlowState,
        selection: PlanSubagentSelection,
    ) -> SubagentResult: ...


class FakeFlowSubagent:
    def __init__(
        self,
        *,
        name: str,
        description: str = "Deterministic fake subagent.",
        content: str | None = None,
        status: str = "completed",
    ):
        self.name = name
        self.description = description
        self._content = content
        self._status = status

    async def ainvoke(
        self,
        *,
        state: AgentFlowState,
        selection: PlanSubagentSelection,
    ) -> SubagentResult:
        content = self._content or (
            f"{self.name} handled query '{state.user_query}'"
            f" for iteration {state.current_iteration}."
        )
        if self._status == "completed":
            return SubagentResult(
                name=self.name,
                status="completed",
                content=content,
            )
        return SubagentResult(
            name=self.name,
            status="error",
            content=content,
            error=AgentError(
                stage="subagents",
                step_name=f"subagent:{selection.name}",
                message=content,
                retryable=False,
            ),
        )


def fake_subagents_from_config(
    subagent_configs: Mapping[str, SubagentConfig],
) -> dict[str, FakeFlowSubagent]:
    return {
        name: FakeFlowSubagent(
            name=config.name,
            description=config.description,
        )
        for name, config in subagent_configs.items()
    }
