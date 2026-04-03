import asyncio
import time
from collections.abc import Mapping

from xagent.agent_app.model import AgentRunResult, PlannerStep, SubagentReply
from xagent.langchain_agents.subagents import Subagent


class LangChainMultiAgentApp:
    def __init__(
        self,
        planner,
        merger,
        subagents: Mapping[str, Subagent],
        max_wait_seconds: float = 10.0,
    ):
        self._planner = planner
        self._merger = merger
        self._subagents = dict(subagents)
        self._max_wait_seconds = max_wait_seconds

    async def arun(self, query: str) -> AgentRunResult:
        plan = await self._planner.aplan(query)
        replies = await self._run_subagents(query, plan)
        final_reply = await self._merger.amerge(query, plan, replies)
        return AgentRunResult(
            query=query,
            plan=plan,
            subagent_replies=replies,
            final_reply=final_reply,
        )

    async def _run_subagents(
        self,
        query: str,
        plan: PlannerStep,
    ) -> list[SubagentReply]:
        if not plan.selections:
            return []

        started_at = {}
        tasks = {}
        for selection in plan.selections:
            subagent = self._subagents.get(selection.name)
            if subagent is None:
                continue
            started_at[selection.name] = time.perf_counter()
            tasks[selection.name] = asyncio.create_task(subagent.ainvoke(query))

        if not tasks:
            return []

        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=self._max_wait_seconds,
        )
        done_lookup = {task: name for name, task in tasks.items()}
        replies_by_name = {}

        for task in done:
            name = done_lookup[task]
            duration = time.perf_counter() - started_at[name]
            try:
                content = task.result()
            except Exception as exc:  # pragma: no cover - defensive path
                replies_by_name[name] = SubagentReply(
                    name=name,
                    status="error",
                    content=str(exc),
                    duration_seconds=duration,
                )
            else:
                replies_by_name[name] = SubagentReply(
                    name=name,
                    status="completed",
                    content=content,
                    duration_seconds=duration,
                )

        for task in pending:
            name = done_lookup[task]
            task.cancel()
            replies_by_name[name] = SubagentReply(
                name=name,
                status="timeout",
                content=(
                    f"Subagent exceeded the {self._max_wait_seconds:.2f}s wait budget."
                ),
                duration_seconds=self._max_wait_seconds,
            )

        return [
            replies_by_name[selection.name]
            for selection in plan.selections
            if selection.name in replies_by_name
        ]
