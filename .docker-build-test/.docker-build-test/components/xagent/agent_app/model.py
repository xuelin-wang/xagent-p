from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class SubagentSelection:
    name: str
    reason: str


@dataclass(slots=True)
class PlannerStep:
    selections: list[SubagentSelection] = field(default_factory=list)
    notes: str = ""


@dataclass(slots=True)
class SubagentReply:
    name: str
    status: Literal["completed", "timeout", "error"]
    content: str
    duration_seconds: float


@dataclass(slots=True)
class AgentRunResult:
    query: str
    plan: PlannerStep
    subagent_replies: list[SubagentReply]
    final_reply: str
