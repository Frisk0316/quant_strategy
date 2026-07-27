---
status: current
type: spec
owner: claude
created: 2026-07-23
last_reviewed: 2026-07-23
expires: none
superseded_by: null
---

# Stage-1 Hypothesis Spec: F-TAKER-FLOW (CVD cross-sectional pressure)

User-authorized direction 2026-07-23: free data sources first; thin data →
composite or long-cycle designs. Written BEFORE any data probe or backtest;
the grid below is pre-registered as of this file's creation. New family,
cumulative n_trials to date: 0. This grid adds 4.

## Mechanism (direction fixed ex-ante)

Taker (aggressor) net flow measures who is crossing the spread. Sustained
net taker buying at daily-to-weekly horizon reflects informed/urgent demand
that price has not fully absorbed — the standard order-flow-imbalance
finding is CONTINUATION at this horizon. Direction fixed ex-ante: high
relative net taker buy pressure → long; low → short. No reversal variant may
be tested under this spec (a reversal design would be a new hypothesis with
its own K accounting).

## Falsifiable hypothesis

A dollar-neutral cross-sectional book over the point-in-time top-30 liquid
USDT-perp universe that longs the top fraction and shorts the bottom
fraction of names ranked by rolling net taker-flow ratio earns a positive
net-of-cost (fees + slippage + short-leg funding) Sharpe surviving
fold-refit WF/CPCV with DSR >= 0.95 and PSR >= 0.95.

## Definitions

- Data: Binance USDT-perp klines with `taker_buy_volume` (Binance Vision /
  existing ingestion; free). Signal per name per day:
  `net_flow_ratio = (2*taker_buy_volume - volume) / volume` aggregated over
  the lookback window (volume-weighted). Point-in-time universe membership
  per the existing parquet; no survivorship.
- Rank: XS z-score of the aggregated ratio (own-history normalization first,
  rolling 90d, so size/regime effects cancel; both steps fixed here, not
  tunable).
- Portfolio: long top fraction, short bottom fraction, equal-weight within
  legs, vol-targeted at book level per engine defaults.
- Execution: signals from day-t close data; fills at day-t+1 open (no
  same-bar fills). Maker-entry assumption not weakened.
- Stats aggregation: daily PnL for WF/CPCV/DSR/PSR.

## Pre-registered grid (4 combos, n_trials = 4)

| combo | lookback_days | rebalance |
|---|---|---|
| 1 | 7 | daily |
| 2 | 7 | weekly |
| 3 | 30 | daily |
| 4 | 30 | weekly |

Top/bottom fraction fixed at 0.2 (6 names/side on a 30-name universe) — not
tunable. Weekly-rebalance combos directly implement the user's long-cycle
cost preference. No other parameter may be tuned; changes after Stage-2
results are seen consume K and need ex-ante rationale.

## Statistical power inputs (Stage-2.5 screen, computed 2026-07-23)

- breadth: asserted 6 effective (12 names traded, undercounted for
  crypto cross-correlation; independence UNCONFIRMED).
- n_obs: ~900 daily observations (2024-01 → 2026-06 universe window minus
  warmup) on EXISTING data — no backfill prerequisite.
- n_trials: 4 (family cumulative 0 + this grid).
- min_detectable_sharpe: **0.7014** at (6, 900, 4). Free upgrade path: the
  2020–2023 Binance Vision backfill for the wide universe lowers the floor
  to ~0.4340 and is authorized to run in parallel, but Stage-2/3 may proceed
  on the 900d window if the backfill lags.
- plausible_net_sharpe: estimated by Stage-2 `cost_after_edge` from a
  sample-window rank-persistence measurement; below the floor → FAIL with 0
  grid trials.

## Kill criteria (Stage-2)

- Data availability: `taker_buy_volume` present and non-degenerate for the
  PIT universe over the window (coverage >= 0.95 of member-days). If the
  current DB does not store the column, ingestion capture is a data task
  gating this probe — not a strategy failure.
- Distinctness (R6.6-guarded): declared gating references and their ranges
  MUST be registered ex-ante before the probe; feasibility guard must pass.
  Highest collision risk: XS price momentum (flow correlates with returns).
  |corr| < 0.30 against active-family reference signals; the H-002
  XS-momentum reference series must ALSO be computed advisory (it is
  shelved, not active) because a flow book that is just momentum-in-disguise
  is a relabel even if the gate technically passes.
- Cost-after-edge: decile-spread gross capture must exceed round-trip cost
  + short-leg funding drag under the engine cost model at the WEEKLY combo
  (the cheapest-turnover variant); if even weekly fails cost, the family
  stops.
- Statistical power: plausible_net_sharpe >= 0.7014 (or the recomputed floor
  if the backfill lands first — use the floor matching the actual probe
  window, computed by the screen, not hand-picked).

## Known risks (declared now)

1. Flow-vs-momentum collinearity is the most likely honest kill: if XS flow
   rank is >0.3-correlated with XS momentum rank, distinctness fails and we
   stop at 0 trials.
2. `taker_buy_volume` provenance: must come from Binance kline fields, not
   derived from trades; wash-trading distortion on thin names is mitigated
   by the PIT liquidity universe but not eliminated.
3. Short-leg funding drag is a first-order cost for XS crypto books; the
   cost model must include it (same treatment as H-002/H-009, not weaker).

## Not authorized by this spec

Stage-3, adapters, promotion, demo/shadow/live. Stage-2 probe execution and
any ingestion-capture work are separate Codex tasks. Liquidation
(candidate 2) and term-structure (candidate 3) families get their own
Stage-1 specs only AFTER their data scouting reports land; term structure
additionally requires a distinctness pre-estimate vs funding/basis before a
spec is worth writing.
