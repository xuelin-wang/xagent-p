# Project Memory Feature Change Summary

Date: 2026-05-11

Compared against: `main`

Scope: project-memory related files only. This summary intentionally excludes unrelated working-tree changes such as `development/notebooks/test-llm-apis.ipynb`, `.swp`, and unrelated prompt edits.

## Feature-Level Summary

This change introduces a Git-backed, Mementum-style project memory layer for the repository.

The feature adds:

1. Shared agent instructions for Codex and Claude Code.
2. A `mementum/` directory containing current project state, synthesized knowledge pages, short durable memories, and reusable templates.
3. A design/reference document describing the intended project-memory bootstrap.
4. Repo-derived memory that captures high-value orientation facts, workflows, testing strategy, security boundaries, architectural invariants, decisions, and open questions without copying the whole repository.

## Rationale

The repository already contains design rationale, provider behavior, deployment practices, and testing conventions spread across source files, changelogs, scripts, Helm values, and tests. Future AI agents and human contributors would otherwise need to rediscover the same context repeatedly.

The memory layer is intended to:

- Reduce startup time for future implementation sessions.
- Preserve durable engineering context that is not obvious from code alone.
- Keep agent guidance checked into the repository rather than relying on local conversation history.
- Make important constraints explicit, such as loose Polylith layout, LLM provider boundaries, live-test gating, and secret handling.
- Avoid storing runtime data, secrets, logs, private data, or large generated artifacts.

## File-by-File Breakdown

## `AGENTS.md`

Adds shared repository instructions for Codex and other AI coding agents.

Meaningful lines:

- Lines 1-13 define the project-orientation workflow: read `mementum/state.md`, search knowledge and memories, inspect code, and prefer small testable changes.
- Lines 15-40 define what project memory is and is not for, with explicit exclusions for secrets, raw logs, runtime records, and large generated artifacts.
- Lines 42-56 define when to propose memory updates and when not to add noisy memory.
- Lines 58-66 define implementation principles: understand code first, preserve behavior, keep changes focused, update tests when behavior changes, and separate facts from assumptions.
- Lines 68-78 define conflict-resolution priority, with explicit user requests and safety/security constraints above project memory.

Rationale:

- Provides a single checked-in source of agent guidance.
- Makes project memory discoverable before major design or implementation work.

## `CLAUDE.md`

Adds Claude Code-specific entrypoint guidance.

Meaningful lines:

- Line 1 imports `AGENTS.md`.
- Lines 3-5 clarify that `AGENTS.md` is the shared instruction source.
- Lines 7-13 repeat the large/ambiguous-change workflow for Claude Code.
- Line 15 reinforces concise, accurate, safe-to-commit memory.

Rationale:

- Lets Claude Code use the same shared repository rules as Codex while keeping Claude-specific notes minimal.

## `changelogs/20250510-project-memory-for-coding-agents-design.md`

Adds the design/reference prompt used to bootstrap the project-memory layer.

Meaningful sections:

- Opening paragraphs explain why checked-in guidance is preferred over local-only memory.
- Goal section defines the memory layer as lightweight, Git-backed, engineering-focused context.
- High-level design section specifies `mementum/state.md`, `mementum/memories/`, and `mementum/knowledge/`.
- Required-files section lists the expected root guidance files, memory files, knowledge pages, and templates.
- AGENTS/CLAUDE sections provide baseline content for cross-agent instructions.
- Mementum README/state/memory/knowledge/template sections provide initial content patterns.
- Final validation section requires showing the tree, summarizing additions, avoiding application-code changes, avoiding invented architecture, and checking that sensitive data was not added.

Rationale:

- Preserves the design intent behind the memory system.
- Gives future maintainers a reference for why the folder structure and content standards exist.

## `mementum/README.md`

Adds top-level documentation for the project-memory directory.

Meaningful lines:

- Lines 1-5 define the directory as repo-local project memory.
- Lines 7-15 document the four memory areas: state, memories, knowledge, and templates.
- Lines 17-29 list acceptable durable engineering/project context.
- Lines 31-44 list data that must not be stored in project memory.
- Lines 46-55 describe the agent workflow for using memory.
- Lines 57-61 define the maintenance rule for keeping memory concise and current.

