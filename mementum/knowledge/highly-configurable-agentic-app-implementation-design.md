Design Doc: Configurable Agentic Runtime Application for xagent-p
1. Goal

Build a simple, highly configurable agentic application using the custom runtime framework already present in this repo.

The target flow is:

User query
-> Planner
-> Parallel subagents
-> Summary / decision step
-> Either final reply or another planner-execution iteration

Do not use LangChain or LangGraph for this runtime path.

The implementation should keep code generic and move most behavior into configuration:

Configurable:
- planner prompt
- summary / decision prompt
- enabled subagents
- subagent descriptions
- subagent prompts
- model selection
- max iterations
- subagent execution mode
- retry attempts
- persistence backend

Hardcoded:
- planner -> subagents -> summary loop
- state model
- step execution semantics
- checkpointing semantics
- error model
- bounded replan guard

The design should stay straightforward. Do not turn this into a generic graph runtime yet.

2. Current repo context

The repo already contains an agent_flow component:

components/xagent/agent_flow/
config.py
errors.py
llm_adapter.py
models.py
planner.py
runtime.py
service.py
step_runner.py
subagents.py
summary.py

The runtime already has the right high-level shape: AgentFlowRuntime runs planner, subagents, and summary in a loop, supports resume, uses StepRunner, and persists runs, steps, and checkpoints through repository protocols.

The config already has workflow, planner, summary, subagent, model, and persistence sections.

The models already define AgentFlowState, AgentFlowIteration, PlanOutput, SubagentResult, SummaryOutput, SummaryDecision, and status enums.

The repo also already has a local config example at:

development/config/agent-flow.local.yaml

It defines fake manuals and repair_history subagents using the fake model provider.

Therefore, this task should focus on hardening and improving the existing implementation, not recreating the component from scratch.

3. Recommended architecture

Keep the current package layout:

components/xagent/agent_flow/
config.py
errors.py
llm_adapter.py
models.py
planner.py
runtime.py
service.py
step_runner.py
subagents.py
summary.py

components/xagent/agent_persistence/
repositories.py
memory.py
postgres.py      # optional later

bases/xagent/agent_flow_cli/
main.py

development/config/
agent-flow.local.yaml

prompts/agent_flow/
planner.md
summary.md
subagents/
manuals.md
repair_history.md

Do not introduce a new src/ package.

Do not create a separate general graph engine.

Do not delete the existing LangChain sample code yet.

4. Runtime behavior

The runtime should keep this bounded loop:

while True:
run planner
run selected subagents
run summary / decision

    if summary.decision == FINAL:
        complete run

    if summary.decision == FAIL:
        fail run

    if summary.decision == REPLAN:
        if max_iterations reached:
            produce safe final fallback or fail based on config
        else:
            increment iteration and continue

Current runtime.py already implements this basic loop. It should be refined, not replaced.

5. Key improvement: make unknown or skipped subagents explicit

Current runtime silently ignores planner selections that are not present in _subagents.

Change this behavior.

Add config:

class AgentWorkflowConfig(StrictConfigModel):
...
unknown_subagent_policy: Literal["skip", "fail"] = "skip"

Behavior:

If planner selects an unknown subagent:
- if policy == "fail": fail the planner/subagent stage
- if policy == "skip": add a SubagentResult with status="skipped"

The skipped result should look like:

{
"name": "unknown_agent",
"status": "skipped",
"content": "",
"error": {
"stage": "subagents",
"step_name": "subagent:unknown_agent",
"message": "Planner selected unknown subagent: unknown_agent",
"error_type": "UnknownSubagent",
"retryable": false
}
}

Rationale: summary/decision should see that the planner made a bad selection instead of silently losing information.

6. Key improvement: add subagent enable/disable config

Update SubagentConfig:

class SubagentConfig(StrictConfigModel):
name: str
enabled: bool = True
description: str
prompt_template: str
model: str = "default_reasoning"
tools: list[str] = Field(default_factory=list)
timeout_seconds: float = 60.0
max_attempts: int = 2

Only enabled subagents should be shown to the planner.

