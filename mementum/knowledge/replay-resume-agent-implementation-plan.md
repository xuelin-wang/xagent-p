# Replay/Resume Agent Runtime Implementation Plan

This plan translates `mementum/knowledge/replay-resume-agent-system-design.md` into staged implementation work for coding agents.

Use this document as the execution checklist. Use the design document as the source of architectural truth. When implementing any stage, first reread the relevant design sections called out below and inspect the current code under:

```text
components/xagent/agent_flow/
components/xagent/agent_persistence/
bases/xagent/agent_flow_cli/
bases/xagent/api_http/routes_agent_flow.py
test/components/xagent/agent_flow/
test/bases/xagent/agent_flow_cli/
test/components/xagent/api_http/
```

Do not create a parallel runtime package. Evolve the existing Polylith components.

## Global implementation rules

- Keep each stage reviewable and testable on its own.
- Preserve current public behavior unless a stage explicitly changes it.
- Keep deterministic fake executors as the default test path.
- Keep provider-backed LLM behavior opt-in through existing config paths.
- Prefer extending existing modules before adding new files.
- Add repository protocols before concrete storage complexity.
- Keep in-memory repositories complete enough to test all new invariants.
- Do not introduce SQL or external stores inside `agent_flow/runtime.py`.
- For every behavior change, add or update tests in the same stage.
- If implementation details conflict with the design, update the design or this plan explicitly rather than drifting silently.
- Execution policy should resolve from global defaults plus optional per-step overrides. If a step does not define a policy field, inherit the global value.
- Distinguish per-attempt `timeout_ms` from total step/tool-call `deadline_ms`.

## Implementation principles

Use these principles as a mandatory review gate for every stage and PR:

- Minimal core: keep generic runtime code limited to the fixed state machine, step execution, step events, checkpoints, snapshots, artifacts, projections, and execution policy.
- Specialized edges: planner, tool calls, merge, decision, ask-user, response, replay, and evaluation should be specialized steps or consumers of recorded data, not custom runtime branches.
- Adaptable/extensible by configuration: prompts, tools, datasets, models, policies, limits, and evaluators should be configured and snapshotted rather than embedded in runtime logic.
- Append-only truth: durable history belongs in append-only events; projections are convenience read models and must be rebuildable.
- Failure-first implementation: timeout, deadline, retry, partial completion, terminal failure, pause, waiting-for-user, and resume semantics must be explicit and tested.
- Repo-aligned evolution: extend `components/xagent/agent_flow/` and `components/xagent/agent_persistence/`; do not introduce a competing runtime architecture.
- Small, justified additions: every new file and public function should have a clear purpose, rationale, design link, caller, tests, and non-goals.

## Conformance checklist

Do not mark a stage done until this checklist is satisfied, or every exception is documented with rationale.

```text
Minimal core
  Did generic runtime code stay limited to orchestration, step execution,
  events, checkpoints, snapshots, artifacts, projections, and policy?

No parallel architecture
  Did the change extend existing Polylith components instead of creating
  a competing runtime package?

Specialized edges
  Are planner/tool/merge/decision/user-response behaviors implemented as
  specialized steps or recorded-data consumers?

Append-only truth
  Is durable history recorded as append-only events, with projections
  rebuildable from those events?

Checkpoint alignment
  Is a step considered complete only when its checkpoint and success event
  are committed as one logical unit?

Failure semantics
  Are timeout, deadline, retry, partial failure, terminal failure, pause,
  waiting-for-user, and resume behavior explicit and tested?

Configurable/adaptable
  Are prompts, tools, policies, model choices, limits, datasets, and
  evaluators configured/snapshotted rather than embedded in runtime logic?

Rationale and tests
  Does each new file or public function have a clear purpose, design-section
  link, caller, tests, and non-goals?
```

For each new file or public function, capture this information in the PR description, docstring, or nearby concise comment when it is not obvious from the name and tests:

```text
Purpose
  What responsibility does it own?

Rationale
  Why can existing code not own this cleanly?

Design link
  Which design section does it implement?

Public surface
  Who calls it?

Tests
  What behavior proves it works?

Non-goals
  What should it not grow into?
```

Useful verification commands:

```bash
PYTHONPATH=. uv run --active pytest -q test/components/xagent/agent_flow
PYTHONPATH=. uv run --active pytest -q test/bases/xagent/agent_flow_cli test/components/xagent/api_http
PYTHONPATH=. uv run --active pytest -q
uv run --active ruff check .
uv run --active ruff format --check .
uv run --active mypy .
```

