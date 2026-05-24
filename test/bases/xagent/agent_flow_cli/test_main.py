import asyncio
import io
import json
from pathlib import Path

import pytest

from xagent.agent_flow.models import AgentFlowState, RunStatus
from xagent.agent_flow_cli.main import _parse_metadata, build_parser, run


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def start_run(
        self,
        *,
        user_query: str,
        case_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AgentFlowState:
        self.calls.append(
            (
                "start_run",
                {
                    "user_query": user_query,
                    "case_id": case_id,
                    "metadata": metadata,
                },
            )
        )
        return AgentFlowState(
            run_id="run_1",
            user_query=user_query,
            case_id=case_id,
            status=RunStatus.COMPLETED,
            final_response="done",
            metadata=metadata or {},
        )

    async def get_run(self, run_id: str) -> AgentFlowState:
        self.calls.append(("get_run", run_id))
        return AgentFlowState(
            run_id=run_id,
            user_query="stored query",
            status=RunStatus.COMPLETED,
            final_response="stored",
        )

    async def resume_run(self, run_id: str) -> AgentFlowState:
        self.calls.append(("resume_run", run_id))
        return AgentFlowState(
            run_id=run_id,
            user_query="stored query",
            status=RunStatus.COMPLETED,
            final_response="resumed",
        )

    async def submit_user_input(self, run_id: str, user_input: str) -> AgentFlowState:
        self.calls.append(
            ("submit_user_input", {"run_id": run_id, "user_input": user_input})
        )
        return AgentFlowState(
            run_id=run_id,
            user_query="stored query",
            status=RunStatus.COMPLETED,
            final_response="continued",
        )


def test_build_parser_has_expected_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["run", "query"]).command == "run"
    assert parser.parse_args(["get", "run_1"]).command == "get"
    assert parser.parse_args(["resume", "run_1"]).command == "resume"
    assert parser.parse_args(["input", "run_1", "user text"]).command == "input"


def test_run_command_dispatches_to_service_and_prints_json() -> None:
    service = FakeService()
    stdout = io.StringIO()

    exit_code = asyncio.run(
        run(
            [
                "run",
                "diagnose no start",
                "--case-id",
                "case_123",
                "--metadata-json",
                '{"vehicle":"example"}',
            ],
            service=service,
            stdout=stdout,
        )
    )

    assert exit_code == 0
    assert service.calls == [
        (
            "start_run",
            {
                "user_query": "diagnose no start",
                "case_id": "case_123",
                "metadata": {"vehicle": "example"},
            },
        )
    ]
    payload = json.loads(stdout.getvalue())
    assert payload["run_id"] == "run_1"
    assert payload["status"] == "completed"
    assert payload["metadata"] == {"vehicle": "example"}


@pytest.mark.parametrize(
    ("argv", "call", "final_response"),
    [
        (["get", "run_1"], "get_run", "stored"),
        (["resume", "run_1"], "resume_run", "resumed"),
    ],
)
def test_get_and_resume_dispatch_to_service(
    argv: list[str],
    call: str,
    final_response: str,
) -> None:
    service = FakeService()
    stdout = io.StringIO()

    exit_code = asyncio.run(run(argv, service=service, stdout=stdout))

    assert exit_code == 0
    assert service.calls == [(call, "run_1")]
    assert json.loads(stdout.getvalue())["final_response"] == final_response


def test_run_loads_config_file_for_default_service(tmp_path: Path) -> None:
    config_file = tmp_path / "agent-flow.yaml"
    config_file.write_text(
        "\n".join(
            [
                "subagents:",
                "  manuals:",
                "    name: manuals",
                "    description: Search service manuals.",
                "    prompt_template: prompts/agent_flow/subagents/manuals.md",
            ]
        ),
        encoding="utf-8",
    )
    stdout = io.StringIO()

    exit_code = asyncio.run(
        run(
            ["--config", str(config_file), "run", "diagnose no start"],
            stdout=stdout,
        )
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["status"] == "completed"
    assert payload["final_response"] == (
        "manuals handled query 'diagnose no start' for iteration 0."
    )


def test_input_command_dispatches_to_submit_user_input() -> None:
    service = FakeService()
    stdout = io.StringIO()

    exit_code = asyncio.run(
        run(["input", "run_1", "It's a 2020 model."], service=service, stdout=stdout)
    )

    assert exit_code == 0
    assert service.calls == [
        ("submit_user_input", {"run_id": "run_1", "user_input": "It's a 2020 model."})
    ]
    assert json.loads(stdout.getvalue())["final_response"] == "continued"


def test_parse_metadata_rejects_non_object_json() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _parse_metadata("[]")