Planner input should use:

enabled_subagents = {
name: config
for name, config in self._config.subagents.items()
if config.enabled
}

Disabled subagents should not be available for selection.

7. Key improvement: use per-subagent timeout

Current SubagentConfig already includes timeout_seconds, but the runtime should enforce it.

In _run_subagent_step, wrap invocation with asyncio.wait_for:

timeout_seconds = self._config.subagents[subagent_name].timeout_seconds

try:
output_json = await self._step_runner.run_step(...)
except TimeoutError:
return SubagentResult(
name=subagent_name,
status="timeout",
content="",
error=AgentError(
stage="subagents",
step_name=f"subagent:{subagent_name}",
message=f"Subagent timed out after {timeout_seconds} seconds.",
error_type="TimeoutError",
retryable=True,
),
)

Prefer to place the timeout around the actual subagent call, not around persistence bookkeeping.

8. Key improvement: separate summary from decision naming

The existing code uses SummaryExecutor and SummaryOutput, where SummaryOutput.decision controls whether the flow finishes or replans. This is acceptable, but the prompt and docs should call it:

summary / decision step

Do not split it into two runtime steps yet.

Reason: splitting into separate “summary” and “decision” agents is more flexible but adds complexity. For v1, one structured output is enough:

class SummaryOutput(BaseModel):
decision: SummaryDecision
answer_draft: str | None = None
rationale: str = ""
missing_information: list[str] = Field(default_factory=list)
suggested_replan: dict[str, Any] | None = None

Keep the existing model.

9. Key improvement: improve replan information passed to planner

Currently LLMPlannerExecutor._render_user_prompt mainly includes the user query and available subagents. It should also include previous iteration summaries/results so replanning is informed.

Update planner prompt rendering to include:

User query
Current iteration
Available subagents
Previous iteration summary
Previous missing information
Previous suggested replan
Previous subagent results, summarized

Add helper:

def render_iteration_history(state: AgentFlowState) -> str:
...

Keep it concise. Do not dump unlimited content.

Suggested limits:

max_history_iterations = 3
max_result_chars_per_subagent = 1500

Add config:

class AgentWorkflowConfig(StrictConfigModel):
...
max_history_iterations_for_prompt: int = 3
max_subagent_result_chars_for_prompt: int = 1500
10. Key improvement: make final behavior after max iterations configurable

Current runtime fails the run when max iteration count is reached.

Add config:

class AgentWorkflowConfig(StrictConfigModel):
...
max_iteration_exceeded_policy: Literal["fail", "finalize_best_effort"] = "finalize_best_effort"

Behavior:

fail:
mark run failed when summary requests REPLAN but max_iterations is reached

finalize_best_effort:
produce a final answer from the latest summary/subagent results
include uncertainty and missing information

For user-facing agentic applications, finalize_best_effort is usually better than failing after doing useful work.

11. Keep StepRunner as the idempotency boundary

StepRunner already provides the right durable-step abstraction:

create_or_get_step
return prior succeeded output
mark running
retry
mark succeeded
mark failed

Keep this. Do not bypass it from runtime steps.

Each durable step should remain named deterministically:

planner
subagent:{subagent_name}
summary

Idempotency key should remain:

{run_id}:{iteration}:{step_name}
12. LLM adapter design

Keep AgentFlowLLMAdapter thin.

It should only do:

resolve model config
call provider.generate
call provider.generate_structured
attach metadata
return text or typed Pydantic output

The current adapter already follows this pattern.

Do not put planner/subagent/summary prompt logic into the LLM adapter.

Do not put provider-specific logic into runtime.

13. Config design

Update AgentFlowAppConfig minimally.

Target shape:

workflow:
name: local_fake_agent_flow
max_iterations: 3
subagent_execution_mode: parallel
continue_on_subagent_failure: true
max_subagents_per_iteration: 5
max_tool_rounds_per_subagent: 3
require_new_evidence_for_replan: false
unknown_subagent_policy: skip
max_iteration_exceeded_policy: finalize_best_effort
max_history_iterations_for_prompt: 3
max_subagent_result_chars_for_prompt: 1500

