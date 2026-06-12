---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-12
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
**short** and **present-tense** — it is not a changelog (history goes to
`docs/CHANGELOG_AI.md`) and not a backlog (gaps go to `docs/KNOWN_ISSUES.md`).

This file complements `docs/AI_HANDOFF.md`: `AI_HANDOFF.md` is the working
handoff between sessions; this is the one-screen "where are we" that
[[CONTEXT_BUDGET]] marks must-load.

## Snapshot

- **Current goal:** Stand up the Doc Sync, Intelligence, and Context Resilience
  harnesses (docs/process scaffolding) without touching trading-core behavior.
- **Current branch:** `feature/chart-ux-overhaul`.
- **Last known good state:** repo builds; `make docs-check` is the doc gate;
  `make docs-impact` is newly added (advisory).
- **In progress:** harness documents and the doc-impact check.
- **Active risks:** several pre-existing uncommitted changes in the working tree
  (backtesting, scripts, src) are unrelated to this harness work — do not
  overwrite them.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, DB schema, API and
  frontend behavior, deployment gates. This task is docs/process only.

## Next steps

- Run `make docs-check`, `make docs-impact`, and `make verify`; record results
  in the session handoff.
- Adopt the harnesses in the next real change (create the first Change Manifest,
  first Context Pack for the active feature).

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` · [[CONTEXT_INDEX]] · [[CONTEXT_BUDGET]].
