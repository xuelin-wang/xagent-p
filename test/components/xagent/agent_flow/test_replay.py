import asyncio

from xagent.agent_flow.models import (
    AgentFlowState,
    FlowStage,
    PlanOutput,
    PlanSubagentSelection,
    RunStatus,
    SubagentResult,
    SummaryDecision,
    SummaryOutput,
    UserInputEvent,
    UserRequest,
)
from xagent.agent_flow.replay import (
    NONDETERMINISTIC_STEP_TYPES,
    RunAuditRecord,
    StepAuditEntry,
    build_audit_record,
    replay_from_steps,
)
from xagent.agent_persistence.memory import (
    InMemoryRunRepository,
    InMemoryStepRepository,
)
from xagent.agent_persistence.repositories import StepStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_completed_run(
    *,
    run_repository: InMemoryRunRepository,
    step_repository: InMemoryStepRepository,
) -> AgentFlowState:
    """Create a completed run with planner + subagent + summary steps."""
    state = AgentFlowState(
        run_id="run_1",
        user_query="diagnose no start",
        status=RunStatus.COMPLETED,
        current_iteration=0,
        final_response="manuals result",
    )
    state.get_or_create_current_iteration().plan = PlanOutput(
        goal="Answer user query",
        selections=[PlanSubagentSelection(name="manuals")],
    )
    state.get_or_create_current_iteration().subagent_results["manuals"] = (
        SubagentResult(
            name="manuals",
            status="completed",
            content="manuals result",
        )
    )
    state.get_or_create_current_iteration().summary = SummaryOutput(
        decision=SummaryDecision.FINAL,
        answer_draft="manuals result",
    )
    await run_repository.create_run(state)
    await run_repository.mark_completed(state.run_id, "manuals result")

    plan = state.iterations[0].plan
    assert plan is not None
    plan_step = await step_repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={"query": "diagnose no start"},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await step_repository.mark_step_running(plan_step.step_id)
    await step_repository.mark_step_succeeded(
        plan_step.step_id, plan.model_dump(mode="json")
    )

    subagent_step = await step_repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="subagent:manuals",
        step_type="subagent",
        input_json={"name": "manuals"},
        max_attempts=1,
        idempotency_key="run_1:0:subagent:manuals",
    )
    await step_repository.mark_step_running(subagent_step.step_id)
    await step_repository.mark_step_succeeded(
        subagent_step.step_id,
        SubagentResult(
            name="manuals", status="completed", content="manuals result"
        ).model_dump(mode="json"),
    )

    summary_step = await step_repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="summary",
        step_type="summary",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:summary",
    )
    await step_repository.mark_step_running(summary_step.step_id)
    await step_repository.mark_step_succeeded(
        summary_step.step_id,
        SummaryOutput(
            decision=SummaryDecision.FINAL, answer_draft="manuals result"
        ).model_dump(mode="json"),
    )

    return await run_repository.get_run_state("run_1")


# ---------------------------------------------------------------------------
# build_audit_record
# ---------------------------------------------------------------------------


def test_audit_record_reconstructs_completed_run() -> None:
    asyncio.run(_audit_record_reconstructs_completed_run())


async def _audit_record_reconstructs_completed_run() -> None:
    run_repository = InMemoryRunRepository()
    step_repository = InMemoryStepRepository()
    await _seed_completed_run(
        run_repository=run_repository, step_repository=step_repository
    )

    record = await build_audit_record(
        "run_1",
        run_repository=run_repository,
        step_repository=step_repository,
    )

    assert isinstance(record, RunAuditRecord)
    assert record.run_id == "run_1"
    assert record.status is RunStatus.COMPLETED
    assert record.user_query == "diagnose no start"
    assert record.final_response == "manuals result"
    assert record.current_iteration == 0
    assert len(record.steps) == 3
    step_names = {s.step_name for s in record.steps}
    assert step_names == {"planner", "subagent:manuals", "summary"}
    assert all(s.status is StepStatus.SUCCEEDED for s in record.steps)
    assert all(s.output_json is not None for s in record.steps)
    assert record.user_input_events == []


def test_audit_record_step_entries_carry_type_and_iteration() -> None:
    asyncio.run(_audit_record_step_entries_carry_type_and_iteration())


