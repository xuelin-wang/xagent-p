from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from xagent.agent_flow.config import AgentModelConfig
from xagent.llm_contracts import GenerateRequest, Message, Role
from xagent.llm_registry import LLMProvider
from xagent.llm_structured import (
    ResponseFormat,
    ResponseFormatType,
    StructuredGenerateRequest,
)

T = TypeVar("T", bound=BaseModel)


class AgentFlowLLMAdapter:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        models: Mapping[str, AgentModelConfig],
    ):
        self._provider = provider
        self._models = dict(models)

    async def generate_text(
        self,
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        model_config = self._model_config(model_name)
        response = await self._provider.generate(
            GenerateRequest(
                model=model_config.model,
                messages=[
                    Message(role=Role.SYSTEM, content=system_prompt),
                    Message(role=Role.USER, content=user_prompt),
                ],
                temperature=model_config.temperature,
                metadata=metadata or {},
            )
        )
        return response.text or ""

    async def generate_structured(
        self,
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        output_type: type[T],
        metadata: dict[str, str] | None = None,
    ) -> T:
        model_config = self._model_config(model_name)
        response = await self._provider.generate_structured(
            StructuredGenerateRequest(
                model=model_config.model,
                messages=[
                    Message(role=Role.SYSTEM, content=system_prompt),
                    Message(role=Role.USER, content=user_prompt),
                ],
                temperature=model_config.temperature,
                response_format=ResponseFormat(
                    type=ResponseFormatType.JSON_SCHEMA,
                    schema_name=output_type.__name__,
                    json_schema=output_type.model_json_schema(),
                    strict=True,
                ),
                metadata=metadata or {},
            ),
            output_type,
        )
        return response.data

    def _model_config(self, model_name: str) -> AgentModelConfig:
        config = self._models.get(model_name)
        if config is None:
            raise KeyError(f"Agent flow model is not configured: {model_name}")
        return config


def read_prompt_template(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
