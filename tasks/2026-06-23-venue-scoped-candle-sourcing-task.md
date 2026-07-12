---
status: archived
type: task
owner: claude
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Claude → Codex Task: Venue-scoped candle sourcing (structural fix)

> Supersedes the "re-run" half of `tasks/2026-06-23-binance-rerun-revalidate-task.md`.
> That task assumed "regenerate the artifacts → DB-parity PASS". **That assumption
> is wrong** — verified below. Do the structural fix first, THEN regenerate.

## Problem (verified by Claude on 2026-06-23)
A run tagged `exchange=binance` silently consumed **okx** candles for the
2024-04-29 day, and re-running did not fix it:

- `canonical_candles` 1H 2024-04-29 = **binance 63229.2** (repaired, correct).
- `data/ticks/.../candles_1H.parquet` 2024-04-29 = 63229.2 now, but has **no
  source column**.
- `raw_candles` still holds **okx 63258.8** alongside binance 63229.2 for that hour.
- The rebuilt run `validation_lab_ma_crossover_btc_binance_1h_20260623_binance_rebuilt`
  config has `storage.backend=parquet`; its `price_series.csv` 2024-04-29 close is
  **63258.8 (okx)**, not 63229.2. db_parity on the pre-repair MA run is **FAIL**
  (24 value mismatches, `ohlcv_source_validation=artifact_warn`).

Root cause: `backtesting/data_loader.py::load_candles` has an **exchange-scoped
path** (`_load_candles_pg`, line ~305, `source_primary=exchange`) AND a
**provenance-less path** (`_load_candles_parquet`, no source column). The
validation-lab runner used the parquet path, so okx leaked in and exchange
scoping was impossible. Repairing data does not help if the read path ignores
provenance.

## The invariant to enforce
**A backtest run that declares an execution venue must source candles only from
that venue's provenance-tagged series. A missing venue bar is an explicit
gap/error — never a silent substitution from another venue (including the
source-less parquet or okx rows in `raw_candles`).**

## Strategy/spec source
- ADR-0007 (multi-venue instrument specs / exchange-scoped reads) — this enforces
  ADR-0007's intent at the candle-read layer, matching the already-exchange-scoped
  `db_parity`.
- `docs/ai_collaboration.md` ct_val/db_parity venue-tag gate.

## Required behavior
1. **Route venue-tagged runs to the exchange-scoped canonical read.** When a run
   declares an `exchange` (multi-venue / Binance/Bybit/etc.), `load_candles` must
   use the postgres canonical path with `source_primary=exchange` (the machinery
   already exists in `_load_candles_pg`). Do **not** silently fall back to the
   source-less parquet for a venue-tagged run.
