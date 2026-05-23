Below is an updated, more minimal design focused on **adaptability, auditability, replayability, pause/resume, and architectural simplicity**.

---

# Minimal Auditable Agentic Runtime Design

## 1. Core idea

Build the system around one simple principle:

> Replay, audit, pause/resume, and evaluation should not be separate special features. They should naturally fall out of a step-based runtime, immutable ledger, versioned snapshots, and serializable checkpoints.

The runtime should stay small:

```text
structured input
→ build context
→ plan
→ validate tool calls
→ execute tools
→ merge results
→ decide
→ respond or iterate
```

The system is adaptable because prompts, tools, datasets, policies, models, and limits are configurable and versioned. The runtime itself stays mostly stable.

## 1.1 Why this shape

The design should keep the core runtime small and stable:

```text
fixed state machine
generic step execution
append-only step events
checkpoint-aligned completion
versioned snapshots
artifact references
execution policy
```

Planner behavior, tool calls, merge logic, decisions, user waits, responses, replay, and evaluation should be built around that core rather than added as independent subsystems.

Principles:

- Minimalist core: generic runtime code should own orchestration, step execution, events, checkpoints, snapshots, artifacts, and policy; it should not own planner/tool/response domain logic.
- Specialized edges: planner, tool calls, merge, decision, ask-user, and response are specialized steps using the same runtime contract.
- Adaptable by configuration: prompts, tools, datasets, models, policies, limits, and evaluators should be configured and snapshotted rather than hard-coded in the runtime.
- Append-only truth: step events are the durable source of truth; projections exist for fast reads and must be rebuildable.
- Failure is first-class: timeout, deadline, retry, partial failure, pause, waiting-for-user, and resume are normal runtime states with explicit records.
- Small extensions: new files and functions should have a clear responsibility, rationale, design-section link, tests, and non-goals.

---

# 2. Minimal state machine

Use a fixed state machine:

```text
START
  ↓
BUILD_CONTEXT
  ↓
PLAN
  ↓
VALIDATE_TOOL_CALLS
  ↓
EXECUTE_TOOLS
  ↓
MERGE_RESULTS
  ↓
DECIDE
  ├── REPLAN → PLAN
  ├── ASK_USER → WAIT_FOR_USER
  ├── RESPOND → RESPONSE
  └── STOP_LIMIT → RESPONSE
WAIT_FOR_USER
  └── USER_INPUT_RECEIVED → BUILD_CONTEXT
RESPONSE
  ↓
END
```

`ASK_USER` is not a final answer. It emits a question or request for clarification, checkpoints the state, and moves the run to `waiting_for_user`.

`RESPONSE` is only for terminal user-visible output:

```text
final answer
limit/stop response
terminal failure response, if exposed to the user
```

`VALIDATE_TOOL_CALLS` replaces `APPROVE_TOOL_CALLS`.

This name is better because it does **not** imply human approval. It means:

```text
planner proposes tool calls
runtime validates and prepares executable tool calls
executor runs only validated calls
```

---

# 3. Step-based runtime

The runtime should treat every phase as a durable step.

Each step follows the same contract:

```text
input state + config snapshot
→ step execution
→ output state
→ checkpoint
→ step success record linked to checkpoint
```

All steps should use the same reusable execution pattern:

```python
class RuntimeStep(Protocol):
    step_type: str

    async def run(
        self,
        state: AgentState,
        context: RuntimeContext,
    ) -> StepResult:
        ...
```

This avoids special framework logic for planner, tools, merge, and response. They are all just steps.

---

# 4. Core reusable components

Keep the system small by using a few generic components.

```text
AgentRuntime
  Runs the fixed state machine.

StepExecutor
  Executes one step using a common contract.

StepEventLedger
  Append-only source of truth for step lifecycle events.

StepProjectionStore
  Rebuildable current-state view of steps derived from step events.

CheckpointStore
  Stores serializable state after each step.

SnapshotStore
  Stores config, prompt, tool, dataset, and model versions.

ArtifactStore
  Stores large JSON payloads, inputs, outputs, and raw tool results.

ToolRegistry
  Holds available dataset-backed tools and metadata.

ReplayEngine
  Reads ledger + artifacts + checkpoints to reconstruct execution.

Evaluator
  Scores completed recorded runs.
```