## Stage 0. Baseline orientation

Goal: establish the current behavior before changing the runtime shape.

Relevant design sections:

- Section 2, minimal state machine
- Section 3, step-based runtime
- Section 17, repo-aligned implementation structure

Likely files to inspect:

```text
components/xagent/agent_flow/runtime.py
components/xagent/agent_flow/step_runner.py
components/xagent/agent_flow/planner.py
components/xagent/agent_flow/subagents.py
components/xagent/agent_flow/summary.py
components/xagent/agent_flow/service.py
components/xagent/agent_persistence/repositories.py
components/xagent/agent_persistence/memory.py
test/components/xagent/agent_flow/test_runtime.py
test/components/xagent/agent_flow/test_step_runner.py
test/components/xagent/agent_flow/test_service.py
```

Actions:

- Run the focused agent-flow tests before editing.
- Identify the current planner, subagent, summary, checkpoint, and resume paths.
- Record any current behavior that must be preserved in tests before refactoring.

Critical notes:

- Existing resume behavior already avoids rerunning succeeded work. Preserve that invariant throughout the migration.
- Do not start by rewriting `runtime.py` wholesale. First create seams around step execution and persistence.

Done when:

- Current tests pass or known failures are documented.
- The implementation entry points and test coverage are understood.

## Stage 1. Introduce the general step contract

Goal: make planner, tool execution, merge/summary, decision, ask-user, and response fit one runtime step pattern.

Relevant design sections:

- Section 3, step-based runtime
- Section 17, repo-aligned implementation structure

Likely files:

```text
components/xagent/agent_flow/models.py
components/xagent/agent_flow/steps.py
components/xagent/agent_flow/step_runner.py
components/xagent/agent_flow/planner.py
components/xagent/agent_flow/summary.py
test/components/xagent/agent_flow/test_models.py
test/components/xagent/agent_flow/test_step_runner.py
test/components/xagent/agent_flow/test_executors.py
```

Actions:

- Add a `RuntimeStep` protocol and `StepResult` model.
- Add execution policy models or placeholders: `RetryPolicy`, `StepExecutionPolicy`, and `RuntimeExecutionPolicy`.
- Keep the existing `StepRunner` name initially if that reduces churn, but shape it toward a generic `StepExecutor`.
- Adapt the planner as the first specialized step, for example `PlannerStep`.
- Keep old executor facades if needed so service/runtime behavior does not change in this stage.

Critical notes:

- A specialized step should contain domain behavior; the generic step executor should contain durability, retries, event append, and checkpoint commit.
- Do not move LLM provider logic into the generic step executor.
- Do not couple `RuntimeStep` to planner-specific models.
- The generic executor owns timeout/deadline enforcement and retry orchestration; specialized steps should not implement their own retry loops.

Tests:

- Planner step returns the same output as the previous planner path.
- Generic step executor can run a fake step and persist success/failure.
- Generic step executor applies global policy when no step override exists.
- Step-specific override replaces only the fields it sets and inherits the rest.
- Existing runtime happy-path tests still pass.

Done when:

- At least one existing specialized executor runs through the general step contract.
- No public CLI or HTTP behavior has changed.

## Stage 2. Add append-only step events and projections

Goal: make `step_events` the source of truth and keep `StepRecord` as a derived read model.

Relevant design sections:

- Section 5, append-only step event ledger
- Section 16, minimal durable data model

Likely files:

```text
components/xagent/agent_flow/models.py
components/xagent/agent_persistence/repositories.py
components/xagent/agent_persistence/memory.py
components/xagent/agent_persistence/events.py
test/components/xagent/agent_flow/test_step_runner.py
test/components/xagent/agent_flow/test_runtime.py
```

Actions:

- Add `StepEvent` models with `event_id`, `run_id`, `step_id`, `sequence_index`, `iteration_index`, `step_type`, `attempt_index`, `event_type`, `snapshot_id`, and artifact references.
- Add optional `parent_step_id`, `tool_call_id`, and `idempotency_key` fields now, even if tools are implemented later.
- Add repository methods to append and query step events.
- Keep or rebuild the existing step repository as a projection over events.
- Update in-memory persistence first.

Critical notes:

- Do not mutate events after append.
- If a projection update fails, replaying events must be enough to rebuild the current step state.
- Sequence ordering must be deterministic and queryable per run.
- Make event append idempotent where retries may call it twice for the same logical transition.

Tests:

- Appending lifecycle events derives the expected `StepRecord`.
- Projection rebuild from events reproduces the same records.
- Query latest `step_succeeded` event by `sequence_index`.
- Retry attempts are represented by distinct events with increasing `attempt_index`.
- Existing resume tests still pass.

Done when:

- Runtime can still use the projection for fast lookups.
- Events are the authoritative history.

## Stage 3. Align checkpoint commit with step success

Goal: make step completion and checkpoint completion one logical commit.

Relevant design sections:

- Section 7, checkpoints
- Section 13, pause and resume

Likely files:

```text
components/xagent/agent_flow/step_runner.py
components/xagent/agent_flow/runtime.py
components/xagent/agent_persistence/repositories.py
components/xagent/agent_persistence/memory.py
test/components/xagent/agent_flow/test_step_runner.py
test/components/xagent/agent_flow/test_runtime.py
test/components/xagent/agent_flow/test_service.py
```

Actions:

- Add checkpoint references to successful step events.
- Change successful step completion to:

```text
run step
write output artifact or output payload
write state_after artifact or payload
save checkpoint for state_after + next_step_type
append step_succeeded event with checkpoint_id
update/rebuild projection
```

- Update resume to load the latest `step_succeeded` event checkpoint by `sequence_index`.
- Treat started/failed/timed-out steps without a later succeeded checkpoint as incomplete.

Critical notes:

- A step is not complete unless the checkpoint exists and the `step_succeeded` event points to it.
- For in-memory repositories, simulate the same transaction boundary through one repository method if useful.
- For future database storage, checkpoint row and `step_succeeded` event must be committed atomically.

Tests:

- Resume restores from the latest succeeded event checkpoint.
- A running step without a succeeded checkpoint is retried according to policy.
- A completed nondeterministic step is not rerun on resume.
- Projection update failure, if simulated, can be repaired from events.

Done when:

- Checkpoint-only resume paths are gone or are compatibility wrappers over latest succeeded event checkpoint.

## Stage 4. Convert runtime phases to specialized steps

Goal: make the state machine in the design explicit in code while preserving existing behavior.

Relevant design sections:

- Section 2, minimal state machine
- Section 3, step-based runtime
- Section 17, repo-aligned implementation structure

Likely files:

```text
components/xagent/agent_flow/runtime.py
components/xagent/agent_flow/planner.py
components/xagent/agent_flow/summary.py
components/xagent/agent_flow/subagents.py
components/xagent/agent_flow/models.py
test/components/xagent/agent_flow/test_runtime.py
test/components/xagent/agent_flow/test_executors.py
```

Actions:

- Represent `BUILD_CONTEXT`, `PLAN`, `VALIDATE_TOOL_CALLS`, `EXECUTE_TOOLS`, `MERGE_RESULTS`, `DECIDE`, `ASK_USER`, and `RESPONSE` as runtime steps or explicit step types.
- Move planner behavior behind a planner step.
- Move summary behavior toward merge/decide/response responsibilities. If full separation is too large, keep one specialized summary step but name the intended boundaries in code and tests.
- Keep subagent behavior as specialized steps until tool-call durability replaces or absorbs it.

Critical notes:

- Do not break the existing configurable app behavior while introducing more step types.
- This stage can be incremental: one phase at a time is acceptable.
- Avoid building a generic graph runtime. The design calls for a fixed state machine.

Tests:

- Happy path follows the expected step sequence.
- Replan loops preserve iteration behavior.
- Max-iteration behavior remains deterministic.
- Failed step transitions still fail the run with useful error details.

Done when:

- Runtime phases are visible as step types and use the common execution path.

## Stage 5. Add tool validation models and registry boundary

Goal: add the model and validation layer needed before durable per-call tool execution.

Relevant design sections:

- Section 9, dataset-backed tools
- Section 10, what `VALIDATE_TOOL_CALLS` does

Likely files:

```text
components/xagent/agent_flow/models.py
components/xagent/agent_flow/tools.py
components/xagent/agent_flow/tool_registry.py
components/xagent/agent_flow/config.py
test/components/xagent/agent_flow/test_models.py
test/components/xagent/agent_flow/test_executors.py
```

