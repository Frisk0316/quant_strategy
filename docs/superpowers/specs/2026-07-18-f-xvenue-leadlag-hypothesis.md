---
status: current
type: spec
owner: claude
created: 2026-07-18
last_reviewed: 2026-07-21
expires: none
superseded_by: null
---

# Stage-1 Hypothesis Spec: F-XVENUE-LEADLAG (H-010)

User-authorized 2026-07-18 (recorded in
`tasks/2026-07-17-abc-delivery-claude-review.md`). Written BEFORE any Stage-2
probe or backtest on the venue-scoped pair; the grid below is pre-registered
as of this file's creation. Family cumulative n_trials to date: 0 (E-029/E-035
were 0-trial data probes). This grid adds 4.

## Mechanism (direction fixed ex-ante)

Price discovery concentrates on the dominant-volume venue. Binance USDT-perp
volume dominates OKX for BTC/ETH, so information arrives on Binance first and
OKX marks adjust with a short lag (crypto price-discovery literature:
information-share studies consistently rank Binance first). The tradable
consequence: when the Binance-vs-OKX log-price gap deviates from its rolling
mean, the OKX leg converges toward Binance — not the reverse. Direction is
fixed ex-ante: we always trade the OKX leg toward the Binance-implied price.
Binance data is signal input only; the book trades OKX-USDT-SWAP exclusively.
This uses venue-scoped data as information, not as substitution (I19 intact).

## Falsifiable hypothesis

A 1m-signaled, vol-targeted long/short book on OKX BTC/ETH-USDT-SWAP that
enters when the venue log-price gap d(t) = ln P_binance(t) − ln P_okx(t)
deviates from its rolling mean by ≥ z_entry rolling stds (position sign =
sign of the deviation: long OKX when Binance is above, short when below) and
exits on mean reversion or after max_hold bars, earns a positive net-of-cost
Sharpe surviving fold-refit WF/CPCV with DSR ≥ 0.95 and PSR ≥ 0.95.

## Definitions

- Data: venue-scoped canonical 1m candles via `canonical_candles_by_source`,
  `source_primary='binance'` and `'okx'`, BTC/ETH-USDT-SWAP, window
  2020-01-01 → 2026-06-17 (requires the authorized 2020–2023 promotion task
  to complete first). Aligned timestamps only; unaligned minutes are skipped,
  never filled cross-venue.
- Gap stats: rolling mean/std of d over `lookback_min` minutes; warmup
  excluded from tradable signals.
- Entry: |z(t)| ≥ z_entry where z(t) = (d(t) − mean)/std. Exit: |z| ≤ 0.5 or
  max_hold = 60 minutes, whichever first. One position per symbol.
- Costs: standard engine cost model for OKX perp (maker entry assumption is
  NOT allowed to be weakened; taker exit permitted on max_hold stop). Funding
  applies per engine.
- Sizing: engine vol-targeting; no leverage beyond existing engine defaults.
- Stats aggregation: daily PnL for WF/CPCV/DSR/PSR.

## Pre-registered grid (4 combos, n_trials = 4)

| combo | lookback_min | z_entry |
|---|---|---|
| 1 | 60 | 2.0 |
| 2 | 60 | 3.0 |
| 3 | 240 | 2.0 |
| 4 | 240 | 3.0 |

No other parameters may be tuned. Any change after Stage-2 results are seen
consumes K and requires ex-ante rationale.

## Statistical power inputs (Stage-2.5 screen, computed 2026-07-18)

- breadth: asserted 1.5 (BTC+ETH books are highly correlated; nominal 2
  undercounted per the review-accepted breadth contract; independence
  UNCONFIRMED).
- n_obs: ~2,250 daily observations (2020-01→2026-06 minus warmup).
- n_trials: 4 (family cumulative 0 + this grid).
- min_detectable_sharpe at these inputs: **0.8682** (long window). Short
  window 2024+ would demand 1.41–1.72 — that is why the long-window
  promotion is a prerequisite, not an option.
- Superseded for implementation by the exact `n_obs=2,268` floor **0.8838**;
  this strictly tightens the original 0.8682 requirement.
- plausible_net_sharpe: to be estimated by Stage-2 `cost_after_edge` from a
  sample-window gap-persistence measurement. If the cheap estimate is below
  0.87, Stage-2 FAILS and the family stops with 0 grid trials burned.

## Kill criteria (Stage-2)

- Data availability: aligned venue-scoped coverage ≥ 0.95 over the window.
- Distinctness: |corr| < 0.30 vs live reference signals of active families
  (note: F-XVENUE-FUNDING-SPREAD is refuted; distinctness still computed and
  reported for the record).
- Cost-after-edge: median gross gap capture per entry must exceed round-trip
  cost under the engine cost model on the sample window; else FAIL.
- Statistical power: plausible_net_sharpe ≥ 0.8682 at the inputs above.

## Known risks (declared now)

1. 1m lead-lag is the most cost-fragile design in this repo to date; the
   most likely honest outcome is a Stage-2 cost_after_edge FAIL at zero
   grid-trial cost. That is the screen working, not a setback.
2. Candle-close timing between venues can embed microstructure noise;
   entries execute on the NEXT bar open after signal (no same-bar fills).
3. Splice/regime: 2020 includes listing-era liquidity for OKX perps; WF folds
   will surface this rather than a manual exclusion.

## Not authorized by this spec

Stage-3, adapters, promotion, demo/shadow/live. Stage-2 probe execution is a
separate Codex task after the history promotion lands.

## Future-round distinctness amendment — 2026-07-21

This amendment is ex-ante for future rounds only; E-057's immutable artifact,
FAIL, and shelved outcome do not change. Any future H-010 Stage-2 round must
compute the candidate distinctness proxy across the post-calibration formal
window, declare each gating reference's available date range, and establish
before probe execution that their intersection can reach
`MIN_COMMON_DAYS=365`. A structurally impossible intersection is refused as a
contract defect rather than recorded as a data-conditional measurement.
