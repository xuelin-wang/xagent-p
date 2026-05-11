---
title: Implementation Invariants
status: active
category: design
tags: [invariants, implementation]
related:
  - architecture-decisions
  - testing-and-evaluation
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
- Normal pytest runs must exclude live provider tests unless explicitly requested with `require_env`.
- Project memory under `mementum/` must not contain secrets, runtime records, logs, or private data.

## Source Pointers

- `workspace.toml`
- `pyproject.toml`
- `components/xagent/llm_registry/provider_protocol.py`
- `components/xagent/llm_registry/factory.py`
- `components/xagent/llm_provider_openai/provider.py`
- `components/xagent/llm_provider_anthropic/provider.py`
- `components/xagent/config.py`
- `changelogs/20250509-llm-api-layer-design.txt`
- `changelogs/20250509-llm-api-layer-changes.md`
- `test/components/xagent/llm_provider_openai/`
- `test/components/xagent/llm_provider_anthropic/`

## Notes for Future Agents

- If an invariant needs to change, update the relevant tests and explain the design reason in memory or changelog.
