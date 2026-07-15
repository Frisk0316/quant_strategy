---
status: current
type: handoff
owner: codex
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Context Handoff: Deribit perpetual D6 and H-021 E-055 - 2026-07-15

## Goal (one sentence)

Ingest venue-scoped Deribit BTC/ETH perpetual 1m candles and re-probe H-021's
frozen Stage-2 gates as E-055 without retuning or entering Stage 3.

## Current state

- Branch: `feature/h014-e052-shadow`.
- Last known good commit / state: `bc055e1`; the D6/E-055 changes are an
  uncommitted, verified working-tree delivery.
- In-progress edits (files): see the paired session handoff for the complete
  bounded file list.
- What works right now: credential-free paginated Deribit ingestion,
  checkpointed/resumable native perpetual storage, forward top-up, coverage
  checks, and the H-021 Stage-2 reprobe.
- What does not work / unfinished: E-055 still fails the frozen robust cost
  gate; inverse-perpetual accounting and Stage 3 remain unauthorized and were
  not implemented or run.

## Decisions made (and why)

- Store Deribit candles under native `BTC-PERPETUAL`/`ETH-PERPETUAL` IDs - the
  canonical primary key cannot store two venues under a shared instrument ID,
  while native IDs plus `source_primary='deribit'` preserve I19 provenance.
- Register those instruments as legacy `exchange='other'` - the pre-existing
  instrument registry CHECK has no Deribit value; widening schema/enums was not
  needed for this bounded canonical-candle path.
- Write through `CandleStore.upsert_canonical_candles` with `quality_status`
  `raw`, instrument-bar metadata, jobs, and checkpoints - the older raw-candle
  source enum also has no Deribit value, and exact canonical provenance is the
  required evidence surface.
- Stop after E-055 Stage 2 - Gate 1 passed, but the frozen conservative cost
  scenario still failed; the task explicitly forbids treating a possible
  basis-PnL rationale as permission for Stage 3.

## Open questions / unverified assumptions

- Whether basis convergence can offset the conservative funding-only proxy
  shortfall is intentionally untested. It requires a separately approved
  inverse-perpetual accounting decision and Stage-3 task for H-021.

## Rules in play (preserve verbatim)

- Invariants touched: I19 (`source_primary='deribit'`; never substitute an
  index or another venue) and I41 (existing bounded settlement alignment reused
  unchanged by E-055).
- Domain rules touched: none changed; existing R6.4/Stage-2 rules were applied.
- Do-not-touch: `research/`, H-014 shadow files, strategy/risk core, gates,
  existing result artifacts, differential validation, and all Stage-3/PnL
  surfaces.

## Context to load next (the reading list)

- Source of truth:
  `docs/superpowers/specs/2026-07-15-f-xvenue-funding-spread-hypothesis.md`,
  H-021 in `docs/HYPOTHESIS_LEDGER.md`, E-055 in
  `docs/EXPERIMENT_REGISTRY.md`, and `config/`.
- Owning files / MODULE_BRIEFS: `scripts/market_data/ingest.py`,
  `src/okx_quant/data/exchange_clients/deribit_public.py`,
  `backtesting/xvenue_funding_spread_probe.py`, and
  `src/okx_quant/data/candle_store.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` (no D6-specific
  pack exists).

## Checks run

- Targeted Deribit/venue-ingest/H-021/registry unit tests - PASS (21 tests).
- Ruff, config validation, docs checkers, strict doc impact, and diff hygiene -
  PASS; see the session handoff for exact commands and counts.
- Backtest smoke - PASS; its idealized fixture is not promotion evidence.
- Database coverage and six fixed public-API OHLC comparisons - PASS.

## Approvals

- Human approval needed / obtained: the user explicitly authorized D6 and the
  E-055 Stage-2 reprobe. No Stage-3, inverse-accounting, promotion, shadow, or
  deployment approval was requested or inferred.

## Next action (single, concrete)

- Claude reviews the bounded implementation, E-055 artifact, trial/K
  accounting, and the enforced stop condition.

## Human Learning Notes

Deribit's native perpetual IDs are not cosmetic in this schema: they prevent
the canonical `(inst_id, bar, ts)` key from collapsing venue identity. The
funding-only Stage-2 smell test can pass data availability and still fail the
cost gate; that is a deliberate stop, not evidence that Stage-3 basis PnL may
be run automatically.
