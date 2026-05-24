from __future__ import annotations

from typing import Literal

from pydantic import Field

from xagent.agent_flow.steps import RuntimeExecutionPolicy
from xagent.config import StrictConfigModel


class AgentWorkflowConfig(StrictConfigModel):
    name: str = "default_agent_flow"
    max_iterations: int = 3
    subagent_execution_mode: Literal["parallel", "sequential"] = "parallel"
    continue_on_subagent_failure: bool = True
    max_subagents_per_iteration: int = 5
    max_tool_rounds_per_subagent: int = 3
    require_new_evidence_for_replan: bool = False


class AgentModelConfig(StrictConfigModel):
    provider: Literal["fake", "openai", "anthropic"] = "fake"
    model: str = "fake"
    temperature: float = 0.0
    timeout_seconds: float = 60.0


class PlannerConfig(StrictConfigModel):
    name: str = "planner"
    prompt_template: str = "prompts/agent_flow/planner.md"
    model: str = "default_reasoning"
    max_attempts: int = 2


class SummaryConfig(StrictConfigModel):
    name: str = "summary"
    prompt_template: str = "prompts/agent_flow/summary.md"
    model: str = "default_reasoning"
    max_attempts: int = 2


class SubagentConfig(StrictConfigModel):
    name: str
    description: str
    prompt_template: str
    model: str = "default_reasoning"
    tools: list[str] = Field(default_factory=list)
    timeout_seconds: float = 60.0
    max_attempts: int = 2


class PersistenceConfig(StrictConfigModel):
    backend: Literal["memory", "postgres"] = "memory"
    dsn: str | None = None


class AgentFlowAppConfig(StrictConfigModel):
    workflow: AgentWorkflowConfig = Field(default_factory=AgentWorkflowConfig)
    execution_policy: RuntimeExecutionPolicy = Field(
        default_factory=RuntimeExecutionPolicy
    )
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    subagents: dict[str, SubagentConfig] = Field(default_factory=dict)
    models: dict[str, AgentModelConfig] = Field(default_factory=dict)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
