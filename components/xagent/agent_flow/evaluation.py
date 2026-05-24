"""Evaluation entrypoints for scoring recorded runs without re-execution.

Evaluators consume the run state, step audit record, and iteration history
to produce deterministic, local metrics. No LLM or tool calls are made.

Design link: Section 14, evaluation as a natural consequence.
Non-goal: live re-execution, LLM-graded scoring, external API calls.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from xagent.agent_flow.models import (
    AgentFlowState,
    RunStatus,
)
from xagent.agent_flow.replay import build_audit_record
from xagent.agent_persistence.repositories import (
    RunRepository,
    StepRepository,
)


class EvaluationScores(BaseModel):
    """Deterministic structural metrics derived from recorded run data."""

    # Run-level
    completed: bool
    iteration_count: int
    final_response_length: int | None = None
    had_user_interaction: bool = False

    # Step-level
    total_steps: int = 0
    succeeded_steps: int = 0
    failed_steps: int = 0
    tool_call_count: int = 0

    # Iteration-level
    summary_decisions: list[str] = Field(default_factory=list)
    subagent_names_used: list[str] = Field(default_factory=list)
    subagents_with_errors: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """Evaluation output for a recorded run.

    Design link: Section 14, evaluation as a natural consequence.
    """

    run_id: str
    status: RunStatus
    scores: EvaluationScores
    failure_modes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def evaluate_state(state: AgentFlowState) -> EvaluationResult:
    """Evaluate a completed or terminal AgentFlowState.

    Pure function — no I/O. Produces structural metrics from the recorded
    state. Suitable for batch offline scoring of recorded runs.
    Design link: Section 14.
    """
    scores = EvaluationScores(
        completed=state.status is RunStatus.COMPLETED,
        iteration_count=state.current_iteration + 1,
        final_response_length=(
            len(state.final_response) if state.final_response is not None else None
        ),
        had_user_interaction=len(state.user_input_events) > 0,
    )
    failure_modes: list[str] = []

    for iteration in state.iterations:
        if iteration.summary is not None:
            scores.summary_decisions.append(iteration.summary.decision)
        for name, result in iteration.subagent_results.items():
            if name not in scores.subagent_names_used:
                scores.subagent_names_used.append(name)
            if (
                result.error is not None or result.status == "error"
            ) and name not in scores.subagents_with_errors:
                scores.subagents_with_errors.append(name)
        for result in iteration.tool_results.values():
            scores.tool_call_count += 1
            if result.status in {"failed", "timed_out"}:
                failure_modes.append(f"tool_call:{result.tool_name}:{result.status}")

    for error in state.errors:
        failure_modes.append(f"error:{error.stage}:{error.message[:80]}")

    if state.status is RunStatus.FAILED and not failure_modes:
        failure_modes.append("run_failed:no_detail")

    return EvaluationResult(
        run_id=state.run_id,
        status=state.status,
        scores=scores,
        failure_modes=failure_modes,
    )


async def evaluate_run(
    run_id: str,
    *,
    run_repository: RunRepository,
    step_repository: StepRepository,
) -> EvaluationResult:
    """Evaluate a run by loading its state and step audit record.

    Reads from repositories; no re-execution is performed.
    Design link: Section 14.
    """
    state = await run_repository.get_run_state(run_id)
    audit = await build_audit_record(
        run_id,
        run_repository=run_repository,
        step_repository=step_repository,
    )
    result = evaluate_state(state)
    result.scores.total_steps = len(audit.steps)
    result.scores.succeeded_steps = sum(
        1 for s in audit.steps if s.status.value == "succeeded"
    )
    result.scores.failed_steps = sum(
        1 for s in audit.steps if s.status.value == "failed"
    )
    return result