async def _audit_record_step_entries_carry_type_and_iteration() -> None:
    run_repository = InMemoryRunRepository()
    step_repository = InMemoryStepRepository()
    await _seed_completed_run(
        run_repository=run_repository, step_repository=step_repository
    )

    record = await build_audit_record(
        "run_1",
        run_repository=run_repository,
        step_repository=step_repository,
    )

    by_name = {s.step_name: s for s in record.steps}
    assert isinstance(by_name["planner"], StepAuditEntry)
    assert by_name["planner"].step_type == "planner"
    assert by_name["planner"].iteration == 0
    assert by_name["subagent:manuals"].step_type == "subagent"
    assert by_name["summary"].step_type == "summary"


def test_audit_record_includes_waiting_for_user_and_input_events() -> None:
    asyncio.run(_audit_record_includes_waiting_for_user_and_input_events())


async def _audit_record_includes_waiting_for_user_and_input_events() -> None:
    from datetime import UTC, datetime

    run_repository = InMemoryRunRepository()
    step_repository = InMemoryStepRepository()

    event = UserInputEvent(
        event_id="evt_1",
        run_id="run_2",
        request_id="req_1",
        content="It's a 2020 model.",
        occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    state = AgentFlowState(
        run_id="run_2",
        user_query="diagnose no start",
        status=RunStatus.WAITING_FOR_USER,
        current_stage=FlowStage.WAITING_FOR_USER,
        pending_user_request=UserRequest(request_id="req_1", prompt="What year?"),
        user_input_events=[event],
    )
    await run_repository.create_run(state)

    record = await build_audit_record(
        "run_2",
        run_repository=run_repository,
        step_repository=step_repository,
    )

    assert record.status is RunStatus.WAITING_FOR_USER
    assert len(record.user_input_events) == 1
    assert record.user_input_events[0].content == "It's a 2020 model."
    assert record.final_response is None


# ---------------------------------------------------------------------------
# replay_from_steps
# ---------------------------------------------------------------------------


def test_replay_from_steps_rebuilds_state_without_calling_executors() -> None:
    asyncio.run(_replay_from_steps_rebuilds_state_without_calling_executors())


async def _replay_from_steps_rebuilds_state_without_calling_executors() -> None:
    step_repository = InMemoryStepRepository()
    base = AgentFlowState(run_id="run_1", user_query="diagnose no start")

    plan = PlanOutput(
        goal="Answer query",
        selections=[PlanSubagentSelection(name="manuals")],
    )
    plan_step = await step_repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={"query": "diagnose no start"},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await step_repository.mark_step_running(plan_step.step_id)
    await step_repository.mark_step_succeeded(
        plan_step.step_id, plan.model_dump(mode="json")
    )

    subagent_result = SubagentResult(
        name="manuals", status="completed", content="manuals result"
    )
    subagent_step = await step_repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="subagent:manuals",
        step_type="subagent",
        input_json={"name": "manuals"},
        max_attempts=1,
        idempotency_key="run_1:0:subagent:manuals",
    )
    await step_repository.mark_step_running(subagent_step.step_id)
    await step_repository.mark_step_succeeded(
        subagent_step.step_id, subagent_result.model_dump(mode="json")
    )

    steps = await step_repository.get_steps_for_run_iteration("run_1", 0)
    # No executors involved — replay uses recorded outputs only.
    replayed = replay_from_steps(base, steps)

    assert replayed.iterations[0].plan == plan
    assert (
        replayed.iterations[0].subagent_results["manuals"].content == "manuals result"
    )


def test_replay_from_steps_skips_failed_steps() -> None:
    asyncio.run(_replay_from_steps_skips_failed_steps())


async def _replay_from_steps_skips_failed_steps() -> None:
    step_repository = InMemoryStepRepository()
    base = AgentFlowState(run_id="run_1", user_query="diagnose no start")

    step = await step_repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={"query": "diagnose no start"},
        max_attempts=1,
        idempotency_key="run_1:0:planner",
    )
    await step_repository.mark_step_running(step.step_id)
    await step_repository.mark_step_failed(step.step_id, {"error": "timeout"})

    steps = await step_repository.get_steps_for_run_iteration("run_1", 0)
    replayed = replay_from_steps(base, steps)

    # Failed step has no output so no plan is applied.
    assert replayed.iterations == []


# ---------------------------------------------------------------------------
# NONDETERMINISTIC_STEP_TYPES constant
# ---------------------------------------------------------------------------


def test_nondeterministic_step_types_covers_llm_and_tool_steps() -> None:
    assert "planner" in NONDETERMINISTIC_STEP_TYPES
    assert "subagent" in NONDETERMINISTIC_STEP_TYPES
    assert "summary" in NONDETERMINISTIC_STEP_TYPES
    assert "tool_call" in NONDETERMINISTIC_STEP_TYPES
