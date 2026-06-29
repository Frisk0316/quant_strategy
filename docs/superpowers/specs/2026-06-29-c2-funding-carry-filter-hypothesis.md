---
status: draft
type: design
owner: claude
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# C2 Funding Carry + Basis/Crowding Filter — Stage 1 Hypothesis (pipeline batch 2)

Strategy Research Pipeline Stage 1 output for batch-2 candidate **C2**. Not a
promotion claim; nothing here is wired into any gate.

- **family_id:** `F-FUNDING-CARRY` (mechanism of the existing `funding_carry`
  strategy; `prior_family_n_trials = 0` — no prior *recorded* pipeline trials)
- **Backlog source:** `research/strategy_synthesis.md` Strategy 3 (Makarov & Schoar
  2020; crypto perpetual-funding literature; Liu, Tsyvinski & Wu).

## Hypothesis (falsifiable)

A delta-neutral **long-spot / short-perp funding-carry** book that enters **only
when expected funding APR net of cost exceeds a threshold AND the basis z-score is
not in a blowout/crowded regime** earns a positive net-of-cost Sharpe that beats
buy-and-hold, surviving WF and CPCV with **DSR ≥ 0.95 and PSR ≥ 0.95**.

## Testable spec

- **Signal:** trailing/expected funding APR (from funding history) and perp-spot
  basis z-score over lookback `L`.
- **Entry:** enter delta-neutral (long spot, short perp) when funding APR after cost
  `> funding_enter_apr` **and** `|basis_z| ≤ basis_z_max` (avoid blowout/crowded).
- **Exit:** funding APR drops below `exit_funding_apr`, basis blowout
  (`|basis_z| > basis_z_max`), min net APR not met, or rebalance drift.
- **Sizing:** delta-neutral notional scaled by expected funding APR / realized vol;
  cap by liquidation buffer.
- **Execution:** both legs maker-preferred; rebalance on delta drift.
- **Universe:** BTC, ETH (spot + perp).
- **Funding:** the edge **is** funding — short perp receives positive funding (R3.1),
  accounted explicitly over the hold.

## Planned grid (pre-registered)

`{funding_enter_apr ∈ [5%,10%,15%], basis_z_max ∈ [2.0,3.0],
exit_funding_apr ∈ [0%,2%], rebalance ∈ [daily,weekly]}` → **24 combos**. prior=0;
CPCV `n_trials = 24`.

## Validation path

Two-pass → DB CPCV N=6/k=2/embargo=2%/purge=1, `n_trials = 24`, fold-refit harness.
Mandatory leak test: funding and basis signals use only data ≤ t; trade t+1.

## Stage 2 feasibility findings

- **(a) Data availability: PASS.** BTC/ETH funding (2,694 rows each) + spot + perp
  canonical candles are all in the DB.
- **(b) Distinctness: SAME-MECHANISM, declared as F-FUNDING-CARRY (not a relabel).**
  This is the same economic mechanism as the enabled `funding_carry` strategy **plus**
  a basis-z/crowding entry filter. Per the retry-vs-new-family rule it is family
  `F-FUNDING-CARRY`; **future tweaks are retries that count toward K**. No prior
  *recorded* pipeline trials → `prior=0`. It also serves as the first honest DSR
  validation of the one `enabled:true` strategy.
- **(c) Cost / overfit: LOW-MEDIUM.** Carry is a structural (funding) return, not
  price prediction; few params. Honest concern: crypto funding-carry net of cost is
  thin and crowded — the filter must add value or the gate rejects. **OI-based
  crowding deferred** (open interest not in DB); v1 crowding proxy = basis-z only.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-007` (F-FUNDING-CARRY), status `proposed`.
- EXPERIMENT_REGISTRY: `E-018` planned, grid 24.

## Hand-off to Stage 3 (Codex)

Implement as a **research backtest module** (like the s5/s6/s7 backtests) — do
**not** change the behavior of the live `src/okx_quant/strategies/funding_carry.py`
(forbidden; it is enabled). Mandatory leak test; `REFERENCE_VALIDATION_CONTRACTS`
entry; ct_val provenance (both BTC/ETH SWAP legs); no idealized-fill; two-pass;
fold-refit harness; note that this run also validates the carry family; stop at
checkpoint ①.