planner:
name: planner
prompt_template: prompts/agent_flow/planner.md
model: default_reasoning
max_attempts: 2

summary:
name: summary
prompt_template: prompts/agent_flow/summary.md
model: default_reasoning
max_attempts: 2

subagents:
manuals:
name: manuals
enabled: true
description: Search service manuals and procedures.
prompt_template: prompts/agent_flow/subagents/manuals.md
model: default_reasoning
tools: []
timeout_seconds: 60
max_attempts: 2

repair_history:
name: repair_history
enabled: true
description: Search prior repair history for similar symptoms.
prompt_template: prompts/agent_flow/subagents/repair_history.md
model: default_reasoning
tools: []
timeout_seconds: 60
max_attempts: 2

models:
default_reasoning:
provider: fake
model: fake-reasoning
temperature: 0.0
timeout_seconds: 60

persistence:
backend: memory

This is close to the current local YAML, but adds enabled and several workflow guardrails.

14. Prompt files

Use external prompt files. Do not hardcode long prompts in Python.

prompts/agent_flow/planner.md
You are the planner for an agentic application.

Your job is to select the smallest useful set of subagents to answer the user query.

Rules:
- Select only subagents from the available catalog.
- Do not select disabled or unknown subagents.
- Prefer fewer subagents when possible.
- Use more than one subagent only when their responsibilities are meaningfully different.
- If this is a replan iteration, focus on missing information from prior iterations.

Return structured output matching the required schema.
prompts/agent_flow/summary.md
You are the summary and decision step for an agentic application.

Your job:
1. Review the user query.
2. Review the planner goal.
3. Review all subagent results.
4. Decide whether the available information is enough to answer.
5. Either produce a final answer, request replanning, or fail.

Decision rules:
- Use FINAL when the subagent results are sufficient.
- Use REPLAN when specific missing information can likely be obtained by another planner/subagent round.
- Use FAIL only when the system cannot proceed or the available data is invalid.
- If producing a final answer, clearly state uncertainty and assumptions.
- Do not hide subagent errors or timeouts if they affect confidence.

Return structured output matching the required schema.
prompts/agent_flow/subagents/manuals.md
You are a manuals subagent.

Use the provided user query and planner input hint to produce useful manual/procedure-oriented findings.

For now, if no real tools are available, return a concise dummy response that explains what this subagent would normally search.
prompts/agent_flow/subagents/repair_history.md
You are a repair history subagent.

Use the provided user query and planner input hint to identify similar prior cases, repeated symptoms, likely causes, and uncertainty.

For now, if no real tools are available, return a concise dummy response that explains what this subagent would normally search.
15. Subagent design

Keep the current protocol:

class FlowSubagent(Protocol):
name: str
description: str

    async def ainvoke(
        self,
        *,
        state: AgentFlowState,
        selection: PlanSubagentSelection,
    ) -> SubagentResult:
        ...

Current FakeFlowSubagent and LLMFlowSubagent are good starting points.

Improve LLMFlowSubagent._render_user_prompt to include:

User query
Case id
Iteration
Planner reason
Planner input hint
Allowed tools
Prior iteration summary, if any

Do not implement tool-calling inside subagents in this PR unless already trivial. Keep tools as config metadata for now.

16. Planner design

Keep two implementations:

FakePlannerExecutor
LLMPlannerExecutor

Current FakePlannerExecutor is useful for deterministic tests. Current LLMPlannerExecutor already uses structured output and filters selections to known subagents.

Improve planner selection validation:

1. remove duplicate subagent names
2. enforce max_subagents_per_iteration
3. reject or skip unknown subagents depending on config
4. only expose enabled subagents
5. preserve rejected/skipped selections as structured warnings

Add optional field to PlanOutput:

warnings: list[str] = Field(default_factory=list)

This gives observability without failing the run unnecessarily.

17. Summary / decision design

Keep two implementations:

FakeSummaryExecutor
LLMSummaryExecutor

Current FakeSummaryExecutor can produce FINAL, REPLAN, or FAIL, which is useful for tests.