The important point: **audit, replay, resume, and evaluation reuse the same records**.

Do not create separate mechanisms for each.

---

# 5. Append-only step event ledger

Every step writes append-only lifecycle events.

The key invariant is:

> A step is complete only when its output, state-after checkpoint, and `step_succeeded` event are committed as one logical unit.

This keeps resume simple and preserves a true immutable audit trail. If a process crashes before that logical commit finishes, the step is treated as incomplete and may be retried. Nondeterministic or side-effecting steps still need idempotency keys so retry is safe.

```python
class StepEvent(BaseModel):
    event_id: str
    run_id: str
    step_id: str
    parent_step_id: str | None = None
    sequence_index: int
    iteration_index: int
    step_type: str
    attempt_index: int = 1
    tool_call_id: str | None = None
    idempotency_key: str | None = None

    event_type: Literal[
        "step_started",
        "step_succeeded",
        "step_failed",
        "step_timed_out",
        "step_paused",
        "step_skipped",
    ]

    input_ref: str | None = None
    output_ref: str | None = None

    state_before_ref: str | None = None
    state_after_ref: str | None = None
    checkpoint_id: str | None = None

    flow_decision: str | None = None
    next_step_type: str | None = None

    snapshot_id: str

    occurred_at: datetime

    error_ref: str | None = None
```

`StepRecord` is a read model, not the immutable source of truth:

```python
class StepRecord(BaseModel):
    step_id: str
    run_id: str
    parent_step_id: str | None = None
    sequence_index: int
    iteration_index: int
    step_type: str
    attempt_count: int = 0
    tool_call_id: str | None = None
    idempotency_key: str | None = None

    status: Literal[
        "pending",
        "running",
        "succeeded",
        "failed",
        "timed_out",
        "paused",
        "skipped",
    ]

    latest_event_id: str
    input_ref: str | None = None
    output_ref: str | None = None
    state_before_ref: str | None = None
    state_after_ref: str | None = None
    checkpoint_id: str | None = None
    next_step_type: str | None = None
    error_ref: str | None = None
```

The `steps` projection can be stored for fast runtime queries, but it must be rebuildable from `step_events`. If projection update fails after an event append, replaying `step_events` repairs the projection.

Large data should live in an artifact store:

```text
input_ref        → artifact://runs/run_123/steps/001/input.json
output_ref       → artifact://runs/run_123/steps/001/output.json
state_before_ref → artifact://runs/run_123/steps/001/state_before.json
state_after_ref  → artifact://runs/run_123/steps/001/state_after.json
```

The database stores event references and projection metadata. The artifact store stores full payloads.

---

# 6. Serializable state

The runtime state should be explicit and serializable.

```python
class AgentState(BaseModel):
    run_id: str
    iteration_index: int = 0

    input_query: AgentInput
    user_input_events: list[UserInputEvent] = []

    conversation_summary: str | None = None

    planned_tool_calls: list[PlannedToolCall] = []
    validated_tool_calls: list[ValidatedToolCall] = []
    tool_results: list[ToolResult] = []

    evidence: list[EvidenceItem] = []

    merge_analysis: MergeAnalysis | None = None
    decision: RuntimeDecision | None = None
    pending_user_request: UserRequest | None = None

    final_response: AgentResponse | None = None
```

Each step consumes one state and produces a new state.

That makes the system naturally:

```text
auditable
checkpointable
replayable
resumable
testable
```

---

# 7. Checkpoints

Every successful step creates exactly one checkpoint.

The checkpoint is the durable state-after image for that step. The runtime should not append `step_succeeded` until the checkpoint exists and the event points to it.

```python
class RuntimeCheckpoint(BaseModel):
    checkpoint_id: str
    run_id: str
    after_step_id: str
    sequence_index: int

    state_ref: str
    next_step_type: str
    iteration_index: int

    snapshot_id: str
    created_at: datetime
```

