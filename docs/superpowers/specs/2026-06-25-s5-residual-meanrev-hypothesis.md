---
status: draft
type: design
owner: claude
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# S5 Crypto Factor Residual Mean-Reversion — Stage 1 Hypothesis (pipeline batch 1)

Strategy Research Pipeline Stage 1 output for candidate **S5**. Not a promotion
claim; nothing here is wired into any gate.

- **family_id:** `F-S5-RESIDUAL-MEANREV` (new family; `prior_family_n_trials = 0`)
- **Backlog source:** `research/strategy_synthesis.md` Strategy 5 (Avellaneda & Lee
  2010; Liu & Tsyvinski 2019; Gu, Kelly & Xiu 2018).

## Hypothesis (falsifiable)

A market-neutral basket that **removes BTC/ETH common beta** from a liquid
point-in-time USDT-perp universe and trades the **mean reversion of the residual**
(short rich residuals, long cheap residuals) earns a positive net-of-cost Sharpe
that beats an equal-weight universe basket, surviving WF and CPCV with
**DSR ≥ 0.95 and PSR ≥ 0.95**.

> **Family-distinctness commitment (load-bearing):** S5 is framed as residual
> **mean-reversion**, the opposite sign to cross-sectional momentum. If it were
> instead built as residual *momentum*, it would be a **retry of F-XS-MOMENTUM**
> (prior_family_n_trials ≥ 24), not a new family. Checkpoint ① must confirm the
> implementation is reversion, not relabeled momentum.

## Testable spec

- **Factor model:** regress each symbol's returns on BTC (and optionally BTC+ETH)
  returns over a rolling window; residual = return − beta·factor.
- **Signal:** `z_t` of the cumulative residual over lookback `L`.
- **Entry/exit:** short top-quantile residual-z (rich), long bottom-quantile
  (cheap), dollar-neutral; exit on residual-z convergence / rebalance.
- **Sizing:** inverse-vol or HRP within legs; per-symbol cap; total-alt cap;
  portfolio vol target.
- **Execution:** maker-preferred low-frequency rebalance; skip a name if expected
  residual edge < maker + slippage.
- **Universe:** point-in-time top-N liquid USDT perps — **reuse `config/universe.yaml`
  + the xs_momentum membership builder** (survivorship/delisting guard already
  built, I20).
- **Funding:** R3.1 sign over hold for the perp legs.

## Planned grid (pre-registered)

`{L ∈ [1d,3d,7d], Z_enter ∈ [1.5,2.0,2.5], Z_exit ∈ [0,0.5], factors ∈ [BTC, BTC+ETH],
top_n ∈ [10,20]}` → **72 combos**. New family → `prior_family_n_trials = 0`; CPCV
`n_trials = 72`.

## Validation path

Two-pass (parquet pre-screen → DB venue-scoped CPCV N=6/k=2/embargo=2%/purge=1,
`n_trials = 72`). Mandatory leak test: betas/residual-z use only data ≤ t; trade
at t+1.

## Stage 2 feasibility findings

- **(a) Data availability: PASS.** Reuses the perp 1m canonical universe + funding
  already used by xs_momentum (no spot data needed).
- **(b) Distinctness: CONDITIONAL → PASS only as residual mean-reversion.** Distinct
  from F-XS-MOMENTUM (momentum) and `ohlcv_rotation` (long-only momentum) *iff* it
  trades residual reversion. Residual momentum = retry of F-XS-MOMENTUM. Committed
  to reversion above.
- **(c) Cost / overfit: HIGHEST RISK in the batch — FLAG.** Wide universe + factor
  model + parameter search is the same family-risk class that just refuted
  xs_momentum, and S5 sits in `strategy_synthesis.md` "Strategies Rejected For Now"
  pending universe/delisting/cost validation. Mitigations: reuse the point-in-time
  membership (survivorship guard) and honest family n_trials. Recommendation:
  proceed, but it is the **most likely of the three to be honestly refuted**, and
  must not be tuned past K=2.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-004` (F-S5-RESIDUAL-MEANREV), status `proposed`.
- EXPERIMENT_REGISTRY: `E-007` planned, grid 72.

## Hand-off to Stage 3 (Codex)

Implement residual mean-reversion (not momentum) per this spec, reusing the
universe membership; leak test + `REFERENCE_VALIDATION_CONTRACTS` + ct_val
provenance + no idealized-fill; two-pass; stop at checkpoint ①.
