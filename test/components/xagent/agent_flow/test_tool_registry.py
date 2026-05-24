from datetime import UTC, datetime

from xagent.agent_flow.steps import RetryPolicy, StepExecutionPolicy
from xagent.agent_flow.tool_registry import (
    EvidenceItem,
    PlannedToolCall,
    ToolMetadata,
    ToolRegistry,
    ToolResult,
    _stable_tool_call_id,
)

# ---------------------------------------------------------------------------
# stable tool_call_id
# ---------------------------------------------------------------------------


def test_stable_tool_call_id_is_deterministic() -> None:
    id1 = _stable_tool_call_id("run1", 0, "search", {"q": "foo"})
    id2 = _stable_tool_call_id("run1", 0, "search", {"q": "foo"})
    assert id1 == id2


def test_stable_tool_call_id_differs_on_input_change() -> None:
    id1 = _stable_tool_call_id("run1", 0, "search", {"q": "foo"})
    id2 = _stable_tool_call_id("run1", 0, "search", {"q": "bar"})
    assert id1 != id2


def test_stable_tool_call_id_differs_on_run_id_change() -> None:
    id1 = _stable_tool_call_id("run1", 0, "search", {"q": "foo"})
    id2 = _stable_tool_call_id("run2", 0, "search", {"q": "foo"})
    assert id1 != id2


def test_stable_tool_call_id_differs_on_iteration_change() -> None:
    id1 = _stable_tool_call_id("run1", 0, "search", {"q": "foo"})
    id2 = _stable_tool_call_id("run1", 1, "search", {"q": "foo"})
    assert id1 != id2


def test_stable_tool_call_id_input_key_order_independent() -> None:
    id1 = _stable_tool_call_id("run1", 0, "search", {"a": 1, "b": 2})
    id2 = _stable_tool_call_id("run1", 0, "search", {"b": 2, "a": 1})
    assert id1 == id2


# ---------------------------------------------------------------------------
# ValidationResult: happy path
# ---------------------------------------------------------------------------


def _registry_with_tools(*names: str, enabled: bool = True) -> ToolRegistry:
    tools = [
        ToolMetadata(name=name, description=f"Tool {name}", enabled=enabled)
        for name in names
    ]
    return ToolRegistry(tools=tools)


def _base_policy() -> StepExecutionPolicy:
    return StepExecutionPolicy(timeout_ms=5_000)


def test_validate_calls_returns_validated_call_for_known_enabled_tool() -> None:
    registry = _registry_with_tools("search")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="search", input={"q": "oil"})],
        base_policy=_base_policy(),
    )

    assert len(result.validated) == 1
    assert len(result.rejected) == 0
    vc = result.validated[0]
    assert vc.tool_name == "search"
    assert vc.tool_call_id == _stable_tool_call_id("run1", 0, "search", {"q": "oil"})
    assert vc.idempotency_key == vc.tool_call_id
    assert vc.timeout_ms == 5_000


def test_validated_call_propagates_purpose() -> None:
    registry = _registry_with_tools("search")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[
            PlannedToolCall(tool_name="search", purpose="find oil records", input={})
        ],
        base_policy=_base_policy(),
    )
    assert result.validated[0].purpose == "find oil records"


def test_validated_call_inherits_base_policy_retry() -> None:
    registry = _registry_with_tools("search")
    base = StepExecutionPolicy(
        timeout_ms=3_000,
        retry=RetryPolicy(max_attempts=3, retryable_error_types=["TimeoutError"]),
    )
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="search", input={})],
        base_policy=base,
    )
    vc = result.validated[0]
    assert vc.retry_policy is not None
    assert vc.retry_policy.max_attempts == 3
    assert vc.retry_policy.retryable_error_types == ["TimeoutError"]


def test_validated_call_has_deferred_validation_notes() -> None:
    registry = _registry_with_tools("search")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="search", input={})],
        base_policy=_base_policy(),
    )
    notes = result.validated[0].validation_notes
    assert any("schema" in n for n in notes)
    assert any("permission" in n for n in notes)
    assert any("cost" in n or "latency" in n for n in notes)
    assert any("dataset" in n for n in notes)


def test_validate_calls_is_deterministic() -> None:
    registry = _registry_with_tools("a", "b")
    calls = [
        PlannedToolCall(tool_name="a", input={"x": 1}),
        PlannedToolCall(tool_name="b", input={"x": 2}),
    ]
    result1 = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=calls,
        base_policy=_base_policy(),
    )
    result2 = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=calls,
        base_policy=_base_policy(),
    )
    assert result1 == result2


