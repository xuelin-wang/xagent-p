import asyncio
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from xagent.agent_flow.config import AgentModelConfig
from xagent.agent_flow.llm_adapter import AgentFlowLLMAdapter, read_prompt_template
from xagent.agent_flow.models import (
    PlanSubagentSelection,
    SummaryDecision,
    SummaryOutput,
)
from xagent.agent_flow.planner import LLMPlannerDecision
from xagent.llm_batch.models import (
    BatchCreateRequest,
    BatchJob,
    BatchResults,
    EmbeddingRequest,
    EmbeddingResponse,
)
from xagent.llm_contracts import (
    Capability,
    GenerateRequest,
    GenerateResponse,
    ModelCapabilities,
)
from xagent.llm_files import FileDeleteRequest, FileUploadRequest, UploadedFile
from xagent.llm_structured import StructuredGenerateRequest, StructuredGenerateResponse

T = TypeVar("T", bound=BaseModel)


class FakeLLMProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.generate_requests: list[GenerateRequest] = []
        self.structured_requests: list[tuple[StructuredGenerateRequest, type[Any]]] = []

    def capabilities(self, model: str | None = None) -> ModelCapabilities:
        return ModelCapabilities(
            provider="fake",
            model=model or "fake",
            capabilities={Capability.TEXT_GENERATION, Capability.STRUCTURED_OUTPUT},
        )

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        self.generate_requests.append(request)
        return GenerateResponse(
            provider="fake", model=request.model or "fake", text="ok"
        )

    async def generate_structured(
        self,
        request: StructuredGenerateRequest,
        output_type: type[T],
    ) -> StructuredGenerateResponse[T]:
        self.structured_requests.append((request, output_type))
        payload: dict[str, Any]
        if output_type is LLMPlannerDecision:
            payload = {
                "goal": "inspect manuals",
                "selections": [
                    {"name": "manuals", "reason": "manuals are relevant"},
                    {"name": "unknown", "reason": "should be filtered"},
                ],
                "rationale": "planner rationale",
            }
        elif output_type is SummaryOutput:
            payload = {
                "decision": "final",
                "answer_draft": "summary answer",
                "rationale": "summary rationale",
            }
        else:
            payload = {}
        return StructuredGenerateResponse(
            provider="fake",
            model=request.model or "fake",
            data=output_type.model_validate(payload),
            raw_json=payload,
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError

    async def upload_file(self, request: FileUploadRequest) -> UploadedFile:
        raise NotImplementedError

    async def delete_file(self, request: FileDeleteRequest) -> None:
        raise NotImplementedError

    async def create_batch(self, request: BatchCreateRequest) -> BatchJob:
        raise NotImplementedError

    async def get_batch(self, batch_id: str) -> BatchJob:
        raise NotImplementedError

    async def cancel_batch(self, batch_id: str) -> BatchJob:
        raise NotImplementedError

    async def get_batch_results(self, batch_id: str) -> BatchResults:
        raise NotImplementedError


def test_adapter_generates_text_with_existing_generate_contract() -> None:
    provider = FakeLLMProvider()
    adapter = AgentFlowLLMAdapter(
        provider=provider,
        models={"reasoning": AgentModelConfig(model="fake-reasoning", temperature=0.2)},
    )

    result = asyncio.run(
        adapter.generate_text(
            model_name="reasoning",
            system_prompt="system",
            user_prompt="user",
            metadata={"run": "run_1"},
        )
    )

    assert result == "ok"
    request = provider.generate_requests[0]
    assert request.model == "fake-reasoning"
    assert request.temperature == 0.2
    assert [message.content for message in request.messages] == ["system", "user"]
    assert request.metadata == {"run": "run_1"}


def test_adapter_generates_structured_with_json_schema_contract() -> None:
    provider = FakeLLMProvider()
    adapter = AgentFlowLLMAdapter(
        provider=provider,
        models={"reasoning": AgentModelConfig(model="fake-reasoning")},
    )

    result = asyncio.run(
        adapter.generate_structured(
            model_name="reasoning",
            system_prompt="system",
            user_prompt="user",
            output_type=LLMPlannerDecision,
        )
    )

    assert result.goal == "inspect manuals"
    assert result.selections == [
        PlanSubagentSelection(name="manuals", reason="manuals are relevant"),
        PlanSubagentSelection(name="unknown", reason="should be filtered"),
    ]
    request, output_type = provider.structured_requests[0]
    assert output_type is LLMPlannerDecision
    assert request.response_format.schema_name == "LLMPlannerDecision"
    assert request.response_format.json_schema is not None


def test_read_prompt_template_reads_utf8_file(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")

    assert read_prompt_template(prompt) == "hello"


def test_adapter_rejects_unknown_model_name() -> None:
    provider = FakeLLMProvider()
    adapter = AgentFlowLLMAdapter(provider=provider, models={})

    with pytest.raises(KeyError, match="not configured"):
        asyncio.run(
            adapter.generate_text(
                model_name="missing",
                system_prompt="system",
                user_prompt="user",
            )
        )


def test_fake_provider_returns_summary_output() -> None:
    provider = FakeLLMProvider()
    adapter = AgentFlowLLMAdapter(
        provider=provider,
        models={"reasoning": AgentModelConfig(model="fake-reasoning")},
    )

    result = asyncio.run(
        adapter.generate_structured(
            model_name="reasoning",
            system_prompt="system",
            user_prompt="user",
            output_type=SummaryOutput,
        )
    )

    assert result.decision is SummaryDecision.FINAL
    assert result.answer_draft == "summary answer"
