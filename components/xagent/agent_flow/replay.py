"""Replay helpers: audit playback and state reconstruction without re-execution.

Audit playback rebuilds a structured record of a completed or waiting run
from stored step records and run state — no executors are invoked.

State replay folds recorded step outputs into a state projection via
derive_state. Nondeterministic steps (planner, subagent, summary, tool_call)
are represented using their recorded outputs; they are never re-executed.

Design link: Section 12, replay model.
Non-goal: re-execution of LLMs or tools (creates a new run), live I/O beyond
repository reads, mutation of stored records.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from xagent.agent_flow.models import (
    AgentFlowState,
    ConversationMessageEvent,
    RunStatus,
    StepStatus,
    UserInputEvent,
)
from xagent.agent_flow.state_projection import derive_state
from xagent.agent_persistence.repositories import (
    RunRepository,
    StepRecord,
    StepRepository,
)

# Step types that rely on LLMs or external tools and must not be re-executed
# during replay. Their recorded outputs are always used instead.
NONDETERMINISTIC_STEP_TYPES: frozenset[str] = frozenset(
    {"planner", "subagent", "summary", "tool_call"}
)


class StepAuditEntry(BaseModel):
    """Snapshot of one recorded step for audit purposes."""

    step_id: str
    step_name: str
    step_type: str
    iteration: int
    status: StepStatus
    attempt_count: int
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None


class RunAuditRecord(BaseModel):
    """Reconstructed execution history for a run, built without re-execution.

    Design link: Section 12, audit playback.
    """

    run_id: str
    status: RunStatus
    user_query: str
    final_response: str | None = None
    current_iteration: int
    steps: list[StepAuditEntry] = Field(default_factory=list)
    user_input_events: list[UserInputEvent] = Field(default_factory=list)
    conversation_messages: list[ConversationMessageEvent] = Field(default_factory=list)


async def build_audit_record(
    run_id: str,
    *,
    run_repository: RunRepository,
    step_repository: StepRepository,
) -> RunAuditRecord:
    """Build a RunAuditRecord from stored state and step records.

    Reads run state and step records for all iterations without executing
    any step logic. Safe to call on completed, failed, or waiting runs.
    Design link: Section 12, audit playback.
    """
    state = await run_repository.get_run_state(run_id)
    all_steps: list[StepRecord] = []
    for iteration in range(state.current_iteration + 1):
        iteration_steps = await step_repository.get_steps_for_run_iteration(
            run_id, iteration
        )
        all_steps.extend(iteration_steps)
    return RunAuditRecord(
        run_id=run_id,
        status=state.status,
        user_query=state.user_query,
        final_response=state.final_response,
        current_iteration=state.current_iteration,
        steps=[
            StepAuditEntry(
                step_id=step.step_id,
                step_name=step.step_name,
                step_type=step.step_type,
                iteration=step.iteration,
                status=step.status,
                attempt_count=step.attempt_count,
                input_json=step.input_json,
                output_json=step.output_json,
                error_json=step.error_json,
            )
            for step in all_steps
        ],
        user_input_events=state.user_input_events,
        conversation_messages=state.conversation_messages,
    )


def replay_from_steps(
    base: AgentFlowState,
    steps: list[StepRecord],
) -> AgentFlowState:
    """Reconstruct AgentFlowState from recorded step outputs without re-executing.

    All step types use their recorded outputs — nondeterministic steps
    (planner, subagent, summary, tool_call) are never re-run. The result
    is identical to the state produced during normal execution.
    Design link: Section 12, deterministic replay.
    """
    return derive_state(base, steps)