2. **Fail loud on a venue gap.** If the exchange-scoped canonical series is
   missing bars the run needs (and the 1m→bar derivation in `_load_candles_pg`
   also can't supply binance bars), surface an explicit error / coverage gap in
   the run (e.g. via the existing data-coverage gate) instead of substituting
   another venue. Do not pull okx from `raw_candles`/`market_klines` for a binance
   run.
3. **Locate-before-edit** the actual decision points (do not guess):
   - `backtesting/data_loader.py::load_candles` backend dispatch + the two backend
     knobs (`storage.backend` vs `candle_backend`) that let the runner pick parquet.
   - `scripts/run_replay_backtest.py` / `scripts/run_validation_lab_signal_order_check.py`
     — where `storage.backend=parquet` is set for these runs.
   - `src/okx_quant/api/routes_backtest.py::_resolve_candle_backend` (or equivalent).
   - `backtesting/replay.py` — confirm `exchange` is propagated into the candle load.
4. If the parquet path must remain usable, it needs venue provenance (a source
   tag + a check that the parquet's venue matches the run exchange), OR be
   disabled for venue-tagged runs. Prefer the smaller change: force venue-tagged
   runs onto the canonical pg read.

## Then (only after the structural fix)
5. Regenerate the three MA/EMA/MACD Binance 1H `strategy_fill` runs with new
   run-ids; verify `price_series.csv` 2024-04-29 now equals **binance 63229.2**.
6. Run DB-parity validation on the regenerated MA run; expect
   `db_parity.status == PASS`, `canonical_source_primary == binance`,
   `ohlcv_source_validation == db_parity_pass`, zero mismatches over 20,400 rows.
7. Mark the stale 2026-06-22 and the failed `_20260623_binance_rebuilt` runs with
   `SUPERSEDED.md` (do not edit their contents).

## PERMITTED FILES
- `backtesting/data_loader.py`, `backtesting/replay.py` (candle-load/exchange
  propagation only — NOT fill/PnL/risk/strategy logic).
- `scripts/run_replay_backtest.py`, `scripts/run_validation_lab_signal_order_check.py`,
  `src/okx_quant/api/routes_backtest.py` (backend selection for venue-tagged runs).
- `tests/` (a regression test: a venue-tagged run must not load another venue's bar).
- `results/**` NEW run + validation dirs; `SUPERSEDED.md` notes on stale runs.
- `docs/INVARIANTS.md` (add the invariant above), `docs/DOMAIN_RULES.md`,
  a Change Manifest from `docs/CHANGE_MANIFEST_TEMPLATE.md` (data-provenance/source
  is a business-rule area — check `docs/DOC_IMPACT_MATRIX.md`), `docs/AI_HANDOFF.md`
  / `docs/CURRENT_STATE.md`, and **correct the "regenerate → PASS" assumption** in
  the AI_HANDOFF 0c bullet and any report text.

## FORBIDDEN (do not touch)
- Trading-core: `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`,
  `execution/`.
- Fill/PnL/fee/funding/sizing math in `replay.py` — only the candle-source
  selection + exchange propagation.
- `backtesting/differential_validation.py` gate logic / tolerances.
- `config/*.yaml`, DB schema/migrations, the repaired 2024-04-29 canonical data,
  existing result artifacts (supersede via note only).

## SCOPE LIMIT
Enforce venue-scoped candle sourcing + fail-loud-on-gap, then regenerate &
validate. Do not change strategy/execution/PnL behavior, risk, or gates. The
regenerated runs are still `strategy_fill`/idealized → a db_parity PASS closes the
source-data leg only; not promotion/live evidence.

## REQUIRED ON COMPLETION
- Show a before/after: a venue-tagged run no longer loads okx for 2024-04-29
  (price_series close == 63229.2), and a missing-venue-bar case now errors/flags
  instead of substituting.
- Paste the regenerated MA run db_parity block (PASS / binance / db_parity_pass /
  0 mismatch / 20,400 rows).
- Confirm `make engine-consistency-smoke` still PASSES.
- Change Manifest created; `make docs-impact` clean; INVARIANTS updated; the
  "regenerate → PASS" wording corrected.

## ACCEPTANCE CRITERIA
- [ ] A venue-tagged run sources candles only from that venue's canonical series;
      a missing venue bar is an explicit gap/error, not a silent substitution.
- [ ] Regression test locks this (a binance run with an injected okx-only bar must
      fail/flag, not silently use it).
- [ ] Regenerated MA Binance 1H run: `price_series` 2024-04-29 == binance;
      `db_parity == PASS`, `canonical_source_primary == binance`,
      `ohlcv_source_validation == db_parity_pass`, 0 mismatches.
- [ ] Stale 2026-06-22 + failed `_20260623_binance_rebuilt` runs marked superseded.
- [ ] No edits to trading-core, gate logic, config, schema, or fill/PnL math.

## Relationship to the other tasks
This is the durable fix for the **source-data leg**: it makes "餵得對" (fed the
right venue's data) an enforced invariant, not a hope. Engine-consistency
(`tasks/2026-06-23-engine-consistency-smoke-task.md`, "算得對") already passes and
is unaffected. Neither leg is promotion evidence alone; WF/CPCV strategy-edge
validation remains a later phase.
