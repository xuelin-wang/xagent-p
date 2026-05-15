# Project State

## Current Direction

- This repository is a Python `xagent` workspace using a loose Polylith layout: `components/`, `bases/`, `projects/`, and `development/`.
- The active implementation includes two main surfaces:
  - A provider-pluggable LLM wrapper with OpenAI and Anthropic providers.
  - A minimal FastAPI LangChain service packaged as `projects/langchain_service`.
- Project memory lives under `mementum/` and is for engineering context only.
- Reusable coding-agent workflow prompts live under `prompts/`; project-memory maintenance workflows live under `skills/mementum-memory/`.

## Current Focus

- Preserve the Polylith component boundaries and provider-specific LLM behavior.
- Keep tests deterministic by default; live provider tests are opt-in through the `require_env` marker.
- Keep deployment secrets outside committed values files except disposable local `kind` overrides.

## Next Steps

- Verify whether there is intended CI outside this repository; no `.github/` workflow files were found.
- Fill in lint/type-check commands if the project adopts dedicated tools.
- If staged changelog deletions are intentional, update memory pages that still cite those historical changelog files.
- Keep updating memory only when a durable implementation lesson or design decision is learned.

## Blockers / Unknowns

- CI configuration is not present in the checked-out repo.
- No dedicated lint or type-check command is configured in `pyproject.toml`.
- `README.md` still contains TODO-level notes for logging/tracing work.
- Several memory pages still reference historical changelog files that are currently absent from the index; verify whether those changelogs should be restored or the memory source pointers should be updated.

## Recent Decisions

- Project memory was added under `mementum/`.
- `AGENTS.md` is the shared agent guidance source; `CLAUDE.md` imports it.
- LLM provider mutation operations should not be retried automatically without caller-level idempotency or deduplication.
- Native batch callers provide `items`; public pre-uploaded batch input-file support was removed.
- Reusable coding-agent workflow prompts belong under `prompts/`; project-memory maintenance workflows belong under `skills/mementum-memory/`.

## Source Pointers

- `workspace.toml`
- `pyproject.toml`
- `README.md`
- `projects/langchain_service/README.md`
- `mementum/knowledge/architecture-decisions.md`
- `mementum/knowledge/codebase-map.md`
- `mementum/knowledge/open-questions.md`
- `mementum/knowledge/development-workflows.md`
- `AGENTS.md`
- `CLAUDE.md`
- `prompts/README.md`
- `skills/mementum-memory/SKILL.md`
