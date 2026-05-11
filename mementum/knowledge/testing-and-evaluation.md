---
title: Testing and Evaluation
status: active
category: testing
tags: [tests, validation, evaluation]
related:
  - development-workflows
  - implementation-invariants
---

# Testing and Evaluation

## Purpose

Summarize validation strategy without duplicating the test suite.

## Current Understanding

- Tests mirror the Polylith layout under `test/components/xagent/` and `test/bases/xagent/`.
- Provider unit tests use mocked/transports or local assertions; live provider tests are separated under `test/integration/`.
- `pyproject.toml` sets `addopts = "-m 'not require_env'"`, so `pytest` excludes live/env-gated tests by default.
- Live tests cover OpenAI and Anthropic generation, structured output, tool calls, file upload/delete, and batch operations where supported.
- The repository has a Kubernetes smoke test script for the LangChain service that builds the image, loads it into kind, installs the Helm chart, checks `/healthz`, and posts to `/query`.

## Required Validation Commands

Default deterministic suite:

```bash
PYTHONPATH=. uv run --active pytest -q
```

Focused component/base suites:

```bash
PYTHONPATH=. uv run --active pytest -q test/components/xagent/llm_provider_openai
PYTHONPATH=. uv run --active pytest -q test/components/xagent/llm_provider_anthropic
PYTHONPATH=. uv run --active pytest -q test/bases/xagent/llm_cli
```

Live provider tests:

```bash
PYTHONPATH=. uv run --active pytest -q -m require_env test/integration
```

Kubernetes smoke test:

```bash
OPENAI_API_KEY=... scripts/test-kind-langchain-service.sh
```

## Known Testing Gaps

- No checked-in CI workflow was found.
- No dedicated lint/type-check command is configured.
- Live provider tests depend on network, provider availability, credentials, and cost.

## Source Pointers

- `pyproject.toml`
- `test/components/xagent/`
- `test/bases/xagent/`
- `test/integration/test_openai_live.py`
- `test/integration/test_anthropic_live.py`
- `scripts/test-kind-langchain-service.sh`
- `changelogs/20250509-llm-api-layer-changes.md`

## Notes for Future Agents

- Add or update focused tests when behavior changes.
- Do not run live tests casually; mark any live-test result separately from the default suite.
