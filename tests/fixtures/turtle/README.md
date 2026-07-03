# Turtle golden parity fixtures

Provenance (regenerated 2026-07-04, user-directed manual pass; supersedes the
2026-07-03 synthetic GBM fixture which was deleted — the spec requires real
exchange data):

- `daily_ohlc.csv` — **898 real BTC-USDT-SWAP UTC daily bars** exported once
  from `canonical_candles` (`bar='1m'`, `source_primary='binance'`,
  `quality_status != 'suspect'`, 2024-01-01 .. 2026-06-16; only days with the
  full 1440 minute-bars kept — all 898 qualified). Aggregation matches the
  reference `resample_to_daily` semantics: per UTC day open=first, high=max,
  low=min, close=last.
- `expected_default.csv` / `expected_stress.csv` — output of the **verbatim
  reference implementation** `new_startegy_海龜/trading_target_func.py ::
  turtle_trading_system_full`, run under polars 1.42.1 in a one-off scratch
  venv (polars/plotly/scipy are NOT project dependencies), selecting columns:
  date, profit, equity, money_in_hand, cumulative_profit, whole_asset,
  s1_units, s2_units, s1_position, s2_position, s1_stop_loss, s2_stop_loss,
  buy_action, sell_action, total_units, cumulative_win_count,
  cumulative_loss_count, realized_pnl.

Parameter sets (spec `2026-07-03-turtle-platform-design.md`):

- default: `(enter1=20, enter2=55, leave1=10, leave2=20, single_limit=4,
  both_limit=4, own_capital=50000.0, invest_pct=0.01, min_position=0.0001,
  fee=0.003, atr_period=20)` — final equity 50578.081905, 7 wins / 19 losses
- stress: same windows, `both_limit=6, own_capital=10000.0, invest_pct=0.25`
  — final equity 12307.892184, 8 wins / 20 losses (heavily exercises the
  cash gate: the reference run emitted hundreds of cash-skip debug lines)

Verified 2026-07-04: `backtesting.turtle_backtest.run_turtle_backtest`
reproduces both expected files exactly on the real-data fixture (ints/flags
equal; floats rtol=atol=1e-9, zero mismatches across all compared columns ×
898 rows) — `tests/unit/test_turtle_backtest.py::test_turtle_matches_golden_fixture`.

To regenerate: re-export `daily_ohlc.csv` from canonical DB with the query
above; build a scratch venv with polars, import
`new_startegy_海龜/trading_target_func.py` unchanged, run both parameter sets
on the fixture (cwd outside the repo — the reference writes a `test.csv`
side effect), and rewrite the expected CSVs with the column list above. Do
not edit the expected files by hand.
