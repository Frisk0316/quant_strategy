---
status: current
type: reference
owner: human
created: 2026-06-12
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Golden Cases

Reference scenarios with **known-correct expected outputs**. They anchor
correctness: when behavior changes, a golden case either still matches (good) or
breaks (investigate before "fixing" the case). Golden cases make the abstract
[[INVARIANTS]] concrete and reviewable.

A golden case is not a substitute for the unit/integration tests that enforce it
— it is the human-readable specification the test encodes.

## Registry

| ID | Scenario | Fixed inputs | Expected output | Guards | Enforcing test |
|---|---|---|---|---|---|
| G-000 | _example: single BTC-SWAP long, open then close at +Δ_ | _ct_val, entry/exit px, fee, qty_ | _realized PnL = qty·ct_val·Δ − fees_ | I1, I2 | _tests/unit/..._ |
| G-001 | Same BTC-SWAP MA crossover replay on OKX vs Binance venue specs | Same strategy/params on a synthetic BTC-USDT-SWAP 1H parquet fixture; OKX `ctVal=0.01`; Binance `ctVal=1.0`; both via `instrument_specs` override | Metrics match within `1e-6` because `ct_val` cancels under notional sizing; any real venue divergence should be lot-rounding/fee/funding, and run validation carries the selected `exchange` | I1, I16 | `tests/unit/test_multi_venue_convergence.py` |
| G-002 | Binance-tagged candle load with an OKX-only/source-less fallback candidate | `load_candles(..., backend="parquet", dsn=<reachable>, exchange="binance")` with parquet close `63258.8` and canonical Binance close `63229.2`; a dated range with a missing Binance bar | Loader returns the Binance canonical close, never the parquet/OKX close; a missing Binance bar raises an explicit venue gap | I19 | `tests/unit/test_data_loader.py` |
| G-003 | Turtle S1/S2 reference quirks plus 600-day golden parity | Tiny synthetic daily OHLCV cases plus `tests/fixtures/turtle/daily_ohlc.csv` with `expected_default.csv` and `expected_stress.csv` generated from the verbatim reference implementation | Entry thresholds exclude the current day; buys require `cost < cash`; a winning S1 exit skips exactly the next S1 breakout; final equity marks open positions with no forced liquidation; default/stress fixture outputs match ints exactly and floats within `1e-9` | I1, I2 | `tests/unit/test_turtle_backtest.py` |
| G-004 | H-014 inverse-option cycle plus shadow intent safety | Short one call at 0.01 coin, `K=55k`, delivery `S_T=60k`; separate short-put-only and `1.0 + 1/30` intent cases | Coin PnL = premium − R8.4 trade fee − inverse payoff − settlement fee; naked put and over-cap intent both raise before quote/fill | I39 | `tests/unit/test_h014_options_accounting.py`, `tests/unit/test_h014_shadow.py` |
| G-005 | H-021 equal-USD-delta inverse-perpetual cycle | Pair NAV 1,000; long 500 USD Binance at 100 and short 500 USD Deribit at 100; exit marks 110/105; Binance funding 1 bp; one nonzero Deribit hourly rate 2 bps at mark 102; entry+exit turnover 2 | Binance price +50 USD; exact Deribit coin PnL `-500×(1/100−1/105)` converts at 105 to -25 USD; funding -0.05/+0.10 USD; gross +25.05; base 4 bps cost 0.80 and net 24.25; stress 7 bps cost 1.40 and net 23.65 | I44 | `tests/unit/test_h021_inverse_perp_accounting.py` |

## What makes a good golden case

- **Deterministic.** Fixed inputs, fixed seed, no wall-clock or network
  dependence.
- **Hand-verifiable.** The expected output can be computed by hand or from first
  principles, so it does not just encode current (possibly wrong) behavior.
- **Targets a specific invariant or failure mode.** Cite the [[INVARIANTS]] /
  [[FAILURE_MODES]] id it guards.
- **Small.** The minimal scenario that exercises the property.

## Rules

- Changing a golden case's expected output is a business-rule change: it needs a
  Change Manifest and, if it reflects a rule change, an ADR.
- If a code change breaks a golden case, the default assumption is the code is
  wrong, not the case. Justify any expected-output change explicitly.
- New accounting/fill/funding logic should add a golden case before it is
  considered done.

Related: [[INVARIANTS]] · [[FAILURE_MODES]] · [[EXPERIMENT_REGISTRY]].
