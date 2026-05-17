---
title: Agent Runtime Framework Design
status: planned
category: architecture
tags: [agent-runtime, durability, polylith, langchain]
related:
  - architecture-decisions
  - implementation-invariants
  - codebase-map
---

# Design Doc: Custom Durable Agent Flow Runtime for xagent-p

1. Goal

Implement a custom agentic flow runtime without LangGraph.

The runtime should support this flow:

User request
-> Planner
-> One or more subagents
-> Each subagent may call skills/tools
-> Summary / merger
-> Either:
- final response
- or replan and run another iteration

The implementation should fit the existing xagent-p repo layout and follow the current Polylith-style organization:

components/xagent/...
bases/xagent/...
projects/...
prompts/...
deploy/...
test/...

The new runtime should coexist with the existing components/xagent/langchain_agents sample rather than immediately deleting it.

2. Current Repo Context

The repo currently has:

components/xagent/
agent_app/
board/
langchain_agents/
piece/
config.py
runtime_config.py

bases/xagent/
api_http/
langchain_cli/

projects/
langchain_service/

prompts/
skills/
deploy/
test/

The existing agent_app/model.py defines simple dataclass models such as SubagentSelection, PlannerStep, SubagentReply, and AgentRunResult.

The existing langchain_agents/app.py already implements a simple async flow:

planner.aplan(query)
-> run selected subagents concurrently
-> merger.amerge(query, plan, replies)

It uses asyncio.create_task, asyncio.wait, timeout handling, and returns AgentRunResult.

The new feature should evolve this concept into a durable, resumable runtime.

3. Key Design Decision

Do not add a generic top-level package like:

src/agent_runtime/

Instead, add new Polylith-style components under the existing namespace:

components/xagent/agent_flow/
components/xagent/agent_persistence/
components/xagent/agent_tools/
components/xagent/llm/
components/xagent/observability/

Add one or more entrypoint bases under:

bases/xagent/agent_flow_cli/
bases/xagent/api_http/

This matches the existing components/xagent/... and bases/xagent/... packaging style already used by the repo. The repo’s Hatch build config includes components/xagent and bases/xagent as packages.

Reuse-first rule:

Before adding a new component, protocol, helper, config model, CLI pattern, or test utility, inspect the existing xagent components for similar functionality. Prefer reusing or extending existing implemented features when they fit the runtime's needs. If an existing feature is close but incomplete, update it in place when that preserves its current contracts and improves the shared abstraction. Add a new feature only when reuse would create unclear ownership, break existing behavior, or force unrelated concerns into an existing module.

In particular, check existing LLM, tool, config, retry, structured-output, file, batch, registry, HTTP, and runtime-config components before creating parallel abstractions. If the runtime introduces a narrower agent-facing adapter over an existing component, document why the adapter exists and keep the adapter thin.

4. Updated Package Layout
   4.1 Final Target Layout
   components/
   xagent/
   agent_app/
   __init__.py
   model.py                  # keep existing simple app models for compatibility

   langchain_agents/
   __init__.py
   app.py                    # keep as existing LangChain sample / legacy path
   planner.py
   subagents.py
   merge.py
   corpus.py

   agent_flow/
   __init__.py
   models.py                 # durable runtime state models
   config.py                 # workflow config models
   runtime.py                # main FlowRuntime
   service.py                # AgentFlowService public API
   step_runner.py            # idempotent durable step wrapper
   checkpoints.py            # checkpoint naming/helpers
   errors.py                 # runtime exceptions
   planner.py                # PlannerExecutor protocol + default implementation
   subagents.py              # SubagentExecutor protocol + default implementation
   summary.py                # SummaryExecutor protocol + default implementation
   final_response.py         # final response composer
   prompt_renderer.py        # prompt template rendering
   resume.py                 # resume-specific helpers

   agent_persistence/
   __init__.py
   models.py                 # persistence DTOs if needed
   repositories.py           # repository protocols
   memory.py                 # in-memory repositories for tests/dev
   postgres.py               # Postgres repositories
   migrations/
   001_agent_flow.sql

   agent_tools/
   __init__.py
   base.py                   # Tool protocol, ToolContext, ToolResult
   registry.py               # ToolRegistry
   fake.py                   # deterministic fake tools
   skill_tool.py             # optional adapter for repo skills later

   llm/
   __init__.py
   base.py                   # LLMClient protocol
   fake.py                   # FakeLLMClient for tests
   langchain_adapter.py      # optional adapter around existing LangChain models
   openai_client.py          # optional later direct provider implementation

   observability/
   __init__.py
   events.py                 # AgentEvent model
   sink.py                   # ObservabilitySink protocol
   logging_sink.py           # logs events
   db_sink.py                # optional stores events in DB

   config.py                   # existing generic strict config loader; reuse it
   runtime_config.py           # existing CLI/env config extraction; reuse it
   4.2 Bases
   bases/
   xagent/
   api_http/
   __init__.py
   main.py
   routes_agent_flow.py      # add new routes here or similar

   langchain_cli/
   __init__.py
   main.py                   # keep existing sample CLI

   agent_flow_cli/
   __init__.py
   main.py                   # optional new CLI for durable custom runtime
   4.3 Projects

