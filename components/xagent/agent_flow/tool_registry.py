"""Tool registry and call validation.

Purpose: validate planned tool calls against registered tool metadata and
produce validated or rejected call records before execution.
Rationale: tool metadata lookup, validation, and policy resolution belong
together but must not be coupled to execution or persistence.
Design link: replay-resume-agent-system-design.md sections 9 and 10.
Public surface: ToolRegistry.validate_calls() is called by the
VALIDATE_TOOL_CALLS step (wired in Stage 6).
Non-goal: tool execution belongs in tools.py (Stage 6).

Policy resolution (design section 10, four levels):
  1. runtime default step policy
  2. tool_call step-type override
  Levels 1+2 are pre-merged by the caller into base_policy.
  3. tool metadata override (timeout_ms, deadline_ms, retry_policy)
  4. explicit per-call override on ValidatedToolCall — deferred to Stage 6
     when the VALIDATE_TOOL_CALLS step is wired into the runtime.

Validation checks in scope for Stage 5 (design section 10):
  - tool exists in registry
  - tool is enabled
  - call is not duplicated (by stable tool_call_id)
  - call fits max tool count (by priority order)
  - timeout/deadline policy is assigned from effective policy

Checks deferred to later stages (all recorded in validation_notes):
  - input matches schema (deferred — input_schema is stored but no validator
    is wired yet; full structured validation requires schema tooling)
  - call is permitted (deferred — permission model not yet defined)
  - call fits latency/cost budget (deferred — budget accounting not yet wired)
  - dataset is available (deferred — dataset availability check requires a
    live registry or manifest; dataset metadata is stored for future use)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from xagent.agent_flow.steps import RetryPolicy, StepExecutionPolicy
from xagent.config import StrictConfigModel

_DEFERRED_NOTES = [
    "schema validation deferred (Stage 6)",
    "permission check deferred (Stage 6)",
    "cost/latency budget check deferred (Stage 6)",
    "dataset availability check deferred (Stage 6)",
]


class ToolMetadata(StrictConfigModel):
    name: str
    version: str | None = None

    dataset_name: str | None = None
    dataset_version: str | None = None
    schema_version: str | None = None

    description: str = ""
    input_schema: str = ""
    output_schema: str = ""

    enabled: bool = True
    timeout_ms: int | None = None
    deadline_ms: int | None = None
    retry_policy: RetryPolicy | None = None
    cost_class: Literal["low", "medium", "high"] = "medium"
    latency_class: Literal["low", "medium", "high"] = "medium"


class PlannedToolCall(BaseModel):
    tool_name: str
    purpose: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100


class ValidatedToolCall(BaseModel):
    tool_call_id: str
    tool_name: str
    purpose: str
    input: dict[str, Any]
    idempotency_key: str
    # 0 means no timeout enforced; callers should treat 0 as "unbounded."
    # The design requires a concrete int here so the executor never has to
    # handle None. When no timeout is configured in the policy chain, the
    # registry sets 0.
    timeout_ms: int
    deadline_ms: int | None = None
    retry_policy: RetryPolicy | None = None
    validation_notes: list[str] = Field(default_factory=list)


class RejectedToolCall(BaseModel):
    tool_name: str
    reason: str


class ToolResult(BaseModel):
    tool_call_id: str
    tool_name: str
    status: Literal["succeeded", "failed", "timed_out", "skipped"]
    output_ref: str | None = None
    error_ref: str | None = None
    retryable: bool = False
    attempt_count: int = 0
    elapsed_ms: int | None = None


class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)

    source_tool: str
    source_dataset: str | None = None
    dataset_version: str | None = None

    retrieved_at: datetime
    confidence: Literal["low", "medium", "high"] | None = None


class ValidationResult(BaseModel):
    validated: list[ValidatedToolCall] = Field(default_factory=list)
    rejected: list[RejectedToolCall] = Field(default_factory=list)


class ToolRegistry:
    """Holds registered tools and validates planned calls against them."""

    def __init__(self, tools: list[ToolMetadata] | None = None) -> None:
        self._tools: dict[str, ToolMetadata] = (
            {t.name: t for t in tools} if tools else {}
        )

    def register(self, tool: ToolMetadata) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolMetadata | None:
        return self._tools.get(name)

    def validate_calls(
        self,
        *,
        run_id: str,
        iteration_index: int,
        planned_calls: list[PlannedToolCall],
        base_policy: StepExecutionPolicy,
        max_tools: int | None = None,
    ) -> ValidationResult:
        """Validate planned calls and return validated + rejected lists.

        Policy resolution: base_policy (levels 1+2 pre-merged by caller) is
        merged with tool metadata overrides (level 3). Level-4 per-call
        override is deferred to Stage 6.

        Calls are processed in ascending priority order. When max_tools is
        set, the lowest-priority excess calls are rejected.
        """
        validated: list[ValidatedToolCall] = []
        rejected: list[RejectedToolCall] = []
        seen_call_ids: set[str] = set()

        for call in sorted(planned_calls, key=lambda c: c.priority):
            metadata = self._tools.get(call.tool_name)

            if metadata is None:
                rejected.append(
                    RejectedToolCall(tool_name=call.tool_name, reason="unknown tool")
                )
                continue

            if not metadata.enabled:
                rejected.append(
                    RejectedToolCall(tool_name=call.tool_name, reason="tool disabled")
                )
                continue

            # tool_call_id: stable across resume for the same logical call.
            # Formula: {run_id}:{iteration_index}:{tool_name}:{sha256(input)[:12]}
            # The 12-hex-char hash prefix provides 48 bits of uniqueness —
            # sufficient for deduplication within a single run iteration.
            call_id = _stable_tool_call_id(
                run_id, iteration_index, call.tool_name, call.input
            )

            if call_id in seen_call_ids:
                rejected.append(
                    RejectedToolCall(
                        tool_name=call.tool_name, reason="duplicate call"
                    )
                )
                continue

            if max_tools is not None and len(validated) >= max_tools:
                rejected.append(
                    RejectedToolCall(
                        tool_name=call.tool_name, reason="exceeds max tool count"
                    )
                )
                continue

            effective = _resolve_tool_policy(base_policy, metadata)
            seen_call_ids.add(call_id)

            validated.append(
                ValidatedToolCall(
                    tool_call_id=call_id,
                    tool_name=call.tool_name,
                    purpose=call.purpose,
                    input=call.input,
                    # idempotency_key == tool_call_id for read-only tools.
                    # Write-side actuators may need a distinct key; that
                    # distinction is handled in Stage 6.
                    idempotency_key=call_id,
                    timeout_ms=effective.timeout_ms or 0,
                    deadline_ms=effective.deadline_ms,
                    retry_policy=effective.retry,
                    validation_notes=list(_DEFERRED_NOTES),
                )
            )

        return ValidationResult(validated=validated, rejected=rejected)


def _stable_tool_call_id(
    run_id: str,
    iteration_index: int,
    tool_name: str,
    input_data: dict[str, Any],
) -> str:
    normalized = json.dumps(input_data, sort_keys=True, ensure_ascii=True)
    hash_hex = hashlib.sha256(normalized.encode()).hexdigest()[:12]
    return f"{run_id}:{iteration_index}:{tool_name}:{hash_hex}"


def _resolve_tool_policy(
    base: StepExecutionPolicy, metadata: ToolMetadata
) -> StepExecutionPolicy:
    """Merge tool metadata overrides (level 3) on top of base policy (levels 1+2).

    Only fields explicitly set in metadata override the base; unset fields
    are inherited from base unchanged.
    """
    updates: dict[str, Any] = {}
    if metadata.timeout_ms is not None:
        updates["timeout_ms"] = metadata.timeout_ms
    if metadata.deadline_ms is not None:
        updates["deadline_ms"] = metadata.deadline_ms
    if metadata.retry_policy is not None:
        updates["retry"] = base.retry.merge(metadata.retry_policy)
    if not updates:
        return base.model_copy(deep=True)
    return base.model_copy(update=updates, deep=True)
