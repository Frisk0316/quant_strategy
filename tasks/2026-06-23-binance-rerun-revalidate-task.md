---
status: archived
type: task
owner: claude
created: 2026-06-23
last_reviewed: 2026-06-23
expires: none
superseded_by: null
---

# Claude → Codex Task: Re-run + revalidate Binance 1H runs on the repaired data

## Task
Regenerate the three BTC-USDT-SWAP / Binance / 1H `strategy_fill` runs
(MA/EMA/MACD) now that the 2024-04-29 Binance gap is filled, then run DB-parity
validation to a clean **all-binance PASS**.

## Why (verified by Claude on 2026-06-23)
The data layer is now correct: DB `canonical_candles` and `data/ticks` parquet
both hold real Binance 1H for 2024-04-29 and agree (24 rows, 0 close mismatch);
the run-window 1H series is 20,400/20,400 binance-sourced. The remaining db_parity
failure is in the **saved artifacts, not the data**: the 2026-06-22 runs were
generated before the backfill, so their `price_series.csv` for 2024-04-29 used
okx-fallback values (run 63258.8 vs Binance 63229.2 — the okx basis). db_parity
correctly reports 24 **price mismatches** on those stale runs. Re-running on the
repaired source fixes it; no further data change is needed.

## Strategy/spec source
- Same configuration as the existing runs: BTC-USDT-SWAP, exchange=binance, 1H,
  2024-01-01 → 2026-04-30, `max_order_notional_usd=250`, `max_pos_pct_equity=1`,
  `execution_profile=strategy_fill`.
- `docs/ai_collaboration.md` DB-parity gate; ADR-0007 exchange-scoped canonical reads.

## Required behavior
1. Regenerate the three runs with **new run-ids** (do not overwrite the stale
   2026-06-22 artifacts), reusing the existing runner
   (`scripts/run_validation_lab_signal_order_check.py` or
   `scripts/run_replay_backtest.py --execution-profile strategy_fill`). Suggested
   suffix: `..._20260623_binance_rebuilt`.
2. **Verify the new `price_series.csv` for 2024-04-29 now equals Binance**
   (≈63229.2 at 00:00), not the okx fallback (63258.8). This confirms the re-run
   actually read the repaired source and did not fall back to okx again.
3. Run DB-parity validation against the new runs with the DSN + flag:
   `DATABASE_URL=postgresql://quant:changeme@localhost:5432/quant \
    DIFF_VALIDATION_ENABLE_DB_PARITY=1 NUMBA_DISABLE_JIT=1 \
    python scripts/run_source_provenance_validation.py --run-id <new_run_id>`
   for at least the MA run (EMA/MACD if cheap).
4. Mark the stale 2026-06-22 runs as superseded (a `SUPERSEDED.md` note pointing
   at the new run-ids); do not edit their contents.

## PERMITTED FILES (only create/edit these)
- `results/**` NEW run dirs + NEW validation evidence dirs (new run-ids only).
- `results/validation_lab_*_20260622_maxord250_pospct1_strategyfill/SUPERSEDED.md`
  (new note files only; do not modify the existing artifact contents).
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` (point at the new passing evidence).
- `docs/validation_lab_report_zh.md` (update the cited run-ids/numbers if the
  report references the stale runs).

## FORBIDDEN (do not touch)
- `backtesting/differential_validation.py` gate logic / tolerances.
- Trading-core: `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`,
  `execution/`; and `backtesting/replay.py` behavior.
- `config/*.yaml`, DB schema/migrations, the canonical data just repaired.
- Existing 2026-06-22 result artifacts (supersede via note, never overwrite).
- The 2024-04-29 backfill — it is correct; do not re-touch the data layer.

## SCOPE LIMIT
Re-run + revalidate + supersede the stale runs only. Do not change run config,
strategy/execution behavior, risk overrides, or the data. These are
`strategy_fill` / idealized runs, so a db_parity PASS closes the **source-data
leg only** — it is still NOT promotion, edge, or live-readiness evidence.

## REQUIRED ON COMPLETION
- List new run-ids and validation evidence paths.
- Paste, for the new MA run: 2024-04-29 00:00 `price_series` close (must be the
  Binance value ≈63229.2), and the validation `checks.db_parity` block showing
  `status == PASS`, `canonical_source_primary == binance`,
  `ohlcv_source_validation == db_parity_pass`, zero mismatches over 20,400 rows.
- Confirm the stale runs carry `SUPERSEDED.md`.
- Update the docs above. `make docs-impact` clean (re-run + revalidate is not a
  business-rule change → no Change Manifest).

## ACCEPTANCE CRITERIA
- [ ] New MA/EMA/MACD Binance 1H `strategy_fill` runs exist under new run-ids;
      stale 2026-06-22 runs untouched but marked superseded.
- [ ] New MA run `price_series.csv` 2024-04-29 closes equal Binance (not okx).
- [ ] `db_parity.status == PASS`, `canonical_source_primary == binance`,
      `ohlcv_source_validation == db_parity_pass`, 0 mismatches, all-binance, for
      at least the MA run.
- [ ] No edits to gate logic, trading-core, config, schema, or the repaired data.

## Reviewer (Claude) risk-checks for the diff
- Confirm the re-run did not silently fall back to okx again for any hour
  (price_series 2024-04-29 must match Binance, not okx, across all 24 hours).
- Confirm the new run window still covers 2024-01-01 → 2026-04-29 23:00 with 20,400
  rows (same as before) so the PASS is over the full window, not a shortened one.
- Engine-consistency smoke (`make engine-consistency-smoke`) must still PASS —
  its frozen fixtures are independent of this re-run.

## Relationship to the other tasks
Closes the **source-data leg** that `tasks/2026-06-23-binance-1h-db-parity-task.md`
opened (data now repaired; this regenerates the artifacts). Independent of
`tasks/2026-06-23-engine-consistency-smoke-task.md` (engine-logic leg, already
passing). Neither is promotion evidence alone; the later WF/CPCV strategy-edge
phase remains out of scope.
