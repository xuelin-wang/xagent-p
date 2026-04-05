import argparse
import asyncio
import sys

from langchain_openai import ChatOpenAI

from xagent.langchain_agents.app import LangChainMultiAgentApp
from xagent.langchain_agents.corpus import build_sample_documents
from xagent.langchain_agents.merge import LangChainResponseMerger
from xagent.langchain_agents.planner import LangChainPlanner
from xagent.langchain_agents.subagents import RAGSubagent
from xagent.config import StrictConfigModel
from xagent.runtime_config import load_runtime_config


class CliConfig(StrictConfigModel):
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    xagent_max_wait_seconds: float = 10.0
    openai_api_key: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the sample LangChain planner/subagent application.",
    )
    parser.add_argument("query", help="User query to answer.")
    parser.add_argument(
        "--show-plan",
        action="store_true",
        help="Print planner output and subagent statuses before the final reply.",
    )
    return parser


async def _run(args: argparse.Namespace, config: CliConfig) -> int:
    planner_model = ChatOpenAI(
        model=config.openai_model,
        temperature=0,
        api_key=config.openai_api_key,
    )
    merger_model = ChatOpenAI(
        model=config.openai_model,
        temperature=0.2,
        api_key=config.openai_api_key,
    )
    rag_subagent = RAGSubagent(
        answer_model=ChatOpenAI(
            model=config.openai_model,
            temperature=0,
            api_key=config.openai_api_key,
        ),
        documents=build_sample_documents(),
        embedding_model=config.openai_embedding_model,
        api_key=config.openai_api_key,
    )
    subagents = {rag_subagent.name: rag_subagent}
    app = LangChainMultiAgentApp(
        planner=LangChainPlanner(planner_model, subagents),
        merger=LangChainResponseMerger(merger_model),
        subagents=subagents,
        max_wait_seconds=config.xagent_max_wait_seconds,
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
    config, remaining_args = load_runtime_config(CliConfig, sys.argv[1:])
    args = build_parser().parse_args(remaining_args)
    return asyncio.run(_run(args, config))


if __name__ == "__main__":
    raise SystemExit(main())