# ---------------------------------------------------------------------------
# timeout_ms fallback when no timeout is configured
# ---------------------------------------------------------------------------


def test_validated_call_timeout_ms_zero_when_policy_has_no_timeout() -> None:
    registry = _registry_with_tools("t")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="t", input={})],
        base_policy=StepExecutionPolicy(),  # timeout_ms=None
    )
    # 0 signals "no timeout enforced" when neither base policy nor tool
    # metadata configures one.
    assert result.validated[0].timeout_ms == 0


# ---------------------------------------------------------------------------
# Rejection: unknown tool
# ---------------------------------------------------------------------------


def test_validate_calls_rejects_unknown_tool() -> None:
    registry = ToolRegistry()
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="ghost", input={})],
        base_policy=_base_policy(),
    )
    assert len(result.validated) == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].tool_name == "ghost"
    assert result.rejected[0].reason == "unknown tool"


# ---------------------------------------------------------------------------
# Rejection: disabled tool
# ---------------------------------------------------------------------------


def test_validate_calls_rejects_disabled_tool() -> None:
    registry = _registry_with_tools("search", enabled=False)
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="search", input={})],
        base_policy=_base_policy(),
    )
    assert len(result.validated) == 0
    assert result.rejected[0].reason == "tool disabled"


# ---------------------------------------------------------------------------
# Rejection: duplicate call
# ---------------------------------------------------------------------------


def test_validate_calls_rejects_duplicate_call() -> None:
    registry = _registry_with_tools("search")
    call = PlannedToolCall(tool_name="search", input={"q": "oil"})
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[call, call],
        base_policy=_base_policy(),
    )
    assert len(result.validated) == 1
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "duplicate call"


def test_validate_calls_allows_same_tool_with_different_inputs() -> None:
    registry = _registry_with_tools("search")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[
            PlannedToolCall(tool_name="search", input={"q": "oil"}),
            PlannedToolCall(tool_name="search", input={"q": "filter"}),
        ],
        base_policy=_base_policy(),
    )
    assert len(result.validated) == 2
    assert len(result.rejected) == 0


# ---------------------------------------------------------------------------
# Rejection: max tool count, with priority ordering
# ---------------------------------------------------------------------------


def test_validate_calls_enforces_max_tools() -> None:
    registry = _registry_with_tools("a", "b", "c")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[
            PlannedToolCall(tool_name="a", input={}),
            PlannedToolCall(tool_name="b", input={}),
            PlannedToolCall(tool_name="c", input={}),
        ],
        base_policy=_base_policy(),
        max_tools=2,
    )
    assert len(result.validated) == 2
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "exceeds max tool count"


def test_validate_calls_max_tools_selects_by_priority() -> None:
    registry = _registry_with_tools("low_pri", "high_pri", "mid_pri")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[
            PlannedToolCall(tool_name="low_pri", input={}, priority=300),
            PlannedToolCall(tool_name="high_pri", input={}, priority=10),
            PlannedToolCall(tool_name="mid_pri", input={}, priority=200),
        ],
        base_policy=_base_policy(),
        max_tools=2,
    )
    validated_names = {vc.tool_name for vc in result.validated}
    rejected_names = {rc.tool_name for rc in result.rejected}
    assert validated_names == {"high_pri", "mid_pri"}
    assert rejected_names == {"low_pri"}


# ---------------------------------------------------------------------------
# Policy resolution: tool metadata overrides base
# ---------------------------------------------------------------------------


def test_tool_metadata_timeout_overrides_base_policy() -> None:
    tool = ToolMetadata(name="slow_tool", description="slow", timeout_ms=30_000)
    registry = ToolRegistry(tools=[tool])
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="slow_tool", input={})],
        base_policy=StepExecutionPolicy(timeout_ms=5_000),
    )
    assert result.validated[0].timeout_ms == 30_000


def test_tool_metadata_deadline_overrides_base_policy() -> None:
    tool = ToolMetadata(name="t", description="t", deadline_ms=60_000)
    registry = ToolRegistry(tools=[tool])
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="t", input={})],
        base_policy=StepExecutionPolicy(timeout_ms=5_000),
    )
    assert result.validated[0].deadline_ms == 60_000


