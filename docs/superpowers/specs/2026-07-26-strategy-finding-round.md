---
status: current
type: spec
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# 2026-07-26 Strategy-Finding Round — Pre-registration

Status: current for this research run only  
Owner: Codex  
Authority: user request dated 2026-07-26  
Scope: Stage 2 feasibility and, only after a complete Stage 2 pass, Stage 3
fold-refit validation. This document is not promotion or deployment authority.

## Decision

Run exactly two directions:

1. **New family — H-023 / F-XS-IDIOVOL:** use the existing Binance
   point-in-time universe, daily close, and funding data to test a weekly
   cross-sectional low-idiosyncratic-volatility book.
2. **Existing-family iteration — H-009 / F-FUNDING-XS-DISPERSION retry 1:**
   restore the three economic assets excluded from E-031 only because their
   data was then unavailable, while collapsing the SHIB alias without changing
   the signal or grid.

Both directions stop at Stage 2 if any mandatory feasibility check fails.
Passing Stage 2 only permits Stage 3; passing Stage 3 is checkpoint evidence,
not promotion evidence.

## Design-space expansion

| Candidate | Existing data ready | Previously validated family | Smallest honest implementation | Main failure mode | Decision |
| --- | --- | --- | --- | --- | --- |
| Cross-sectional idiosyncratic volatility | Yes: PIT universe + Binance close/funding | No | Reuse the XS backtest, WF/CPCV, power, and checkpoint helpers | Residual-volatility score may duplicate broad XS risk or lack power | Select as the new family |
| CME gap mean reversion | Partial | No | Requires a new venue/session alignment path | Thin and venue-mismatched sample | Defer |
| Intraday session residual reversal | Yes | No | Requires a new intraday panel and session-boundary contract | Timing/leakage surface is larger | Defer |
| H-014 parameter retune | Yes | Yes, already supported | Small code change | Gate-chasing; its next gate is shadow, not another backtest | Reject |
| H-009 breadth restoration | Yes after the data rebuild and ADR-0015 alias | Yes, marginal E-031 miss | Reuse the frozen E-031 mechanism and grid | Retry may still miss DSR/PSR after higher trial count | Select as the iteration |

This choice changes only if the frozen Stage 2 evidence fails. In that case the
candidate is stopped, not replaced mid-run.

## Shared data and execution contract

- Window: `[2024-01-01, 2026-06-17)`.
- Universe: `data/universe/universe_membership.parquet`, selected
  point-in-time before any aliasing.
- Venue: Binance only.
- Close: `canonical_candles`, `source_primary='binance'`, daily last close
  derived from canonical intraday candles.
- Funding: `funding_rates`, Binance 8-hour observations collapsed to the daily
  engine input with the existing R3.1 convention.
- Alias: consumer-time `SHIB-USDT-SWAP -> 1000SHIB-USDT-SWAP` per ADR-0015,
  with same-day duplicate economic assets collapsed and no rank-31 refill.
- Execution: signal information through day `t`; executable target no earlier
  than `t+1`; intraday positions use the existing one-bar execution lag.
- Costs: existing engine defaults, 2 bps fee plus 2 bps slippage per unit of
  turnover, plus funding cashflows; no idealized-fill claim.
- Stage 3: walk-forward `365/90`; CPCV `N=6`, `k=2`, `embargo=2%`, `purge=1`;
  fold-local parameter selection only.
- Statistical checkpoint: DSR `>=0.95`, PSR `>=0.95`, nonzero activity,
  leak check pass, `idealized_fill=false`, authoritative venue-matched
  `ct_val`, and raw CPCV path returns retained.

## Direction 1 — H-023 / F-XS-IDIOVOL

### Research prior and uncertainty

