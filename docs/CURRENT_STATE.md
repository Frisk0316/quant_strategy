---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-17
expires: none
superseded_by: null
---

# Current State

A small, always-current snapshot a session can trust on a cold start. Keep this
**short** and **present-tense** - it is not a changelog (history goes to
`docs/CHANGELOG_AI.md`) and not a backlog (gaps go to `docs/KNOWN_ISSUES.md`).

This file complements `docs/AI_HANDOFF.md`: `AI_HANDOFF.md` is the working
handoff between sessions; this is the one-screen "where are we" that
[[CONTEXT_BUDGET]] marks must-load.

## Snapshot

- **Current goal:** ADR-0007 P1 multi-venue instrument specs are locally
  implemented and verified on `codex/impl-multi-venue-instrument-specs`.
- **Current branch:** `codex/impl-multi-venue-instrument-specs`.
- **Last known good state:** Commits through `7be7f65` implement Tasks 1-5:
  venue specs migration/seed, exchange-aware `ct_val` resolution, exchange-tagged
  provenance, source-gate exchange surfacing, and Run Backtest exchange selection.
- **Current working state:** Task 6 adds the convergence golden case, required
  docs/manifest updates, and final local verification. No existing result
  artifacts were modified.
- **Active risks:** DB seed/application was not run in this shell because
  `DATABASE_URL` and `psql` were unavailable. The first DB-backed source
  provenance PASS is still unverified.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, DB schema, API and
  frontend behavior, deployment gates, and existing result artifacts.

## Next steps

- Apply `sql/migrations/0011_venue_instrument_specs.sql` and
  `sql/seed_venue_instrument_specs.sql` against a reachable dev DB, then run the
  source-provenance gate against a fresh Binance run.
- Ask Claude to review ADR-0007 P1 docs/manifest and the seed values before a
  shared DB application or PR merge.
- Preserve the unrelated dirty `docs/backtest_external_validation_report_zh.pptx`.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].
