---
name: prune-stale-memory
version: 1
status: active
purpose: Find and correct stale, misleading, or unsafe project memory.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Prune Stale Memory

## When to Use

Use this when project memory may be outdated, misleading, redundant, or unsafe to keep.

## Prompt

```text
Audit `mementum/` for stale or misleading memory.

Inspect:
1. `mementum/state.md`
2. `mementum/knowledge/`
3. `mementum/memories/`
4. Source files, tests, docs, scripts, and config referenced by memory

Look for:
- claims that conflict with current repo files
- obsolete next steps, blockers, or decisions
- duplicated memories that should be synthesized
- memory that is too broad, too obvious, or too noisy
- missing source pointers for repo-derived facts
- sensitive data, runtime records, raw logs, private data, or large generated artifacts

When fixing:
1. Treat current repo files as source of truth.
2. Update memory in place when the corrected version is still useful.
3. Mark knowledge pages as superseded when historical context matters.
4. Move repeated lessons into knowledge pages when appropriate.
5. Remove or replace unsafe content.

After editing, summarize:
1. Stale or risky memory found.
2. Files updated.
3. Source pointers used.
4. Remaining to-be-verified items.
5. Confirmation that no sensitive/runtime data was added.
```

## Expected Output

- Cleaned project memory.
- Summary of stale items and fixes.
- Remaining uncertainties.
