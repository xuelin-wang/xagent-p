import asyncio
from pathlib import Path

from test.components.xagent.agent_flow.test_llm_adapter import FakeLLMProvider

from xagent.agent_flow.config import (
    AgentModelConfig,
    PlannerConfig,
    SubagentConfig,
    SummaryConfig,
)
from xagent.agent_flow.llm_adapter import AgentFlowLLMAdapter
from xagent.agent_flow.models import (
    AgentFlowIteration,
    AgentFlowState,
    SubagentResult,
    SummaryDecision,
)
from xagent.agent_flow.planner import LLMPlannerExecutor
from xagent.agent_flow.summary import LLMSummaryExecutor


def test_llm_planner_executor_filters_unknown_subagents(tmp_path: Path) -> None:
    asyncio.run(_llm_planner_executor_filters_unknown_subagents(tmp_path))


async def _llm_planner_executor_filters_unknown_subagents(tmp_path: Path) -> None:
    prompt = tmp_path / "planner.md"
    prompt.write_text("planner system", encoding="utf-8")
    provider = FakeLLMProvider()
    executor = LLMPlannerExecutor(
        config=PlannerConfig(prompt_template=str(prompt), model="reasoning"),
        llm=AgentFlowLLMAdapter(
            provider=provider,
            models={"reasoning": AgentModelConfig(model="fake-reasoning")},
        ),
    )

    plan = await executor.plan(
        state=AgentFlowState(run_id="run_1", user_query="diagnose no start"),
        subagents={
            "manuals": SubagentConfig(
                name="manuals",
                description="Search service manuals.",
                prompt_template="manuals.md",
            )
        },
        max_selections=5,
    )

    assert plan.goal == "inspect manuals"
    assert [selection.name for selection in plan.selections] == ["manuals"]
    request, _ = provider.structured_requests[0]
    assert request.messages[0].content == "planner system"
    assert "Available subagents" in str(request.messages[1].content)


def test_llm_summary_executor_returns_provider_structured_output(
    tmp_path: Path,
) -> None:
    asyncio.run(_llm_summary_executor_returns_provider_structured_output(tmp_path))


async def _llm_summary_executor_returns_provider_structured_output(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "summary.md"
    prompt.write_text("summary system", encoding="utf-8")
    provider = FakeLLMProvider()
    executor = LLMSummaryExecutor(
        config=SummaryConfig(prompt_template=str(prompt), model="reasoning"),
        llm=AgentFlowLLMAdapter(
            provider=provider,
            models={"reasoning": AgentModelConfig(model="fake-reasoning")},
        ),
    )

    summary = await executor.summarize(
        state=AgentFlowState(run_id="run_1", user_query="diagnose no start"),
        iteration=AgentFlowIteration(
            iteration=0,
            subagent_results={
                "manuals": SubagentResult(
                    name="manuals",
                    status="completed",
                    content="manual result",
                )
            },
        ),
    )

    assert summary.decision is SummaryDecision.FINAL
    assert summary.answer_draft == "summary answer"
    request, _ = provider.structured_requests[0]
    assert request.messages[0].content == "summary system"
    assert "manual result" in str(request.messages[1].content)
