import asyncio

from xagent.agent_flow.config import SubagentConfig
from xagent.agent_flow.models import (
    AgentFlowIteration,
    AgentFlowState,
    PlanSubagentSelection,
    SubagentResult,
    SummaryDecision,
)
from xagent.agent_flow.planner import FakePlannerExecutor, FakePlannerRule
from xagent.agent_flow.subagents import FakeFlowSubagent, fake_subagents_from_config
from xagent.agent_flow.summary import FakeSummaryExecutor


def _subagent_configs() -> dict[str, SubagentConfig]:
    return {
        "manuals": SubagentConfig(
            name="manuals",
            description="Search service manuals.",
            prompt_template="prompts/agent_flow/subagents/manuals.md",
        ),
        "history": SubagentConfig(
            name="history",
            description="Search repair history.",
            prompt_template="prompts/agent_flow/subagents/history.md",
        ),
    }


def test_fake_planner_selects_known_subagents_with_max_bound() -> None:
    asyncio.run(_fake_planner_selects_known_subagents_with_max_bound())


async def _fake_planner_selects_known_subagents_with_max_bound() -> None:
    planner = FakePlannerExecutor(selection_names=["missing", "manuals", "history"])
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")

    plan = await planner.plan(
        state=state,
        subagents=_subagent_configs(),
        max_selections=2,
    )

    assert plan.goal == "Answer user query: diagnose no start"
    assert [selection.name for selection in plan.selections] == ["manuals"]
    assert plan.rationale == "Deterministic fake planner selection."


def test_fake_planner_rules_override_default_selection() -> None:
    asyncio.run(_fake_planner_rules_override_default_selection())


async def _fake_planner_rules_override_default_selection() -> None:
    planner = FakePlannerExecutor(
        selection_names=["manuals"],
        rules=[
            FakePlannerRule(query_contains="history", select=["history"]),
        ],
    )
    state = AgentFlowState(run_id="run_1", user_query="compare repair history")

    plan = await planner.plan(
        state=state,
        subagents=_subagent_configs(),
        max_selections=5,
    )

    assert [selection.name for selection in plan.selections] == ["history"]


def test_fake_subagent_returns_deterministic_completed_result() -> None:
    asyncio.run(_fake_subagent_returns_deterministic_completed_result())


async def _fake_subagent_returns_deterministic_completed_result() -> None:
    subagent = FakeFlowSubagent(name="manuals")
    state = AgentFlowState(
        run_id="run_1",
        user_query="diagnose no start",
        current_iteration=2,
    )

    result = await subagent.ainvoke(
        state=state,
        selection=PlanSubagentSelection(name="manuals"),
    )

    assert result.status == "completed"
    assert (
        result.content == "manuals handled query 'diagnose no start' for iteration 2."
    )


def test_fake_subagent_can_return_structured_error_result() -> None:
    asyncio.run(_fake_subagent_can_return_structured_error_result())


async def _fake_subagent_can_return_structured_error_result() -> None:
    subagent = FakeFlowSubagent(
        name="manuals",
        content="manual lookup failed",
        status="error",
    )
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")

    result = await subagent.ainvoke(
        state=state,
        selection=PlanSubagentSelection(name="manuals"),
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.step_name == "subagent:manuals"
    assert result.error.message == "manual lookup failed"


def test_fake_subagents_from_config_preserves_configured_names() -> None:
    subagents = fake_subagents_from_config(_subagent_configs())

    assert sorted(subagents) == ["history", "manuals"]
    assert subagents["manuals"].name == "manuals"
    assert subagents["history"].description == "Search repair history."


def test_fake_summary_final_combines_completed_results() -> None:
    asyncio.run(_fake_summary_final_combines_completed_results())


async def _fake_summary_final_combines_completed_results() -> None:
    summary = FakeSummaryExecutor()
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    iteration = AgentFlowIteration(
        iteration=0,
        subagent_results={
            "manuals": SubagentResult(
                name="manuals",
                status="completed",
                content="Inspect starter relay.",
            ),
            "history": SubagentResult(
                name="history",
                status="error",
                content="History unavailable.",
            ),
        },
    )

    result = await summary.summarize(state=state, iteration=iteration)

    assert result.decision is SummaryDecision.FINAL
    assert result.answer_draft == "Inspect starter relay."


def test_fake_summary_supports_replan_and_fail_decisions() -> None:
    asyncio.run(_fake_summary_supports_replan_and_fail_decisions())


async def _fake_summary_supports_replan_and_fail_decisions() -> None:
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    iteration = AgentFlowIteration(iteration=0)

    replan = await FakeSummaryExecutor(decision=SummaryDecision.REPLAN).summarize(
        state=state,
        iteration=iteration,
    )
    fail = await FakeSummaryExecutor(decision=SummaryDecision.FAIL).summarize(
        state=state,
        iteration=iteration,
    )

    assert replan.decision is SummaryDecision.REPLAN
    assert replan.suggested_replan == {"reason": "fake_replan"}
    assert fail.decision is SummaryDecision.FAIL
