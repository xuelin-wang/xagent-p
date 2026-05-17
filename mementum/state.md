# Project State

## Current Direction

- This repository is a Python `xagent` workspace using a loose Polylith layout: `components/`, `bases/`, `projects/`, and `development/`.
- The active implementation includes two main surfaces:
  - A provider-pluggable LLM wrapper with OpenAI and Anthropic providers.
  - A minimal FastAPI LangChain service packaged as `projects/langchain_service`.
- A custom durable agent-flow runtime is now implemented under `components/xagent/agent_flow/` with CLI and HTTP entrypoints under `bases/xagent/`.
- Project memory lives under `mementum/` and is for engineering context only.
- Reusable coding-agent workflow prompts live under `prompts/`; project-memory maintenance workflows live under `skills/mementum-memory/`.

## Current Focus

- Preserve the Polylith component boundaries and provider-specific LLM behavior.
- Keep provider API keys modeled as config data: config models own `api_key` hydration, and provider code consumes the loaded `SecretStr` without re-reading env vars.
- For the agent-flow runtime, reuse or extend existing xagent features before adding parallel abstractions.
- Keep the runtime deterministic by default with fake planner/subagent/summary executors, and select provider-backed executors from model config when requested.
- Keep tests deterministic by default; live provider tests are opt-in through the `require_env` marker.
- Keep deployment secrets outside committed values files except disposable local `kind` overrides.

## Next Steps

- Add memory only when a durable implementation lesson or design decision is learned.

## Blockers / Unknowns

- `README.md` still contains TODO-level notes for logging/tracing work.

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
- `components/xagent/llm_config/settings.py`
- `AGENTS.md`
- `CLAUDE.md`
- `prompts/README.md`
- `skills/mementum-memory/SKILL.md`
