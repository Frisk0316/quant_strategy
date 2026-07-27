---
status: current
type: task
owner: codex
created: 2026-07-18
last_reviewed: 2026-07-21
expires: none
superseded_by: null
---

# H-010 strategy-selection pipeline execution contract

## User authorization and current/target/gap

The user's 2026-07-18 request starts a new strategy-selection round, permits
minimal pipeline repair, and authorizes Stage 2 plus Stage 3 backtesting only
when every preceding gate passes. This newer request supersedes only the older
H-010 clauses that said Stage 2 was a separate future task and Stage 3 was not
yet authorized. It does not authorize promotion, demo, shadow, or live changes.

- Current: the H-010 Stage-1 spec and four-cell grid are frozen, the
  source-aware 2020-01-01 through 2026-06-17 candle prerequisite has been
  independently re-verified, but the registered Stage-2 probe only implements
  data availability and no H-010 Stage-3 runner exists.
- Target: run a complete, fail-closed H-010 Stage 2. Implement and run the
  four-cell Stage 3 only if Stage 2 passes without an override.
- Known gap: the Stage-1 text says `n_obs ~2,250` while its reported 0.8682
  power floor corresponds to about 2,350 observations. The implementation does
  not silently choose either value. It excludes the calibration-only dates from
  the formal series and fixes the CPCV/DSR observation count at `n_obs=2,268`.
  With breadth 1.5 and four trials, the accepted ADR-0013 implementation gives
  a frozen minimum detectable Sharpe of `0.8838161258`.

## Locate-before-edit

- User-facing surface: research pipeline artifacts and governance records only;
  no frontend, API, live strategy, or deployment behavior.
- Owning implementation: `backtesting/xvenue_leadlag_probe.py`,
  `backtesting/pipeline_stage2_registry.py`, and
  `scripts/run_pipeline_stage2_data_probe.py`.
- Conditional Stage 3 ownership: `backtesting/xvenue_leadlag_backtest.py` and
  `backtesting/pipeline_stage3_registry.py`, created/touched only after an
  unoverridden Stage-2 PASS.
- Tests: a focused H-010 unit test module plus the existing pipeline Stage-2,
  orchestrator, power-screen, refit, and registry tests.
- Permitted docs: this task, a new Change Manifest, experiment/hypothesis
  ledgers, strategy history, feature/data/runbook/current-state handoff docs,
  changelog, workstream status, and the mandatory Context/Session handoffs.
- Forbidden: `research/`, live strategy/risk/portfolio/execution code,
  `config/strategies.yaml`, `config/risk.yaml`, deployment gates,
  `backtesting/differential_validation.py` (separately owned boundary), existing
  result artifacts, and the pre-existing dirty OKX promotion files.
- Rollback: delete only the fresh H-010 artifacts/files and revert the exact
  H-010 hunks listed above; no database write is part of this task.

## Design-space expansion

1. Build Stage 2 and Stage 3 together. Rejected for now: Stage 3 may be dead
   code if the expected cost-fragility gate fails.
2. Run a one-off backtest. Rejected: it bypasses the registered gates and leaves
   the pipeline defect in place.
3. Add only the specialized H-010 Stage-2 probe, run it, and add Stage 3 only on
   PASS. Chosen: it is the smallest complete path and preserves the stop rule.

This choice changes only if the immutable Stage-2 artifact is PASS.

## Frozen pre-Stage2 calibration

Calibration is a separate, read-only invocation. It cannot write
`stage2_feasibility.json`, mutate pipeline status, compare the four grid cells,
or count as a grid trial.

- Full candle source boundary: `canonical_candles_by_source`, exact
  `source_primary in {'binance','okx'}`, exact aligned 1m timestamps, BTC and ETH
  USDT swaps. No resolved-canonical or cross-venue substitution.
- Calibration-only interval: `[2020-01-01T00:00:00Z,
  2020-04-01T00:00:00Z)`. These dates are excluded from the formal return
  frame, CPCV, WF, and all reported OOS statistics.
- One diagnostic anchor: `lookback_min=240`, `z_entry=2.0`, `z_exit=0.5`,
  `max_hold_min=60`. This is the slowest, most permissive pre-registered cell,
  fixed for sample size and a conservative median-capture screen; no other cell
  is evaluated during calibration.
- Signal: `d_t = log(Binance close_t) - log(OKX close_t)`; rolling mean and
  sample standard deviation include `t` and require 240 consecutive aligned
  minutes. Zero variance yields no signal.
- Execution proxy: the hypothesis's synthetic next-open convention is frozen
  explicitly. A close-`t` entry decision is classified as maker and executes at
  the exact aligned OKX open at `t+1`; this candle-only proxy has no post-only
  queue/miss model and is therefore always labelled `idealized_fill=true` and
  can never be promotion evidence. A position exits at the exact next aligned
  open after `abs(z)<=0.5` using the same maker proxy, or at the open after 60
  completed holding minutes using taker execution. A timestamp gap fails the
  input rather than crossing or compressing it; an incomplete terminal episode
  is discarded in calibration.
- Direction: trade only OKX toward Binance; Binance is signal-only.
- Costs: maker entry/mean-reversion exit each charge 2 bps fee plus 2 bps
  slippage; a max-hold taker exit charges 5 bps fee plus 2 bps slippage. Thus
  an episode costs 8 or 11 bps according to its frozen exit reason. Gross
  capture is the signed linear OKX entry-open-to-exit-open return. Net return
  deducts the exact episode costs plus signed, venue-matched OKX funding at each
  8h settlement (long pays a positive rate; short receives it, and vice versa).
  Missing required funding fails closed; it is never substituted.
