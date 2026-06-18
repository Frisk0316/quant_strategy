---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-06-18
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

- **Current goal:** ADR-0007 P1 multi-venue instrument specs are locally closed
  out on `codex/impl-multi-venue-instrument-specs`; the validation workstream's
  Binance DB-backed PASS milestone is unblocked by code/docs and now fails on
  artifact-vs-canonical OHLC parity.
- **Current branch:** `codex/impl-multi-venue-instrument-specs`.
- **Last known good state:** Commits through `d48361c`, plus this follow-up,
  implement Tasks 1-6, structural Binance/Bybit USDT-M `ct_val =
  exchange_base_unit`, DB parity exchange scoping, and source-scoped regression
  coverage. No existing result artifacts were modified.
- **Current working state:** Local unit/docs checks pass for the ADR-0007 P1
  closeout. `db_parity` now reports `canonical_source_primary`, and Binance
  PASS evidence must show it is `binance`. A 2026-06-18 DB-backed Binance run
  showed that source scoping works (`canonical_source_primary == "binance"`),
  but `db_parity` FAILs because replay `price_series.csv` collapses OHLC to the
  close/mid while DB canonical candles preserve true OHLC.
- **Active risks:** DB-backed Binance source-provenance PASS is blocked by that
  artifact OHLC semantic mismatch. Port 5432 repo DSN is currently reachable;
  local PostgreSQL on port 5433 still rejects the repo `quant` credentials.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, DB schema, API and
  frontend behavior, deployment gates, and existing result artifacts.

## Next steps

- Fix replay artifact OHLC semantics or the DB parity input contract, then rerun
  the Binance DB-backed source-provenance gate following `docs/RUNBOOK.md`.
- Ask Claude to review ADR-0007 P1 docs/manifest, seed values, and the
  source-scoped DB parity evidence requirement before PR merge.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].
