from typing import Protocol, TypeVar

from xagent.llm_batch.models import (
    BatchCreateRequest,
    BatchJob,
    BatchResults,
    EmbeddingRequest,
    EmbeddingResponse,
)
from xagent.llm_contracts import GenerateRequest, GenerateResponse, ModelCapabilities
from xagent.llm_files import FileDeleteRequest, FileUploadRequest, UploadedFile
from xagent.llm_structured import StructuredGenerateRequest, StructuredGenerateResponse

T = TypeVar("T")


class LLMProvider(Protocol):
    provider_name: str

    def capabilities(self, model: str | None = None) -> ModelCapabilities:
        ...

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        ...

    async def generate_structured(
        self,
        request: StructuredGenerateRequest,
        output_type: type[T],
    ) -> StructuredGenerateResponse[T]:
        ...

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        ...

    async def upload_file(self, request: FileUploadRequest) -> UploadedFile:
        ...

    async def delete_file(self, request: FileDeleteRequest) -> None:
        ...

    async def create_batch(self, request: BatchCreateRequest) -> BatchJob:
        ...

    async def get_batch(self, batch_id: str) -> BatchJob:
        ...

    async def cancel_batch(self, batch_id: str) -> BatchJob:
        ...

    async def get_batch_results(self, batch_id: str) -> BatchResults:
        ...
