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

Keep only decisions with continuing design value.

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

## 2026-05-17 - Plan Custom Durable Agent Runtime Without LangGraph

Status: accepted

Decision:
- Design a custom durable agent-flow runtime under the existing `xagent` Polylith layout rather than adopting LangGraph or adding a parallel `src/` package.
- Keep `components/xagent/langchain_agents/` as a working sample/legacy reference during the new runtime implementation.
- Reuse or extend existing xagent features before introducing parallel LLM, tool, config, retry, structured-output, HTTP, or runtime-config abstractions.

Rationale:
- The repository already has shared LLM/provider/tool/config bricks that should remain the starting point for new agent runtime work.
- A custom runtime can add durable planner/subagent/summary/replan behavior while keeping implementation ownership inside existing `components/xagent/` and `bases/xagent/` boundaries.
- Keeping the LangChain sample avoids an unnecessary migration during the first durable runtime PR.

Implications:
- New reusable runtime code should live under `components/xagent/agent_flow/` and related Polylith components only when existing bricks cannot be cleanly extended.
- Runtime entrypoints should live under `bases/xagent/`.
- Any new agent-facing adapter over existing LLM or tool components should be thin and documented.

Source pointers:
- `mementum/knowledge/agent-runtime-framework-design.md`
- `components/xagent/langchain_agents/`
- `components/xagent/llm_contracts/`
- `components/xagent/llm_registry/`
- `components/xagent/llm_tools/`

## 2026-05-17 - Implement Durable Agent Flow Runtime With Thin LLM Adapters

Status: accepted

Decision:
- Implement the durable agent-flow runtime under `components/xagent/agent_flow/` with memory-backed repositories, resume reconciliation, CLI, and HTTP entrypoints.
- Keep `AgentFlowLLMAdapter` thin over the existing `LLMProvider` protocol instead of introducing a parallel LLM stack.
- Select fake or provider-backed planner, subagent, and summary executors from agent-flow model config.
- Reconcile succeeded step records into state before resuming a run so partially completed work can be skipped safely.

Rationale:
- The existing provider contracts already cover text and structured generation.
- A thin adapter keeps the runtime aligned with the existing provider layer and avoids duplicate abstractions.
- Resume needs to recover step-level successes, not just checkpoint state, to survive crashes between substeps.

Implications:
- `fake` model configs remain the default for deterministic local runs.
- Provider-backed executors should stay configuration-driven and not be hard-coded into runtime loops.
- Resume logic must continue to prefer persisted successful steps over rerunning them.

Source pointers:
- `components/xagent/agent_flow/llm_adapter.py`
- `components/xagent/agent_flow/service.py`
- `components/xagent/agent_flow/runtime.py`
- `components/xagent/agent_flow/planner.py`
- `components/xagent/agent_flow/subagents.py`
- `components/xagent/agent_flow/summary.py`
- `components/xagent/agent_persistence/repositories.py`

## 2026-05-17 - Put Provider API Key Binding On Config Models

Status: accepted

Decision:
- Remove `api_key_env` from provider config objects and bind provider API keys through config-model metadata instead.
- Use provider-specific config subclasses with `json_schema_extra={"secret": True, "env_var": "..."}` on the `api_key` field.
- Keep provider clients consuming loaded `SecretStr` values from config rather than reading environment variables directly.

Rationale:
- API key loading is configuration, not provider behavior.
- Centralizing env binding in config models keeps provider clients simpler and removes duplicate env lookup paths.
- The provider default env name should still be validated so config metadata stays aligned with the provider contract.

Implications:
- Config construction now hydrates provider API keys before clients are built.
- Downstream code should not rely on `api_key_env` or perform its own provider-env lookup.
- Provider-specific config subclasses are the supported place for provider default env metadata.

Source pointers:
- `components/xagent/llm_config/settings.py`
- `components/xagent/llm_config/auth.py`
- `components/xagent/llm_registry/factory.py`
- `bases/xagent/llm_cli/main.py`

## 2026-05-23 - Evolve Agent Flow Toward Replay/Resume Event Runtime

Status: accepted

Decision:
- Evolve the existing durable `agent_flow` runtime toward a minimal replay/resume architecture instead of creating a parallel runtime package.
- Keep the generic runtime core limited to a fixed state machine, generic step execution, append-only step events, checkpoint-aligned completion, snapshots, artifacts, projections, and execution policy.
- Model planner, tool calls, merge, decision, ask-user, and response behavior as specialized `RuntimeStep` implementations or recorded-data consumers.
- Treat append-only `StepEvent` records as the durable source of truth, with `StepRecord`/step tables as rebuildable projections.
- Consider a step complete only when its state-after checkpoint and `step_succeeded` event are committed as one logical unit.
- Execute each validated tool call as a durable child `tool_call` step with stable `tool_call_id` and `idempotency_key`.
- Represent pause/resume as a durable `WaitStep` plus `MessageInputStep` on the same `conversation_id`; a new message resumes the waiting run and is recorded in the audit trail. Keep `submit_user_input` only as compatibility glue.
- Resolve timeout, deadline, retry, and continue-on-failure behavior through global execution policy plus optional per-step/tool overrides.

Rationale:
- Audit, replay, pause/resume, and evaluation should fall out of the same records rather than become separate subsystems.
- Append-only events preserve a true audit trail while projections keep runtime reads efficient.
- Checkpoint-aligned step success removes the old ambiguity where checkpoints could lag completed step rows after a crash.
- Per-call tool durability prevents duplicate work after partial tool execution, especially for side-effecting actuators.
- Keeping implementation under existing `components/xagent/agent_flow/` and `components/xagent/agent_persistence/` preserves the repo's Polylith ownership boundaries.

Implications:
- Future agent-flow work should follow `mementum/knowledge/replay-resume-agent-implementation-plan.md` and its conformance checklist.
- New runtime code should extend the existing `agent_flow` and `agent_persistence` components rather than introducing a generic graph engine or parallel package.
- Replay and evaluation should consume recorded runs, events, checkpoints, artifacts, snapshots, wait steps, and conversation message steps without rerunning nondeterministic steps.
- Write-side actuator retries require idempotency support or explicit policy approval.

Source pointers:
- `mementum/knowledge/replay-resume-agent-system-design.md`
- `mementum/knowledge/replay-resume-agent-implementation-plan.md`
- `mementum/memories/agent-flow-resume-reconciles-succeeded-steps.md`
- `components/xagent/agent_flow/runtime.py`
- `components/xagent/agent_persistence/repositories.py`