Rationale:

- Provides a local index for humans and agents entering `mementum/`.

## `mementum/state.md`

Adds current project state.

Meaningful lines:

- Lines 3-9 summarize the current direction: Python `xagent` workspace, loose Polylith layout, LLM wrapper, LangChain service, and engineering-only memory.
- Lines 11-15 capture current focus: preserve Polylith boundaries, provider-specific LLM behavior, deterministic tests, and secret hygiene.
- Lines 17-21 list next steps around CI verification, lint/type-check adoption, and ongoing memory hygiene.
- Lines 23-27 list known unknowns: no checked-in CI found, no configured lint/type-check command, and TODO-level logging/tracing notes.
- Lines 29-34 record recent decisions: project memory was added, `AGENTS.md`/`CLAUDE.md` establish guidance, provider mutations should not auto-retry, and native batch input files remain unsupported.
- Lines 36-44 provide source pointers.

Rationale:

- Gives future sessions a short, current entrypoint before inspecting the broader repo.

## `mementum/knowledge/README.md`

Adds guidance for synthesized knowledge pages.

Meaningful lines:

- Defines knowledge pages as longer-lived than short memories.
- Recommends frontmatter fields for title, status, category, tags, and related pages.
- Provides maintenance guidance to keep pages concise, decision-focused, and explicit when superseded.

Rationale:

- Establishes consistent formatting and maintenance expectations for knowledge pages.

## `mementum/knowledge/project-memory-policy.md`

Adds the policy page for project memory.

Meaningful lines:

- Lines 1-9 add active policy frontmatter.
- Lines 13-17 define project memory as durable context not obvious from code alone.
- Lines 19-30 list acceptable memory content.
- Lines 31-40 list disallowed memory content.
- Lines 42-50 define the quality bar for adding memory.
- Lines 52-61 define the agent workflow.
- Lines 63-67 state that project memory should be reviewed like repository documentation.

Rationale:

- Keeps the policy in `mementum/knowledge/` rather than relying only on root agent instructions.

## `mementum/knowledge/codebase-map.md`

Adds a selective orientation map.

Meaningful lines:

- Lines 1-9 add active architecture frontmatter.
- Lines 13-15 state the page purpose: orient without duplicating the repo tree.
- Lines 17-29 summarize high-value areas: `components/`, `bases/`, `projects/`, `deploy/`, `test/`, `development/notebooks/`, and `changelogs/`.
- Lines 31-36 list key entry points and scripts.
- Lines 38-43 capture architectural boundaries between shared LLM bricks, registry protocol/factory, and provider implementations.
- Lines 45-49 identify generated or do-not-edit areas.
- Lines 51-63 provide source pointers.
- Lines 65-69 add future-agent notes.
- Lines 71-73 leave CI location as a verified unknown.

Rationale:

- Gives a map of the repository without listing every file or copying source details.

## `mementum/knowledge/architecture-decisions.md`

Adds durable architecture decisions.

Meaningful lines:

- Lines 1-9 add active architecture-decision frontmatter.
- Lines 13-15 define the page as a place for decisions with continuing value.
- Lines 19-39 record the provider-pluggable LLM wrapper decision and its implications.
- Lines 41-58 record the decision to use the existing loose Polylith layout.
- Lines 60-79 record the decision not to auto-retry provider resource mutations.
- Lines 81-98 record the decision that native batch inputs come from request items rather than public pre-uploaded batch input files.

Rationale:

- Moves important changelog/design lessons into a durable, searchable decision page.

## `mementum/knowledge/implementation-invariants.md`

Adds implementation rules that should remain true.

Meaningful lines:

- Lines 1-9 add active design frontmatter.
- Lines 13-15 define invariants as rules requiring coordinated design/test/memory updates if changed.
- Lines 17-29 list current invariants:
  - Preserve loose Polylith layout.
  - Keep shared LLM bricks independent of provider implementations.
  - Keep provider imports out of registry protocol.
  - Normalize common LLM shapes without hiding provider differences.
  - Fail Anthropic embeddings explicitly.
  - Avoid automatic retries for provider resource mutations.
  - Keep native batch API item-based.
  - Keep runtime config strict.
  - Exclude live provider tests by default.
  - Keep project memory free of secrets and runtime data.