Resume becomes simple:

```text
load latest step_succeeded event for the run by sequence_index
load that event's checkpoint
load state
load snapshot
continue from next_step_type
```

Rule:

> Resume should never re-run a completed nondeterministic step unless explicitly requested.

If an LLM planner step already completed, resume should reuse its recorded output.

Incomplete step rule:

```text
started/failed/timed_out event without a later step_succeeded checkpoint
→ incomplete
→ eligible for retry according to retry/idempotency policy
```

Recommended commit order:

```text
run step
write output artifact
write state_after artifact
save checkpoint for state_after + next_step_type
append step_succeeded event with checkpoint_id
update derived step projection
```

For a database-backed implementation, save the checkpoint row and append the `step_succeeded` event in one transaction. Projection updates may happen in the same transaction for convenience, but correctness must come from the append-only event. For an artifact-backed implementation, write artifacts first and only then commit the checkpoint and success event metadata.

## Execution policy, retries, timeouts, and deadlines

Every step should resolve an execution policy before it runs.

Use global defaults first. A step may define an optional override. If a field is not set on the step override, inherit the global value.

```python
class RetryPolicy(BaseModel):
    max_attempts: int = 1
    backoff_initial_ms: int = 0
    backoff_max_ms: int | None = None
    backoff_multiplier: float = 1.0
    retryable_error_types: list[str] = Field(default_factory=list)


class StepExecutionPolicy(BaseModel):
    timeout_ms: int | None = None       # per attempt
    deadline_ms: int | None = None      # total wall-clock budget for this step
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    continue_on_failure: bool = False


class RuntimeExecutionPolicy(BaseModel):
    default_step_policy: StepExecutionPolicy
    step_overrides: dict[str, StepExecutionPolicy] = Field(default_factory=dict)
```

Resolution:

```text
effective_policy = runtime.default_step_policy merged with step_overrides[step_type]
```

For tool calls, the lookup may be more specific:

```text
runtime default
→ step_type override for "tool_call"
→ tool metadata/config override for the specific tool
→ validated call override, if explicitly set
```

Timeout and deadline semantics:

```text
timeout_ms
  maximum duration for one attempt

deadline_ms
  maximum total wall-clock duration for all attempts of the same step/tool_call_id,
  including backoff
```

Retry semantics:

```text
on attempt failure:
  write error artifact
  append step_failed or step_timed_out event with error_ref
  if retryable and attempts remain and deadline remains:
    back off according to policy
    append a new step_started event with the next attempt_index
  else:
    terminal failure for that step
```

A timeout is retryable only if policy says timeout errors are retryable.

Write-side actuators are stricter:

```text
if the tool has external side effects:
  retries require a stable idempotency_key
  retries should forward the key to the external system when supported
  if idempotency cannot be guaranteed, default to no automatic retry
```

---

# 8. Versioned snapshot

Each run should point to a snapshot.

```python
class RunSnapshot(BaseModel):
    snapshot_id: str

    config_ref: str
    prompt_refs: list[str]
    tool_registry_ref: str
    dataset_manifest_refs: list[str]
    model_config_ref: str | None = None

    code_version: str | None = None
    container_image_digest: str | None = None
    git_commit: str | None = None

    created_at: datetime
```

Snapshot these things:

```text
runtime config
planner / merge / response prompts
tool registry
tool metadata
dataset versions
dataset schema versions
model config
code version
container image digest, if available
```

This gives you reproducibility and auditability without requiring perfect deterministic re-execution.

---

# 9. Dataset-backed tools

Dataset tools should be treated as versioned sensors.

A tool has a stable contract:

```python
class ToolMetadata(BaseModel):
    name: str
    version: str | None = None

    dataset_name: str | None = None
    dataset_version: str | None = None
    schema_version: str | None = None

    description: str
    input_schema: str
    output_schema: str

    enabled: bool = True
    timeout_ms: int | None = None
    deadline_ms: int | None = None
    retry_policy: RetryPolicy | None = None
    cost_class: Literal["low", "medium", "high"] = "medium"
    latency_class: Literal["low", "medium", "high"] = "medium"
```

