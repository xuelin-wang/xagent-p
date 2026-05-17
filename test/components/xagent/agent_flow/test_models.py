from xagent.agent_flow.models import (
    AgentFlowIteration,
    AgentFlowState,
    PlanOutput,
    SummaryDecision,
    SummaryOutput,
)


def test_agent_flow_state_preserves_distinct_iterations() -> None:
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")

    first = state.get_or_create_current_iteration()
    first.plan = PlanOutput(goal="inspect history")
    first.summary = SummaryOutput(
        decision=SummaryDecision.REPLAN,
        missing_information=["manual procedure"],
    )

    state.current_iteration = 1
    second = state.get_or_create_current_iteration()
    second.plan = PlanOutput(goal="inspect manuals")
    second.summary = SummaryOutput(
        decision=SummaryDecision.FINAL,
        answer_draft="final answer",
    )

    assert state.iterations == [
        AgentFlowIteration(
            iteration=0,
            plan=PlanOutput(goal="inspect history"),
            summary=SummaryOutput(
                decision=SummaryDecision.REPLAN,
                missing_information=["manual procedure"],
            ),
        ),
        AgentFlowIteration(
            iteration=1,
            plan=PlanOutput(goal="inspect manuals"),
            summary=SummaryOutput(
                decision=SummaryDecision.FINAL,
                answer_draft="final answer",
            ),
        ),
    ]


def test_should_stop_replanning_uses_current_iteration_guard() -> None:
    state = AgentFlowState(
        run_id="run_1",
        user_query="diagnose no start",
        current_iteration=3,
    )

    assert state.should_stop_replanning(max_iterations=3) is True
    assert state.should_stop_replanning(max_iterations=4) is False
