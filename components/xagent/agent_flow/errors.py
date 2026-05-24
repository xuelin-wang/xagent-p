from __future__ import annotations

from typing import Any

from xagent.agent_persistence.repositories import StepRecord


class AgentFlowError(Exception):
    """Base exception for the custom agent-flow runtime."""


class StepRunnerError(AgentFlowError):
    """Raised when a durable step cannot produce a successful output."""

    def __init__(self, message: str, *, step: StepRecord, error_json: dict[str, Any]):
        super().__init__(message)
        self.step = step
        self.error_json = error_json


class StepWaiting(AgentFlowError):
    """Raised internally when a durable step enters a waiting state."""

    def __init__(
        self,
        *,
        step: StepRecord,
        output_json: dict[str, Any],
        wait_spec: Any,
        state: Any = None,
    ):
        super().__init__("Step is waiting.")
        self.step = step
        self.output_json = output_json
        self.wait_spec = wait_spec
        self.state = state


class NonRetryableStepError(AgentFlowError):
    """Raise from a step function to stop retrying that step."""