The agent should not care whether the dataset is stored in BigQuery, Postgres, Parquet, DuckDB, GCS, or an API.

The tool hides storage details and returns normalized evidence.

```python
class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    summary: str
    payload: dict[str, Any]

    source_tool: str
    source_dataset: str | None = None
    dataset_version: str | None = None

    retrieved_at: datetime
    confidence: Literal["low", "medium", "high"] | None = None
```

---

# 10. What `VALIDATE_TOOL_CALLS` does

The planner proposes tool calls. The runtime validates them.

This step checks:

```text
tool exists
tool is enabled
input matches schema
call is permitted
call is not duplicated
call fits max tool count
call fits latency/cost budget
dataset is available
timeout/deadline policy is assigned
```

Input:

```python
class PlannedToolCall(BaseModel):
    tool_name: str
    purpose: str
    input: dict[str, Any]
    priority: int = 100
```

Output:

```python
class ValidatedToolCall(BaseModel):
    tool_call_id: str
    tool_name: str
    purpose: str
    input: dict[str, Any]
    idempotency_key: str
    timeout_ms: int
    deadline_ms: int | None = None
    retry_policy: RetryPolicy | None = None
    validation_notes: list[str] = []
```

`tool_call_id` must be stable for the planned call within the run. A simple default is:

```text
{run_id}:{iteration_index}:{tool_name}:{normalized_input_hash}
```

`idempotency_key` should be passed to tool implementations and, for external APIs or write-side actuators, forwarded to the external system when supported.

The validated call should include the effective timeout, deadline, and retry policy after global defaults and tool-specific overrides are resolved.

Rejected calls should also be recorded:

```python
class RejectedToolCall(BaseModel):
    tool_name: str
    reason: str
```

Tool results should preserve terminal failure information for merge, decision, audit, and evaluation:

```python
class ToolResult(BaseModel):
    tool_call_id: str
    tool_name: str
    status: Literal["succeeded", "failed", "timed_out", "skipped"]
    output_ref: str | None = None
    error_ref: str | None = None
    retryable: bool = False
    attempt_count: int = 0
    elapsed_ms: int | None = None
```

This is useful for audit and evaluation:

```text
Planner selected repair_history_tool.
Runtime rejected it because the dataset was disabled.

Planner selected 8 tools.
Runtime kept the top 4 due to max_tools_per_iteration.
```

---

# 11. Per-call tool execution durability

`EXECUTE_TOOLS` is an orchestration phase, not one monolithic durable unit.

Each validated tool call must run as its own child durable step:

```text
EXECUTE_TOOLS parent step
  ├── tool_call child step: tool_call_id=A
  ├── tool_call child step: tool_call_id=B
  └── tool_call child step: tool_call_id=C
```

The child step uses:

```text
step_type = "tool_call"
parent_step_id = execute_tools_step_id
tool_call_id = validated_tool_call.tool_call_id
idempotency_key = validated_tool_call.idempotency_key
```

Resume rule:

```text
for each validated tool call:
  if a child step_succeeded event exists for tool_call_id:
    reuse recorded tool result
  elif a terminal failed/timed_out child step exists and retry policy is exhausted:
    reuse recorded terminal failure result
  else:
    execute or retry that tool call according to policy
```

This prevents duplicate work after a partial crash. If three tools are selected and the first succeeds before the process exits, resume reuses the first result and only runs the remaining two.

Write-side actuators need stricter handling:

```text
must have stable idempotency_key
must record request and response artifacts
should forward idempotency_key to the external system
should require validation or human approval when policy says so
should not automatically retry unless idempotency is guaranteed
must not be blindly re-executed if prior success is recorded
```

The parent `EXECUTE_TOOLS` step succeeds only after all required child tool-call steps have reached a terminal status and the merged `tool_results` state has been checkpointed. The parent output should reference the child step IDs rather than duplicating large result payloads.