Actions:

- Add `ToolMetadata`, `PlannedToolCall`, `ValidatedToolCall`, `RejectedToolCall`, `ToolResult`, and `EvidenceItem` if not already present.
- Generate stable `tool_call_id` values from run, iteration, tool name, and normalized input hash.
- Generate and propagate `idempotency_key`.
- Implement validation checks for enabled tools, schema validity, duplicate calls, max tool count, timeout/deadline assignment, retry policy resolution, and policy constraints.
- Resolve tool execution policy in this order: runtime default, `tool_call` step override, tool metadata/config override, explicit validated-call override.
- Add `ToolResult` terminal statuses: `succeeded`, `failed`, `timed_out`, and `skipped`.

Critical notes:

- Use structured validation, not ad hoc string parsing.
- Tool-call IDs must be stable across resume.
- Rejected calls should be recorded for audit/evaluation, not silently dropped.
- `timeout_ms` is per attempt. `deadline_ms` is total wall-clock budget across all attempts and backoff for the same `tool_call_id`.
- A timeout is retryable only when the effective retry policy includes timeout as retryable.

Tests:

- Valid calls receive stable `tool_call_id` and `idempotency_key`.
- Duplicate or disabled calls are rejected and recorded.
- Max tool count and timeout/deadline policy are enforced.
- Tool-specific config overrides global default policy while inheriting unspecified fields.
- `ToolResult` preserves failure status, `error_ref`, retryable flag, attempt count, and elapsed time.
- Validation is deterministic.

Done when:

- Tool calls can be planned and validated without executing external tools.

## Stage 6. Introduce composite step hierarchy

Goal: express workflows as trees of atomic and composite steps so the executor stays generic and workflow structure is configuration, not hard-coded runtime logic.

Relevant design sections:

- Section 3, step-based runtime
- Section 3.1, step hierarchy
- Section 11, per-call tool execution durability

Likely files:

```text
components/xagent/agent_flow/steps.py
components/xagent/agent_flow/step_runner.py
components/xagent/agent_flow/workflow.py
components/xagent/agent_flow/runtime.py
test/components/xagent/agent_flow/test_steps.py
test/components/xagent/agent_flow/test_runtime.py
```

Actions:

- Add `SequenceStepGroup` and `ParallelStepGroup` composite step types to `steps.py`.
- Update `StepExecutor` (currently `StepRunner`) to handle all three cases: atomic, sequence, parallel.
- Composite steps create their own step record with `parent_step_id` on each child.
- Express the existing planner-subagents-summary loop as a `SequenceStepGroup` workflow tree in `workflow.py`.
- Replace `_run_loop / _run_planner / _run_subagents / _run_summary` with the workflow tree execution.
- `runtime.py` shrinks to: build the workflow tree, hand it to the executor, return the result.

Critical notes:

- A composite step is just another step from the executor's perspective — same contract, same event/checkpoint sequence.
- `ParallelStepGroup` children run concurrently; each appends its own step events independently.
- Resume within a composite: skip already-succeeded children, run remaining. This is the same rule as section 11, generalised.
- Do not build a generic graph runtime. `SequenceStepGroup` and `ParallelStepGroup` cover all current needs.
- The `asyncio.gather` in `_run_subagents` is the embryonic `ParallelStepGroup`; extract it.

Tests:

- `SequenceStepGroup` runs children in order and passes derived state to each.
- `ParallelStepGroup` runs children concurrently; all results are present in output.
- Resume of a partially completed `ParallelStepGroup` skips already-succeeded children.
- A composite step creates its own step record and events.
- Nested composites execute correctly.
- Existing runtime happy-path and replan tests still pass.

Done when:

- The planner-subagents-summary loop is expressed as a composite step tree.
- `runtime.py` contains no per-phase orchestration logic.

## Stage 7. Replace in-place state mutation with event-derived state

Goal: make `AgentState` a pure projection derived from the step event ledger, eliminating all in-place mutation, `on_success` callbacks, and shared-state locks.

Relevant design sections:

- Section 5, append-only step event ledger
- Section 6, serializable state
- Section 6.1, state as a derived projection

Likely files:

```text
components/xagent/agent_flow/state_projection.py
components/xagent/agent_flow/steps.py
components/xagent/agent_flow/step_runner.py
components/xagent/agent_flow/runtime.py
components/xagent/agent_persistence/repositories.py
components/xagent/agent_persistence/memory.py
test/components/xagent/agent_flow/test_state_projection.py
test/components/xagent/agent_flow/test_runtime.py
```