- Lines 31-43 provide source pointers.
- Lines 45-47 explain how future invariant changes should be handled.

Rationale:

- Converts easy-to-miss architectural constraints into a concise implementation checklist.

## `mementum/knowledge/development-workflows.md`

Adds common development workflow commands and caveats.

Meaningful lines:

- Lines 1-9 add active workflow frontmatter.
- Lines 13-15 define the page purpose.
- Lines 17-24 document dependency/package-management commands.
- Lines 26-30 document the default deterministic test command.
- Lines 32-36 document opt-in live provider tests.
- Lines 38-42 document running the LangChain API locally.
- Lines 44-49 document LLM CLI examples.
- Lines 51-55 document Docker image build.
- Lines 57-61 document the local `kind`/Helm smoke test.
- Lines 63-68 capture workflow notes around pytest defaults, runtime config, Helm config/secrets, and smoke-test prerequisites.
- Lines 70-80 provide source pointers.
- Lines 82-85 identify missing lint/type-check and CI configuration.

Rationale:

- Gives future contributors the commands most likely to be needed before changing code.

## `mementum/knowledge/testing-and-evaluation.md`

Adds testing and validation strategy.

Meaningful lines:

- Lines 1-9 add active testing frontmatter.
- Lines 13-15 define the page purpose.
- Lines 17-23 summarize test structure, default live-test exclusion, live-test coverage, and Kubernetes smoke testing.
- Lines 25-31 give the default test command.
- Lines 33-39 give focused test examples for provider and CLI changes.
- Lines 41-45 give the live provider test command.
- Lines 47-51 give the Kubernetes smoke-test command.
- Lines 53-57 list testing gaps.
- Lines 59-67 provide source pointers.
- Lines 69-72 add future-agent testing notes.

Rationale:

- Makes validation expectations discoverable without duplicating every test file.

## `mementum/knowledge/security-and-data-boundaries.md`

Adds repo-visible security and data-handling boundaries.

Meaningful lines:

- Lines 1-8 add active security frontmatter.
- Lines 12-14 define the page purpose.
- Lines 16-25 summarize boundaries around secrets, runtime data, config loading, nested env keys, Helm ConfigMap/Secret split, External Secrets Operator guidance, local `kind` secret creation, and provider logging exclusions.
- Lines 27-39 provide source pointers.
- Lines 41-44 add future-agent notes about treating runtime/provider payloads as data.
- Lines 46-48 record logging/tracing policy as still to be verified.

Rationale:

- Reduces the chance that future memory updates or deployment edits commit sensitive/runtime data.

## `mementum/knowledge/open-questions.md`

Adds unresolved project questions.

Meaningful lines:

- Lines 1-8 add active open-question frontmatter.
- Lines 12-14 define the page purpose.
- Lines 18-29 record the open CI-location question.
- Lines 31-42 record the open lint/type-check question.
- Lines 44-57 record the open logging/tracing-policy question.

Rationale:

- Separates verified facts from unresolved areas and prevents future agents from inventing answers.

## `mementum/memories/README.md`

Adds memory-file guidance.

Meaningful lines:

- Defines memories as short durable observations.
- Specifies that each memory should be one insight, short, useful, safe to commit, and searchable.
- Provides the suggested memory format and symbol meanings.

Rationale:

- Keeps memory files concise and prevents noisy accumulation.

## `mementum/memories/do-not-store-runtime-data-in-project-memory.md`

Adds a safety memory.

Meaningful lines:

- Title and symbol identify a caution.
- Main body states that `mementum/` is for engineering/project context only.
- The disallowed-data list excludes runtime records, raw logs, user/customer/production data, secrets, credentials, and large generated artifacts.
- Rationale explains Git durability and privacy/access-control concerns.
- Future implication directs runtime data to runtime datastores instead of project memory.

Rationale:

- Makes the most important memory-boundary rule searchable as a standalone durable lesson.

## `mementum/memories/project-memory-is-engineering-context.md`

Adds a purpose memory.

Meaningful lines:

- Title and symbol identify a decision.
- Main body says project memory helps future engineering sessions start with better context.
- Rationale explains why agents and humans benefit from preserved rationale.
- Future implication limits memory additions to content likely to help future design or implementation.

