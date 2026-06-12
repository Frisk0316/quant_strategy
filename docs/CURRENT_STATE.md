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

- **Current goal:** Doc Sync, Intelligence, and Context Resilience harnesses are
  in place; `docs-impact` is now wired into CI. No trading-core behavior touched.
- **Current branch:** `feature/chart-ux-overhaul`.
- **Last known good state:** harness scaffolding committed (`7d7128a`) and
  pushed; `make verify` green. `docs-impact` runs strict on PRs, advisory on
  push to `main` (`.github/workflows/ci.yml` `docs` job).
- **In progress:** none for the harness; CI wiring + PR template + runbook update
  are the active uncommitted change.
- **Active risks:** the in-flight backtest-validation work (`backtesting/`,
  `scripts/run_replay_backtest.py`, `tests/`) is a business-rule change (A5/A9)
  and will need its own Change Manifest before its PR can pass strict
  `docs-impact`. Do not overwrite that work — it is another session's.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, DB schema, API and
  frontend behavior, deployment gates. This task is docs/process only.

## Next steps

- The backtest-validation session must add a Change Manifest (A5/A9) so its PR
  passes the new strict CI gate.
- Decide via branch protection whether the `docs` CI job is a required check.
- Backfill lifecycle metadata on the 11 pre-existing metadata-less docs.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` · [[CONTEXT_INDEX]] · [[CONTEXT_BUDGET]].
