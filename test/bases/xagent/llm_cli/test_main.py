import io
import json

import pytest

from xagent.llm_batch import BatchJob, BatchResults, BatchStatus, EmbeddingResponse, EmbeddingVector
from xagent.llm_config import ProviderConfig
from xagent.llm_contracts import GenerateResponse
from xagent.llm_files import FilePurpose, UploadedFile
from xagent.llm_structured import StructuredGenerateResponse
from xagent.llm_cli.main import build_parser, run


class FakeFactory:
    def __init__(self) -> None:
        self.config: ProviderConfig | None = None
        self.provider = FakeProvider()

    def create(self, config: ProviderConfig) -> "FakeProvider":
        self.config = config
        return self.provider


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def generate(self, request):
        self.calls.append(("generate", request))
        return GenerateResponse(provider="openai", model="gpt-5.5", text="ok")

    async def generate_structured(self, request, output_type):
        self.calls.append(("generate_structured", (request, output_type)))
        return StructuredGenerateResponse(
            provider="openai",
            model="gpt-5.5",
            data=output_type.model_validate({"value": "ok"}),
            raw_json={"value": "ok"},
        )

    async def embed(self, request):
        self.calls.append(("embed", request))
        return EmbeddingResponse(
            provider="openai",
            model="text-embedding-3-small",
            vectors=[EmbeddingVector(index=0, embedding=[0.1, 0.2])],
            dimensions=2,
        )

    async def upload_file(self, request):
        self.calls.append(("upload_file", request))
        return UploadedFile(provider="openai", file_id="file-123", purpose=FilePurpose.PROMPT_INPUT)

    async def create_batch(self, request):
        self.calls.append(("create_batch", request))
        return BatchJob(provider="openai", batch_id="batch-123", status=BatchStatus.VALIDATING)

    async def get_batch(self, batch_id):
        self.calls.append(("get_batch", batch_id))
        return BatchJob(provider="openai", batch_id=batch_id, status=BatchStatus.SUCCEEDED)

    async def get_batch_results(self, batch_id):
        self.calls.append(("get_batch_results", batch_id))
        return BatchResults(provider="openai", batch_id=batch_id, status=BatchStatus.SUCCEEDED, items=[])


def test_build_parser_has_expected_commands() -> None:
    commands = build_parser()._subparsers._group_actions[0].choices

    assert sorted(commands) == [
        "batch-results",
        "create-batch",
        "embed",
        "get-batch",
        "structured",
        "text",
        "upload-file",
    ]


@pytest.mark.parametrize(
    ("argv", "call"),
    [
        (["text", "hello"], "generate"),
        (
            [
                "structured",
                "hello",
                "--schema-json",
                '{"type":"object","properties":{"value":{"type":"string"}},"required":["value"]}',
            ],
            "generate_structured",
        ),
        (["embed", "hello"], "embed"),
        (["upload-file", "/tmp/note.txt"], "upload_file"),
        (["create-batch", "one", "two"], "create_batch"),
        (["get-batch", "batch-123"], "get_batch"),
        (["batch-results", "batch-123"], "get_batch_results"),
    ],
)
def test_run_dispatches_command(argv: list[str], call: str) -> None:
    factory = FakeFactory()
    stdout = io.StringIO()

    exit_code = async_run(run(argv, factory=factory, stdout=stdout))

    assert exit_code == 0
    assert factory.provider.calls[0][0] == call
    assert json.loads(stdout.getvalue())


def test_run_builds_provider_config() -> None:
    factory = FakeFactory()
    stdout = io.StringIO()

    exit_code = async_run(
        run(
            ["--provider", "anthropic", "--model", "claude-sonnet-4-6", "text", "hi"],
            factory=factory,
            stdout=stdout,
        )
    )

    assert exit_code == 0
    assert factory.config.provider == "anthropic"
    assert factory.config.default_model == "claude-sonnet-4-6"
    assert factory.config.api_key_env == "ANTHROPIC_API_KEY"


def async_run(coro):
    import asyncio

    return asyncio.run(coro)
