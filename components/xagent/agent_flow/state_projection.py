"""State projection: derive AgentFlowState from the ordered step event ledger.

Purpose: replace in-place state mutation with a pure fold over step_succeeded
events, unifying normal execution and resume under the same derivation logic.
Design link: Section 6, serializable state; Section 6.1, state as derived projection.
Non-goal: no persistence, retry, or step orchestration logic.
"""

from __future__ import annotations

from typing import Any

from xagent.agent_flow.models import (
    AgentFlowState,
    PlanOutput,
    StepStatus,
    SubagentResult,
    SummaryOutput,
)
from xagent.agent_persistence.repositories import StepRecord


def _apply(
    state: AgentFlowState, step_name: str, output_json: dict[str, Any]
) -> AgentFlowState:
    """Derive next state by applying a single step_succeeded output.

    Returns a fresh deep copy — the input state is never mutated.
    Maps planner/subagent/summary step names to their iteration fields.
    Design link: Section 6.1.
    """
    state = state.model_copy(deep=True)
    iteration = state.get_or_create_current_iteration()

    if step_name == "planner":
        iteration.plan = PlanOutput.model_validate(output_json)
    elif step_name.startswith("subagent:"):
        result = SubagentResult.model_validate(output_json)
        iteration.subagent_results[result.name] = result
        if result.error is not None and result.error not in iteration.errors:
            iteration.errors.append(result.error)
    elif step_name == "summary":
        iteration.summary = SummaryOutput.model_validate(output_json)

    return state


def derive_state(base: AgentFlowState, steps: list[StepRecord]) -> AgentFlowState:
    """Fold step_succeeded events into base to reconstruct current state.

    Pure function — no I/O, no side effects. Only SUCCEEDED steps with
    output_json are applied; all other steps are skipped.
    Design link: Section 6.1.
    """
    state = base
    for step in steps:
        if step.status is StepStatus.SUCCEEDED and step.output_json is not None:
            state = _apply(state, step.step_name, step.output_json)
    return state