Actions:

- Add `state_projection.py` with `derive_state(run_id, events) -> AgentFlowState` and `_apply(state, event) -> AgentFlowState`.
- `derive_state` is a pure fold: sorted events, only `step_succeeded` events mutate state.
- `_apply` maps step names to state fields (planner → `iteration.plan`, subagent → `iteration.subagent_results`, summary → `iteration.summary`, etc.).
- Add `state_after: AgentFlowState` to `StepResult` so `SequenceStepGroup` can pass derived state to the next child without an extra event-log read.
- Remove all `on_success` callbacks from `StepRunner` / `StepExecutor` and `runtime.py`.
- Remove `_state_commit_lock`.
- Promote `_hydrate_succeeded_step` to `_apply` in `state_projection.py` and use it during normal execution, not just resume.
- Update resume to use `derive_state` as its starting point (unified with normal execution).

Critical notes:

- `derive_state` must be a pure function — no I/O, no side effects.
- `_apply` is where domain knowledge lives (step name → state field). It must be explicit and tested.
- Checkpoints remain as materialized snapshots; resume loads the latest checkpoint as a base and replays only events appended after it.
- If no checkpoint is available, `derive_state` over the full event log is always correct.
- The existing `_hydrate_succeeded_step` is already the right shape; this stage promotes it.

Tests:

- `derive_state([])` returns initial state.
- `derive_state` with planner `step_succeeded` event populates `iteration.plan`.
- `derive_state` with multiple subagent `step_succeeded` events merges all results.
- `derive_state` with summary `step_succeeded` sets `iteration.summary`; `REPLAN` increments `current_iteration`.
- `derive_state(events[:n])` gives the exact historical state at step `n`.
- Normal execution and resume produce identical state from identical events.
- `on_success` callbacks are gone — grep confirms no `on_success` references remain.
- State is never mutated after derivation — `AgentFlowState` objects returned by `_apply` are fresh copies.

Done when:

- `AgentFlowState` is never directly mutated by the runtime or executor.
- State is always derived from the ordered step event ledger.
- `on_success`, `_state_commit_lock`, and `_hydrate_succeeded_step` are removed.

## Stage 8. Implement per-call tool durability

Goal: make each validated tool call its own durable child step.

Relevant design sections:

- Section 11, per-call tool execution durability
- Section 5, append-only step event ledger
- Section 7, checkpoints

Likely files:

```text
components/xagent/agent_flow/tools.py
components/xagent/agent_flow/runtime.py
components/xagent/agent_flow/step_runner.py
components/xagent/agent_persistence/repositories.py
components/xagent/agent_persistence/memory.py
test/components/xagent/agent_flow/test_runtime.py
test/components/xagent/agent_flow/test_step_runner.py
test/components/xagent/agent_flow/test_executors.py
```

Actions:

- Implement `EXECUTE_TOOLS` as a parent orchestration step.
- Execute each validated call as a child `tool_call` step with `parent_step_id`, `tool_call_id`, and `idempotency_key`.
- On resume, reuse recorded child `step_succeeded` results for completed tool calls.
- Run only missing or retry-eligible tool calls.
- For each failed or timed-out attempt, write an error artifact and append `step_failed` or `step_timed_out` with `error_ref` before deciding whether to retry.
- Enforce per-attempt `timeout_ms`, total `deadline_ms`, `max_attempts`, and backoff from the effective policy.
- Make the parent `EXECUTE_TOOLS` step succeed only after required child calls reach terminal status and merged `tool_results` are checkpointed.

Critical notes:

- Never make a monolithic `EXECUTE_TOOLS` step the only durability boundary.
- Write-side actuators must have stable idempotency keys and request/response artifacts.
- If an external API supports idempotency keys, forward the key.
- If prior success is recorded for a write-side actuator, do not blindly re-execute it.
- If idempotency cannot be guaranteed for a write-side actuator, default to no automatic retry unless policy explicitly allows it.
- Parent failure behavior must be explicit: required child failure with `continue_on_failure = false` fails `EXECUTE_TOOLS`; optional child failure or `continue_on_failure = true` produces terminal `ToolResult` entries for merge/decide.

Tests:

- If three tool calls are selected and one succeeds before interruption, resume only executes the remaining calls.
- Parent step output references child step IDs.
- Failed child behavior follows policy.
- Retryable tool failure retries until success, `max_attempts`, or `deadline_ms`.
- Nonretryable tool failure records a terminal failed result without retry.
- Tool attempt exceeding `timeout_ms` records `step_timed_out`.
- Tool call exceeding `deadline_ms` stops retrying even if attempts remain.
- Parent `EXECUTE_TOOLS` fails when a required child fails and `continue_on_failure` is false.
- Parent `EXECUTE_TOOLS` succeeds with failed/timed-out `ToolResult` entries when policy allows continuing.
- Write-side actuator fake receives the expected idempotency key.

Done when:

- Partial tool execution is safe to resume without duplicate successful calls.

## Stage 9. Add waiting-for-user flow

Goal: distinguish final responses from runs paused for external user input.

Relevant design sections:

- Section 2, minimal state machine
- Section 6, serializable state
- Section 6.1, state as a derived projection
- Section 13, pause and resume
- Section 16, minimal durable data model

Likely files:

```text
components/xagent/agent_flow/models.py
components/xagent/agent_flow/runtime.py
components/xagent/agent_flow/service.py
components/xagent/agent_persistence/repositories.py
components/xagent/agent_persistence/memory.py
bases/xagent/agent_flow_cli/main.py
bases/xagent/api_http/routes_agent_flow.py
test/components/xagent/agent_flow/test_runtime.py
test/components/xagent/agent_flow/test_service.py
test/bases/xagent/agent_flow_cli/test_main.py
test/components/xagent/api_http/test_api_http_app.py
```

Actions:

- Add `waiting_for_user` run status.
- Add `UserRequest` and `UserInputEvent`.
- Add `pending_user_request` and `user_input_events` to state.
- Implement `ASK_USER -> WAIT_FOR_USER`.
- Add service method to resume a run with user input.
- Add CLI and HTTP surfaces only after the service behavior is tested.

Critical notes:

- `ASK_USER` is not a terminal response.
- User input continues the same run; it does not create a new run.
- The user reply must be an append-only input event with an artifact reference.
- Resume with user input should restore the latest checkpoint, attach the input event, clear `pending_user_request`, set status to `running`, and continue from `BUILD_CONTEXT` or the configured next step.

Tests:

- Ask-user decision sets status `waiting_for_user`.
- Resume without required user input does not continue a waiting run.
- Resume with user input appends a durable event and continues the same run.
- API and CLI surfaces return stable JSON.

Done when:

- Waiting runs are auditable and resumable with explicit user input records.

## Stage 10. Add replay helpers

Goal: provide audit playback and deterministic replay over recorded events, checkpoints, and artifacts.

Relevant design sections:

- Section 12, replay model
- Section 5, append-only step event ledger
- Section 7, checkpoints

Likely files:

```text
components/xagent/agent_flow/replay.py
components/xagent/agent_persistence/repositories.py
components/xagent/agent_persistence/memory.py
test/components/xagent/agent_flow/test_runtime.py
test/components/xagent/agent_flow/test_replay.py
```

Actions:

- Implement audit playback with no execution.
- Reconstruct step order, inputs/outputs, tool choices, user input events, decisions, and final response.
- Add deterministic replay only for deterministic steps such as validation, normalization, reducers, and policy checks.
- Ensure re-execution of LLMs/tools creates a new run if added later.

Critical notes:

- Audit playback should never call LLMs, tools, or external systems.
- Deterministic replay should compare selected structured outputs, not require exact equality for nondeterministic steps.
- Keep replay read-only.

Tests:

- Playback reconstructs a completed run from events and checkpoints.
- Playback includes waiting-for-user and user input events.
- Deterministic replay skips nondeterministic steps.

Done when:

- A recorded run can be explained without rerunning the agent.

## Stage 11. Add evaluation entrypoints

Goal: score recorded runs without requiring agent re-execution.

Relevant design sections:

- Section 14, evaluation as a natural consequence
- Section 16, minimal durable data model

Likely files:

```text
components/xagent/agent_flow/evaluation.py
components/xagent/agent_flow/replay.py
components/xagent/agent_persistence/repositories.py
test/components/xagent/agent_flow/test_evaluation.py
```

Actions:

