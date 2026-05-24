"""Iteration workflow tree for the agent flow runtime.

Purpose: express the planner-subagents-summary loop as a composite step tree so
the executor stays generic and the workflow structure is configuration, not
hard-coded runtime logic.
Design link: Section 3.1, step hierarchy; Section 17, repo-aligned structure.
Non-goal: should not contain persistence, checkpoint, or state-machine logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from xagent.agent_flow.config import AgentFlowAppConfig, SubagentConfig
from xagent.agent_flow.models import AgentFlowIteration, AgentFlowState
from xagent.agent_flow.planner import PlannerExecutor, PlannerStep
from xagent.agent_flow.step_runner import ChildStep
from xagent.agent_flow.steps import (
    ParallelStepGroup,
    RetryPolicy,
    RuntimeContext,
    SequenceStepGroup,
    StepExecutionPolicy,
)
from xagent.agent_flow.subagents import FlowSubagent, SubagentStep
from xagent.agent_flow.summary import SummaryExecutor, SummaryStep


def build_iteration_step(
    *,
    config: AgentFlowAppConfig,
    planner: PlannerExecutor,
    subagents: Mapping[str, FlowSubagent],
    summary: SummaryExecutor,
    state: AgentFlowState,
) -> SequenceStepGroup:
    """Build the workflow tree for one agent iteration.

    Returns a SequenceStepGroup containing planner → subagents → summary.
    The subagents slot is a lazy callable so children are built after the planner
    runs and populates iteration.plan.
    Design link: Section 3.1.
    Non-goal: does not implement the outer replanning loop (that stays in runtime.py).
    """
    planner_context = RuntimeContext(
        execution_policy=StepExecutionPolicy(
            retry=RetryPolicy(max_attempts=config.planner.max_attempts),
        )
    )
    summary_context = RuntimeContext(
        execution_policy=StepExecutionPolicy(
            retry=RetryPolicy(max_attempts=config.summary.max_attempts),
        )
    )

    planner_child = ChildStep(
        step=PlannerStep(
            executor=planner,
            subagents=config.subagents,
            max_selections=config.workflow.max_subagents_per_iteration,
        ),
        step_name="planner",
        input_json={
            "query": state.user_query,
            "subagents": list(config.subagents),
        },
        context=planner_context,
    )

    def build_subagents_slot(current_state: AgentFlowState) -> ChildStep | None:
        current_iteration = current_state.get_or_create_current_iteration()
        if current_iteration.plan is None:
            return None

        children = _build_subagent_children(
            current_state,
            current_iteration,
            config.subagents,
            subagents,
            config,
        )
        if not children:
            return None

        if config.workflow.subagent_execution_mode == "parallel":
            group: SequenceStepGroup | ParallelStepGroup = ParallelStepGroup(
                step_type="parallel:subagents",
                step_name="subagents",
                children=children,
            )
        else:
            group = SequenceStepGroup(
                step_type="sequence:subagents",
                step_name="subagents",
                children=children,
            )
        return ChildStep(step=group, step_name="subagents", input_json={})

    summary_child = ChildStep(
        step=SummaryStep(executor=summary),
        step_name="summary",
        input_json=_summary_input_json,
        context=summary_context,
    )

    return SequenceStepGroup(
        step_type="sequence:iteration",
        step_name="iteration",
        children=[planner_child, build_subagents_slot, summary_child],
    )


def _build_subagent_children(
    state: AgentFlowState,
    iteration: AgentFlowIteration,
    subagent_configs: Mapping[str, SubagentConfig],
    subagents: Mapping[str, FlowSubagent],
    config: AgentFlowAppConfig,
) -> list[ChildStep]:
    children: list[ChildStep] = []
    if iteration.plan is None:
        return children
    for selection in iteration.plan.selections:
        if selection.name not in subagents:
            continue
        subagent_context = RuntimeContext(
            execution_policy=StepExecutionPolicy(
                retry=RetryPolicy(
                    max_attempts=subagent_configs[selection.name].max_attempts,
                ),
            )
        )
        children.append(
            ChildStep(
                step=SubagentStep(
                    subagent=subagents[selection.name],
                    selection=selection,
                ),
                step_name=f"subagent:{selection.name}",
                input_json=selection.model_dump(mode="json"),
                context=subagent_context,
            )
        )
    return children


def _summary_input_json(state: AgentFlowState) -> dict[str, Any]:
    iteration = state.get_or_create_current_iteration()
    return {
        "query": state.user_query,
        "subagent_results": {
            name: result.model_dump(mode="json")
            for name, result in iteration.subagent_results.items()
        },
    }