Parent failure behavior is configurable:

```text
required tool failed/timed_out and continue_on_failure = false
→ parent EXECUTE_TOOLS fails

optional tool failed/timed_out, or continue_on_failure = true
→ parent EXECUTE_TOOLS succeeds with terminal ToolResult entries
→ MERGE_RESULTS / DECIDE determines whether to answer, replan, ask user, or fail
```

---

# 12. Replay model

Replay should have clear modes.

## Audit playback

No execution. Just reconstruct the recorded flow from ledger and artifacts.

```text
show what happened
show step inputs/outputs
show tool choices
show flow path
show final response
```

## Deterministic replay

Re-run only deterministic steps and compare output with recorded output.

Good for:

```text
schema validation
tool-call validation
normalization
policy checks
state reducers
```

## Re-execution

Re-run LLMs or tools using the same input and snapshot.

This should create a **new run**, because external systems and LLMs may produce different outputs.

---

# 13. Pause and resume

Pause should happen at step boundaries.

Useful pause points:

```text
after PLAN
before EXECUTE_TOOLS
after EXECUTE_TOOLS
before RESPONSE
before any write-side actuator
```

Pause is just a completed step checkpoint plus a paused run status:

```text
step completed
checkpoint written and linked from the step_succeeded event
run status = paused
```

Resume is:

```text
load latest step_succeeded event checkpoint by sequence_index
restore state
continue from next_step_type
```

No special pause/resume architecture is needed.

Waiting for user input is a specific pause state:

```text
ASK_USER step succeeds
checkpoint is written with pending_user_request
run status = waiting_for_user
next_step_type = WAIT_FOR_USER
```

The user reply is recorded as an append-only input event:

```python
class UserInputEvent(BaseModel):
    event_id: str
    run_id: str
    request_id: str
    input_ref: str
    occurred_at: datetime
```

The pending request should also be explicit in state:

```python
class UserRequest(BaseModel):
    request_id: str
    prompt: str
    required: bool = True
```

Resume with user input:

```text
append UserInputEvent
load latest step_succeeded checkpoint
restore state
attach user input event to state.user_input_events
clear pending_user_request
set run status = running
continue from BUILD_CONTEXT or the configured next step
```

The original run continues; this is not a new run. The new user input is an explicit durable input record so audit playback can show exactly where the agent paused and what user data resumed it.

---

# 14. Evaluation as a natural consequence

Evaluation should consume recorded runs.

It should not need to re-run the agent.

Evaluator input:

```text
run record
step event ledger
user input events
final response
planner output
validated tool calls
tool results
evidence items
merge analysis
snapshot
```

Example metrics:

```text
answer quality
grounding quality
tool selection quality
missed expected tools
unnecessary tool calls
unsupported claims
latency
cost
number of iterations
timeout rate
```

Because every run has a ledger and snapshot, evaluation becomes straightforward.

---

# 15. PEAS mapping

Use PEAS as an organizing concept, not as extra architecture.

```text
Performance
  Evaluators and objectives:
  correctness, grounding, latency, cost, actionability, uncertainty handling.

Environment
  User, conversation, case state, datasets, external APIs, tool availability.

Sensors
  Read paths:
  dataset query tools, RAG retrieval, case readers, conversation readers,
  previous evidence readers.

Actuators
  Actions that affect the environment:
  ask user, render response, update case state, create diagnostic plan,
  write case note, escalate, trigger workflow.
```

Most dataset query tools are primarily **sensors**.

Write-side actions are stronger **actuators** and should have stricter validation, audit, and possibly human approval.

---

# 16. Minimal durable data model

Use only a few durable concepts:

```text
runs
snapshots
user_input_events
step_events
steps projection
checkpoints
artifacts
evaluations
```

That is enough.

