---
title: Codebase Map
status: active
category: architecture
tags: [repo, orientation, polylith]
related:
  - development-workflows
  - implementation-invariants
---

# Codebase Map

## Purpose

Give future contributors enough orientation to choose the right entry point without duplicating the repository tree.

## Current Understanding

This is a Python `xagent` repository using a loose Polylith structure.

High-value areas:

- `components/xagent/`: reusable bricks under the shared `xagent` namespace.
- `bases/xagent/`: executable entry points, including the HTTP API and LLM CLI.
- `projects/langchain_service/`: Docker packaging for the FastAPI LangChain service.
- `deploy/langchain-service/`: Helm chart and environment values for Kubernetes deployment.
- `test/`: tests mirror base/component structure; live provider tests live under `test/integration/`.
- `development/notebooks/`: local exploration notebooks.
- `changelogs/`: design and change rationale that should be consulted before changing LLM behavior.

Important entry points:

- `xagent-langchain-api` -> `xagent.api_http.main:main`.
- `xagent-langchain-sample` -> `xagent.langchain_cli.main:main`.
- `xagent-llm` -> `xagent.llm_cli.main:main`.
- Docker service entrypoint is `xagent-langchain-api`.

Architectural boundaries:

- Shared LLM contracts/config/retry/files/tools/structured/batch/registry bricks are separated from provider implementation bricks.
- `llm_registry.provider_protocol` defines the provider protocol and does not import providers.
- `llm_registry.factory.default_registry()` imports built-in providers lazily.
- Provider components map common contracts to provider-specific APIs and preserve raw responses.

## Generated or Do-Not-Edit Areas

- Do not manually edit generated Python caches, build artifacts, virtual environments, `.pytest_cache`, `.uv-cache`, or `.docker-build-test` output.
- `uv.lock` is a lockfile; update it through dependency tooling rather than hand editing.
- Notebook checkpoint directories are ignored and should not become project memory.

## Source Pointers

- `workspace.toml`
- `pyproject.toml`
- `projects/langchain_service/Dockerfile`
- `projects/langchain_service/README.md`
- `bases/xagent/api_http/main.py`
- `bases/xagent/llm_cli/main.py`
- `components/xagent/llm_registry/provider_protocol.py`
- `components/xagent/llm_registry/factory.py`
- `.gitignore`
- `.dockerignore`
- `changelogs/20250509-llm-api-layer-changes.md`

## Notes for Future Agents

- Do not add `src/` or `src/common_llm` style layout unless the Polylith configuration changes.
- Before changing LLM provider behavior, read the LLM changelog and relevant provider tests.
- Keep memory as an orientation map; use source files for detailed APIs.

## To Be Verified

- Whether project-level CI exists outside this checkout.