The existing project is:

projects/langchain_service/
Dockerfile
README.md

Its README says the chart renders config.yaml from Helm .Values.appConfig, mounts it into the container, and starts the service with --config /app/config/config.yaml. It also states that runtime env vars have higher precedence than config files and that secrets should come from Kubernetes secrets or External Secrets Operator.

For the new runtime, keep the same project initially:

projects/langchain_service/

but consider renaming later to:

projects/xagent_service/

Do not rename it in the first PR unless Codex is explicitly asked to handle deployment changes.

5. Existing Modules: Keep, Reuse, or Replace
   5.1 Keep components/xagent/langchain_agents

Keep this as a working sample / legacy implementation.

Do not delete it in this feature. It is useful for comparison and tests because it already expresses the basic planner → parallel subagents → merger flow.

5.2 Keep components/xagent/agent_app/model.py

Keep the existing dataclasses for compatibility.

But introduce richer durable runtime models under:

components/xagent/agent_flow/models.py

Do not overload agent_app/model.py with persistence/runtime concerns.

5.3 Reuse components/xagent/config/

The repo already has a strict config model helper based on Pydantic, with StrictConfigModel using extra="forbid".

The new runtime config should extend this instead of creating another unrelated config base class.

5.4 Reuse components/xagent/config/runtime.py

The repo already has helpers for extracting --config and --env arguments, validating YAML config paths, and loading typed config.

The new CLI/API setup should use the existing config loading pattern.

6. Runtime Model Design

Create:

components/xagent/agent_flow/models.py
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
PENDING = "pending"
RUNNING = "running"
PAUSED = "paused"
FAILED = "failed"
COMPLETED = "completed"


class FlowStage(StrEnum):
START = "start"
PLANNING = "planning"
SUBAGENTS = "subagents"
SUMMARIZING = "summarizing"
FINALIZING = "finalizing"
COMPLETED = "completed"
FAILED = "failed"


class StepStatus(StrEnum):
PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
SKIPPED = "skipped"


class SummaryDecision(StrEnum):
FINAL = "final"
REPLAN = "replan"
FAIL = "fail"


class AgentError(BaseModel):
stage: str
step_name: str | None = None
message: str
error_type: str | None = None
retryable: bool = False
details: dict[str, Any] = Field(default_factory=dict)


class PlanSubagentSelection(BaseModel):
name: str
reason: str = ""
input_hint: str | None = None


class PlanOutput(BaseModel):
goal: str
selections: list[PlanSubagentSelection] = Field(default_factory=list)
rationale: str = ""
constraints: dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
tool_name: str
arguments: dict[str, Any] = Field(default_factory=dict)
result: dict[str, Any] | None = None
error: dict[str, Any] | None = None
duration_seconds: float | None = None


class SubagentResult(BaseModel):
name: str
status: Literal["completed", "timeout", "error", "skipped"]
content: str
duration_seconds: float | None = None
evidence: list[dict[str, Any]] = Field(default_factory=list)
tool_calls: list[ToolCallRecord] = Field(default_factory=list)
structured_output: dict[str, Any] = Field(default_factory=dict)
error: AgentError | None = None


