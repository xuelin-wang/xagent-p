import asyncio
import json

import httpx
import pytest

from xagent.llm_batch import BatchCreateRequest, BatchRequestItem, BatchStatus
from xagent.llm_config import ProviderConfig, RetryConfig
from xagent.llm_contracts import GenerateRequest, Message, ProviderServerError, Role
from xagent.llm_provider_anthropic import AnthropicProvider
from xagent.llm_provider_anthropic.batch import (
    batch_job_from_anthropic,
    batch_results_from_anthropic_jsonl,
    request_to_anthropic_batch_payload,
)


def test_request_to_anthropic_batch_payload() -> None:
    payload = request_to_anthropic_batch_payload(
        BatchCreateRequest(
            model="claude-haiku-4-5-20251001",
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
        "claude-sonnet-4-6",
    )

    assert payload == {
        "requests": [
            {
                "custom_id": "case-1",
                "params": {
                    "model": "claude-haiku-4-5-20251001",
                    "messages": [{"role": "user", "content": "hello"}],
                    "max_tokens": 16,
                },
            }
        ]
    }


def test_batch_job_from_anthropic() -> None:
    job = batch_job_from_anthropic(
        {
            "id": "msgbatch_123",
            "processing_status": "ended",
            "created_at": "2024-08-20T18:37:24.100435Z",
            "ended_at": "2024-08-20T18:38:24.100435Z",
            "request_counts": {
                "processing": 0,
                "succeeded": 1,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
        }
    )

    assert job.batch_id == "msgbatch_123"
    assert job.status == BatchStatus.SUCCEEDED
    assert job.created_at is not None
    assert job.completed_at is not None
    assert job.request_counts["succeeded"] == 1


def test_batch_results_from_anthropic_jsonl() -> None:
    results = batch_results_from_anthropic_jsonl(
        batch_id="msgbatch_123",
        status=BatchStatus.SUCCEEDED,
        text=(
            json.dumps(
                {
                    "custom_id": "case-1",
                    "result": {
                        "type": "succeeded",
                        "message": {
                            "model": "claude-sonnet-4-6",
                            "content": [{"type": "text", "text": "ok"}],
                            "stop_reason": "end_turn",
                            "usage": {"input_tokens": 1, "output_tokens": 2},
                        },
                    },
                }
            )
            + "\n"
            + json.dumps(
                {
                    "custom_id": "case-2",
                    "result": {
                        "type": "errored",
                        "error": {"type": "invalid_request_error", "message": "bad request"},
                    },
                }
            )
            + "\n"
        ),
    )

    assert results.items[0].custom_id == "case-1"
    assert results.items[0].response.text == "ok"
    assert results.items[1].custom_id == "case-2"
    assert results.items[1].error.message == "bad request"


async def _test_anthropic_create_get_cancel_and_results_batch() -> None:
    seen: dict = {"requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["requests"].append((request.method, str(request.url)))
        if request.method == "POST" and str(request.url) == "https://anthropic.test/v1/messages/batches":
            seen["batch_payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "msgbatch_123",
                    "processing_status": "in_progress",
                    "created_at": "2024-08-20T18:37:24.100435Z",
                    "ended_at": None,
                    "request_counts": {
                        "processing": 1,
                        "succeeded": 0,
                        "errored": 0,
                        "canceled": 0,
                        "expired": 0,
                    },
                },
            )
        if request.method == "GET" and str(request.url) == "https://anthropic.test/v1/messages/batches/msgbatch_123":
            return httpx.Response(
                200,
                json={
                    "id": "msgbatch_123",
                    "processing_status": "ended",
                    "created_at": "2024-08-20T18:37:24.100435Z",
                    "ended_at": "2024-08-20T18:38:24.100435Z",
                    "request_counts": {
                        "processing": 0,
                        "succeeded": 1,
                        "errored": 0,
                        "canceled": 0,
                        "expired": 0,
                    },
                },
            )
        if request.method == "POST" and str(request.url) == "https://anthropic.test/v1/messages/batches/msgbatch_123/cancel":
            return httpx.Response(
                200,
                json={
                    "id": "msgbatch_123",
                    "processing_status": "ended",
                    "request_counts": {
                        "processing": 0,
                        "succeeded": 0,
                        "errored": 0,
                        "canceled": 1,
                        "expired": 0,
                    },
                },
            )
        if request.method == "GET" and str(request.url) == "https://anthropic.test/v1/messages/batches/msgbatch_123/results":
            return httpx.Response(
                200,
                text=json.dumps(
                    {
                        "custom_id": "case-1",
                        "result": {
                            "type": "succeeded",
                            "message": {
                                "model": "claude-sonnet-4-6",
                                "content": [{"type": "text", "text": "ok"}],
                                "stop_reason": "end_turn",
                                "usage": {"input_tokens": 1, "output_tokens": 2},
                            },
                        },
                    }
                )
                + "\n",
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    created = await provider.create_batch(
        BatchCreateRequest(
            items=[
                BatchRequestItem(
                    custom_id="case-1",
                    request=GenerateRequest(messages=[Message(role=Role.USER, content="hello")]),
                )
            ],
        )
    )
    got = await provider.get_batch("msgbatch_123")
    cancelled = await provider.cancel_batch("msgbatch_123")
    results = await provider.get_batch_results("msgbatch_123")

    assert seen["batch_payload"] == {
        "requests": [
            {
                "custom_id": "case-1",
                "params": {
                    "model": "claude-sonnet-4-6",
                    "messages": [{"role": "user", "content": "hello"}],
                    "max_tokens": 1024,
                },
            }
        ]
    }
    assert created.status == BatchStatus.RUNNING
    assert got.status == BatchStatus.SUCCEEDED
    assert cancelled.status == BatchStatus.CANCELLED
    assert results.items[0].response.text == "ok"


def test_anthropic_create_get_cancel_and_results_batch() -> None:
    asyncio.run(_test_anthropic_create_get_cancel_and_results_batch())


async def _test_anthropic_create_batch_does_not_retry_resource_creation() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"message": "try later"}})

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
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

    assert calls == 1


def test_anthropic_create_batch_does_not_retry_resource_creation() -> None:
    asyncio.run(_test_anthropic_create_batch_does_not_retry_resource_creation())


async def _test_anthropic_cancel_batch_does_not_retry_resource_mutation() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"message": "try later"}})

    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            default_model="claude-sonnet-4-6",
            api_key="test-key",
            base_url="https://anthropic.test/v1",
            retry=RetryConfig(jitter=False, initial_delay_seconds=0, max_attempts=2),
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderServerError):
        await provider.cancel_batch("msgbatch_123")

    assert calls == 1


def test_anthropic_cancel_batch_does_not_retry_resource_mutation() -> None:
    asyncio.run(_test_anthropic_cancel_batch_does_not_retry_resource_mutation())