def test_tool_metadata_retry_merges_with_base_retry() -> None:
    tool = ToolMetadata(
        name="t",
        description="t",
        retry_policy=RetryPolicy(max_attempts=5),
    )
    registry = ToolRegistry(tools=[tool])
    base = StepExecutionPolicy(
        timeout_ms=1_000,
        retry=RetryPolicy(
            max_attempts=2,
            backoff_initial_ms=200,
            retryable_error_types=["NetworkError"],
        ),
    )
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="t", input={})],
        base_policy=base,
    )
    rp = result.validated[0].retry_policy
    assert rp is not None
    assert rp.max_attempts == 5
    assert rp.backoff_initial_ms == 200
    assert rp.retryable_error_types == ["NetworkError"]


def test_tool_metadata_unset_fields_inherit_base_timeout() -> None:
    tool = ToolMetadata(name="t", description="t")
    registry = ToolRegistry(tools=[tool])
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[PlannedToolCall(tool_name="t", input={})],
        base_policy=StepExecutionPolicy(timeout_ms=9_000, deadline_ms=20_000),
    )
    vc = result.validated[0]
    assert vc.timeout_ms == 9_000
    assert vc.deadline_ms == 20_000


# ---------------------------------------------------------------------------
# ToolResult model
# ---------------------------------------------------------------------------


def test_tool_result_succeeded_status() -> None:
    result = ToolResult(
        tool_call_id="run1:0:search:abc123",
        tool_name="search",
        status="succeeded",
        output_ref="artifact://runs/run1/steps/001/output.json",
        attempt_count=1,
        elapsed_ms=120,
    )
    assert result.status == "succeeded"
    assert result.output_ref is not None
    assert result.elapsed_ms == 120


def test_tool_result_preserves_all_failure_fields() -> None:
    result = ToolResult(
        tool_call_id="run1:0:search:abc123",
        tool_name="search",
        status="failed",
        error_ref="artifact://runs/run1/steps/001/error.json",
        retryable=True,
        attempt_count=3,
        elapsed_ms=4_500,
    )
    assert result.status == "failed"
    assert result.retryable is True
    assert result.attempt_count == 3
    assert result.elapsed_ms == 4_500
    assert result.error_ref is not None


def test_tool_result_timed_out_status() -> None:
    result = ToolResult(
        tool_call_id="run1:0:search:abc123",
        tool_name="search",
        status="timed_out",
        retryable=True,
        attempt_count=1,
    )
    assert result.status == "timed_out"


def test_tool_result_skipped_status() -> None:
    result = ToolResult(
        tool_call_id="run1:0:search:abc123",
        tool_name="search",
        status="skipped",
    )
    assert result.status == "skipped"
    assert result.attempt_count == 0


# ---------------------------------------------------------------------------
# EvidenceItem model
# ---------------------------------------------------------------------------


def test_evidence_item_stores_source_metadata() -> None:
    item = EvidenceItem(
        evidence_id="ev_001",
        evidence_type="vehicle_history",
        summary="3 prior repairs",
        payload={"count": 3},
        source_tool="history_tool",
        source_dataset="repair_history",
        dataset_version="v2",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
        confidence="high",
    )
    assert item.source_tool == "history_tool"
    assert item.dataset_version == "v2"
    assert item.confidence == "high"


def test_evidence_item_optional_fields_default_to_none() -> None:
    item = EvidenceItem(
        evidence_id="ev_002",
        evidence_type="sensor",
        summary="voltage ok",
        source_tool="sensor_tool",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    assert item.source_dataset is None
    assert item.dataset_version is None
    assert item.confidence is None


# ---------------------------------------------------------------------------
# RejectedToolCall recorded for audit
# ---------------------------------------------------------------------------


def test_all_rejected_calls_are_recorded() -> None:
    registry = _registry_with_tools("a")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[
            PlannedToolCall(tool_name="ghost1", input={}),
            PlannedToolCall(tool_name="ghost2", input={}),
        ],
        base_policy=_base_policy(),
    )
    assert len(result.rejected) == 2
    rejected_names = {r.tool_name for r in result.rejected}
    assert rejected_names == {"ghost1", "ghost2"}


def test_mixed_valid_and_invalid_calls_recorded_separately() -> None:
    registry = _registry_with_tools("known")
    result = registry.validate_calls(
        run_id="run1",
        iteration_index=0,
        planned_calls=[
            PlannedToolCall(tool_name="known", input={}),
            PlannedToolCall(tool_name="unknown", input={}),
        ],
        base_policy=_base_policy(),
    )
    assert len(result.validated) == 1
    assert len(result.rejected) == 1
    assert result.validated[0].tool_name == "known"
    assert result.rejected[0].tool_name == "unknown"
