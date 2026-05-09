from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from xagent.llm_contracts import GenerateRequest, Usage

T = TypeVar("T")


class ResponseFormatType(str, Enum):
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class ResponseFormat(BaseModel):
    type: ResponseFormatType = ResponseFormatType.TEXT
    schema_name: str | None = None
    json_schema: dict[str, Any] | None = None
    strict: bool = True


class StructuredGenerateRequest(GenerateRequest):
    response_format: ResponseFormat
    validation_retries: int = 1


class StructuredGenerateResponse(BaseModel, Generic[T]):
    provider: str
    model: str
    data: T
    raw_json: dict[str, Any]
    usage: Usage | None = None
    raw_response: dict[str, Any] | None = None
