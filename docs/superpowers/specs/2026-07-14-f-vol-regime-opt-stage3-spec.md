---
status: accepted
type: design
owner: claude
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# F-VOL-REGIME-OPT Stage-3 spec (H-014) — user-signed-off 2026-07-14

Pre-registers the options backtest BEFORE any code runs. Accounting is
governed by ADR-0010 (proposed) and the draft manifest
`docs/change_manifests/2026-07-14-inverse-options-research-accounting.md`.
Evidence to date: E-039 (mechanism separation), E-043 (Stage-2 pricing PASS),
entry-leg traded premiums collected (`results/h014_leg_marks_20260714/`).

## What Stage 3 tests

The falsifiable H-014 claim on its pre-registered grid, restricted to the
**short side of the C target** (the CHEAP-bucket long-straddle leg stays OFF,
as fixed in the 2026-07-13 Stage-1 spec after E-039 refuted it; re-enabling
it would be a separately registered twist):

- RICH regime (per combo): sell the 30d ~25Δ covered call AND the 25Δ/10Δ
  put spread; otherwise hold no option positions.
- Gate: coin-denominated overlay return Sharpe surviving fold-refit WF/CPCV
  with **DSR ≥ 0.95 and PSR ≥ 0.95** (`n_trials = 4`, caller-declared;
  family cumulative stays 4 — all prior E-rows were 0-trial probes).

## Construction (fixed ex-ante)

- **Validated series:** daily coin-denominated PnL of the OPTION OVERLAY
  only, per symbol then equal-weighted. The 1-coin collateral's own price
  return is beta, not the strategy, and is excluded (reported as context).
- **Signal:** day-t DVOL close → IVP(365d) and VRP z(90d) exactly as in the
  immutable E-039 series construction. RICH(combo) = IVP ≥ ivp_min AND
  z ≥ z_min. Grid `{ivp_min ∈ [75, 85], z_min ∈ [0.5, 1.0]}` = 4 combos —
  restated unchanged from the 2026-07-13 pre-registration.
- **Entry timing (leak guard):** a day-t signal opens positions at **day
  t+1 traded VWAP** (F26-class discipline; the already-collected day-t marks
  are calibration data, not entry fills — a t+1 collection extension is
  required before the run).
- **Daily-tranche laddering:** each qualifying day opens a 1/30-unit tranche
  per structure per symbol, capped at 1.0 aggregate unit per symbol (fully
  covered, never naked); each tranche is held to its own expiry (official
  delivery price). This densifies the sparse RICH cycles into a valid daily
  series instead of ~10 lumpy non-overlapping cycles.
- **Legs per tranche:** short call at the nearest listed strike to the 25Δ
  target; short 25Δ put + long 10Δ put (spread); nearest-30d expiry among
  instruments with `creation_timestamp` ≤ entry day (the E-044-era collector
  lesson, now mandatory).
- **Marks/fees/settlement:** per ADR-0010 rules 2/5/6 (trade-tape daily VWAP
  marks, BS-DVOL-offset fallback capped at 30% of position-days, published
  Deribit fee formulas, official delivery prices).

## Data extension required (Claude runs it; free official sources)

1. t+1 entry-day VWAPs for all grid-qualifying days (superset already
   enumerated; same collector, shifted one day).
2. Daily M2M VWAPs for every held instrument-day until expiry.
3. `public/get_delivery_prices` history for BTC/ETH (settlement).

## Validation path

`refit_validation` fold-refit WF 365/90 + CPCV 6/2/2%/1 on the daily overlay
series; retained `path_returns` (I25); family minting re-run vs the
F-FUNDING-XS-DISPERSION and F-OI-POSITIONING references (I27); golden-cycle
unit test (hand-computed covered-call cycle incl. ITM settlement and fees)
must pass before the grid executes; fresh-verifier pass after the run.
Experiment id **E-051 reserved**; artifacts under
`results/h014_stage3_<date>/`.

## Honest power statement (read before signing)

RICH days are 3–12% of the sample depending on combo; even laddered, most
days carry zero or small overlay PnL. With ~2.5 years and n=4, the
observed-Sharpe bar stays ≈ 1.7 on a sparse series — an inconclusive-by-power
outcome is plausible and would SHELVE the family under standing rules without
invalidating the Stage-2 pricing evidence. No post-hoc grid extension, no
gate-chasing retry, regardless of how near a miss lands.

## What sign-off covers (one decision)

1. Accept ADR-0010 (accounting rules 1–7).
2. Authorize the data extension + research runner
   (`research/probes/h014_stage3_backtest.py`) + E-051 Stage-3 run.
3. Confirm the long leg stays OFF and naked short puts remain prohibited.

Nothing here creates promotion/demo/shadow/live readiness under any outcome.
