---
name: generate-changelog
version: 1
status: active
purpose: Generate a detailed changelog comparing the current branch to main.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Generate Changelog

## When to Use

Use this when you want a detailed explanation of current branch changes.

## Prompt

```text
Compare the current branch against the `main` branch.

Create a detailed change summary that includes:
1. A feature-level summary of all changes introduced by the current branch.
2. The rationale or likely motivation for each major change.
3. A file-by-file breakdown of all changed files.
4. A line-by-line interpretation of the meaningful changes in each changed file.

Write the final report to:

`changelogs/YYYYMMDD-feature-summary-changes.md`

Replace `YYYYMMDD` with today's date.

Do not modify application code. Only create or update the changelog file.
Do not include unrelated local artifacts, secrets, runtime data, private data, raw logs, or large generated outputs.
```

## Expected Output

- Markdown changelog file.
- Summary of inspected files and commands.
- No application code changes.
