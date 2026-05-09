import asyncio
from typing import Protocol

from xagent.llm_batch.models import ConcurrentBatchRequest, ConcurrentBatchResult
from xagent.llm_contracts import GenerateRequest, GenerateResponse, LLMError


class BatchGenerateProvider(Protocol):
    provider_name: str

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        ...


async def generate_many(
    provider: BatchGenerateProvider,
    batch: ConcurrentBatchRequest,
) -> list[ConcurrentBatchResult]:
    semaphore = asyncio.Semaphore(batch.max_concurrency)
    results: list[ConcurrentBatchResult | None] = [None] * len(batch.requests)

    async def _run_one(index: int) -> None:
        async with semaphore:
            try:
                response = await provider.generate(batch.requests[index])
            except LLMError as exc:
                if batch.fail_fast:
                    raise
                results[index] = ConcurrentBatchResult(index=index, error=exc.payload)
            else:
                results[index] = ConcurrentBatchResult(index=index, response=response)

    await asyncio.gather(*(_run_one(index) for index in range(len(batch.requests))))
    return [result for result in results if result is not None]
