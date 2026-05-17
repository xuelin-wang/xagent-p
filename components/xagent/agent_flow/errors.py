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


class NonRetryableStepError(AgentFlowError):
    """Raise from a step function to stop retrying that step."""
