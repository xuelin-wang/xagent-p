---
title: Development Workflows
status: active
category: workflow
tags: [development, agents, process]
related:
  - codebase-map
  - testing-and-evaluation
---

# Development Workflows

## Purpose

Record commands and workflows that affect implementation choices.

## Current Understanding

Package management/build:

```bash
uv sync --active
uv add <package>
```

Run tests:

```bash
PYTHONPATH=. uv run --active pytest -q
```

Run live provider tests only when credentials/network/cost are acceptable:

```bash
PYTHONPATH=. uv run --active pytest -q -m require_env test/integration
```

Run the LangChain service locally through the installed script:

```bash
uv run --active xagent-langchain-api --config path/to/config.yaml
```

Run LLM wrapper CLI commands:

```bash
uv run --active xagent-llm --provider openai text "hello"
uv run --active xagent-llm --provider anthropic text "hello"
```

Build the deployable service image:

```bash
docker build -f projects/langchain_service/Dockerfile -t xagent-langchain-service .
```

Run the local `kind` Helm smoke test:

```bash
OPENAI_API_KEY=... scripts/test-kind-langchain-service.sh
```

Expose repo-local skills to coding agents:

```bash
mkdir -p .agents/skills .claude/skills
ln -s ../../skills/mementum-memory .agents/skills/mementum-memory
ln -s ../../skills/mementum-memory .claude/skills/mementum-memory
```

## Workflow Notes

- The default pytest configuration excludes `require_env`, so normal test runs should not call real providers.
- Runtime config accepts `--config` for YAML files and `--env` for env-style files; environment variables matching top-level config fields override file settings.
- Helm deploys render non-secret `appConfig` into a ConfigMap and inject secrets through `envFrom`.
- The `kind` smoke-test script requires Docker, kind, kubectl, helm, curl, and `OPENAI_API_KEY`.
- Repo-local skill sources live under `skills/`; agent-specific discovery folders should symlink to them rather than copying skill files.

## Source Pointers

- `pyproject.toml`
- `workspace.toml`
- `components/xagent/runtime_config.py`
- `components/xagent/config.py`
- `projects/langchain_service/README.md`
- `projects/langchain_service/Dockerfile`
- `scripts/test-kind-langchain-service.sh`
- `deploy/langchain-service/templates/deployment.yaml`
- `deploy/langchain-service/values.yaml`
- `README.md`
- `skills/mementum-memory/SKILL.md`

## To Be Verified

- No lint or type-check command is configured in repo metadata.
- No CI workflow files were found under `.github/`.