Rationale:

- Clarifies that the feature is not application runtime memory.

## `mementum/memories/update-memory-when-lessons-become-durable.md`

Adds a maintenance memory.

Meaningful lines:

- Title and symbol identify a recurring pattern.
- Main body says durable lessons should update project memory.
- Good examples include design decisions, repeated mistakes, important conventions, validated strategies, and resolved open questions.
- Avoid list excludes temporary notes, obvious facts, speculation, sensitive data, and routine summaries.
- Future implication asks agents to consider memory updates after substantial work.

Rationale:

- Encourages useful updates without turning memory into a scratchpad.

## `mementum/memories/preserve-loose-polylith-boundaries.md`

Adds a repo-specific architecture memory.

Meaningful lines:

- Title and symbol identify an accepted decision.
- Main body says shared code belongs under `components/xagent` and executable code under `bases/xagent`.
- Rationale ties this to package/build config, tests, and LLM component boundaries.
- Source pointers link to `workspace.toml`, `pyproject.toml`, and the LLM design changelog.
- Future implication warns against adding a parallel `src/` tree unless architecture changes intentionally.

Rationale:

- Captures a high-value convention that is easy to violate during new feature work.

## `mementum/memories/provider-mutations-are-not-auto-retried.md`

Adds a provider-behavior memory.

Meaningful lines:

- Title and symbol identify a caution.
- Main body says provider resource mutations are sent once by default.
- Rationale explains duplicate resource and ambiguous delete risks.
- Source pointers link to the changelog and both provider implementations.
- Future implication requires caller-owned idempotency or deduplication before changing retry behavior.

Rationale:

- Preserves a production-hardening lesson that could otherwise be accidentally regressed.

## `mementum/memories/live-provider-tests-are-opt-in.md`

Adds a testing memory.

Meaningful lines:

- Title and symbol identify a validated pattern.
- Main body states normal pytest runs exclude live provider tests.
- Rationale explains credentials, network, availability, and cost.
- Source pointers link to pytest config and live provider tests.
- Future implication instructs agents to use `-m require_env` explicitly for real provider validation.

Rationale:

- Prevents accidental live provider calls during routine validation.

## `mementum/memories/runtime-config-env-overrides-files.md`

Adds a runtime-config memory.

Meaningful lines:

- Title and symbol identify an insight.
- Main body states config files load first and matching environment variables overlay them.
- Rationale explains Kubernetes `envFrom` override behavior and nested double-underscore keys.
- Source pointers link to runtime config, config parsing, service README, and Helm deployment.
- Future implication tells agents to check environment variables when debugging config differences.

Rationale:

- Captures a deployment/config behavior that is important but not obvious from a single file.

## `mementum/templates/memory.md`

Adds a reusable short-memory template.

Meaningful lines:

- Provides title, symbol, lesson, why-it-matters, future implication, and related sections.

Rationale:

- Standardizes future memory additions.

## `mementum/templates/knowledge.md`

Adds a reusable knowledge-page template.

Meaningful lines:

- Provides frontmatter for title, status, category, tags, and related pages.
- Provides sections for summary, context, details, decisions/rules, implications, and related files.

Rationale:

- Standardizes future synthesized knowledge pages.

## `mementum/templates/decision.md`

Adds a reusable architecture-decision template.

Meaningful lines:

- Provides a dated decision heading.
- Provides status, decision, context, alternatives, rationale, implications, and follow-up sections.

Rationale:

- Makes future architecture decisions easier to record consistently.

## Overall Impact

The change adds a project-memory system without changing application code.

The most important behavioral impact is on future development workflow: agents and contributors now have explicit guidance to consult memory before major work, preserve current architectural boundaries, run appropriate validation, and update memory only for durable lessons.

## Notes and Follow-Up

- `AGENTS.md` and `CLAUDE.md` are part of the project-memory feature but were untracked at the time this summary was written.
- `mementum/` files are staged as new project-memory documentation.
- Unrelated notebook output and unrelated prompt edits are intentionally excluded from this summary.
- The memory layer currently records CI, lint/type-check configuration, and logging/tracing policy as open or to-be-verified areas.