- Define evaluator input from run record, step events, user input events, final response, planner output, validated tool calls, tool results, evidence, merge analysis, and snapshot.
- Add simple deterministic metrics first.
- Store evaluation output as artifact references.

Critical notes:

- Evaluation should consume recorded runs.
- Do not require live provider calls in default tests.
- Keep evaluator storage independent from runtime mutation paths.

Tests:

- Evaluator scores a fake completed run.
- Evaluator handles runs with rejected tool calls.
- Evaluator handles waiting-for-user history.

Done when:

- Recorded runs can be scored with deterministic local tests.

## Stage 12. Final integration and cleanup

Goal: remove compatibility paths only after the new event/checkpoint/step model is covered.

Relevant design sections:

- Section 17, repo-aligned implementation structure
- Section 18, final design principle

Likely files:

```text
components/xagent/agent_flow/
components/xagent/agent_persistence/
bases/xagent/agent_flow_cli/
bases/xagent/api_http/
test/components/xagent/agent_flow/
```

Actions:

- Rename `StepRunner` to `StepExecutor` only if the new name clarifies code and churn is manageable.
- Remove obsolete checkpoint-only resume helpers.
- Remove duplicated planner/subagent/summary execution paths.
- Update docs or memory if durable design decisions changed during implementation.
- Run full lint, type check, and test suite.

Critical notes:

- Cleanup should be mechanical and covered by tests.
- Do not delete compatibility behavior that API or CLI tests still exercise unless the public contract intentionally changed.
- If a stage exposed a durable lesson or corrected assumption, propose a `mementum/` update.

Tests:

- Full test suite.
- CLI start/get/resume/replay/evaluate if implemented.
- HTTP start/get/resume/user-input if implemented.

Done when:

- The implementation matches the design sections listed above.
- Agent-flow tests cover composite step execution, event-derived state, checkpoint-aligned completion, append-only events, per-call tool durability, waiting-for-user resume, and replay.

## Suggested PR slicing

Prefer small PRs in this order:

1. Step contract and planner adaptation. *(done)*
2. Step events plus projection in memory repositories. *(done)*
3. Checkpoint-aligned step success and event-based resume. *(done)*
4. Tool validation models and registry. *(done)*
5. Composite step hierarchy (SequenceStepGroup, ParallelStepGroup). *(done)*
6. Event-derived state (derive_state, _apply, remove on_success). *(done)*
7. Per-call durable tool execution. *(done)*
8. Waiting-for-user state and service/API/CLI input resume. *(done)*
9. Replay helpers. *(done)*
10. Evaluation helpers. *(done)*
11. Cleanup and naming alignment. *(done)*

Each PR should explicitly state which design sections it implements and which sections remain future work.

## Post-stage update. Conversation message wait steps

Goal: generalize `ASK_USER` pause/resume into ordinary durable steps.

Design update:

- `WaitStep` is a normal runtime step that pauses execution until a new message
  arrives for the same `conversation_id`.
- `MessageInputStep` is a normal runtime step that records inbound conversation
  messages. It is used for both new conversations and resumed conversations.
- A message without `conversation_id` starts a new run and creates a UUID
  conversation id.
- A message with `conversation_id` resumes the active waiting run for that
  conversation by completing the current `WaitStep`, then recording the message
  with `MessageInputStep`.

Implementation slice:

- Add conversation-message and wait-step models to `models.py`.
- Add `WaitStep` and `MessageInputStep`.
- Add `StepStatus.WAITING` plus `step_waiting`/`step_resumed` events.
- Teach `StepRunner` to persist `StepResult.wait_spec` as a waiting step.
- Keep `submit_user_input` as a compatibility wrapper around conversation-message
  resume.
- Add a message-oriented service and HTTP entrypoint.
- Update replay/audit and demo UI types for `waiting`, `wait`, and
  `message_input`.

Audit shape:

```text
A succeeded
WaitStep waiting
new conversation message arrives
WaitStep resumed/succeeded
MessageInputStep succeeded
B succeeded
C succeeded
```

Source pointers:

- `components/xagent/agent_flow/messages.py`
- `components/xagent/agent_flow/runtime.py`
- `components/xagent/agent_flow/step_runner.py`
- `components/xagent/agent_flow/workflow.py`
- `components/xagent/agent_persistence/repositories.py`
- `bases/xagent/api_http/routes_agent_flow.py`
- `test/components/xagent/agent_flow/test_service.py`
