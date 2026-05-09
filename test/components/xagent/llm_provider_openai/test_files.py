import asyncio

import httpx
import pytest

from xagent.llm_config import ProviderConfig, RetryConfig
from xagent.llm_contracts import ProviderServerError
from xagent.llm_files import BytesFileSource, FileDeleteRequest, FilePurpose, FileUploadRequest
from xagent.llm_provider_openai import OpenAIProvider
from xagent.llm_provider_openai.files import openai_file_purpose


def test_openai_file_purpose_mapping() -> None:
    assert openai_file_purpose(FilePurpose.PROMPT_INPUT) == "user_data"
    assert openai_file_purpose(FilePurpose.BATCH_INPUT) == "batch"


async def _test_openai_upload_file_posts_multipart_and_normalizes_response() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={
                "id": "file-123",
                "filename": "note.txt",
                "bytes": 5,
                "purpose": "user_data",
                "expires_at": 1_700_000_000,
            },
        )

    provider = OpenAIProvider(
        ProviderConfig(
            provider="openai",
            default_model="gpt-5.5",
            api_key="test-key",
            base_url="https://openai.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    uploaded = await provider.upload_file(
        FileUploadRequest(
            source=BytesFileSource(filename="note.txt", data=b"hello", media_type="text/plain"),
            purpose=FilePurpose.PROMPT_INPUT,
        )
    )

    assert seen["url"] == "https://openai.test/v1/files"
    assert seen["auth"] == "Bearer test-key"
    assert seen["content_type"].startswith("multipart/form-data")
    assert b'name="purpose"' in seen["body"]
    assert b"user_data" in seen["body"]
    assert b'name="file"; filename="note.txt"' in seen["body"]
    assert uploaded.file_id == "file-123"
    assert uploaded.size_bytes == 5
    assert uploaded.media_type == "text/plain"
    assert uploaded.expires_at is not None


def test_openai_upload_file_posts_multipart_and_normalizes_response() -> None:
    asyncio.run(_test_openai_upload_file_posts_multipart_and_normalizes_response())


async def _test_openai_upload_file_does_not_retry_resource_creation() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"message": "try later"}})

    provider = OpenAIProvider(
        ProviderConfig(
            provider="openai",
            default_model="gpt-5.5",
            api_key="test-key",
            base_url="https://openai.test/v1",
            retry=RetryConfig(jitter=False, initial_delay_seconds=0, max_attempts=2),
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderServerError):
        await provider.upload_file(
            FileUploadRequest(
                source=BytesFileSource(filename="note.txt", data=b"hello", media_type="text/plain"),
                purpose=FilePurpose.PROMPT_INPUT,
            )
        )

    assert calls == 1


def test_openai_upload_file_does_not_retry_resource_creation() -> None:
    asyncio.run(_test_openai_upload_file_does_not_retry_resource_creation())


async def _test_openai_delete_file_deletes_provider_file() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["method"] = request.method
        return httpx.Response(200, json={"id": "file-123", "deleted": True})

    provider = OpenAIProvider(
        ProviderConfig(
            provider="openai",
            default_model="gpt-5.5",
            api_key="test-key",
            base_url="https://openai.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    await provider.delete_file(FileDeleteRequest(provider="openai", file_id="file-123"))

    assert seen == {"url": "https://openai.test/v1/files/file-123", "method": "DELETE"}


def test_openai_delete_file_deletes_provider_file() -> None:
    asyncio.run(_test_openai_delete_file_deletes_provider_file())


async def _test_openai_delete_file_does_not_retry_ambiguous_delete() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"message": "try later"}})

    provider = OpenAIProvider(
        ProviderConfig(
            provider="openai",
            default_model="gpt-5.5",
            api_key="test-key",
            base_url="https://openai.test/v1",
            retry=RetryConfig(jitter=False, initial_delay_seconds=0, max_attempts=2),
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderServerError):
        await provider.delete_file(FileDeleteRequest(provider="openai", file_id="file-123"))

    assert calls == 1


def test_openai_delete_file_does_not_retry_ambiguous_delete() -> None:
    asyncio.run(_test_openai_delete_file_does_not_retry_ambiguous_delete())
