import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from xagent.llm_contracts import LLMErrorPayload, StructuredOutputValidationError
from xagent.llm_structured.response_format import ResponseFormat, ResponseFormatType

T = TypeVar("T", bound=BaseModel)


def response_format_for_model(model_type: type[BaseModel], *, strict: bool = True) -> ResponseFormat:
    return ResponseFormat(
        type=ResponseFormatType.JSON_SCHEMA,
        schema_name=model_type.__name__,
        json_schema=model_type.model_json_schema(),
        strict=strict,
    )


def parse_json_object(raw_text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise StructuredOutputValidationError(
            LLMErrorPayload(
                provider="unknown",
                operation="parse_structured_output",
                message=f"Structured output is not valid JSON: {exc}",
                retryable=False,
            )
        ) from exc
    if not isinstance(loaded, dict):
        raise StructuredOutputValidationError(
            LLMErrorPayload(
                provider="unknown",
                operation="parse_structured_output",
                message="Structured output must be a JSON object.",
                retryable=False,
            )
        )
    return loaded


def validate_structured_output(
    raw_json: dict[str, Any],
    output_type: type[T],
    *,
    provider: str,
    model: str | None,
) -> T:
    try:
        return output_type.model_validate(raw_json)
    except ValidationError as exc:
        raise StructuredOutputValidationError(
            LLMErrorPayload(
                provider=provider,
                model=model,
                operation="validate_structured_output",
                message=f"Structured output failed validation: {exc}",
                retryable=False,
            )
        ) from exc
