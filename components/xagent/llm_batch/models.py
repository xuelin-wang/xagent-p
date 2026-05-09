from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from xagent.llm_contracts import GenerateRequest, GenerateResponse, LLMErrorPayload


class EmbeddingRequest(BaseModel):
    model: str | None = None
    inputs: list[str]
    dimensions: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class EmbeddingVector(BaseModel):
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    provider: str
    model: str
    vectors: list[EmbeddingVector]
    dimensions: int
    usage: Any | None = None
    raw_response: dict[str, Any] | None = None


class ConcurrentBatchRequest(BaseModel):
    requests: list[GenerateRequest]
    max_concurrency: int = 8
    fail_fast: bool = False


class ConcurrentBatchResult(BaseModel):
    index: int
    custom_id: str | None = None
    response: GenerateResponse | None = None
    error: LLMErrorPayload | None = None


class BatchRequestItem(BaseModel):
    custom_id: str
    request: Any


class BatchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Native providers build/upload batch input from items; pre-uploaded input files are intentionally unsupported.
    model: str | None = None
    items: list[BatchRequestItem]
    mode: Literal["native", "concurrent"] = "native"
    metadata: dict[str, str] = Field(default_factory=dict)


class BatchStatus(str, Enum):
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BatchJob(BaseModel):
    provider: str
    batch_id: str
    status: BatchStatus
    created_at: datetime | None = None
    completed_at: datetime | None = None
    request_counts: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)
    raw_response: dict[str, Any] | None = None


class BatchResultItem(BaseModel):
    custom_id: str
    response: Any | None = None
    error: LLMErrorPayload | None = None
    raw: dict[str, Any] | None = None


class BatchResults(BaseModel):
    provider: str
    batch_id: str
    status: BatchStatus
    items: list[BatchResultItem]
    raw_response: dict[str, Any] | None = None
