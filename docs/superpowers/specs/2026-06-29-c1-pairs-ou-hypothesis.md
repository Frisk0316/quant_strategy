---
status: draft
type: design
owner: claude
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# C1 BTC/ETH OU-Gated Pairs — Stage 1 Hypothesis (pipeline batch 2)

Strategy Research Pipeline Stage 1 output for batch-2 candidate **C1**. Not a
promotion claim; nothing here is wired into any gate.

- **family_id:** `F-PAIRS-OU` (new family; `prior_family_n_trials = 0`)
- **Backlog source:** `research/strategy_synthesis.md` Strategy 4 (Gatev, Goetzmann
  & Rouwenhorst 2006; Bertram 2009; Avellaneda & Lee 2010; Tadic & Kortchemski 2021).

## Hypothesis (falsifiable)

A dollar-neutral **BTC/ETH relative-value** book — trade the BTC–ETH spread under a
rolling hedge ratio, entering only when the **OU half-life and hedge-ratio quality
gates pass** — earns a positive net-of-cost Sharpe that beats both BTC buy-and-hold
and a static 50/50 BTC/ETH basket, surviving WF and CPCV with **DSR ≥ 0.95 and
PSR ≥ 0.95**.

## Testable spec

- **Signal:** rolling hedge ratio of ETH on BTC (log-price spread; rolling OLS or
  Kalman), spread z-score over lookback `L`, and OU half-life from an AR(1) fit on
  the spread. All rolling — **no full-sample fit**.
- **Entry:** enter dollar-neutral (long the cheap leg, short the rich leg) when
  `|z| ≥ z_enter` **and** `half_life ≤ max_half_life_days` (cointegration-quality
  gate).
- **Exit:** `|z| ≤ z_exit`, half-life break (`> max_half_life_days`), or max hold.
- **Sizing:** dollar-neutral (equal gross per leg), vol-targeted; per-leg cap.
- **Execution:** maker-first; taker only for risk exits.
- **Universe:** BTC-USDT-SWAP, ETH-USDT-SWAP (both perp legs).
- **Funding:** R3.1 sign on both perp legs over the hold.

## Planned grid (pre-registered)

`{L ∈ [7d,14d,30d], z_enter ∈ [2.0,2.5], z_exit ∈ [0.0,0.5],
max_half_life_days ∈ [3,7]}` → **24 combos**. New family →
`prior_family_n_trials = 0`; CPCV `n_trials = 24`.

## Validation path

Two-pass (parquet pre-screen → DB venue-scoped CPCV N=6/k=2/embargo=2%/purge=1,
`n_trials = 24`) on the **fold-refit** harness (`backtesting/pipeline_refit.py`).
Mandatory leak test: hedge ratio, z-score, and half-life use only data ≤ t; trade
at t+1.

## Stage 2 feasibility findings

- **(a) Data availability: PASS.** BTC/ETH perp 1m canonical candles are in the DB
  (1,293,120 rows each, 0 gaps). No spot needed.
- **(b) Distinctness: PASS (new family), CONFIRM vs `pairs_trading`.** Distinct from
  S7 (perp-vs-spot single-instrument basis convergence + funding carry) — C1 is
  **cross-asset BTC↔ETH** relative value driven by hedge-ratio cointegration, not
  basis/funding. The `pairs_trading` module exists (`enabled:false`) but was never
  CPCV-validated; C1 is its first proper validation. **Stage-2 gate:** verify C1's
  spec is not merely re-encoding existing `pairs_trading` params — if it is, this is
  a **retry of that family**, not a new family.
- **(c) Cost / overfit: MEDIUM.** Cointegration gating adds parameters; BTC/ETH
  cointegration is well-documented but regime-unstable. Honest concern is
  hedge-ratio drift / cointegration break. The 24-combo grid is modest.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-006` (F-PAIRS-OU), status `proposed`.
- EXPERIMENT_REGISTRY: `E-017` planned, grid 24.

## Hand-off to Stage 3 (Codex)

Implement per this spec with a **rolling** (not full-sample) hedge-ratio/half-life
estimate; mandatory leak test; `REFERENCE_VALIDATION_CONTRACTS` entry; ct_val
provenance; no idealized-fill; two-pass; fold-refit harness; record distinctness vs
`pairs_trading` in the evidence notes; stop at checkpoint ①.
