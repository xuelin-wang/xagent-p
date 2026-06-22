# Drafts

This directory contains design work that is not yet approved or stable.

Store here:

- raw thinking and partial notes
- meeting notes
- AI-human back-and-forth design discussions
- working drafts
- proposals under review

## Lifecycle

```
drafts/   →  (approved)  →  knowledge/
          →  (abandoned) →  delete or archive
```

When a draft is approved and stable, move it to `knowledge/` and update its frontmatter to `status: active`.

## Suggested Frontmatter

```yaml
---
title: Draft Title
status: draft
category: architecture | design | workflow | policy | testing | security | open-question
tags: []
related: []
---
```

## Notes

- Files here are works-in-progress — do not treat them as authoritative.
- Raw notes and meeting transcripts do not need frontmatter.
- Delete or supersede stale drafts rather than leaving them to accumulate.
