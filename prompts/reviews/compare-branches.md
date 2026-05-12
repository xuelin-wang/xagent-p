---
name: compare-branches
version: 1
status: active
purpose: Compare two branches and summarize meaningful differences.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Compare Branches

## When to Use

Use this when asking an agent to compare two branches for change scope, risk, or review preparation.

## Prompt

```text
Compare the current branch against the target branch.

Default target branch: `main`.

Please:
1. Inspect the branch diff, including staged, unstaged, and untracked files if the task is local.
2. Group changes by feature or purpose.
3. Identify unrelated files or generated artifacts.
4. Identify risky changes and missing validation.
5. Note project-memory changes separately from application-code changes.
6. Summarize commands inspected or run.

Do not modify files.
Do not include secrets, runtime data, raw logs, private data, or large generated artifacts in the response.
```

## Expected Output

- Feature-level comparison.
- File groups by purpose.
- Risk and validation notes.
- Unrelated-file callouts.
