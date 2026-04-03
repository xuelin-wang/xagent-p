import asyncio

from xagent.agent_app.model import PlannerStep, SubagentReply, SubagentSelection
from xagent.langchain_agents.app import LangChainMultiAgentApp


class StubPlanner:
    async def aplan(self, query: str) -> PlannerStep:
        return PlannerStep(
            selections=[
                SubagentSelection(
                    name="rag_researcher",
                    reason=f"Needed for query: {query}",
                )
            ],
            notes="Use the dummy subagent.",
        )


class StubMerger:
    async def amerge(
        self,
        query: str,
        plan: PlannerStep,
        replies: list[SubagentReply],
    ) -> str:
        return f"{query} => {replies[0].status}: {replies[0].content}"


class FastSubagent:
    name = "rag_researcher"
    description = "Fast stub."

    async def ainvoke(self, query: str) -> str:
        return f"handled {query}"


class SlowSubagent:
    name = "rag_researcher"
    description = "Slow stub."

    async def ainvoke(self, query: str) -> str:
        await asyncio.sleep(0.2)
        return f"handled {query}"


async def _test_app_runs_selected_subagent_and_merges_reply():
    app = LangChainMultiAgentApp(
        planner=StubPlanner(),
        merger=StubMerger(),
        subagents={"rag_researcher": FastSubagent()},
        max_wait_seconds=0.1,
    )

    result = await app.arun("summarize this")

    assert result.plan.selections[0].name == "rag_researcher"
    assert result.subagent_replies[0].status == "completed"
    assert "handled summarize this" in result.final_reply


def test_app_runs_selected_subagent_and_merges_reply():
    asyncio.run(_test_app_runs_selected_subagent_and_merges_reply())


async def _test_app_marks_subagent_timeout_when_wait_budget_is_exceeded():
    app = LangChainMultiAgentApp(
        planner=StubPlanner(),
        merger=StubMerger(),
        subagents={"rag_researcher": SlowSubagent()},
        max_wait_seconds=0.05,
    )

    result = await app.arun("slow query")

    assert result.subagent_replies[0].status == "timeout"
    assert "wait budget" in result.subagent_replies[0].content
    assert "timeout" in result.final_reply


def test_app_marks_subagent_timeout_when_wait_budget_is_exceeded():
    asyncio.run(_test_app_marks_subagent_timeout_when_wait_budget_is_exceeded())
