---
name: pr-desc
description: Summarize the current branch's changes relative to main for a pull request description. Produces a concise, reviewer-focused summary with rationale and per-file change notes.
---

# PR Description

Use this skill to generate a pull request description for the current branch.

## Goal

Produce a description that helps a reviewer understand:

- **Why** the changes were made (rationale, motivation, context)
- **What** changed at a meaningful level (not a rehash of the diff)
- **Where to focus** during review (non-obvious decisions, trade-offs, risk areas)

Do not restate facts that are immediately obvious from reading the diff. Omit trivial changes entirely.

## Process

1. Identify the base: `git merge-base main HEAD` to find the branch point.
2. Get the commit list: `git log --oneline <base>..HEAD`.
3. Get the diff summary: `git diff --stat <base>..HEAD`.
4. Read the full diff: `git diff <base>..HEAD`.
5. Identify the intent: what problem does this branch solve, or what capability does it add?
6. Identify non-obvious decisions, trade-offs, or risks in the changes.
7. Group related file changes together where it aids understanding.

## Output Format

Produce the description in this structure:

---

## Summary

One to three sentences. What this branch does and why. Focus on intent and impact, not mechanics.

## Rationale

Bullet points. Why these changes were necessary or chosen this way. Skip if the summary is self-explanatory.

## Changes

Per-file or per-group notes. For each, write one short sentence explaining the **non-obvious** aspect of the change — the decision made, the constraint respected, or the risk mitigated. Skip files where the change is self-evident from the filename and diff (e.g. a rename, a trivial config value update, or a mechanical type annotation fix).

## Review Notes

Optional. Flag anything that warrants extra attention: trade-offs left open, areas of higher risk, things that are intentionally incomplete, or decisions the reviewer should validate.

---

## Quality Bar

- If a file change can be described as "updated X to Y" and that is already clear from the diff, omit it.
- Prefer one sharp sentence over two vague ones.
- Do not list every file if a group description covers them equally well.
- Do not invent rationale — if the intent is unclear from commits and code, say so.
