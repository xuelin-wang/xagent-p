from __future__ import annotations

from xagent.agent_flow.models import (
    AgentFlowState,
    ConversationMessageEvent,
    WaitStepSpec,
)
from xagent.agent_flow.steps import RuntimeContext, StepResult


class MessageInputStep:
    """Durable input step for inbound conversation messages."""

    step_type = "message_input"

    def __init__(self, *, message: ConversationMessageEvent) -> None:
        self._message = message

    async def run(
        self,
        state: AgentFlowState,
        context: RuntimeContext,
    ) -> StepResult:
        _ = (state, context)
        return StepResult(
            output_json={
                "message": self._message.model_dump(mode="json"),
            }
        )


class WaitStep:
    """Durable pause step completed by the next conversation message."""

    step_type = "wait"

    def __init__(self, *, spec: WaitStepSpec) -> None:
        self._spec = spec

    async def run(
        self,
        state: AgentFlowState,
        context: RuntimeContext,
    ) -> StepResult:
        _ = (state, context)
        return StepResult(
            output_json={
                "wait_spec": self._spec.model_dump(mode="json"),
            },
            wait_spec=self._spec,
        )
