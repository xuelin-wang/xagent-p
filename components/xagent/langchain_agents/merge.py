from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from xagent.agent_app.model import PlannerStep, SubagentReply


class LangChainResponseMerger:
    def __init__(self, model):
        self._chain = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are the supervisor agent. Merge specialist results into a single "
                        "concise reply for the user. If a subagent timed out or failed, mention "
                        "that only if it affects the answer."
                    ),
                ),
                (
                    "human",
                    (
                        "User query:\n{query}\n\n"
                        "Planner notes:\n{planner_notes}\n\n"
                        "Subagent results:\n{subagent_results}"
                    ),
                ),
            ]
        ) | model

    async def amerge(
        self,
        query: str,
        plan: PlannerStep,
        replies: list[SubagentReply],
    ) -> str:
        serialized_results = "\n\n".join(
            (
                f"Subagent: {reply.name}\n"
                f"Status: {reply.status}\n"
                f"Duration seconds: {reply.duration_seconds:.2f}\n"
                f"Content:\n{reply.content}"
            )
            for reply in replies
        ) or "No subagent results were available."
        response = await self._chain.ainvoke(
            {
                "query": query,
                "planner_notes": plan.notes or "No planner notes.",
                "subagent_results": serialized_results,
            }
        )
        if isinstance(response, AIMessage):
            return str(response.content)
        return str(response)
