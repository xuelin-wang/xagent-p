from enum import Enum

from pydantic import BaseModel, Field

from xagent.llm_contracts.errors import LLMErrorPayload, UnsupportedCapabilityError


class Capability(str, Enum):
    TEXT_GENERATION = "text_generation"
    STRUCTURED_OUTPUT = "structured_output"
    APP_TOOL_CALLS = "app_tool_calls"
    PROVIDER_HOSTED_TOOLS = "provider_hosted_tools"
    MIXED_APP_AND_PROVIDER_TOOLS = "mixed_app_and_provider_tools"
    FILE_UPLOAD = "file_upload"
    FILE_INPUT = "file_input"
    EMBEDDINGS = "embeddings"
    NATIVE_BATCH = "native_batch"
    CONCURRENT_BATCH = "concurrent_batch"


class ModelCapabilities(BaseModel):
    provider: str
    model: str
    capabilities: set[Capability]
    provider_tools: set[str] = Field(default_factory=set)
    max_files_per_request: int | None = None
    max_file_size_bytes: int | None = None
    notes: str | None = None


def assert_capability(
    capabilities: ModelCapabilities,
    capability: Capability,
    *,
    operation: str = "capability_check",
) -> None:
    if capability in capabilities.capabilities:
        return
    raise UnsupportedCapabilityError(
        LLMErrorPayload(
            provider=capabilities.provider,
            model=capabilities.model,
            operation=operation,
            message=f"Capability {capability.value} is not supported.",
            retryable=False,
        )
    )
