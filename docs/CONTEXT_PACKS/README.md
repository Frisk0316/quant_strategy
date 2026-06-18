---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Context Packs

A **Context Pack** is a curated, minimal reading list for one feature or work
area: exactly what a session must load to work on it safely, and nothing more.
Packs operationalize [[CONTEXT_BUDGET]] — instead of loading the whole repo, load
the pack.

A pack is a pointer file: it links the authoritative files; it does not copy
their content (copies go stale and become a second, wrong source of truth).

## When to create one

- Starting sustained work on a feature/area that spans several files.
- Resuming an area after a context reset.
- Handing an area to another session.

## Pack template

```markdown
---
status: current
type: reference
owner: <human|claude|codex>
created: <YYYY-MM-DD>
last_reviewed: <YYYY-MM-DD>
expires: none
superseded_by: null
---

# Context Pack: <feature / area>

## Goal
<what work this pack supports, one sentence>

## Must read (authority)
- <source-of-truth files: config / research / ADR / DOMAIN_RULES ids>

## Owning files
- <code paths; link the MODULE_BRIEFS entry if one exists>

## Rules in play
- Invariants: <INVARIANTS ids>
- Failure modes to watch: <FAILURE_MODES ids>

## Tests / checks
- <commands and test paths that verify this area>

## Out of scope / do not touch
- <explicit list>
```

## Index

| Pack | Area |
|---|---|
| [harness-scaffolding.md](harness-scaffolding.md) | Doc/Intelligence/Context harnesses |

Keep the index in sync when adding a pack. Related: [[../CONTEXT_INDEX]] ·
[[../CONTEXT_BUDGET]].
