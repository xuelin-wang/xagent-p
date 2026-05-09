from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from xagent.llm_contracts import (
    GenerateRequest,
    GenerateResponse,
    LLMErrorPayload,
    Message,
    Role,
    ToolLoopExceededError,
)
from xagent.llm_tools.app_tools import AppToolDefinition
from xagent.llm_tools.validation import validate_app_tool_call


class AppToolExecutor(Protocol):
    def __call__(self, arguments: dict[str, Any]) -> Awaitable[Any]:
        ...


class ToolLoopProvider(Protocol):
    provider_name: str

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        ...


async def run_app_tool_loop(
    provider: ToolLoopProvider,
    request: GenerateRequest,
    executors: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]],
    max_rounds: int = 5,
) -> GenerateResponse:
    current = request
    definitions = {
        tool.name: tool
        for tool in current.app_tools
        if isinstance(tool, AppToolDefinition)
    }
    for _ in range(max_rounds):
        response = await provider.generate(current)
        if not response.app_tool_calls:
            return response

        messages = list(current.messages)
        for call in response.app_tool_calls:
            definition = definitions.get(call.name)
            if definition is not None:
                validate_app_tool_call(call, definition)
            executor = executors[call.name]
            result = await executor(call.arguments)
            messages.append(
                Message(
                    role=Role.TOOL,
                    content=str(result),
                    name=call.name,
                    tool_call_id=call.id,
                )
            )
        current = current.model_copy(update={"messages": messages})

    raise ToolLoopExceededError(
        LLMErrorPayload(
            provider=provider.provider_name,
            model=current.model,
            operation="run_app_tool_loop",
            message=f"App tool loop exceeded {max_rounds} rounds.",
            retryable=False,
        )
    )
