---
status: current
type: handoff
owner: codex
created: 2026-08-06
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# Context Handoff: OKX 2020+ canonical promotion — 2026-08-06

## Goal (one sentence)

Verify and document the authorized ADR-0014 BTC/ETH OKX 1m historical-window
extension without changing the Binance-resolved layer, funding, or artifacts.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good state: DB verification PASS on 2026-08-06; git commit
  `b40f15b` already contains the 2026-07-18 implementation/execution record.
- In-progress edits: ADR/data-flow/runbook/changelog/current-state/workstream
  docs and this task's handoffs only.
- What works: `[2020-01-01, 2026-06-17)` has 3,396,960 raw and OKX venue rows
  per symbol, exact OHLCV parity, 1.0 alignment, and no gaps.
- Unfinished: Claude/user review of the ADR amendment and delivery diff.

## Decisions made (and why)

- No Python change — existing CLI flags, guards, verifier, and tests already
  cover the requested window; duplicate implementation would add no behavior.
- Record the run as re-verification, not a new 4.2M-row insertion — the DB was
  already complete before this session wrote anything.

## Open questions / unverified assumptions

- Any future power floor must use the measured joined observations for its
  exact consumer; no generic power floor was computed in this data-only task.

## Rules in play (preserve verbatim)

- I19: no source-less parquet or alternate venue may substitute missing bars.
- I47: source-aware promotion matches closed raw OHLCV and never replaces a
  corrected/validated same-source row.
- Do-not-touch: strategy/signals/risk/portfolio/execution, funding,
  `results/**`, `research/**`, and canonical Binance contents.

## Context to load next (the reading list)

- Source of truth: `docs/ADR/0014-source-aware-canonical-candles.md`.
- Owning files: `scripts/promote_okx_canonical_1m.py`,
  `scripts/verify_okx_1m_backfill.py`,
  `tests/unit/test_venue_canonical_promotion.py`.
- Context Pack: none exists for canonical candles; use `docs/CONTEXT_INDEX.md`.

## Checks run

- Pre-write raw coverage (identical in `market_klines` and `raw_candles`):
  BTC `2020-01-01 00:00`→`2026-07-01 14:59`, 3,418,020 rows; ETH
  `2020-01-01 00:00`→`2026-06-16 23:59`, 3,396,960 rows.
- Pre-write gap SQL — each symbol had 2,103,840/2,103,840 pre-2024 minutes,
  zero missing minutes, zero gap runs, and largest gap zero minutes.
- Promotion twice — both symbols returned `promoted=0`, `venue_promoted=0`.
- Full-range verifier — PASS; 3,396,960 rows per leg, mismatch 0.
- Binance affected-window before/after — unchanged at 3,396,960 per symbol.
- Targeted pytest — `10 passed in 2.86s`.
- Docs metadata/links/ledger, doc-impact, and config checks — PASS.

## Approvals

- User authorization obtained 2026-08-06. Claude/user amendment review pending.

## Next action (single, concrete)

- Claude reviews the ADR amendment, evidence, and permitted-file-only diff.

## Human Learning Notes

The data extension was already completed in July, but stale current-state text
made it look pending. Measure live state and inspect git history before
re-running large data operations; here that turned the operation into a safe
no-op confirmation and prevented a false claim of newly inserted rows.
