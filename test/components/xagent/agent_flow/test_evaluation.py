import asyncio

from xagent.agent_flow.evaluation import (
    EvaluationResult,
    EvaluationScores,
    evaluate_run,
    evaluate_state,
)
from xagent.agent_flow.models import (
    AgentError,
    AgentFlowIteration,
    AgentFlowState,
    FlowStage,
    PlanOutput,
    PlanSubagentSelection,
    RunStatus,
    SubagentResult,
    SummaryDecision,
    SummaryOutput,
    ToolResult,
    UserInputEvent,
    UserRequest,
)
from xagent.agent_persistence.memory import (
    InMemoryRunRepository,
    InMemoryStepRepository,
)


def _completed_state() -> AgentFlowState:
    state = AgentFlowState(
        run_id="run_1",
        user_query="diagnose no start",
        status=RunStatus.COMPLETED,
        final_response="manuals result",
        current_iteration=0,
    )
    iteration = state.get_or_create_current_iteration()
    iteration.plan = PlanOutput(
        goal="Answer query",
        selections=[PlanSubagentSelection(name="manuals")],
    )
    iteration.subagent_results["manuals"] = SubagentResult(
        name="manuals",
        status="completed",
        content="manuals result",
    )
    iteration.summary = SummaryOutput(
        decision=SummaryDecision.FINAL,
        answer_draft="manuals result",
    )
    return state


def _failed_state() -> AgentFlowState:
    state = AgentFlowState(
        run_id="run_2",
        user_query="diagnose no start",
        status=RunStatus.FAILED,
        current_iteration=0,
    )
    state.errors.append(
        AgentError(
            stage=FlowStage.PLANNING,
            message="LLM timeout",
            error_type="TimeoutError",
        )
    )
    return state


# ---------------------------------------------------------------------------
# evaluate_state
# ---------------------------------------------------------------------------


def test_evaluate_state_completed_run() -> None:
    state = _completed_state()

    result = evaluate_state(state)

    assert isinstance(result, EvaluationResult)
    assert result.run_id == "run_1"
    assert result.status is RunStatus.COMPLETED
    assert isinstance(result.scores, EvaluationScores)
    assert result.scores.completed is True
    assert result.scores.iteration_count == 1
    assert result.scores.final_response_length == len("manuals result")
    assert result.scores.had_user_interaction is False
    assert result.scores.subagent_names_used == ["manuals"]
    assert result.scores.subagents_with_errors == []
    assert result.scores.summary_decisions == [SummaryDecision.FINAL]
    assert result.failure_modes == []


def test_evaluate_state_failed_run_records_failure_mode() -> None:
    state = _failed_state()

    result = evaluate_state(state)

    assert result.scores.completed is False
    assert len(result.failure_modes) == 1
    assert "error:planning:LLM timeout" in result.failure_modes[0]


def test_evaluate_state_waiting_for_user_run() -> None:
    from datetime import UTC, datetime

    state = AgentFlowState(
        run_id="run_3",
        user_query="diagnose no start",
        status=RunStatus.WAITING_FOR_USER,
        current_stage=FlowStage.WAITING_FOR_USER,
        pending_user_request=UserRequest(request_id="req_1", prompt="What year?"),
        user_input_events=[
            UserInputEvent(
                event_id="evt_1",
                run_id="run_3",
                request_id="req_1",
                content="It's a 2020 model.",
                occurred_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        ],
    )

    result = evaluate_state(state)

    assert result.scores.completed is False
    assert result.scores.had_user_interaction is True
    assert result.scores.final_response_length is None
    assert result.failure_modes == []


def test_evaluate_state_run_with_subagent_error() -> None:
    state = AgentFlowState(
        run_id="run_4",
        user_query="diagnose no start",
        status=RunStatus.COMPLETED,
        final_response="fallback answer",
        current_iteration=0,
    )
    iteration = state.get_or_create_current_iteration()
    iteration.subagent_results["history"] = SubagentResult(
        name="history",
        status="error",
        content="connection failed",
        error=AgentError(stage=FlowStage.SUBAGENTS, message="timeout"),
    )
    iteration.summary = SummaryOutput(
        decision=SummaryDecision.FINAL,
        answer_draft="fallback answer",
    )

    result = evaluate_state(state)

    assert result.scores.subagent_names_used == ["history"]
    assert result.scores.subagents_with_errors == ["history"]


def test_evaluate_state_multiple_iterations_and_replan() -> None:
    state = AgentFlowState(
        run_id="run_5",
        user_query="diagnose no start",
        status=RunStatus.COMPLETED,
        final_response="final answer",
        current_iteration=1,
    )
    iter0 = AgentFlowIteration(iteration=0)
    iter0.summary = SummaryOutput(
        decision=SummaryDecision.REPLAN, rationale="need more"
    )
    iter0.subagent_results["manuals"] = SubagentResult(
        name="manuals", status="completed", content="partial"
    )
    iter1 = AgentFlowIteration(iteration=1)
    iter1.summary = SummaryOutput(
        decision=SummaryDecision.FINAL, answer_draft="final answer"
    )
    iter1.subagent_results["history"] = SubagentResult(
        name="history", status="completed", content="evidence"
    )
    state.iterations = [iter0, iter1]

    result = evaluate_state(state)

    assert result.scores.iteration_count == 2
    assert result.scores.summary_decisions == [
        SummaryDecision.REPLAN,
        SummaryDecision.FINAL,
    ]
    assert sorted(result.scores.subagent_names_used) == ["history", "manuals"]


def test_evaluate_state_tool_call_failures_recorded() -> None:
    state = AgentFlowState(
        run_id="run_6",
        user_query="diagnose no start",
        status=RunStatus.COMPLETED,
        final_response="answer despite failure",
        current_iteration=0,
    )
    iteration = state.get_or_create_current_iteration()
    iteration.tool_results["call_1"] = ToolResult(
        tool_call_id="call_1",
        tool_name="search",
        status="failed",
        retryable=False,
        attempt_count=1,
    )
    iteration.summary = SummaryOutput(
        decision=SummaryDecision.FINAL,
        answer_draft="answer despite failure",
    )

    result = evaluate_state(state)

    assert result.scores.tool_call_count == 1
    assert any("tool_call:search:failed" in f for f in result.failure_modes)


# ---------------------------------------------------------------------------
# evaluate_run
# ---------------------------------------------------------------------------


def test_evaluate_run_counts_steps_from_repository() -> None:
    asyncio.run(_evaluate_run_counts_steps_from_repository())


async def _evaluate_run_counts_steps_from_repository() -> None:
    run_repository = InMemoryRunRepository()
    step_repository = InMemoryStepRepository()

    state = _completed_state()
    await run_repository.create_run(state)
    await run_repository.mark_completed(state.run_id, "manuals result")

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
        plan_step.step_id,
        PlanOutput(
            goal="Answer query",
            selections=[PlanSubagentSelection(name="manuals")],
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
    await step_repository.mark_step_failed(summary_step.step_id, {"error": "oops"})

    result = await evaluate_run(
        "run_1",
        run_repository=run_repository,
        step_repository=step_repository,
    )

    assert result.run_id == "run_1"
    assert result.scores.total_steps == 2
    assert result.scores.succeeded_steps == 1
    assert result.scores.failed_steps == 1
