import asyncio
import json

import httpx

from xagent.llm_config import ProviderConfig
from xagent.llm_contracts import GenerateRequest, Message, Role
from xagent.llm_files import (
    BytesFileSource,
    FileDeleteRequest,
    FileInput,
    FilePurpose,
    FileUploadRequest,
    ProviderFileRef,
)
from xagent.llm_provider_anthropic import AnthropicProvider
from xagent.llm_provider_anthropic.files import ANTHROPIC_FILES_BETA, anthropic_files_beta_header


def test_anthropic_files_beta_header() -> None:
    assert anthropic_files_beta_header() == {"anthropic-beta": ANTHROPIC_FILES_BETA}


async def _test_anthropic_generate_posts_uploaded_file_reference() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["beta"] = request.headers["anthropic-beta"]
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-6",
                "content": [{"type": "text", "text": "summary"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    await provider.generate(
        GenerateRequest(
            messages=[Message(role=Role.USER, content="summarize")],
            files=[
                FileInput(
                    source=ProviderFileRef(
                        provider="anthropic",
                        file_id="file_123",
                        media_type="application/pdf",
                    )
                )
            ],
        )
    )

    assert seen["beta"] == ANTHROPIC_FILES_BETA
    assert seen["payload"]["messages"][0]["content"] == [
        {"type": "text", "text": "summarize"},
        {"type": "document", "source": {"type": "file", "file_id": "file_123"}},
    ]


def test_anthropic_generate_posts_uploaded_file_reference() -> None:
    asyncio.run(_test_anthropic_generate_posts_uploaded_file_reference())


async def _test_anthropic_upload_file_posts_multipart_and_normalizes_response() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers["x-api-key"]
        seen["version"] = request.headers["anthropic-version"]
        seen["beta"] = request.headers["anthropic-beta"]
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={
                "id": "file_123",
                "filename": "note.txt",
                "size_bytes": 5,
            },
        )

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    uploaded = await provider.upload_file(
        FileUploadRequest(
            source=BytesFileSource(filename="note.txt", data=b"hello", media_type="text/plain"),
            purpose=FilePurpose.PROMPT_INPUT,
        )
    )

    assert seen["url"] == "https://anthropic.test/v1/files"
    assert seen["api_key"] == "test-key"
    assert seen["version"] == "2023-06-01"
    assert seen["beta"] == ANTHROPIC_FILES_BETA
    assert seen["content_type"].startswith("multipart/form-data")
    assert b'name="file"; filename="note.txt"' in seen["body"]
    assert uploaded.file_id == "file_123"
    assert uploaded.filename == "note.txt"
    assert uploaded.size_bytes == 5
    assert uploaded.media_type == "text/plain"
    assert uploaded.purpose == FilePurpose.PROMPT_INPUT


def test_anthropic_upload_file_posts_multipart_and_normalizes_response() -> None:
    asyncio.run(_test_anthropic_upload_file_posts_multipart_and_normalizes_response())


async def _test_anthropic_delete_file_deletes_provider_file() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["beta"] = request.headers["anthropic-beta"]
        return httpx.Response(200, json={"id": "file_123", "deleted": True})

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    await provider.delete_file(FileDeleteRequest(provider="anthropic", file_id="file_123"))

    assert seen == {
        "url": "https://anthropic.test/v1/files/file_123",
        "method": "DELETE",
        "beta": ANTHROPIC_FILES_BETA,
    }


def test_anthropic_delete_file_deletes_provider_file() -> None:
    asyncio.run(_test_anthropic_delete_file_deletes_provider_file())