Recent spot-market evidence reports a low-volatility premium, strongest around
two-to-three-month formation and one-month holding horizons
([Pyo and Jang, 2026](https://doi.org/10.1016/j.frl.2026.109851)). Earlier
crypto evidence reports a positive cross-sectional relation between
idiosyncratic volatility and expected returns
([Zhang and Li, 2020](https://doi.org/10.1016/j.ribaf.2020.101252)).
Neither result establishes the sign for this Binance perp, BTC-residual,
net-of-funding implementation. The disagreement is the reason to test the
frozen direction, not evidence that it will pass.

### Falsifiable hypothesis

A weekly, dollar-neutral cross-sectional book that is long the lowest and
short the highest BTC-factor residual volatility among the eligible
point-in-time Binance USDT-perp universe earns positive net-of-cost returns
and survives fold-refit WF/CPCV with DSR and PSR both at least 0.95.

### Frozen signal

1. Compute daily close-to-close asset and BTC returns.
2. For each asset, estimate rolling beta to BTC over `lookback_days`, using
   observations available through the decision date.
3. Residual return is `asset_return - beta * BTC_return`; score is the rolling
   standard deviation of those residuals over the same lookback.
4. Exclude BTC from cross-sectional ranking because its self-residual is
   mechanically near zero.
5. Rebalance weekly: long the lowest-score fraction and short the
   highest-score fraction, equal weighted within each leg.
6. Apply the existing portfolio book-vol target `0.175`, max absolute
   name weight `0.10`, and existing market-risk multiplier. Do not add
   inverse-vol weighting inside either leg.

Frozen grid: `lookback_days in {14, 28}` crossed with
`quantile in {0.20, 0.30}` = **4 prospective trials**. The Stage 2 proxy is
`lookback_days=28`, `quantile=0.20`.

### Stage 2 gates

- **Data availability:** at least 10 alias-adjusted symbols each have at least
  80% eligible-day close coverage and 80% eligible-day days with all three
  Binance funding observations; stale fraction at most 10%; post-warmup
  eligible breadth at least 10.
- **Distinctness:** the frozen proxy has absolute daily-return correlation
  below `0.70` against the E-031
  `family_minting_candidate.json::signal` and against **each of the four**
  E-045 `combo_daily_returns.csv` cells; the gate uses the maximum absolute
  correlation. Each comparison requires at least 365 common observations.
  Undefined or insufficient overlap fails closed.
- **Cost-after-edge:** the proxy's engine-net annualized Sharpe is strictly
  positive and its mean weekly engine-net return is strictly positive.
  This is a feasibility smell test, not validation evidence.
- **Statistical power:** use the shared `pipeline_power_screen` with
  `breadth=6`, actual post-warmup non-null daily observations,
  prospective family `n_trials=4`, and the proxy engine-net Sharpe as the
  plausible effect. Plausible Sharpe must meet the recomputed floor.

Only a four-of-four pass permits Stage 3 and consumes the four trials.

## Direction 2 — H-009 breadth-restored retry 1

### Ex-ante retry rationale

E-031 was evaluated on 28 unique economic assets. Current data adds
`CC-USDT-SWAP`, `FIL-USDT-SWAP`, and `M-USDT-SWAP`; E-031 already contained
`1000SHIB-USDT-SWAP`, so ADR-0015 requires `SHIB-USDT-SWAP` to collapse into
that existing asset rather than count as a fourth addition. The correct
breadth-restored target is therefore 31 unique assets. Restoring breadth is a
data-availability change formed before this run, not a response to E-031
per-combination results.

### Frozen retry

- Restore CC, FIL, and M where the shared coverage gate admits them; collapse
  SHIB into 1000SHIB after PIT selection with no replacement or double count.
- Preserve the E-031 mechanism, weekly rebalance, execution, costs, risk
  sizing, and grid exactly:
  `lookback_days in {7, 14}` crossed with `quantile in {0.20, 0.30}` =
  **4 retry trials**.
- Family-cumulative trial count passed to CPCV/DSR: **8**.
- Retry budget after execution: **K=1/2**, regardless of outcome.
- Stage 2 proxy: `lookback_days=7`, `quantile=0.20`.

### Stage 2 gates

- **Data availability:** the same shared coverage and breadth thresholds as
  H-023; restored breadth is reported explicitly.
- **Distinctness:** this is declared as the same F-FUNDING-XS-DISPERSION
  family, never minted as a new family. The mechanism and declared neighbor
  remain unchanged from E-031.
- **Cost-after-edge:** the proxy's engine-net annualized Sharpe and mean
  weekly engine-net return are both strictly positive.
- **Statistical power:** `pipeline_power_screen` with `breadth=6`, actual
  post-warmup observations, family-cumulative `n_trials=8`, and proxy
  engine-net Sharpe. Plausible Sharpe must meet the recomputed floor.

Only a four-of-four pass permits the unchanged four-cell Stage 3 run.

## Decision rules

- **Stage 2 FAIL:** no Stage 3, no trial consumption, no retune.
- **Stage 3 statistical FAIL:** record the full metrics and shelve the new
  family; for H-009, record retry consumption and leave any further retry to
  a new ex-ante decision.
- **Stage 3 statistical PASS:** checkpoint-only pass. Portable validation,
  robustness, human review, and the collaboration-contract gates remain
  required. `promotion_gate_passed` stays false here.
- Existing artifacts are immutable; this run writes only below
  `results/strategy_finding_20260726/`.
