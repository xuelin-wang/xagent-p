---
title: Architecture Decisions
status: active
category: architecture
tags: [decisions, rationale, llm, polylith]
related:
  - implementation-invariants
  - open-questions
---

# Architecture Decisions

## Purpose

Keep only decisions with continuing design value. Detailed commit summaries remain in changelogs.

## Decisions

## 2025-05-09 - Provider-Pluggable LLM Wrapper

Status: accepted

Decision:
- Implement a reusable LLM wrapper with common contracts and provider-specific OpenAI/Anthropic implementations.

Rationale:
- Callers get a stable interface while provider differences remain explicit.

Implications:
- Preserve raw provider responses.
- Capability-check unsupported features.
- Do not silently emulate a provider feature with another provider or fallback.

Source pointers:
- `changelogs/20250509-llm-api-layer-design.txt`
- `changelogs/20250509-llm-api-layer-changes.md`
- `components/xagent/llm_contracts/`
- `components/xagent/llm_provider_openai/`
- `components/xagent/llm_provider_anthropic/`

## 2025-05-09 - Use Existing Loose Polylith Layout

Status: accepted

Decision:
- Put reusable code in Polylith bricks under `components/xagent/` and executable bases under `bases/xagent/`.

Rationale:
- The repository already declares `namespace = "xagent"` and loose Polylith structure.

Implications:
- Do not introduce a parallel `src/` architecture for new shared code.
- Tests should mirror component/base paths.

Source pointers:
- `workspace.toml`
- `pyproject.toml`
- `changelogs/20250509-llm-api-layer-design.txt`

## 2025-05-09 - Do Not Retry Provider Resource Mutations Automatically

Status: accepted

Decision:
- Provider mutations such as file upload/delete and native batch create/cancel are sent once by provider implementations.

Rationale:
- Providers do not document a reliable idempotency-key contract for these operations; automatic retry can duplicate files or batch jobs or produce ambiguous delete state.

Implications:
- Higher-level callers must own durable deduplication before retrying these operations.
- Tests should protect this behavior.

Source pointers:
- `changelogs/20250509-llm-api-layer-changes.md`
- `components/xagent/llm_provider_openai/provider.py`
- `components/xagent/llm_provider_anthropic/provider.py`
- `test/components/xagent/llm_provider_openai/test_files.py`
- `test/components/xagent/llm_provider_anthropic/test_files.py`

## 2025-05-09 - Native Batch Inputs Come From Items

Status: accepted

Decision:
- Remove public support for `BatchCreateRequest.input_file`; native batch providers build/upload batch input from `items`.

Rationale:
- Pre-uploaded batch input files were not supported consistently across providers.

Implications:
- Reject `input_file` in public batch request models.
- Keep batch API narrow until a cross-provider design exists.

Source pointers:
- `changelogs/20250509-llm-api-layer-changes.md`
- `components/xagent/llm_batch/models.py`
- `test/components/xagent/llm_batch/test_models.py`

## 2026-05-11 - Keep Reusable Workflows Separate From Project Memory

Status: accepted

Decision:
- Store reusable coding-agent workflow prompts under `prompts/`.
- Store project-memory maintenance workflows under the repo-local `skills/mementum-memory/` skill.
- Keep `mementum/` focused on project memory: state, decisions, rationale, conventions, pitfalls, and durable lessons.

Rationale:
- Prompts are reusable task instructions, while project memory is durable knowledge about the repository.
- Skills are a better fit for automating project-memory maintenance workflows.
- Keeping reusable workflows separate prevents `mementum/` from becoming a prompt or skill library.

Implications:
- Root agent guidance should point agents to `prompts/` when a reusable workflow applies.
- Project-memory maintenance guidance should point agents to `skills/mementum-memory/`.
- Prompt improvements belong in `prompts/`.
- Memory-maintenance workflow improvements belong in `skills/mementum-memory/`.
- Durable lessons learned from prompt use can still be captured in `mementum/`.

Source pointers:
- `prompts/README.md`
- `skills/mementum-memory/SKILL.md`
- `AGENTS.md`
- `CLAUDE.md`