Improve summary prompt input to include:

User query
Current iteration
Planner goal
Planner rationale
Subagent result table
Errors/timeouts/skipped results
Previous iteration summaries

Add a helper to serialize subagent results compactly. Avoid raw dumping large JSON into the prompt.

18. Service API

Keep AgentFlowService as the public interface.

Current service already has:

start_run(...)
get_run(...)
resume_run(...)

and an AgentFlowExecutorFactory that chooses fake vs LLM executors based on model provider config. This is a good design and should stay.

Improve factory validation:

- every planner/summary/subagent model reference must exist in config.models
- every subagent config key should match SubagentConfig.name, or fail config validation
- fake provider should never instantiate a real LLM adapter
19. CLI

Keep the existing CLI base:

bases/xagent/agent_flow_cli/main.py

It already supports:

run
get
resume

and uses load_runtime_config(AgentFlowAppConfig, argv).

Keep the README command working:

uv run --active xagent-agent-flow \
--config development/config/agent-flow.local.yaml \
run "diagnose intermittent no-start"

Add a pretty-output option:

--pretty

Behavior:

Default:
compact JSON, current behavior

--pretty:
indented JSON

Optional later:

--final-only

prints only final_response.

20. Persistence

Keep current repository protocol design. Runtime should depend only on:

RunRepository
StepRepository
CheckpointRepository

Do not put SQL inside runtime.py.

For this implementation round, prioritize memory-backed runtime and tests. Postgres persistence can be a separate follow-up unless already partially implemented.

21. Observability metadata

Every LLM call should include metadata:

{
"agent_flow_run_id": state.run_id,
"agent_flow_stage": "...",
"agent_flow_iteration": str(state.current_iteration),
}

For subagents:

{
"agent_flow_run_id": state.run_id,
"agent_flow_stage": "subagent",
"agent_flow_subagent": self.name,
"agent_flow_iteration": str(state.current_iteration),
}

The current planner, summary, and subagent executors already attach some metadata. Extend it consistently.

22. Error handling rules

Use AgentError for all structured runtime errors.

Rules:

Planner failure:
fail the run unless StepRunner can retry successfully.

Unknown subagent:
skip or fail based on unknown_subagent_policy.

Subagent timeout:
produce SubagentResult(status="timeout") if continue_on_subagent_failure=true.
fail the run if continue_on_subagent_failure=false.

Subagent exception:
produce SubagentResult(status="error") if continue_on_subagent_failure=true.
fail the run if continue_on_subagent_failure=false.

Summary failure:
fail the run unless StepRunner can retry successfully.

Max iterations reached:
fail or finalize best effort based on max_iteration_exceeded_policy.
23. Tests to add or update

Add tests under the existing test structure.

Recommended tests:

test/agent_flow/test_config.py
- loads development/config/agent-flow.local.yaml
- rejects unknown config fields
- supports enabled=false on subagent
- validates model references

test/agent_flow/test_planner.py
- fake planner selects configured subagents
- planner does not receive disabled subagents
- duplicate planner selections are deduplicated
- unknown selections are skipped or fail based on config

test/agent_flow/test_runtime.py
- happy path: planner -> parallel subagents -> final
- replan path stops after final decision
- max iteration policy fail
- max iteration policy finalize_best_effort
- continue_on_subagent_failure=true
- continue_on_subagent_failure=false
- subagent timeout produces timeout result

test/agent_flow/test_resume.py
- succeeded planner step is not rerun on resume
- succeeded subagent step is not rerun on resume
- summary can run after resumed partial execution

test/agent_flow/test_cli.py
- run command returns valid JSON
- --pretty returns indented JSON
- metadata-json must be object

Use fake providers only. No real API calls in unit tests.

24. Implementation plan for Codex

Implement in this order:

Inspect existing components/xagent/agent_flow and components/xagent/agent_persistence.
Update AgentWorkflowConfig with:
unknown_subagent_policy
max_iteration_exceeded_policy
max_history_iterations_for_prompt
max_subagent_result_chars_for_prompt
Add enabled: bool = True to SubagentConfig.
Add config validation:
subagent dict key should match SubagentConfig.name
planner model exists
summary model exists
subagent model exists
Add compact prompt-history rendering helper.
Update planner to receive only enabled subagents and previous iteration context.
Update runtime to explicitly handle unknown/skipped subagents.
Add per-subagent timeout enforcement.
Add max-iteration best-effort finalization policy.
Improve summary serialization to include errors/timeouts/skipped results.
Add CLI --pretty.
Add or update tests.
Run formatting, linting, type checks, and tests according to repo conventions.
25. Non-goals for this PR

Do not implement these yet:

Generic DAG runtime
LangGraph compatibility
Distributed subagent workers
Remote subagent RPC
Full tool-calling loop inside subagents
Postgres persistence if memory-backed runtime is not fully tested yet
Complex prompt templating engine
Dynamic Python plugin loading from YAML

Keep the runtime simple.

26. Acceptance criteria

The implementation is complete when:

1. `uv run --active xagent-agent-flow --config development/config/agent-flow.local.yaml run "diagnose intermittent no-start"` works.

2. The runtime uses:
   planner -> subagents -> summary/decision -> final/replan.

3. Fake provider path works without API keys.

4. Disabled subagents are not visible to planner.

5. Unknown planner-selected subagents are explicitly skipped or fail based on config.

6. Subagent timeout is enforced.

7. Replanning is bounded by max_iterations.

8. Max-iteration behavior is configurable.

9. Resume does not rerun already-succeeded durable steps.

10. Tests cover happy path, replan, timeout, unknown subagent, disabled subagent, failure handling, and CLI JSON output.
27. Codex instruction

Use this as the direct instruction:

Please review and improve the existing custom agent-flow runtime in this repository.

Do not implement a greenfield framework. The repo already has components/xagent/agent_flow with config, models, runtime, planner, summary, subagents, service, step_runner, and llm_adapter. Refine this implementation.

Main goals:
- keep the fixed planner -> subagents -> summary/decision -> final/replan loop
- keep code generic
- keep prompts, subagent definitions, model choices, and runtime policy configurable
- do not use LangChain or LangGraph for this runtime path
- do not introduce a generic DAG engine
- do not delete existing langchain sample code

Implement these improvements:
1. Add SubagentConfig.enabled, default true.
2. Only expose enabled subagents to the planner.
3. Add workflow.unknown_subagent_policy = "skip" | "fail".
4. Explicitly represent skipped unknown subagents as SubagentResult(status="skipped") when policy is skip.
5. Add per-subagent timeout enforcement using SubagentConfig.timeout_seconds.
6. Add workflow.max_iteration_exceeded_policy = "fail" | "finalize_best_effort".
7. Add concise previous-iteration context to planner and summary prompts.
8. Add config validation for model references and subagent key/name consistency.
9. Keep StepRunner as the idempotency/retry/persistence boundary.
10. Add CLI --pretty output.
11. Add tests for happy path, replan, disabled subagents, unknown subagents, timeout, max iteration policy, resume, and CLI output.

Keep implementation simple. Prefer small helper functions over new abstractions. Do not add new packages unless necessary. Use the existing xagent config, LLM provider, structured-output, service, and persistence patterns.

28. Implementation order

Implement the feature in this sequence:

1. Add config validation and the new workflow knobs.
2. Add `SubagentConfig.enabled` and expose only enabled subagents to the planner.
3. Add explicit unknown-subagent handling with `skip` / `fail` policy.
4. Add compact previous-iteration context to planner and summary prompts.
5. Enforce per-subagent timeout at the runtime boundary.
6. Add the max-iteration exceeded policy.
7. Update tests alongside each slice.

Design guardrails for the implementation:

- Keep the fixed planner -> subagents -> summary/decision -> final/replan loop.
- Keep `StepRunner` as the durable idempotency and retry boundary.
- Keep prompt shaping in planner, summary, and subagent executors, not in the LLM adapter.
- Keep the adapter thin and provider-agnostic.
- Keep code generic, but do not add a generic graph engine.
