# Project State

## Current Direction

- This repository is a Python `xagent` workspace using a loose Polylith layout: `components/`, `bases/`, `projects/`, and `development/`.
- The active implementation includes two main surfaces:
  - A provider-pluggable LLM wrapper with OpenAI and Anthropic providers.
  - A minimal FastAPI LangChain service packaged as `projects/langchain_service`.
- A custom durable agent-flow runtime is fully implemented under `components/xagent/agent_flow/` with CLI and HTTP entrypoints under `bases/xagent/`.
- All 12 stages of `mementum/knowledge/replay-resume-agent-implementation-plan.md` are complete on branch `replay-resume-implementation`.
- Project memory lives under `mementum/` and is for engineering context only.
- Reusable coding-agent workflow prompts live under `prompts/`; project-memory maintenance workflows live under `skills/mementum-memory/`.

## Current Focus

- Preserve the Polylith component boundaries and provider-specific LLM behavior.
- Keep provider API keys modeled as config data: config models own `api_key` hydration, and provider code consumes the loaded `SecretStr` without re-reading env vars.
- For the agent-flow runtime, reuse or extend existing xagent features before adding parallel abstractions.
- Keep the runtime deterministic by default with fake planner/subagent/summary executors, and select provider-backed executors from model config when requested.
- Keep tests deterministic by default; live provider tests are opt-in through the `require_env` marker.
- Keep deployment secrets outside committed values files except disposable local `kind` overrides.
- The replay/resume implementation is complete. The next decision is which gap to address: real tool execution or evaluation quality metrics (see open questions).
- A React + Vite demo UI (`bases/xagent/demo_ui/`) is implemented for visualising agent-flow runs: flow chart, append-only audit log, state JSON, step detail panel, conversation id, and wait/message resume markers.
- Durable case/business records are now being designed separately from step execution records: facts are immutable and may carry relationship edges, while case plans are immutable latest-wins records with no plan-to-plan edges.

## Next Steps

- **Real tool execution**: wire concrete `ToolExecutor` implementations into the subagent path, replacing the monolithic `LLMFlowSubagent` with the planner→validate→execute→merge pipeline. `ToolCallStep` and `build_execute_tools_step` are ready.
- **Evaluation quality metrics**: extend `evaluation.py` with content-quality scoring (answer quality, grounding, tool selection) using reference answers or LLM judges. Current evaluation is structural only.

## Blockers / Unknowns

- `README.md` still contains TODO-level notes for logging/tracing work.
- No decision yet on whether real tool execution or evaluation quality metrics should be prioritised next.

## Recent Decisions

- Project memory was added under `mementum/`.
- `AGENTS.md` is the shared agent guidance source; `CLAUDE.md` imports it.
- LLM provider mutation operations should not be retried automatically without caller-level idempotency or deduplication.
- Native batch callers provide `items`; public pre-uploaded batch input-file support was removed.
- Reusable coding-agent workflow prompts belong under `prompts/`; project-memory maintenance workflows belong under `skills/mementum-memory/`.
- ruff (>= 0.15.13) and mypy (>= 2.1.0, strict mode) are the standard lint and type-check tools; all existing ruff lint, ruff format, and mypy strict violations have been resolved.
- The mementum skill requires explicit user approval before any write to `mementum/`; enforced in SKILL.md and all six reference workflow files.
- GitHub Actions CI added at `.github/workflows/ci.yml`; runs ruff check, ruff format --check, mypy, and pytest on every push and PR to main.
- pr-desc skill added at `skills/pr-desc/`; generates concise reviewer-focused PR descriptions from the current branch diff against main.
- Agent runtime framework design added under `mementum/knowledge/agent-runtime-framework-design.md`; the implemented runtime avoids LangGraph, coexists with the existing LangChain sample, follows Polylith layout, and prefers reuse of existing xagent features.
- Durable agent-flow runtime implemented under `components/xagent/agent_flow/` with memory-backed repositories, resume reconciliation from succeeded step records, thin LLM adapter over the existing `LLMProvider` protocol, and service/CLI/HTTP entrypoints.
- Provider API key loading moved into config models via explicit `secret` and `env_var` field metadata, with provider-specific config subclasses and config construction helpers.
- Pause/resume is now conversation-scoped: a durable `WaitStep` pauses the run, a new inbound conversation message resumes it, and a durable `MessageInputStep` records the message in the audit trail. `conversation_id` is the resume key, `pending_wait` tracks the active pause, and `submit_user_input` remains only as compatibility glue.
- `evaluation.py` produces only structural metrics (counts, flags, decision sequences, failure modes); LLM-graded content quality scoring is deferred pending ground-truth dataset or judge design.
- `replay.py` audit playback reads from repositories without executing any step logic; `replay_from_steps` wraps `derive_state` and is the canonical way to reconstruct state from recorded steps.
- `StepRunner` rename to `StepExecutor` deferred — churn across tests and runtime is too high relative to current value; revisit when the public surface stabilises.
- Demo UI added at `bases/xagent/demo_ui/` as a Vite + React 18 + Tailwind v3 base; built output deploys to `bases/xagent/api_http/static/demo/` (gitignored) and served as a FastAPI static mount at `/demo`.
- `XAGENT_API_HTTP_CONFIG` env var wired into `create_app()`: when set, its value is passed as `--config` to `load_runtime_config`, enabling config file selection without touching CLI argv (needed for `uvicorn` direct start).
- Dev config at `development/config/api-http.dev.yaml` enables fake executors, CORS for `http://localhost:5173`, and two named fake subagents (`manuals`, `repair_history`) for demo purposes.
- Two new HTTP endpoints added to `routes_agent_flow.py`: `GET /agent-flow/runs` (list all runs) and `GET /agent-flow/runs/{run_id}/audit` (fetch `RunAuditRecord`).
- Agent-flow execution policy is now a top-level app config element (`agent_flow.execution_policy`). `StepRunner` enforces `timeout_ms` and `deadline_ms` with `asyncio.wait_for`; values are milliseconds, `0` means unbounded, and negative values are rejected. Top-level steps use app policy; composite children inherit parent policy; step-type and local overrides can refine it.
- Agent-flow pause/resume now uses durable `WaitStep` and `MessageInputStep` records tied to `conversation_id`; the audit shape is `A -> WaitStep -> MessageInputStep -> B -> C`, including resumed runs.
- Domain records should be written at the semantic owner boundary, not necessarily the whole workflow boundary: for example, a subagent can persist facts when it finishes if those facts are already stable.

## Source Pointers

- `workspace.toml`
- `pyproject.toml`
- `README.md`
- `projects/langchain_service/README.md`
- `mementum/knowledge/architecture-decisions.md`
- `mementum/knowledge/codebase-map.md`
- `mementum/knowledge/open-questions.md`
- `mementum/knowledge/development-workflows.md`
- `mementum/knowledge/agent-runtime-framework-design.md`
- `mementum/knowledge/replay-resume-agent-system-design.md`
- `mementum/knowledge/replay-resume-agent-implementation-plan.md`
- `components/xagent/llm_config/settings.py`
- `components/xagent/agent_flow/config.py`
- `components/xagent/agent_flow/steps.py`
- `components/xagent/agent_flow/step_runner.py`
- `components/xagent/agent_flow/tools.py`
- `AGENTS.md`
- `CLAUDE.md`
- `prompts/README.md`
- `skills/mementum-memory/SKILL.md`
- `bases/xagent/demo_ui/`
- `development/config/api-http.dev.yaml`
- `mementum/knowledge/demo-ui-design.md`
