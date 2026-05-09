import json
from datetime import datetime
from typing import Any

from xagent.llm_batch import BatchCreateRequest, BatchJob, BatchResultItem, BatchResults, BatchStatus
from xagent.llm_contracts import GenerateRequest, LLMErrorPayload
from xagent.llm_provider_anthropic.mapping import (
    request_to_anthropic_messages_payload,
    response_from_anthropic_message,
)


def request_to_anthropic_batch_payload(request: BatchCreateRequest, default_model: str) -> dict[str, Any]:
    if not request.items:
        raise ValueError("Anthropic batch requires at least one item.")
    return {
        "requests": [
            {
                "custom_id": item.custom_id,
                "params": _batch_item_params(item.request, request.model, default_model),
            }
            for item in request.items
        ]
    }


def batch_job_from_anthropic(raw: dict[str, Any]) -> BatchJob:
    return BatchJob(
        provider="anthropic",
        batch_id=raw["id"],
        status=_batch_status(raw.get("processing_status"), raw.get("request_counts")),
        created_at=_datetime_from_rfc3339(raw.get("created_at")),
        completed_at=_datetime_from_rfc3339(raw.get("ended_at")),
        request_counts=raw.get("request_counts") or {},
        raw_response=raw,
    )


def batch_results_from_anthropic_jsonl(
    *,
    batch_id: str,
    status: BatchStatus,
    text: str,
) -> BatchResults:
    items = [
        _batch_result_item_from_line(line)
        for line in text.splitlines()
        if line.strip()
    ]
    return BatchResults(provider="anthropic", batch_id=batch_id, status=status, items=items)


def _batch_item_params(request: Any, batch_model: str | None, default_model: str) -> dict[str, Any]:
    if not isinstance(request, GenerateRequest):
        raise TypeError(f"Unsupported Anthropic batch request type: {type(request).__name__}")
    if request.response_format is not None:
        raise ValueError("Anthropic native batch does not support wrapper-managed structured output.")
    model = request.model or batch_model or default_model
    return request_to_anthropic_messages_payload(request, model)


def _batch_result_item_from_line(line: str) -> BatchResultItem:
    raw = json.loads(line)
    custom_id = raw["custom_id"]
    result = raw.get("result") or {}
    result_type = result.get("type")
    if result_type == "succeeded":
        message = result.get("message") or {}
        return BatchResultItem(
            custom_id=custom_id,
            response=response_from_anthropic_message(message, message.get("model") or "unknown"),
            raw=raw,
        )

    error = result.get("error") if isinstance(result.get("error"), dict) else None
    return BatchResultItem(
        custom_id=custom_id,
        error=LLMErrorPayload(
            provider="anthropic",
            operation="batch_result",
            message=_result_error_message(result_type, error),
            retryable=False,
            raw_error=result,
        ),
        raw=raw,
    )


def _result_error_message(result_type: Any, error: dict[str, Any] | None) -> str:
    if error and isinstance(error.get("message"), str):
        return error["message"]
    if result_type == "canceled":
        return "Anthropic batch item was canceled."
    if result_type == "expired":
        return "Anthropic batch item expired."
    return "Anthropic batch item failed."


def _batch_status(status: Any, request_counts: Any) -> BatchStatus:
    if status in {"in_progress", "canceling"}:
        return BatchStatus.RUNNING
    if status != "ended":
        return BatchStatus.FAILED
    counts = request_counts if isinstance(request_counts, dict) else {}
    if counts.get("errored", 0) > 0:
        return BatchStatus.FAILED
    if counts.get("canceled", 0) > 0:
        return BatchStatus.CANCELLED
    if counts.get("expired", 0) > 0:
        return BatchStatus.EXPIRED
    return BatchStatus.SUCCEEDED


def _datetime_from_rfc3339(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
