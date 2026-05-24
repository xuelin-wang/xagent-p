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

Run lint and format checks:

```bash
uv run --active ruff check .
uv run --active ruff format --check .
uv run --active mypy components bases
```

Auto-fix lint and format:

```bash
uv run --active ruff check --fix .
uv run --active ruff format .
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

Run the custom agent-flow CLI with the local deterministic config:

```bash
uv run --active xagent-agent-flow --config development/config/agent-flow.local.yaml run "diagnose intermittent no-start"
```

Run the demo UI in development (two terminals):

```bash
# Terminal 1 — backend (fake executors, CORS allowed for Vite dev server)
XAGENT_API_HTTP_CONFIG=development/config/api-http.dev.yaml \
  uv run --active uvicorn xagent.api_http.app:app --reload --port 8000

# Terminal 2 — Vite dev server (proxies /agent-flow/* to localhost:8000)
cd bases/xagent/demo_ui
npm install   # first time only
npm run dev   # opens http://localhost:5173
```

Build the demo UI for production (embeds into the FastAPI static mount at `/demo`):

```bash
cd bases/xagent/demo_ui
npm run build
# Output goes to dist/, which must be copied to
# bases/xagent/api_http/static/demo/
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
- Runtime config accepts `--config` for YAML files and `--env` for env-style files; explicit field metadata controls which environment variables are eligible to override config values, and the env var name must match the field metadata exactly.
- Provider API key env binding belongs on provider-specific config models, not in provider clients or factories.
- Helm deploys render non-secret `appConfig` into a ConfigMap and inject secrets through `envFrom`.
- The `kind` smoke-test script requires Docker, kind, kubectl, helm, curl, and `OPENAI_API_KEY`.
- Repo-local skill sources live under `skills/`; agent-specific discovery folders should symlink to them rather than copying skill files.

## Source Pointers

- `pyproject.toml`
- `workspace.toml`
- `components/xagent/config/runtime.py`
- `components/xagent/config/loader.py`
- `components/xagent/llm_config/settings.py`
- `projects/langchain_service/README.md`
- `projects/langchain_service/Dockerfile`
- `scripts/test-kind-langchain-service.sh`
- `deploy/langchain-service/templates/deployment.yaml`
- `deploy/langchain-service/values.yaml`
- `README.md`
- `skills/mementum-memory/SKILL.md`
- `.github/workflows/ci.yml`
- `bases/xagent/demo_ui/`
- `development/config/api-http.dev.yaml`
- `mementum/knowledge/demo-ui-design.md`
