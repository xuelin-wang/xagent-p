import argparse
import asyncio
import json
import sys
from typing import Protocol, TextIO

from xagent.agent_flow.config import AgentFlowAppConfig
from xagent.agent_flow.models import AgentFlowState
from xagent.agent_flow.service import AgentFlowService
from xagent.runtime_config import load_runtime_config


class AgentFlowServiceRunner(Protocol):
    async def start_run(
        self,
        *,
        user_query: str,
        case_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AgentFlowState: ...

    async def get_run(self, run_id: str) -> AgentFlowState: ...

    async def resume_run(self, run_id: str) -> AgentFlowState: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the custom durable xagent agent-flow runtime.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Start and run an agent flow.")
    run_parser.add_argument("query", help="User query to answer.")
    run_parser.add_argument("--case-id")
    run_parser.add_argument(
        "--metadata-json",
        default="{}",
        help="JSON object to attach to the run metadata.",
    )

    get_parser = subparsers.add_parser("get", help="Fetch a run from this process.")
    get_parser.add_argument("run_id")

    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a run from this process.",
    )
    resume_parser.add_argument("run_id")
    return parser


async def run(
    argv: list[str],
    *,
    service: AgentFlowServiceRunner | None = None,
    stdout: TextIO = sys.stdout,
) -> int:
    config, remaining_args = load_runtime_config(AgentFlowAppConfig, argv)
    args = build_parser().parse_args(remaining_args)
    agent_service = service or AgentFlowService.in_memory(config)
    result = await _dispatch(agent_service, args)
    print(_state_to_json(result), file=stdout)
    return 0


def main() -> int:
    return asyncio.run(run(sys.argv[1:]))


async def _dispatch(
    service: AgentFlowServiceRunner,
    args: argparse.Namespace,
) -> AgentFlowState:
    if args.command == "run":
        return await service.start_run(
            user_query=args.query,
            case_id=args.case_id,
            metadata=_parse_metadata(args.metadata_json),
        )
    if args.command == "get":
        return await service.get_run(args.run_id)
    if args.command == "resume":
        return await service.resume_run(args.run_id)
    raise ValueError(f"Unsupported command: {args.command}")


def _parse_metadata(raw_metadata: str) -> dict[str, object]:
    loaded = json.loads(raw_metadata)
    if not isinstance(loaded, dict):
        raise ValueError("--metadata-json must be a JSON object.")
    return loaded


def _state_to_json(state: AgentFlowState) -> str:
    return json.dumps(state.model_dump(mode="json"), separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
