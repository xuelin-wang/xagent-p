from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from xagent.agent_flow.config import SubagentConfig
from xagent.agent_flow.llm_adapter import AgentFlowLLMAdapter, read_prompt_template
from xagent.agent_flow.models import (
    AgentError,
    AgentFlowState,
    PlanSubagentSelection,
    SubagentResult,
)
from xagent.agent_flow.steps import RuntimeContext, StepResult


class FlowSubagent(Protocol):
    name: str
    description: str

    async def ainvoke(
        self,
        *,
        state: AgentFlowState,
        selection: PlanSubagentSelection,
    ) -> SubagentResult: ...


class SubagentStep:
    """RuntimeStep adapter for one selected subagent invocation."""

    step_type = "subagent"

    def __init__(
        self,
        *,
        subagent: FlowSubagent,
        selection: PlanSubagentSelection,
    ):
        self._subagent = subagent
        self._selection = selection

    async def run(
        self,
        state: AgentFlowState,
        context: RuntimeContext,
    ) -> StepResult:
        _ = context
        result = await self._subagent.ainvoke(
            state=state,
            selection=self._selection,
        )
        return StepResult(output_json=result.model_dump(mode="json"))


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


class LLMFlowSubagent:
    def __init__(
        self,
        *,
        config: SubagentConfig,
        llm: AgentFlowLLMAdapter,
    ):
        self.name = config.name
        self.description = config.description
        self._config = config
        self._llm = llm

    async def ainvoke(
        self,
        *,
        state: AgentFlowState,
        selection: PlanSubagentSelection,
    ) -> SubagentResult:
        content = await self._llm.generate_text(
            model_name=self._config.model,
            system_prompt=read_prompt_template(self._config.prompt_template),
            user_prompt=self._render_user_prompt(state=state, selection=selection),
            metadata={
                "agent_flow_run_id": state.run_id,
                "agent_flow_stage": "subagent",
                "agent_flow_subagent": self.name,
            },
        )
        return SubagentResult(
            name=self.name,
            status="completed",
            content=content,
        )

    def _render_user_prompt(
        self,
        *,
        state: AgentFlowState,
        selection: PlanSubagentSelection,
    ) -> str:
        return (
            f"User query:\n{state.user_query}\n\n"
            f"Iteration: {state.current_iteration}\n\n"
            f"Planner reason:\n{selection.reason or 'No reason provided.'}\n\n"
            f"Input hint:\n{selection.input_hint or 'No input hint provided.'}"
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
