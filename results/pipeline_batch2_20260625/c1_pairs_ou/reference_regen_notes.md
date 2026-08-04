---
status: current
type: result
owner: codex
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# E-025 dated reference regeneration

This is a reference-series regeneration for distinctness only. It does not
reopen H-006/F-PAIRS-OU, consume K or family trials, create an experiment row,
or change the refuted E-025 outcome.

## Reproduction basis

- Runner: `backtesting.c1_pairs_ou_backtest.load_c1_inputs` followed by
  `run_c1_pairs_ou_backtest`; this is the same C1 implementation called by
  `scripts/run_pipeline_batch2_checkpoint.py`.
- Window: `[2024-01-01T00:00:00Z, 2026-06-17T00:00:00Z)`.
- Source: `primary_exchange=binance`, PostgreSQL canonical 1-minute candles.
- Frozen params:
  `bar=1m`, `symbol_x=BTC-USDT-SWAP`, `symbol_y=ETH-USDT-SWAP`,
  `lookback_days=14`, `max_half_life_days=3.0`, `max_hold_days=14`,
  `z_enter=2.5`, `z_exit=0.0`, `fee_bps=2.0`, and
  `slippage_bps=2.0`.
- Input coverage: 1,293,120 candles and 2,694 funding rows for each symbol,
  matching the recorded E-025 coverage.

## Comparison with E-025

- Recorded `full_sample_best_sharpe`: `0.9954104408913999`.
- Regenerated runner full-sample Sharpe: `0.9954104408913999`.
- Difference: `0.0`; no observed input/result drift.
- Recorded fold-refit `cpcv_oos_sharpe`: `-0.9097221657913156`.
- Regenerated fixed-parameter daily-series Sharpe: `0.8418761339570187`.
  This is expected to differ from CPCV: the CSV is the fixed selected combo's
  full-window dated daily return stream, while the recorded CPCV statistic is
  assembled from fold-refit OOS paths with split-specific selection.

## Output

- `combo_daily_returns.csv`: 898 consecutive UTC dates from 2024-01-01 through
  2026-06-16, including 9 non-zero return days.
- CSV SHA-256:
  `115b128cc84860c43f219ac61c98706b058da29fb779f2eb40f5b66c67bf15bb`.
- The pre-existing `summary.json` was not modified; its SHA-256 remains
  `16c00b0d0ff116bdb47a1697959b85d00ba249b981b600871262d91bbd343ef1`.
