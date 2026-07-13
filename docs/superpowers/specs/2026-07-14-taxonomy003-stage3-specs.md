---
status: accepted
type: design
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Taxonomy_003 Stage-3 pre-registration (H-015..H-020) — written BEFORE any run

User authorization 2026-07-14: run performance backtests for all six
taxonomy_003 candidates, Claude solo (no Codex), fetching any missing data
directly. This file pre-registers every grid, direction, and protocol choice
BEFORE the first backtest executes. H-015's grid was already pre-registered
in `docs/superpowers/specs/2026-07-13-f-optflow-positioning-hypothesis.md`
and is restated unchanged.

## Common protocol (all candidates)

- Window: 2024-01-01 → last common canonical-candle day (detected, reported
  per run). ~2.5y ⇒ observed-Sharpe bar ≈ 1.7 at n_trials = 4 per
  `2026-07-03-statistical-power-gates.md`; a marginal fail is a plausible
  outcome with no retry entitlement.
- Prices: Binance venue-scoped canonical 1m closes → daily last close via the
  existing loaders (`backtesting/funding_xs_dispersion_backtest.py`).
- Execution: day-t target trades at t+1 (`target.shift(1)`); fee 2 bps +
  slippage 2 bps per side on turnover; funding cashflow on held perp
  positions; portfolio vol-target 0.175 with 28d window for TS books.
- External CSV signals (`results/idea_batch_20260713_taxonomy_003/data/`,
  retrieval meta recorded): value stamped date D usable no earlier than
  D+1 00:00 UTC (conservative one-day publication lag, fixed ex-ante).
  DB optflow uses `published_at` ≤ day-t close as-of joins (F26).
- Validation: fold-refit WF/CPCV via `backtesting/pipeline_refit.refit_validation`
  (WF 365/90; CPCV N=6/k=2/embargo=2%/purge=1), caller-declared family
  `n_trials` = grid size (all families new, prior 0). Statistical gate:
  DSR ≥ 0.95 AND PSR ≥ 0.95. Runner is research-grade Claude-authored
  (`research/probes/taxonomy003_stage3.py`); stage3-registry registration is
  deferred to any promotion path.
- Family minting: candidate default-combo daily returns vs the E-031
  (F-FUNDING-XS-DISPERSION) and E-037 (F-OI-POSITIONING) reference series via
  `backtesting/pipeline_family_minting.decide_family_minting`; `ASSIGN` folds
  budgets per I27 and corrects the ledger.
- Nothing here is promotion/live evidence regardless of outcome.

## Per-candidate registration (direction and grid frozen ex-ante)

**H-015 F-OPTFLOW-POSITIONING** (restated): per-symbol BTC/ETH long/flat;
flat when trailing L-day mean of hourly put/call taker-buy premium imbalance
z(90d) ≥ z_cut, else long. Grid `{L ∈ [1,3], z_cut ∈ [1.0,1.5]}` = 4.

**H-016 F-XS-ILLIQUIDITY**: weekly-rebalanced dollar-neutral XS book over the
PIT universe (complete-window symbols with daily dollar volume): long the
top-quantile Amihud-illiquid names, short the bottom-quantile liquid names.
Amihud_i = trailing-W mean of |daily return| / daily dollar volume.
Direction ex-ante: LONG illiquid (illiquidity premium). Grid
`{W ∈ [14, 28] days, quantile ∈ [0.20, 0.30]}` = 4. Same construction
mechanics as `funding_xs_dispersion` (weights, caps, vol scaling) with only
the ranking signal replaced.

**H-017 F-STABLECOIN-LIQUIDITY**: BTC/ETH long/flat; signal = trailing G-day
log growth of aggregate stablecoin circulating USD (DefiLlama), z vs 365d;
long when z ≥ z_min, else flat. Direction ex-ante: supply growth = inflow
liquidity = risk-on. Grid `{G ∈ [14, 28], z_min ∈ [0.0, 0.5]}` = 4.

**H-018 F-COINBASE-PREMIUM**: per-symbol BTC/ETH long/flat; premium_t =
Coinbase USD close / Binance USDT daily close − 1 (USD-vs-USDT peg spread is
inside the measure — accepted, stated ex-ante); signal = trailing L-day mean
premium z vs 90d; long when z ≥ z_min else flat. Direction ex-ante: positive
premium = US demand pressure = bullish continuation. Grid
`{L ∈ [1, 3], z_min ∈ [0.0, 0.5]}` = 4. Minting risk vs F-XVENUE-LEADLAG
noted; that family has no reference series (data-blocked), so the check runs
vs available references only and the neighbor risk stays a human item.

**H-019 F-ONCHAIN-FLOW**: BTC-only long/flat hash-ribbon: flat while the
fast hashrate SMA is below the slow SMA (miner capitulation), long
otherwise. Direction ex-ante: capitulation = risk-off. Grid
`{fast ∈ [14, 30], slow ∈ [60, 90]}` = 4. Honest power note: single symbol —
registered as research-baseline; the gate verdict is recorded but even a pass
is weak evidence at breadth 1.

**H-020 F-CALENDAR-SEASONALITY**: BTC/ETH; exactly two pre-registered cells,
`n_trials = 2`, no other grid: cell A = hold long weekdays only (Mon 00:00 →
Fri 24:00 UTC), cell B = hold long weekends only. No calendar scanning.

## E-row and ledger allocation (reserved now)

E-043 = H-014 Stage-2 calibration rerun (post hourly-DVOL backfill, same
deterministic sample and E-041 script/deltas). E-044..E-049 = Stage-3 runs
for H-015..H-020 in order. New K rows: F-XS-ILLIQUIDITY,
F-STABLECOIN-LIQUIDITY, F-COINBASE-PREMIUM, F-ONCHAIN-FLOW,
F-CALENDAR-SEASONALITY (all 0/2).

## Scope

Research/docs + research-grade runner only. No strategy/, risk/, execution/,
config-gate, engine, or adapter changes; no promotion claims.
