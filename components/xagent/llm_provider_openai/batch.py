import json
from datetime import UTC, datetime
from typing import Any, Literal

from xagent.llm_batch import (
    BatchCreateRequest,
    BatchJob,
    BatchRequestItem,
    BatchResultItem,
    BatchResults,
    BatchStatus,
    EmbeddingRequest,
)
from xagent.llm_contracts import GenerateRequest, LLMErrorPayload
from xagent.llm_provider_openai.embeddings import (
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODELS,
    request_to_openai_embeddings_payload,
    response_from_openai_embeddings,
)
from xagent.llm_provider_openai.mapping import (
    request_to_openai_responses_payload,
    response_from_openai_responses,
)

OPENAI_BATCH_COMPLETION_WINDOW = "24h"


def request_to_openai_batch_jsonl(request: BatchCreateRequest, default_model: str) -> tuple[str, str]:
    endpoint = _batch_endpoint(request.items)
    lines = [
        json.dumps(
            {
                "custom_id": item.custom_id,
                "method": "POST",
                "url": endpoint,
                "body": _batch_item_body(item, request.model, default_model),
            },
            separators=(",", ":"),
        )
        for item in request.items
    ]
    return endpoint, "\n".join(lines) + "\n"


def batch_job_from_openai(raw: dict[str, Any]) -> BatchJob:
    return BatchJob(
        provider="openai",
        batch_id=raw["id"],
        status=_batch_status(raw.get("status")),
        created_at=_datetime_from_unix_seconds(raw.get("created_at")),
        completed_at=_datetime_from_unix_seconds(raw.get("completed_at")),
        request_counts=raw.get("request_counts") or {},
        metadata=raw.get("metadata") or {},
        raw_response=raw,
    )


def batch_results_from_openai_jsonl(
    *,
    batch_id: str,
    status: BatchStatus,
    output_text: str,
    error_text: str = "",
) -> BatchResults:
    items = [
        _batch_result_item_from_line(line)
        for text in (output_text, error_text)
        for line in text.splitlines()
        if line.strip()
    ]
    return BatchResults(provider="openai", batch_id=batch_id, status=status, items=items)


def _batch_endpoint(items: list[BatchRequestItem]) -> Literal["/v1/responses", "/v1/embeddings"]:
    if not items:
        raise ValueError("OpenAI batch requires at least one item.")
    first_is_embedding = isinstance(items[0].request, EmbeddingRequest)
    for item in items:
        if isinstance(item.request, EmbeddingRequest) != first_is_embedding:
            raise ValueError("OpenAI native batch cannot mix embeddings and responses requests.")
    return "/v1/embeddings" if first_is_embedding else "/v1/responses"


def _batch_item_body(item: BatchRequestItem, batch_model: str | None, default_model: str) -> dict[str, Any]:
    request = item.request
    if isinstance(request, EmbeddingRequest):
        model = request.model or batch_model or DEFAULT_OPENAI_EMBEDDING_MODEL
        if model not in OPENAI_EMBEDDING_MODELS:
            raise ValueError(f"OpenAI embedding model is not supported: {model}.")
        return request_to_openai_embeddings_payload(request, model)
    if isinstance(request, GenerateRequest):
        model = request.model or batch_model or default_model
        return request_to_openai_responses_payload(request, model)
    raise TypeError(f"Unsupported OpenAI batch request type: {type(request).__name__}")


def _batch_result_item_from_line(line: str) -> BatchResultItem:
    raw = json.loads(line)
    custom_id = raw["custom_id"]
    if raw.get("error"):
        return BatchResultItem(
            custom_id=custom_id,
            error=LLMErrorPayload(
                provider="openai",
                operation="batch_result",
                message=raw["error"].get("message") or "OpenAI batch item failed.",
                retryable=False,
                raw_error=raw["error"],
            ),
            raw=raw,
        )

    response = raw.get("response") or {}
    status_code = response.get("status_code")
    body = response.get("body") or {}
    request_id = response.get("request_id")
    if isinstance(status_code, int) and status_code >= 400:
        error = body.get("error") if isinstance(body, dict) else None
        return BatchResultItem(
            custom_id=custom_id,
            error=LLMErrorPayload(
                provider="openai",
                operation="batch_result",
                status_code=status_code,
                request_id=request_id,
                message=_error_message(error) or "OpenAI batch item returned an error.",
                retryable=status_code in {408, 429, 500, 502, 503, 504},
                raw_error=error if isinstance(error, dict) else body,
            ),
            raw=raw,
        )

    parsed_response = (
        response_from_openai_embeddings(body, body.get("model") or "unknown")
        if _is_embedding_body(body)
        else response_from_openai_responses(body, body.get("model") or "unknown")
    )
    return BatchResultItem(custom_id=custom_id, response=parsed_response, raw=raw)


def _is_embedding_body(body: dict[str, Any]) -> bool:
    data = body.get("data")
    return isinstance(data, list) and bool(data) and isinstance(data[0], dict) and "embedding" in data[0]


def _error_message(error: Any) -> str | None:
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return None


def _batch_status(status: Any) -> BatchStatus:
    return {
        "validating": BatchStatus.VALIDATING,
        "queued": BatchStatus.QUEUED,
        "in_progress": BatchStatus.RUNNING,
        "finalizing": BatchStatus.RUNNING,
        "completed": BatchStatus.SUCCEEDED,
        "failed": BatchStatus.FAILED,
        "cancelled": BatchStatus.CANCELLED,
        "cancelling": BatchStatus.RUNNING,
        "expired": BatchStatus.EXPIRED,
    }.get(status, BatchStatus.FAILED)


def _datetime_from_unix_seconds(value: object) -> datetime | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value, tz=UTC)
