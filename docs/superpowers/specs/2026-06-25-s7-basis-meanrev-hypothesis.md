---
status: draft
type: design
owner: claude
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# S7 Basis Z-Score Mean Reversion — Stage 1 Hypothesis (pipeline batch 1)

Strategy Research Pipeline Stage 1 output for candidate **S7**. Driver:
`docs/superpowers/pipeline/driver.md`. This is the testable hypothesis + Stage 2
feasibility findings; it is **not** a promotion claim and nothing here is wired
into any gate.

- **family_id:** `F-S7-BASIS-MEANREV` (new family; `prior_family_n_trials = 0`)
- **Backlog source:** `research/strategy_synthesis.md` Strategy 7 (Bertram 2009;
  Makarov & Schoar 2020; perpetual funding literature).

## Hypothesis (falsifiable)

A delta-neutral BTC/ETH perp-vs-spot **basis mean-reversion** book — entering when
the basis z-score is extreme and exiting on convergence — earns a positive
net-of-cost (fees + slippage + funding over the hold) Sharpe that **beats the
static funding-carry baseline**, surviving walk-forward and CPCV with
**DSR ≥ 0.95 and PSR ≥ 0.95**.

## Testable spec

- **Signal:** `basis_t = perp_mark_t / spot_t − 1`; `z_t = (basis_t − mean_L) / std_L`
  over rolling lookback `L`. OU half-life estimated over `L`; trade only when
  half-life ≤ `H` (reversion fast enough to capture before carry erodes it).
- **Entry (bidirectional — the key distinction from funding_carry):**
  - `z_t ≥ +Z_enter` (basis rich, perp > spot) → **short perp / long spot**.
  - `z_t ≤ −Z_enter` (basis cheap, backwardation) → **long perp / short spot**.
- **Exit:** `|z_t| ≤ Z_exit` (convergence) OR half-life break OR `max_hold`
  reached OR basis-blowout stop.
- **Sizing:** delta-neutral equal gross per leg; scale by expected convergence
  edge ÷ realized basis vol; per-trade cap; portfolio vol target; gross cap.
- **Execution:** maker-first both legs; taker only for risk exit. Funding charged
  with R3.1 sign over the actual hold (a short perp receives positive funding,
  which *adds* to the convergence edge when basis is rich — a genuine synergy, but
  it must be accounted, not assumed).
- **Universe:** BTC-USDT, ETH-USDT (spot) vs BTC-USDT-SWAP, ETH-USDT-SWAP (perp),
  Binance, point-in-time, both legs liquid.
- **Costs:** spot maker ~0.08% + perp maker ~0.02% per leg per side, plus slippage
  and funding over hold; net edge must clear the round-trip cost.

## Planned grid (pre-registered)

`{L ∈ [3d,7d,14d], Z_enter ∈ [1.5,2.0,2.5], Z_exit ∈ [0,0.5], H ∈ [1d,3d],
max_hold ∈ [7d,14d]}` → **72 combos**. First attempt of a new family, so
`prior_family_n_trials = 0`; CPCV `n_trials = 0 + 72 = 72` (per I23 / family
accounting). Any later retry of F-S7-BASIS-MEANREV adds to this.

## Validation path

Two-pass (per spec decision 6):

- **Pass A pre-screen:** parquet research-tier, coarse-grid WF → drop obvious
  losers. Not promotion evidence; trials still count toward the family.
- **Pass B:** survivors → DB venue-scoped CPCV (N=6, k=2, embargo=2%, purge=1),
  `n_trials = 72`, → DSR/PSR.
- **Leak guard (mandatory test):** `basis_t`/`z_t` use only data ≤ t; entry
  executes at t+1; funding applied over the realized hold, never look-ahead.

## Stage 2 feasibility findings

- **(b) Correlation distinctness vs `funding_carry`: PASS.** `funding_carry` enters
  on high funding APR and **blocks** entry when `|basis_z| > 2.5`; S7's entry
  trigger *is* extreme basis-z, it is bidirectional, and its alpha is convergence
  (exit on z→0) rather than ongoing carry. Opposite basis-z regime → genuine new
  family, not a relabel.
- **(a) Data availability: GATING — must confirm before Stage 3.** Perp 1m candles
  + funding for BTC/ETH-SWAP are in the canonical DB; **spot canonical candles
  (BTC-USDT, ETH-USDT, Binance, 2024-2026) are UNCONFIRMED** — the project has been
  perp-only and on-disk parquet is just a ~1-month tick mirror. **First Stage 3
  sub-task for Codex: verify/load spot 1m canonical for BTC-USDT and ETH-USDT
  (Binance) over the window.** If absent, S7 is data-blocked until loaded.
- **(c) Cost-after-edge smell test: pending data.** First cheap probe: on the
  ~1-month parquet, check whether historical basis-z reversion magnitude plausibly
  exceeds the ~0.20%+ round-trip leg-pair cost before committing to the full run.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-003` (F-S7-BASIS-MEANREV), status `proposed`.
- EXPERIMENT_REGISTRY: `E-006` planned, grid 72, artifact pending.

## Hand-off to Stage 3 (Codex)

1. Confirm/load spot canonical candles (gating).
2. Implement per this spec with the leak regression test + a
   `REFERENCE_VALIDATION_CONTRACTS` entry + ct_val provenance + no idealized-fill.
3. Run two-pass; emit gate-evidence `summary.json`.
4. Stop at checkpoint ① (Claude evidence review) before any shortlist entry.