class SummaryOutput(BaseModel):
decision: SummaryDecision
answer_draft: str | None = None
rationale: str = ""
missing_information: list[str] = Field(default_factory=list)
suggested_replan: dict[str, Any] | None = None


class AgentFlowState(BaseModel):
run_id: str
case_id: str | None = None
user_query: str

    status: RunStatus = RunStatus.PENDING
    current_stage: FlowStage = FlowStage.START
    iteration: int = 0

    plan: PlanOutput | None = None
    subagent_results: dict[str, SubagentResult] = Field(default_factory=dict)
    summary: SummaryOutput | None = None
    final_response: str | None = None

    errors: list[AgentError] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def should_stop_replanning(self, max_iterations: int) -> bool:
        return self.iteration >= max_iterations
7. Runtime Config Design

Create:

components/xagent/agent_flow/config.py

Use the existing StrictConfigModel from xagent.config.

from __future__ import annotations

from typing import Literal

from pydantic import Field

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
provider: str = "fake"
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
planner: PlannerConfig = Field(default_factory=PlannerConfig)
summary: SummaryConfig = Field(default_factory=SummaryConfig)
subagents: dict[str, SubagentConfig] = Field(default_factory=dict)
models: dict[str, AgentModelConfig] = Field(default_factory=dict)
persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
8. Config File Location

Add config examples under:

prompts/agent_flow/
planner.md
summary.md
subagents/
repair_history.md
manual_rag.md
dtc_analysis.md

deploy/langchain-service/values-kind.yaml
deploy/langchain-service/values-dev.yaml
deploy/langchain-service/values-prod.yaml

Add a local config file:

development/config/agent-flow.local.yaml

Example:

workflow:
name: diagnosis_agent_flow
max_iterations: 3
subagent_execution_mode: parallel
continue_on_subagent_failure: true
max_subagents_per_iteration: 5
max_tool_rounds_per_subagent: 3

planner:
name: diagnosis_planner
prompt_template: prompts/agent_flow/planner.md
model: default_reasoning
max_attempts: 2

summary:
name: diagnosis_summary
prompt_template: prompts/agent_flow/summary.md
model: default_reasoning
max_attempts: 2

subagents:
repair_history:
name: repair_history
description: Analyze past repair records for similar symptoms.
prompt_template: prompts/agent_flow/subagents/repair_history.md
model: default_reasoning
tools:
- repair_history_search
timeout_seconds: 60
max_attempts: 2

manual_rag:
name: manual_rag
description: Search manuals and official procedures.
prompt_template: prompts/agent_flow/subagents/manual_rag.md
model: default_reasoning
tools:
- manual_semantic_search
timeout_seconds: 90
max_attempts: 2

models:
default_reasoning:
provider: fake
model: fake-reasoning
temperature: 0.0

persistence:
backend: memory
9. Persistence Component

Create:

components/xagent/agent_persistence/
9.1 Repository Protocols

File:

components/xagent/agent_persistence/repositories.py
from __future__ import annotations

from typing import Any, Protocol

from xagent.agent_flow.models import AgentFlowState


class RunRepository(Protocol):
async def create_run(self, state: AgentFlowState) -> None:
...

    async def get_run_state(self, run_id: str) -> AgentFlowState:
        ...

    async def update_run_state(self, state: AgentFlowState) -> None:
        ...

    async def mark_completed(self, run_id: str, final_response: str) -> None:
        ...

    async def mark_failed(self, run_id: str, error: dict[str, Any]) -> None:
        ...


class StepRepository(Protocol):
async def create_or_get_step(
self,
*,
run_id: str,
iteration: int,
step_name: str,
step_type: str,
input_json: dict[str, Any],
max_attempts: int,
idempotency_key: str,
) -> dict[str, Any]:
...

    async def mark_step_running(self, step_id: str) -> None:
        ...

    async def mark_step_succeeded(
        self,
        step_id: str,
        output_json: dict[str, Any],
    ) -> None:
        ...

    async def mark_step_failed(
        self,
        step_id: str,
        error_json: dict[str, Any],
    ) -> None:
        ...

    async def get_steps_for_run_iteration(
        self,
        run_id: str,
        iteration: int,
    ) -> list[dict[str, Any]]:
        ...