- Aggregation: completed episode returns accrue on the UTC exit day; BTC and ETH
  are equal-weighted and no-trade days are zero. Calibration Sharpe is
  `mean(daily_net)/sample_std(daily_net)*sqrt(365)` and must be finite.
- Cost gate: completed trades must exist and median gross capture must be
  strictly greater than the median exact per-episode round-trip cost. The
  measured calibration Sharpe becomes the frozen `plausible_net_sharpe`; it
  must also be at least `0.8838161258`.
- Formal validation count: `n_obs=2,268`, the calendar days from 2020-04-01
  through 2026-06-16 inclusive in every retained CPCV path; `breadth=1.5`;
  prospective cumulative `n_trials=4`. WF necessarily uses fewer OOS days
  after its 365-day IS prefix; this does not replace the CPCV/DSR `n_obs`.

The calibration writes a fresh immutable `h010_power_input.json` with the four
I45 inputs, method/window/anchor/cost details, observations/trades, gross median,
net Sharpe, source/reference hashes, and a canonical payload hash. The active
Stage-2 caller must load and validate it before opening a DB connection.

## Frozen distinctness screen

The candidate proxy is the fixed-anchor daily net strategy return, in the same
return units as every reference, over their common dates. It uses the identical
next-open/cost/funding rules above and never compares or selects the four grid
cells. This follows the repository's existing family-minting convention; it is
used only for redundancy classification, not to select a parameter or estimate
the Stage-3 performance gate. Undefined or zero-variance correlation fails
closed; at least 365 common dates are required.

Gate references (maximum absolute correlation must be `< 0.30`):

- `F-FUNDING-XS-DISPERSION`:
  `results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/family_minting_candidate.json`,
  key `signal`.
- `F-VOL-REGIME-OPT`:
  `results/h014_stage3_20260714/combo_daily_returns.csv`, frozen default column
  `ivp_min=75.0|z_min=0.5` from that family's summary.

Advisory-only record (does not gate because the family is refuted):

- `F-XVENUE-FUNDING-SPREAD`:
  `results/h021_stage3_20260715/combo_daily_returns.csv`, fixed original/base
  column `L3_H1__base`.

Every reference file hash is embedded in the calibration evidence and checked
again by registered Stage 2.

### Review amendment for future rounds — 2026-07-21

E-057 exposed that its 91-day calibration proxy could never satisfy 365 common
days with references beginning in 2022. E-057 remains immutable and its outcome
stands. Before any future probe, distinctness must instead use the
post-calibration formal candidate-return window, declare gating-reference date
ranges whose intersection can reach `MIN_COMMON_DAYS=365`, and refuse a
structurally impossible contract before measurement. This amendment is committed
before any future H-010 probe or reuse.

## Frozen conditional Stage 3

These mechanics are frozen before Stage 2. Code is added and the grid is run
only after an unoverridden Stage-2 PASS.

- Input: exact aligned source-aware Binance/OKX 1m OHLC, plus complete
  venue-matched OKX 8h funding. Any timestamp gap, non-positive price, suspect
  row, missing funding settlement, or cross-venue substitution fails the run.
- Formal daily return frame: `[2020-04-01, 2026-06-17)`, exactly 2,268 UTC days;
  the 2020-Q1 calibration interval is not present in any formal fold.
- Signals/execution: exactly the four Stage-1 cells and the frozen state,
  t+1, exit, fee/slippage, funding, and terminal rules above. At the dataset end
  an open position is force-closed at the last OKX close with taker exit cost.
- Portfolio: each active symbol starts at 0.5 gross weight. A single daily scale
  is computed only from the preceding 28 completed daily gross book returns to
  target 17.5% annualized volatility, uses scale 1.0 until 14 observations are
  available, and is capped at 2.0 gross leverage. The scale is fixed for the
  next UTC day; no intraday or same-day volatility input is allowed.
- Aggregation: minute episode PnL, exact costs, and funding cashflows aggregate
  to UTC daily returns before validation; no-trade days remain explicit zeros.
- Validation: `refit_validation` semantics with WF `365/90` and CPCV
  `n_splits=6`, `k_test=2`, `embargo_pct=0.02`, `purge_size=1`, annualization
  365, caller-declared cumulative `n_trials=4`, and retained raw CPCV path
  returns. Both DSR and PSR must be at least 0.95.
- Artifacts: immutable summary, all four daily-return series, retained CPCV path
  returns, checkpoint output, family-distinctness output, data/cost/funding
  census, and hashes. `idealized_fill=true` and `promotion_gate_passed=false`
  remain mandatory regardless of the statistical result.

## Stop and accounting rules

- Calibration artifact is consumed by the registered Stage-2 runner. Missing
  venue data may freeze a conservative `plausible_net_sharpe=0.0` sentinel only
  when the evidence also says `valid=false` and `measured=false`; it is never
  described as a measured Sharpe.
- Data/calibration failure: E-057 records zero trials and H-010 is
  `data-blocked/inconclusive`. Cost or power feasibility failure records E-057
  at zero trials and shelves H-010 at Stage 2. Neither case is called refuted,
  and no Stage-3 code/grid runs.
- Stage-2 PASS: E-057 remains zero trials; implement the existing four-cell
  Stage 3 and register E-058 with cumulative `n_trials=4`, K still 0/2.
- DSR and PSR must both be at least 0.95 for a statistical pass. A near miss is
  reported as testing evidence only. No repeated search, threshold relaxation,
  or unregistered parameter is allowed.
- Existing artifacts are immutable; every output directory for this task is
  fresh and content-addressed where practical.
