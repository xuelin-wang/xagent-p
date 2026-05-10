import asyncio

import pytest
from pydantic import BaseModel

from xagent.llm_batch import BatchCreateRequest, BatchRequestItem, BatchStatus
from xagent.llm_config import ProviderConfig
from xagent.llm_contracts import GenerateRequest, Message, Role
from xagent.llm_files import BytesFileSource, FileDeleteRequest, FilePurpose, FileUploadRequest
from xagent.llm_provider_anthropic import AnthropicProvider
from xagent.llm_structured import StructuredGenerateRequest, response_format_for_model
from xagent.llm_tools import AppToolDefinition, ToolChoice


LIVE_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


class LiveAnthropicStructuredOutput(BaseModel):
    value: str


pytestmark = pytest.mark.require_env


def test_live_anthropic_generates_text() -> None:
    async def run() -> None:
        provider = AnthropicProvider(
            ProviderConfig(provider="anthropic", default_model=LIVE_ANTHROPIC_MODEL)
        )
        response = await provider.generate(
            GenerateRequest(
                messages=[
                    Message(
                        role=Role.USER,
                        content="Reply with exactly the lowercase string ok and no other text.",
                    )
                ],
                max_output_tokens=16,
            )
        )

        assert response.provider == "anthropic"
        assert response.text is not None
        assert response.text.strip().lower() == "ok"
        assert response.usage is not None
        assert response.raw_response is not None

    asyncio.run(run())


def test_live_anthropic_generates_structured_output() -> None:
    async def run() -> None:
        provider = AnthropicProvider(
            ProviderConfig(provider="anthropic", default_model=LIVE_ANTHROPIC_MODEL)
        )
        response = await provider.generate_structured(
            StructuredGenerateRequest(
                messages=[Message(role=Role.USER, content="Return ok in the value field.")],
                response_format=response_format_for_model(LiveAnthropicStructuredOutput),
                max_output_tokens=128,
            ),
            LiveAnthropicStructuredOutput,
        )

        assert response.provider == "anthropic"
        assert response.data.value == "ok"
        assert response.raw_json == {"value": "ok"}
        assert response.raw_response is not None

    asyncio.run(run())


def test_live_anthropic_returns_app_tool_call() -> None:
    async def run() -> None:
        provider = AnthropicProvider(
            ProviderConfig(provider="anthropic", default_model=LIVE_ANTHROPIC_MODEL)
        )
        response = await provider.generate(
            GenerateRequest(
                messages=[Message(role=Role.USER, content="Look up id abc using the tool.")],
                app_tools=[
                    AppToolDefinition(
                        name="lookup",
                        description="Lookup a record by id.",
                        input_schema={
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                            "required": ["id"],
                        },
                    )
                ],
                tool_choice=ToolChoice(mode="required", tool_name="lookup"),
                max_output_tokens=64,
            )
        )

        assert response.provider == "anthropic"
        assert len(response.app_tool_calls) == 1
        assert response.app_tool_calls[0].name == "lookup"
        assert response.app_tool_calls[0].arguments == {"id": "abc"}

    asyncio.run(run())


def test_live_anthropic_uploads_and_deletes_file() -> None:
    async def run() -> None:
        provider = AnthropicProvider(
            ProviderConfig(provider="anthropic", default_model=LIVE_ANTHROPIC_MODEL)
        )
        uploaded = await provider.upload_file(
            FileUploadRequest(
                source=BytesFileSource(
                    filename="xagent-integration-anthropic.txt",
                    data=b"hello from xagent integration",
                    media_type="text/plain",
                ),
                purpose=FilePurpose.PROMPT_INPUT,
            )
        )
        try:
            assert uploaded.provider == "anthropic"
            assert uploaded.file_id.startswith("file_")
            assert uploaded.filename == "xagent-integration-anthropic.txt"
        finally:
            await provider.delete_file(FileDeleteRequest(provider=uploaded.provider, file_id=uploaded.file_id))

    asyncio.run(run())


def test_live_anthropic_creates_gets_and_cancels_batch() -> None:
    async def run() -> None:
        provider = AnthropicProvider(
            ProviderConfig(provider="anthropic", default_model=LIVE_ANTHROPIC_MODEL)
        )
        created = await provider.create_batch(
            BatchCreateRequest(
                model=LIVE_ANTHROPIC_MODEL,
                items=[
                    BatchRequestItem(
                        custom_id="integration-1",
                        request=GenerateRequest(
                            messages=[Message(role=Role.USER, content="Reply with ok.")],
                            max_output_tokens=16,
                        ),
                    )
                ],
                metadata={"suite": "xagent-integration"},
            )
        )
        got = await provider.get_batch(created.batch_id)
        cancelled = await provider.cancel_batch(created.batch_id)

        assert created.batch_id.startswith("msgbatch_")
        assert got.batch_id == created.batch_id
        assert cancelled.batch_id == created.batch_id
        assert created.status in {BatchStatus.VALIDATING, BatchStatus.QUEUED, BatchStatus.RUNNING}
        assert cancelled.status in {BatchStatus.RUNNING, BatchStatus.CANCELLED}

    asyncio.run(run())
