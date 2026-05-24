---
title: Implementation Invariants
status: active
category: design
tags: [invariants, implementation]
related:
  - architecture-decisions
  - testing-and-evaluation
  - security-and-data-boundaries
---

# Implementation Invariants

## Purpose

Record rules that should remain true unless an explicit design change updates code, tests, and memory together.

## Current Invariants

- Preserve the loose Polylith layout under the `xagent` namespace; build config packages `components/xagent` and `bases/xagent`.
- Shared LLM bricks must not depend on provider implementation bricks.
- Provider implementations may depend on shared contracts/config/retry/files/tools/structured/batch/registry modules.
- The registry protocol layer must stay provider-implementation independent; provider imports belong in factory/default-registration code.
- Common LLM request/response shapes should be normalized, but provider-specific behavior must remain visible through capability checks, explicit unsupported-feature errors, and preserved raw responses.
- OpenAI embeddings are supported; Anthropic embeddings should fail explicitly rather than route to OpenAI.
- Provider resource mutations such as file upload/delete and batch create/cancel should not be automatically retried without a documented idempotency strategy.
- Native batch callers provide request `items`; public pre-uploaded batch input-file support is intentionally unsupported.
- Runtime config models are strict and reject extra keys.
- Config and dataclass fields holding API keys or other secrets must use `SecretStr | None`, not `str | None`.
- Provider API keys are hydrated through explicit config-model metadata such as `json_schema_extra={"secret": True, "env_var": "OPENAI_API_KEY"}`.
- Runtime environment-variable overrides must only apply to fields with explicit env metadata; do not infer env bindings from field names.
- Normal pytest runs must exclude live provider tests unless explicitly requested with `require_env`.
- Project memory under `mementum/` must not contain secrets, runtime records, logs, or private data.

## Agent-Flow Replay/Resume Invariants

- Agent-flow runtime evolution must extend `components/xagent/agent_flow/` and `components/xagent/agent_persistence/`; do not create a competing runtime or graph package.
- Generic agent-flow runtime code should stay limited to orchestration, step execution, events, checkpoints, snapshots, artifacts, projections, and execution policy.
- Planner, tool-call, merge, decision, ask-user, and response behavior should live in specialized steps or recorded-data consumers, not hard-coded runtime branches.
- Append-only `StepEvent` records are the durable source of truth; `StepRecord` or step tables are projections and must be rebuildable.
- A step is complete only when its state-after checkpoint and `step_succeeded` event are committed as one logical unit.
- Resume must use recorded successful step/tool-call events and must not rerun completed nondeterministic work unless explicitly requested.
- Each validated tool call must have a stable `tool_call_id` and `idempotency_key`, and should execute as a durable child `tool_call` step.
- Write-side actuator retries require idempotency support or explicit policy approval.
- Per-attempt timeout, total deadline, retry, and continue-on-failure behavior must be explicit in execution policy and covered by deterministic tests.
- Execution-policy time values are milliseconds. `timeout_ms` applies per attempt, `deadline_ms` applies to the total step or composite execution, and unset or `0` values are unbounded. Negative timeout or deadline values are invalid config.
- Agent-flow execution policy must flow through the step tree: top-level steps use `agent_flow.execution_policy`, child steps inherit their parent composite policy, app step-type overrides may refine inherited policy, and local child contexts may override inherited fields.
- Waiting for user input should use an explicit `waiting_for_user` status and append-only user input records, not terminal response state.

## Source Pointers

- `workspace.toml`
- `pyproject.toml`
- `components/xagent/llm_registry/provider_protocol.py`
- `components/xagent/llm_registry/factory.py`
- `components/xagent/llm_config/settings.py`
- `components/xagent/config/loader.py`
- `components/xagent/config/runtime.py`
- `components/xagent/llm_provider_openai/provider.py`
- `components/xagent/llm_provider_anthropic/provider.py`
- `components/xagent/config/strict.py`
- `components/xagent/agent_flow/config.py`
- `components/xagent/agent_flow/steps.py`
- `components/xagent/agent_flow/step_runner.py`
- `components/xagent/agent_flow/tools.py`
- `mementum/knowledge/replay-resume-agent-system-design.md`
- `mementum/knowledge/replay-resume-agent-implementation-plan.md`
- `test/components/xagent/llm_provider_openai/`
- `test/components/xagent/llm_provider_anthropic/`

## Notes for Future Agents

- If an invariant needs to change, update the relevant tests and explain the design reason in memory or changelog.