class CheckpointRepository(Protocol):
async def save_checkpoint(
self,
*,
run_id: str,
iteration: int,
checkpoint_name: str,
stage: str,
state: AgentFlowState,
) -> None:
...

    async def get_latest_checkpoint(self, run_id: str) -> AgentFlowState | None:
        ...
9.2 In-Memory Implementation

File:

components/xagent/agent_persistence/memory.py

Use this for unit tests and local dev.

The in-memory repositories should support:

create_run
get_run_state
update_run_state
mark_completed
mark_failed
create_or_get_step
mark_step_running
mark_step_succeeded
mark_step_failed
save_checkpoint
get_latest_checkpoint
9.3 Postgres Implementation

File:

components/xagent/agent_persistence/postgres.py

Add dependency to pyproject.toml:

dependencies = [
...
"psycopg[binary,pool]>=3.2",
]

Do not use SQL directly in agent_flow/runtime.py.

10. Database Migration

Create:

components/xagent/agent_persistence/migrations/001_agent_flow.sql
CREATE TABLE IF NOT EXISTS agent_runs (
run_id TEXT PRIMARY KEY,
case_id TEXT NULL,
user_query TEXT NOT NULL,

    status TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 0,

    latest_state_json JSONB NOT NULL,
    final_response TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ NULL,
    failed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_case_id
ON agent_runs(case_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_status
ON agent_runs(status);

CREATE TABLE IF NOT EXISTS agent_steps (
step_id TEXT PRIMARY KEY,
run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,

    iteration INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,

    input_json JSONB NULL,
    output_json JSONB NULL,
    error_json JSONB NULL,

    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,

    idempotency_key TEXT NOT NULL,

    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(run_id, iteration, step_name)
);

CREATE INDEX IF NOT EXISTS idx_agent_steps_run_id
ON agent_steps(run_id);

CREATE INDEX IF NOT EXISTS idx_agent_steps_run_iteration
ON agent_steps(run_id, iteration);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_steps_idempotency_key
ON agent_steps(idempotency_key);

CREATE TABLE IF NOT EXISTS agent_checkpoints (
checkpoint_id TEXT PRIMARY KEY,
run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,

    iteration INTEGER NOT NULL,
    checkpoint_name TEXT NOT NULL,
    stage TEXT NOT NULL,

    state_json JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(run_id, iteration, checkpoint_name)
);

CREATE INDEX IF NOT EXISTS idx_agent_checkpoints_run_created
ON agent_checkpoints(run_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_events (
event_id TEXT PRIMARY KEY,
run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
step_id TEXT NULL,

    event_type TEXT NOT NULL,
    event_json JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_events_run_id
ON agent_events(run_id);

CREATE INDEX IF NOT EXISTS idx_agent_events_type
ON agent_events(event_type);
11. LLM Component

Create:

components/xagent/llm/
11.1 Base Protocol

File:

components/xagent/llm/base.py
from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
async def generate_text(
self,
*,
model_name: str,
prompt: str,
metadata: dict | None = None,
) -> str:
...

    async def generate_structured(
        self,
        *,
        model_name: str,
        prompt: str,
        output_type: type[T],
        metadata: dict | None = None,
    ) -> T:
        ...
11.2 Fake LLM

File:

components/xagent/llm/fake.py

The fake client should produce deterministic outputs for tests:

planner -> selects configured fake subagents
subagent -> returns deterministic content
summary -> FINAL or REPLAN based on test mode
11.3 LangChain Adapter

Optional but useful because the repo already has LangChain dependencies and LangChain sample code. The adapter should live in:

components/xagent/llm/langchain_adapter.py

This lets the custom runtime use LangChain chat models without depending on LangGraph.

12. Tool Component

Create:

components/xagent/agent_tools/
12.1 Tool Base

File:

components/xagent/agent_tools/base.py
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class ToolContext(BaseModel):
run_id: str
case_id: str | None = None
iteration: int
subagent_name: str
idempotency_key: str
metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
tool_name: str
arguments: dict[str, Any] = Field(default_factory=dict)
result: dict[str, Any] = Field(default_factory=dict)
summary: str | None = None
error: dict[str, Any] | None = None


class Tool(Protocol):
name: str
description: str

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        ...
12.2 Registry

File:

components/xagent/agent_tools/registry.py
class ToolRegistry:
def __init__(self) -> None:
self._tools = {}

    def register(self, tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools[name]

    async def call_tool(self, *, tool_name: str, arguments: dict, context):
        tool = self.get(tool_name)
        return await tool.execute(arguments=arguments, context=context)
13. Main Runtime Component

Create:

components/xagent/agent_flow/runtime.py

Core behavior:

create/update run state
loop until max_iterations
run planner step
save planner checkpoint
run subagents
save subagents checkpoint
run summary
save summary checkpoint
if FINAL: compose final response, complete run
if REPLAN: next iteration
if FAIL: fail run

The current LangChain sample already uses async subagent execution with task timeout handling. Reuse that idea, but move durable state, checkpoint, and retry behavior into the new agent_flow runtime.

14. Step Runner

Create:

components/xagent/agent_flow/step_runner.py

Responsibilities:

Create or load step row.
If step already succeeded, return stored output.
If not succeeded, run the function.
Retry up to max_attempts.
Persist output or error.
Emit observability events.
class StepRunner:
async def run_step(
self,
*,
state,
step_name: str,
step_type: str,
input_json: dict,
max_attempts: int,
fn,
) -> dict:
...

Idempotency key:

{run_id}:{iteration}:{step_name}
15. Planner Executor

Create:

components/xagent/agent_flow/planner.py

The planner should output PlanOutput.

The new executor can be implemented independently from LangChain but can mirror the existing planner behavior. The current LangChainPlanner already has the key concept: it receives a subagent catalog and asks the model to select names only from that catalog.

16. Subagent Executor

Create:

components/xagent/agent_flow/subagents.py

The existing Subagent protocol in langchain_agents/subagents.py has:

name: str
description: str
async def ainvoke(self, query: str) -> str: ...

and an example RAG subagent implementation.

For the new runtime, define a richer protocol:

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

In version 1, implement a configurable prompt-based subagent that can call tools through ToolRegistry.

Parallel execution should:

Use asyncio.create_task.
Use per-subagent timeout.
Persist each subagent as an individual durable step.
On resume, skip already-succeeded subagents.
Continue on subagent failure if configured.
17. Summary Executor

Create:

components/xagent/agent_flow/summary.py

This replaces the old simple “merger only” concept with a summary agent that can decide:

FINAL
REPLAN
FAIL

The existing LangChainResponseMerger merges specialist results into a concise response. The new summary executor should preserve that responsibility but add a structured decision.

18. Service API

Create:

components/xagent/agent_flow/service.py
class AgentFlowService:
async def start_run(
self,
*,
user_query: str,
case_id: str | None = None,
metadata: dict | None = None,
) -> AgentFlowState:
...

    async def resume_run(self, run_id: str) -> AgentFlowState:
        ...

    async def get_run(self, run_id: str) -> AgentFlowState:
        ...

This is the main interface that api_http and CLI bases should call.

19. HTTP API Integration

Add:

bases/xagent/api_http/routes_agent_flow.py

Suggested endpoints:

POST /agent-flow/runs
GET  /agent-flow/runs/{run_id}
POST /agent-flow/runs/{run_id}/resume

Request:

{
"query": "Vehicle has intermittent no-start issue",
"case_id": "case_123",
"metadata": {
"vehicle_model": "example",
"model_year": 2021
}
}

Response:

{
"run_id": "run_...",
"status": "completed",
"current_stage": "completed",
"iteration": 1,
"final_response": "...",
"state": {}
}

Do not remove existing HTTP routes.

20. CLI Integration

Add optional CLI base:

bases/xagent/agent_flow_cli/main.py

Add script entry to pyproject.toml:

[project.scripts]
xagent-agent-flow = "xagent.agent_flow_cli.main:main"

Current pyproject.toml already defines scripts for the LangChain API/sample/LLM CLI, so add this alongside the existing entries.

Example usage:

uv run xagent-agent-flow \
--config development/config/agent-flow.local.yaml \
run "Vehicle has intermittent no-start issue"
21. Testing Layout

Use the existing top-level test/ directory.

Add:

test/
agent_flow/
test_models.py
test_config.py
test_step_runner.py
test_runtime_happy_path.py
test_runtime_replan.py
test_runtime_resume.py
test_subagent_partial_resume.py
test_subagent_failure_continue.py

agent_persistence/
test_memory_repositories.py
test_postgres_repositories.py

Initial implementation should use memory repositories and fake LLM/tool clients so tests do not need real OpenAI keys.

22. Implementation Order for Codex

Ask Codex to implement in this order:

Add components/xagent/agent_flow/models.py.
Add components/xagent/agent_flow/config.py.
Add components/xagent/agent_persistence/repositories.py.
Add components/xagent/agent_persistence/memory.py.
Add components/xagent/llm/base.py.
Add components/xagent/llm/fake.py.
Add components/xagent/agent_tools/base.py.
Add components/xagent/agent_tools/registry.py.
Add components/xagent/agent_tools/fake.py.
Add components/xagent/agent_flow/step_runner.py.
Add planner/subagent/summary/final executors.
Add components/xagent/agent_flow/runtime.py.
Add components/xagent/agent_flow/service.py.
Add tests using memory persistence.
Add Postgres SQL migration.
Add Postgres repository implementation.
Add HTTP route or CLI base.
Update pyproject.toml dependencies/scripts only as needed.
23. Key Migration Rule

Do not replace this immediately:

components/xagent/langchain_agents/

with the new runtime.

Instead:

components/xagent/langchain_agents/     # existing sample / legacy
components/xagent/agent_flow/           # new durable custom runtime

After the new runtime is tested, a later PR can decide whether langchain_agents should be deprecated, adapted, or removed.

24. Codex Prompt

You can send this to Codex:

Implement a custom durable agent flow runtime in the existing xagent-p repository.

Important repo constraints:
- Keep the existing Polylith-style layout.
- Put reusable components under components/xagent/.
- Put CLI/API entrypoints under bases/xagent/.
- Do not create a new src/ package.
- Do not introduce LangGraph.
- Do not delete the existing components/xagent/langchain_agents sample.
- Reuse or extend existing implemented xagent features before adding new parallel abstractions.
- Reuse xagent.config.StrictConfigModel and the existing runtime_config config loading style where appropriate.
- Target the repo's current Python version and packaging setup.

Add these components:
- components/xagent/agent_flow/
- components/xagent/agent_persistence/
- components/xagent/agent_tools/
- components/xagent/llm/
- components/xagent/observability/ if useful

The runtime should support:
- planner -> subagents -> summary -> final/replan
- async parallel subagent execution
- durable run state
- durable step records
- checkpoints after planner/subagents/summary/final
- resume from latest checkpoint
- skip already-succeeded steps during resume
- structured errors
- max iteration guard
- deterministic fake LLM client
- fake tools
- in-memory repositories for tests
- Postgres SQL migration and repository implementation if practical

Use Pydantic models for runtime state and config.
Use repository protocols so runtime code does not depend directly on SQL.
Use a StepRunner so every durable step has idempotency, retry, persisted status, and saved output.

Do not hardcode provider-specific model calls in the runtime.
Do not put SQL in runtime.py.
Do not put prompt text directly in executors.
Do not change unrelated board/piece code.

Add tests under test/agent_flow/ and test/agent_persistence/.

First make the memory-backed runtime pass tests. Then add Postgres persistence.

My main recommendation: treat this as a new durable runtime component, not a rewrite of the existing LangChain sample. The existing sample is useful as a behavioral reference, but the new code should live under components/xagent/agent_flow and become the future core runtime.
