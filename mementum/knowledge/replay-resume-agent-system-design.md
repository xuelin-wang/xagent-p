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
  ├── ASK_USER → RESPONSE
  ├── RESPOND → RESPONSE
  └── STOP_LIMIT → RESPONSE
  ↓
END
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
→ ledger record
→ checkpoint
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

ExecutionLedger
  Append-only record of every step.

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

# 5. Immutable execution ledger

Every step writes one durable record.

```python
class StepRecord(BaseModel):
    step_id: str
    run_id: str
    iteration_index: int
    step_type: str

    status: Literal[
        "pending",
        "running",
        "succeeded",
        "failed",
        "timed_out",
        "paused",
        "skipped",
    ]

    input_ref: str
    output_ref: str | None = None

    state_before_ref: str
    state_after_ref: str | None = None

    flow_decision: str | None = None
    next_step_type: str | None = None

    snapshot_id: str

    started_at: datetime
    finished_at: datetime | None = None

    error_ref: str | None = None
```

Large data should live in an artifact store:

```text
input_ref        → artifact://runs/run_123/steps/001/input.json
output_ref       → artifact://runs/run_123/steps/001/output.json
state_before_ref → artifact://runs/run_123/steps/001/state_before.json
state_after_ref  → artifact://runs/run_123/steps/001/state_after.json
```

The database stores references and metadata. The artifact store stores full payloads.

---

# 6. Serializable state

The runtime state should be explicit and serializable.

```python
class AgentState(BaseModel):
    run_id: str
    iteration_index: int = 0

    input_query: AgentInput

    conversation_summary: str | None = None

    planned_tool_calls: list[PlannedToolCall] = []
    validated_tool_calls: list[ValidatedToolCall] = []
    tool_results: list[ToolResult] = []

    evidence: list[EvidenceItem] = []

    merge_analysis: MergeAnalysis | None = None
    decision: RuntimeDecision | None = None

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

After every successful step, write a checkpoint.

```python
class RuntimeCheckpoint(BaseModel):
    checkpoint_id: str
    run_id: str
    after_step_id: str

    state_ref: str
    next_step_type: str
    iteration_index: int

    snapshot_id: str
    created_at: datetime
```

Resume becomes simple:

```text
load latest checkpoint
load state
load snapshot
continue from next_step_type
```

Rule:

> Resume should never re-run a completed nondeterministic step unless explicitly requested.

If an LLM planner step already completed, resume should reuse its recorded output.

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
timeout is assigned
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
    timeout_ms: int
    validation_notes: list[str] = []
```

Rejected calls should also be recorded:

```python
class RejectedToolCall(BaseModel):
    tool_name: str
    reason: str
```

This is useful for audit and evaluation:

```text
Planner selected repair_history_tool.
Runtime rejected it because the dataset was disabled.

Planner selected 8 tools.
Runtime kept the top 4 due to max_tools_per_iteration.
```

---

# 11. Replay model

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

# 12. Pause and resume

Pause should happen at step boundaries.

Useful pause points:

```text
after PLAN
before EXECUTE_TOOLS
after EXECUTE_TOOLS
before RESPONSE
before any write-side actuator
```

Pause is just a checkpoint with status:

```text
step completed
checkpoint written
run status = paused
```

Resume is:

```text
load checkpoint
restore state
continue from next_step_type
```

No special pause/resume architecture is needed.

---

# 13. Evaluation as a natural consequence

Evaluation should consume recorded runs.

It should not need to re-run the agent.

Evaluator input:

```text
run record
step ledger
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

# 14. PEAS mapping

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

# 15. Minimal durable data model

Use only a few durable concepts:

```text
runs
snapshots
steps
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

snapshots
  id
  config_ref
  prompt_refs
  tool_registry_ref
  dataset_manifest_refs
  model_config_ref
  code_version

steps
  id
  run_id
  iteration_index
  step_type
  status
  input_ref
  output_ref
  state_before_ref
  state_after_ref
  next_step_type
  error_ref

checkpoints
  id
  run_id
  after_step_id
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

# 16. Final recommended structure

```text
agent_runtime/
  runner.py
  state.py
  steps.py
  executor.py
  decision.py

agent_tools/
  base.py
  registry.py
  validation.py

agent_records/
  ledger.py
  checkpoints.py
  snapshots.py
  artifacts.py

agent_replay/
  playback.py
  deterministic_replay.py

agent_eval/
  evaluator.py
  metrics.py
  report.py
```

This is intentionally small.

The most reusable layer is `agent_records`. It supports runtime, replay, resume, and evaluation.

---

# 17. Final design principle

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
