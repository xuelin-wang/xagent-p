import argparse
import asyncio
import os

from langchain_openai import ChatOpenAI

from xagent.langchain_agents.app import LangChainMultiAgentApp
from xagent.langchain_agents.corpus import build_sample_documents
from xagent.langchain_agents.merge import LangChainResponseMerger
from xagent.langchain_agents.planner import LangChainPlanner
from xagent.langchain_agents.subagents import RAGSubagent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the sample LangChain planner/subagent application.",
    )
    parser.add_argument("query", help="User query to answer.")
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        help="OpenAI chat model name for the planner and merger.",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        help="OpenAI embedding model used by the RAG subagent.",
    )
    parser.add_argument(
        "--max-wait-seconds",
        type=float,
        default=10.0,
        help="Maximum total wait time for all subagents.",
    )
    parser.add_argument(
        "--show-plan",
        action="store_true",
        help="Print planner output and subagent statuses before the final reply.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    planner_model = ChatOpenAI(model=args.model, temperature=0)
    merger_model = ChatOpenAI(model=args.model, temperature=0.2)
    rag_subagent = RAGSubagent(
        answer_model=ChatOpenAI(model=args.model, temperature=0),
        documents=build_sample_documents(),
        embedding_model=args.embedding_model,
    )
    subagents = {rag_subagent.name: rag_subagent}
    app = LangChainMultiAgentApp(
        planner=LangChainPlanner(planner_model, subagents),
        merger=LangChainResponseMerger(merger_model),
        subagents=subagents,
        max_wait_seconds=args.max_wait_seconds,
    )
    result = await app.arun(args.query)
    if args.show_plan:
        print("Plan:")
        for selection in result.plan.selections:
            print(f"- {selection.name}: {selection.reason}")
        print("\nSubagent replies:")
        for reply in result.subagent_replies:
            print(f"- {reply.name} [{reply.status}] ({reply.duration_seconds:.2f}s)")
    print("\nFinal reply:")
    print(result.final_reply)
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