```text
runs
  id
  status
  input_ref
  snapshot_id
  started_at
  finished_at
  final_response_ref

run status should include:
  pending
  running
  paused
  waiting_for_user
  completed
  failed

user_input_events
  event_id
  run_id
  request_id
  input_ref
  occurred_at

snapshots
  id
  config_ref
  prompt_refs
  tool_registry_ref
  dataset_manifest_refs
  model_config_ref
  code_version

step_events
  event_id
  run_id
  step_id
  parent_step_id
  sequence_index
  iteration_index
  step_type
  attempt_index
  tool_call_id
  idempotency_key
  event_type
  input_ref
  output_ref
  state_before_ref
  state_after_ref
  checkpoint_id
  next_step_type
  error_ref
  snapshot_id
  occurred_at

steps projection
  id
  run_id
  parent_step_id
  sequence_index
  iteration_index
  step_type
  attempt_count
  tool_call_id
  idempotency_key
  status
  latest_event_id
  input_ref
  output_ref
  state_before_ref
  state_after_ref
  checkpoint_id
  next_step_type
  error_ref

checkpoints
  id
  run_id
  after_step_id
  sequence_index
  state_ref
  next_step_type

artifacts
  id
  kind
  uri
  sha256
  size_bytes

evaluations
  id
  run_id
  scores_ref
  failure_modes_ref
```

Avoid many component-specific tables early. Store detailed payloads as JSON artifacts.

---

# 17. Repo-aligned implementation structure

Implement this design by evolving the existing Polylith components, not by creating parallel top-level runtime packages.

The current `components/xagent/agent_flow/` package remains the owner of orchestration, state, and specialized step behavior. The current planner, subagent, and summary executors should become specialized steps that extend the general step pattern rather than separate runtime concepts.

```text
components/xagent/agent_flow/
  runtime.py          # fixed state machine and run orchestration
  service.py          # application-facing start/get/resume facade
  models.py           # AgentState, decisions, tool calls, user requests
  steps.py            # RuntimeStep protocol and common StepResult types
  step_executor.py    # generic step execution around event/checkpoint commit
  planner.py          # planner step implementation
  tools.py            # EXECUTE_TOOLS parent step and tool_call child steps
  tool_registry.py    # tool metadata, lookup, validation helpers
  subagents.py        # subagent-backed specialized steps, if still needed
  summary.py          # merge/decide/response specialized steps
  replay.py           # audit playback and deterministic replay helpers
  evaluation.py       # evaluator entrypoints over recorded runs

components/xagent/agent_persistence/
  repositories.py     # repository protocols for runs, events, checkpoints, artifacts
  memory.py           # in-memory implementations for deterministic tests
  events.py           # StepEvent append/read helpers and projection rebuild
  checkpoints.py      # checkpoint store implementations
  artifacts.py        # artifact references and payload storage
  snapshots.py        # config/prompt/tool/model snapshot storage

bases/xagent/agent_flow_cli/
  main.py             # CLI surface for start/get/resume/replay/evaluate

bases/xagent/api_http/
  routes_agent_flow.py # HTTP surface for start/get/resume/user-input
```

This structure is a migration target, not a mandate to rename every existing file immediately. Prefer small changes that adapt current modules:

```text
existing PlannerExecutor
→ PlannerStep implementing RuntimeStep

existing subagent execution
→ specialized step or tool_call child step, depending on whether it is still a subagent abstraction

existing SummaryExecutor
→ Merge/Decide/Response step implementation

existing StepRunner
→ generic StepExecutor that appends StepEvent records and commits checkpoints
```

The most reusable layer is still the persistence record layer: step events, checkpoints, snapshots, artifacts, and projections. In this repo, that layer belongs under `components/xagent/agent_persistence/`, while orchestration and domain-specific step implementations belong under `components/xagent/agent_flow/`.

---

# 18. Final design principle

The system should not be designed as:

```text
agent runtime
+ audit feature
+ replay feature
+ pause/resume feature
+ evaluation feature
```

It should be designed as:

```text
step-based runtime
+ immutable ledger
+ serializable checkpoints
+ versioned snapshots
```

Then audit, replay, pause/resume, and evaluation are natural consequences.

That keeps the architecture minimal, adaptable, and easier to reason about.
