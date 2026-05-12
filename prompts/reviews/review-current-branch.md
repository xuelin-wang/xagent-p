---
name: review-current-branch
version: 1
status: active
purpose: Review the current branch for bugs, risks, regressions, and missing tests.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Review Current Branch

## When to Use

Use this when asking an agent to review local branch changes before merge.

## Prompt

```text
Review the current branch against `main`.

Focus on:
1. Bugs and behavioral regressions.
2. Architecture or boundary violations.
3. Missing or weak tests.
4. Security, privacy, or data-handling risks.
5. Generated artifacts, logs, secrets, or unrelated files accidentally included.
6. Stale or misleading project memory updates.

Before reviewing:
1. Read `AGENTS.md`.
2. Read `mementum/state.md`.
3. Search relevant `mementum/knowledge/` and `mementum/memories/`.
4. Inspect the branch diff and relevant source files.

Output findings first, ordered by severity.
For each finding, include:
- severity
- file and line reference
- problem
- why it matters
- suggested fix

If no issues are found, say so clearly and mention residual risks or unrun tests.
Do not modify files unless explicitly asked.
```

## Expected Output

- Findings first, ordered by severity.
- Open questions or assumptions.
- Brief summary only after findings.
