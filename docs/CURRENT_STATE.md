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
  Binance DB-backed source-provenance milestone now has durable repo-local
  `db_parity` PASS evidence.
- **Current branch:** `codex/impl-multi-venue-instrument-specs`.
- **Last known good state:** Commits through `d48361c`, plus this follow-up,
  implement Tasks 1-6, structural Binance/Bybit USDT-M `ct_val =
  exchange_base_unit`, DB parity exchange scoping, and source-scoped regression
  coverage. No existing result artifacts were modified.
- **Current working state:** Local ADR-0007 P1 closeout is implemented.
  `db_parity` reports `canonical_source_primary`, scopes canonical reads to the
  run exchange, and now compares timestamped `close` only for `price_series.csv`
  provenance. A direct 2026-06-18 check of the saved Binance run matched 192/192
  artifact closes to DB canonical Binance closes with zero mismatches. Durable
  source-provenance evidence now lives at
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/validation_result.json`
  and passes `ct_val_provenance`, `db_parity`, and `ohlcv_source_validation`.
- **Active risks:** The older checked-in validation artifact
  `adr0007_binance_btc_1h_db_pass_20260618_source_provenance` still records the
  pre-fix FAIL and now carries `SUPERSEDED.md`; cite the new
  `codex_close_only_db_parity_pass_20260618` artifact for PASS evidence. Port
  5432 repo DSN is currently reachable; local PostgreSQL on port 5433 still
  rejects the repo `quant` credentials.
- **Do-not-touch:** trading-core (`strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`), PnL/fee/funding behavior, DB schema, API and
  frontend behavior, deployment gates, and existing result artifacts.

## Next steps

- Ask Claude to review ADR-0007 P1 docs/manifest, seed values, and the
  source-scoped DB parity PASS evidence before PR merge.

## How to update

Overwrite the snapshot whenever it goes stale; do not append history. Move
completed detail to `docs/CHANGELOG_AI.md` and durable gaps to
`docs/KNOWN_ISSUES.md`.

Related: `docs/AI_HANDOFF.md` and [[CONTEXT_INDEX]] and [[CONTEXT_BUDGET]].
