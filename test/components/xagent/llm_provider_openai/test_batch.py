import asyncio
import json

import httpx
import pytest

from xagent.llm_batch import BatchCreateRequest, BatchRequestItem, BatchStatus, EmbeddingRequest
from xagent.llm_config import ProviderConfig, RetryConfig
from xagent.llm_contracts import GenerateRequest, Message, ProviderServerError, Role
from xagent.llm_provider_openai import OpenAIProvider
from xagent.llm_provider_openai.batch import (
    batch_job_from_openai,
    batch_results_from_openai_jsonl,
    request_to_openai_batch_jsonl,
)


def test_request_to_openai_batch_jsonl_for_responses() -> None:
    endpoint, jsonl = request_to_openai_batch_jsonl(
        BatchCreateRequest(
            model="gpt-5.4-mini",
            items=[
                BatchRequestItem(
                    custom_id="case-1",
                    request=GenerateRequest(
                        messages=[Message(role=Role.USER, content="hello")],
                        max_output_tokens=16,
                    ),
                )
            ],
        ),
        "gpt-5.5",
    )

    assert endpoint == "/v1/responses"
    assert json.loads(jsonl) == {
        "custom_id": "case-1",
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": "gpt-5.4-mini",
            "input": [{"role": "user", "content": "hello"}],
            "max_output_tokens": 16,
        },
    }


def test_request_to_openai_batch_jsonl_for_embeddings() -> None:
    endpoint, jsonl = request_to_openai_batch_jsonl(
        BatchCreateRequest(
            items=[
                BatchRequestItem(
                    custom_id="embed-1",
                    request=EmbeddingRequest(inputs=["hello"], dimensions=32),
                )
            ],
        ),
        "gpt-5.5",
    )

    assert endpoint == "/v1/embeddings"
    assert json.loads(jsonl) == {
        "custom_id": "embed-1",
        "method": "POST",
        "url": "/v1/embeddings",
        "body": {
            "model": "text-embedding-3-small",
            "input": ["hello"],
            "encoding_format": "float",
            "dimensions": 32,
        },
    }


def test_batch_job_from_openai() -> None:
    job = batch_job_from_openai(
        {
            "id": "batch_123",
            "status": "completed",
            "created_at": 1_700_000_000,
            "completed_at": 1_700_000_010,
            "request_counts": {"total": 1, "completed": 1, "failed": 0},
            "metadata": {"trace": "unit"},
        }
    )

    assert job.batch_id == "batch_123"
    assert job.status == BatchStatus.SUCCEEDED
    assert job.request_counts["completed"] == 1
    assert job.metadata == {"trace": "unit"}


def test_batch_results_from_openai_jsonl() -> None:
    results = batch_results_from_openai_jsonl(
        batch_id="batch_123",
        status=BatchStatus.SUCCEEDED,
        output_text=(
            json.dumps(
                {
                    "custom_id": "case-1",
                    "response": {
                        "status_code": 200,
                        "request_id": "req-1",
                        "body": {
                            "model": "gpt-5.4-mini",
                            "output_text": "ok",
                            "status": "completed",
                        },
                    },
                }
            )
            + "\n"
        ),
        error_text=(
            json.dumps(
                {
                    "custom_id": "case-2",
                    "response": {
                        "status_code": 400,
                        "request_id": "req-2",
                        "body": {"error": {"message": "bad request"}},
                    },
                }
            )
            + "\n"
        ),
    )

    assert results.items[0].custom_id == "case-1"
    assert results.items[0].response.text == "ok"
    assert results.items[1].custom_id == "case-2"
    assert results.items[1].error.status_code == 400
    assert results.items[1].error.message == "bad request"


