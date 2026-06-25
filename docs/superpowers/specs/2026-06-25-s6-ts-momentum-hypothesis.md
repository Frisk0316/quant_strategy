---
status: draft
type: design
owner: claude
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# S6 Slow Time-Series Momentum — Stage 1 Hypothesis (pipeline batch 1)

Strategy Research Pipeline Stage 1 output for candidate **S6**. Not a promotion
claim; nothing here is wired into any gate.

- **family_id:** `F-S6-TS-MOMENTUM` (new family; `prior_family_n_trials = 0`)
- **Backlog source:** `research/strategy_synthesis.md` Strategy 6 (Moskowitz, Ooi &
  Pedersen 2012; Daniel & Moskowitz 2016; Hurst, Ooi & Pedersen 2018).

## Hypothesis (falsifiable)

A low-turnover **time-series momentum** sleeve on BTC/ETH perps — each asset sized
long/short by the sign and strength of its *own* trailing trend, vol-targeted with
a crash filter — earns a positive net-of-cost Sharpe that beats BTC buy-and-hold,
surviving WF and CPCV with **DSR ≥ 0.95 and PSR ≥ 0.95**.

## Testable spec

- **Signal:** sign/strength of trailing return over lookback `L` (optionally
  vol-normalized); per asset, independently (time-series, not cross-sectional).
- **Entry/exit:** long if trend up, short/flat if trend down; rebalance on schedule;
  no taker breakout scalping.
- **Sizing:** vol-targeted exposure per asset; drawdown-based size reduction; max
  leverage cap; Daniel-Moskowitz momentum-crash filter.
- **Execution:** maker-first on pullbacks / scheduled rebalance; taker only for risk
  exits.
- **Universe:** BTC-USDT-SWAP, ETH-USDT-SWAP (optionally a few liquid majors).
- **Funding:** R3.1 sign over hold.

## Planned grid (pre-registered)

`{L ∈ [30d,60d,90d,120d], vol_target ∈ [10%,15%,20%], crash_filter ∈ [on,off],
rebalance ∈ [weekly,monthly]}` → **48 combos**. New family →
`prior_family_n_trials = 0`; CPCV `n_trials = 48`.

## Validation path

Two-pass (parquet pre-screen → DB venue-scoped CPCV N=6/k=2/embargo=2%/purge=1,
`n_trials = 48`). Mandatory leak test: trend signal uses only data ≤ t; trade at
t+1.

## Stage 2 feasibility findings

- **(a) Data availability: PASS.** BTC/ETH perp candles + funding are in the
  canonical DB (no spot needed).
- **(b) Distinctness: PASS (new family), with a portfolio caveat.** Time-series
  momentum (own-asset trend autocorrelation) is a distinct mechanism from
  cross-sectional momentum (`xs_momentum`) and long-only rotation
  (`ohlcv_rotation`). **Caveat (not a relabel):** realized returns may *correlate*
  with `ohlcv_rotation` in trending regimes — a diversification note for the
  portfolio, recorded but not a distinctness failure.
- **(c) Cost / overfit: LOW risk.** Narrow universe + small grid (48). Honest
  concern is **edge decay**: crypto TS-momentum net-of-cost edge has weakened, so
  the most likely honest outcome is a thin/insignificant edge that the gate
  correctly rejects — which is fine. Low overfit risk means *if* it passes, the
  pass is trustworthy.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-005` (F-S6-TS-MOMENTUM), status `proposed`.
- EXPERIMENT_REGISTRY: `E-008` planned, grid 48.

## Hand-off to Stage 3 (Codex)

Implement per this spec; leak test + `REFERENCE_VALIDATION_CONTRACTS` + ct_val
provenance + no idealized-fill; two-pass; record return-correlation vs
`ohlcv_rotation` in the evidence notes; stop at checkpoint ①.