async def _test_openai_create_get_cancel_and_results_batch() -> None:
    seen: dict = {"requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["requests"].append((request.method, str(request.url)))
        if request.method == "POST" and str(request.url) == "https://openai.test/v1/files":
            seen["upload_body"] = request.content
            return httpx.Response(200, json={"id": "file-input", "filename": "batch.jsonl"})
        if request.method == "POST" and str(request.url) == "https://openai.test/v1/batches":
            seen["batch_payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "batch_123",
                    "status": "validating",
                    "created_at": 1_700_000_000,
                    "request_counts": {"total": 1, "completed": 0, "failed": 0},
                    "metadata": {"trace": "unit"},
                },
            )
        if request.method == "GET" and str(request.url) == "https://openai.test/v1/batches/batch_123":
            return httpx.Response(
                200,
                json={
                    "id": "batch_123",
                    "status": "completed",
                    "output_file_id": "file-output",
                    "error_file_id": "file-error",
                    "request_counts": {"total": 1, "completed": 1, "failed": 0},
                },
            )
        if request.method == "POST" and str(request.url) == "https://openai.test/v1/batches/batch_123/cancel":
            return httpx.Response(200, json={"id": "batch_123", "status": "cancelled"})
        if request.method == "GET" and str(request.url) == "https://openai.test/v1/files/file-output/content":
            return httpx.Response(
                200,
                text=json.dumps(
                    {
                        "custom_id": "case-1",
                        "response": {
                            "status_code": 200,
                            "body": {
                                "model": "gpt-5.4-mini",
                                "output_text": "ok",
                                "status": "completed",
                            },
                        },
                    }
                )
                + "\n",
            )
        if request.method == "GET" and str(request.url) == "https://openai.test/v1/files/file-error/content":
            return httpx.Response(200, text="")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    provider = OpenAIProvider(
        ProviderConfig(
            provider="openai",
            default_model="gpt-5.5",
            api_key="test-key",
            base_url="https://openai.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    created = await provider.create_batch(
        BatchCreateRequest(
            model="gpt-5.4-mini",
            items=[
                BatchRequestItem(
                    custom_id="case-1",
                    request=GenerateRequest(messages=[Message(role=Role.USER, content="hello")]),
                )
            ],
            metadata={"trace": "unit"},
        )
    )
    got = await provider.get_batch("batch_123")
    cancelled = await provider.cancel_batch("batch_123")
    results = await provider.get_batch_results("batch_123")

    assert b"batch" in seen["upload_body"]
    assert seen["batch_payload"] == {
        "input_file_id": "file-input",
        "endpoint": "/v1/responses",
        "completion_window": "24h",
        "metadata": {"trace": "unit"},
    }
    assert created.status == BatchStatus.VALIDATING
    assert got.status == BatchStatus.SUCCEEDED
    assert cancelled.status == BatchStatus.CANCELLED
    assert results.items[0].response.text == "ok"


def test_openai_create_get_cancel_and_results_batch() -> None:
    asyncio.run(_test_openai_create_get_cancel_and_results_batch())


async def _test_openai_create_batch_does_not_retry_resource_creation() -> None:
    batch_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal batch_calls
        if request.method == "POST" and str(request.url) == "https://openai.test/v1/files":
            return httpx.Response(200, json={"id": "file-input", "filename": "batch.jsonl"})
        if request.method == "POST" and str(request.url) == "https://openai.test/v1/batches":
            batch_calls += 1
            return httpx.Response(500, json={"error": {"message": "try later"}})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

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
        await provider.create_batch(
            BatchCreateRequest(
                items=[
                    BatchRequestItem(
                        custom_id="case-1",
                        request=GenerateRequest(messages=[Message(role=Role.USER, content="hello")]),
                    )
                ]
            )
        )

    assert batch_calls == 1


def test_openai_create_batch_does_not_retry_resource_creation() -> None:
    asyncio.run(_test_openai_create_batch_does_not_retry_resource_creation())


async def _test_openai_cancel_batch_does_not_retry_resource_mutation() -> None:
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
        await provider.cancel_batch("batch_123")

    assert calls == 1


def test_openai_cancel_batch_does_not_retry_resource_mutation() -> None:
    asyncio.run(_test_openai_cancel_batch_does_not_retry_resource_mutation())
