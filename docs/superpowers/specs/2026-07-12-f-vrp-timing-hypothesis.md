---
status: accepted
type: design
owner: claude
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# F-VRP-TIMING — Stage 1 Hypothesis (Deribit-data frontier candidate)

Strategy Research Pipeline Stage 1 output for `H-013`. Not a promotion claim;
nothing here is wired into any gate. First candidate from the Deribit data
workstream (`research/deribit_data_strategy_research.md` §3 C1), enabled by
the D1–D5 ingestion accepted on 2026-07-12
(`tasks/2026-07-11-deribit-ingestion-review.md`).

- **family_id:** `F-VRP-TIMING` (new family; `prior_family_n_trials = 0` —
  no probe or grid has run)
- **Backlog source:** `research/deribit_data_strategy_research.md` §3
  candidate C1 (volatility-risk-premium timing), user-approved top pick of
  the Deribit candidate ranking (plan sign-off 2026-07-11).

## Design-space expansion (per `docs/DESIGN_SPACE.md`)

**Problem:** turn the implied-vs-realized volatility spread (volatility risk
premium, VRP) from the newly ingested hourly DVOL into ONE falsifiable,
small-grid, time-series hypothesis on the data we actually have (DVOL exists
for BTC and ETH only).

**Constraints:** hard — 2 symbols only (Deribit publishes no other DVOL;
no breadth backfill exists, unlike H-012's OI); PIT discipline via
`published_at` as-of joins (bucket-end labeling per DATA_FLOW convention,
F26 guard); DSR/PSR ≥ 0.95 gates; family K=0/2; small pre-registered grid.
Soft — reuse the daily vectorized research-runner mechanics; docs-only at
this stage.

**Option A — VRP-level long/flat timing:** long the perp when the VRP
z-score is high (options market pays a rich premium over realized risk —
the classic Bollerslev-Tauchen-Zhou result: high VRP predicts positive
underlying returns), flat when VRP is low or inverted (IV below RV =
stress / risk underpriced). Assumes the equity-market VRP-return relation
carries to crypto majors. Wrong if crypto VRP is only a crowding gauge with
no return forecast. Blast radius: one new research module.

**Option B — VRP-collapse risk-off filter only:** binary exit when RV
crosses above DVOL (VRP inversion), long otherwise. A strict subset of
Option A (it is A with `z_min` pinned at the inversion point); testing it
alone spends the family budget on the less general rule.

**Option C — DVOL momentum / vol mean-reversion:** trade the vol series
itself. We hold no tradable vol instrument (no options execution in this
platform), so the mechanism→instrument link is indirect (perp proxy), and
the return source would collide with TS-momentum families at minting.

**Option D — options-flow imbalance signal:** use `optflow_deribit_*`
taker-premium imbalance instead. That is candidate C2 in the research doc —
a *different* mechanism (informed flow vs risk premium) reserved as its own
future family; folding it in here would blur the falsifiable claim.

**Axis:** which VRP reading gives the most direct, mechanically distinct
implementation of "options market prices risk vs realized risk" on
instruments we can actually trade.

**Decision:** Option A — it is the direct risk-premium mechanism, subsumes B
as a grid point, and keeps the family distinct from trend (C) and flow (D)
return sources.

**Would change if:** the Stage-3 family-minting checker returns `ASSIGN`
against `F-FUNDING-XS-DISPERSION` or `F-OI-POSITIONING` (fold per I27), or
the DVOL data-integrity check below flags a frozen/degenerate feed.

**User sign-off:** APPROVED 2026-07-12 through the explicit request to implement
`tasks/2026-07-12-claude-p0-review.md`. This authorizes the separately scoped
Stage-2 probe; it does not authorize a Stage-3 grid or promotion work.

## Hypothesis (falsifiable)

A daily-rebalanced long/flat time-series book on BTC-USDT-SWAP and
ETH-USDT-SWAP that is **long when the trailing volatility-risk premium
(hourly Deribit DVOL minus realized vol from canonical 1m candles) is high
versus its own 90-day distribution, and flat otherwise**, vol-targeted at
the portfolio level, earns a positive net-of-cost Sharpe surviving WF and
CPCV with **DSR ≥ 0.95 and PSR ≥ 0.95**. Beating buy-hold is *not* the bar
(the book is long/flat); buy-hold is reported for context only.

## Testable spec

- **Instruments:** BTC-USDT-SWAP, ETH-USDT-SWAP, Binance venue-scoped
  canonical 1m candles (full 2024-01-01 → 2026-07-10 coverage confirmed).
  Window `2024-01-01` → `2026-07-10` end-inclusive, matching the ingested
  DVOL/funding range. `ct_val` provenance venue-matched per I16.
- **Price series:** canonical 1m closes collapsed to daily last close (same
  loader/collapse as `backtesting/funding_xs_dispersion_backtest.py`).
- **Implied-vol series:** `dvol_deribit_btc_1h` / `dvol_deribit_eth_1h`
  from `external_observations` (22,128 hourly rows each, verified gap-free
  ≤2h). Daily sample = last observation with **`published_at` ≤ the day-t
  daily-close timestamp** (bucket-end labeling per the DATA_FLOW aggregate
  convention; this is the F26 leak class — do not join on `observed_at`).
  `value_num` is the DVOL close in index points = annualized implied vol %.
  Exclude `quality_status='suspect'` rows. A day with no observation carries
  the previous day's *position* (no forward-fill of the value beyond 1 day).
- **Realized-vol series (per symbol, at day t, from data ≤ t):**
  `RV_t` = annualized std of 1m log returns over the trailing `W` calendar
  days ending at the day-t close, in percent (× sqrt(365·1440) on the 1m
  std, matching DVOL's annualized-percent units). Days with < 90% of
  expected 1m bars in the window: reuse the previous day's RV (no fabricated
  vol from sparse bars).
- **Signal (per symbol, at day t):**
  - `VRP_t = DVOL_t − RV_t` (both annualized %, same units).
  - `z_t` = (`VRP_t` − rolling 90-day mean of VRP) / rolling 90-day std of
    VRP (fixed 90-day normalization window, not a grid dimension; first 90
    days are warmup, no positions).
  - Position: long if `z_t ≥ z_min`, else flat. No short leg in v1 (short
    on VRP inversion is a possible pre-registered *future* twist; adding it
    now would double the grid for the weaker half of the mechanism).
- **Leak guard (mandatory, known failure classes):** (1) day-t signal uses
  DVOL rows with `published_at` ≤ day-t close only (F26); (2) the day-t
  target trades at t+1 — same shift discipline as
  `test_daily_close_target_is_not_traded_on_same_day`. Reuse the existing
  pattern; do not re-derive.
- **Construction/sizing:** equal weight across active legs (1–2 names — a
  per-name cap is meaningless at this breadth and is deliberately omitted),
  portfolio vol-targeting on the corrected annualized path
  (`vol_target_annual = 0.175`, `vol_window_days = 28`, both fixed). Daily
  rebalance (VRP is a days-scale regime variable; weekly would blur entries
  around VRP collapses).
- **Costs:** `fee_bps = 2.0`, `slippage_bps = 2.0` per side (runner
  defaults). Funding *cashflow* on held perp positions accounted per R3.1
  (long-only book held across settlement windows — funding drag is a real
  cost of this strategy and must not be idealized away).
- **Data-integrity check (advisory, mirrors H-012's):** report the count of
  days with exactly zero Δ in the daily-sampled DVOL close per symbol; if
  > 5% of days, stop and flag before trusting the signal (a frozen feed
  pushes the book to a constant position).

## Distinctness vs testing/enabled families

| | F-FUNDING-XS-DISPERSION (H-009) | F-OI-POSITIONING (H-012) | F-VRP-TIMING (this spec) |
|---|---|---|---|
| Data | Funding rates, 28 symbols | Contract-count OI, 31 symbols | Deribit DVOL + own realized vol, 2 symbols |
| Construction | XS dollar-neutral rank book, weekly | Per-symbol TS long/short/flat, daily | Per-symbol TS long/flat, daily |
| Signal | Relative funding APR across names | ΔOI × own-price direction | Implied-minus-realized vol spread vs own history |
| Return source | Cross-name positioning premium | Transient unwind/squeeze reversal | Volatility risk premium as a risk-appetite state variable |

Shape caveat stated honestly: the refuted `F-SENTIMENT` (H-008) was also a
BTC long/flat regime book, and Alternative.me F&G embeds a volatility
component — the *mechanism* differs (option-market risk pricing vs composite
retail sentiment), but the realized position series could correlate.
**Hand-off requirement (same as H-009/H-012):** run
`backtesting/pipeline_family_minting.py` with the constructed VRP signal
against the `F-FUNDING-XS-DISPERSION` and `F-OI-POSITIONING` reference
series before or alongside the grid. `ASSIGN`/`SKIP_RECOMMENDED` → fold
budgets per I27 and correct `H-013`'s ledger row.

## Planned grid (pre-registered, deliberately small)

`{RV window W ∈ [14, 28] days, entry threshold z_min ∈ [0.0, 0.5]}` →
**4 combos**. `prior_family_n_trials = 0` → CPCV `n_trials = 4`.

Rebalance frequency, 90-day VRP normalization window, vol-target, vol
window, and costs are fixed, not grid dimensions. **Power note (the honest
weakness):** 2 correlated majors, no breadth remedy exists (Deribit
publishes no third DVOL). At `n_trials = 4` the observed-Sharpe bar is
≈ 1.7 (`2026-07-03-statistical-power-gates.md`). This family is cheap to
test precisely because the data is already ingested and verified; a
marginal-fail outcome here (à la H-009/H-012) is a plausible result and
carries no retry entitlement.

## Validation path

DB CPCV `N=6/k=2/embargo=2%/purge=1`, fold-refit harness
(`backtesting/pipeline_refit.py`). Mandatory leak test per the guard above
(both classes: published_at as-of and t+1 shift). Retain CPCV
`path_returns` (I25). Caller-declared family-cumulative `n_trials=4` (I23).
No idealized fill (I17). Stop at checkpoint ① per
`docs/superpowers/specs/2026-06-30-checkpoint1-automation-contract.md`.

## Stage 2 feasibility findings

- **(a) Data availability: PASS in substance, formal probe pending.** The
  2026-07-12 ingestion re-review verified by direct DB query: 22,128 hourly
  DVOL rows per symbol, 2024-01-01 → 2026-07-10 23:00Z, zero gaps > 2h,
  100% bucket-end `published_at` labeling; canonical 1m candles are complete
  over the window. Stage-3 preflight must still emit the standard
  `stage2_feasibility.json` (new E-row `E-038`) so the pipeline record is
  mechanical, not narrative.
- **(b) Distinctness: NOT YET RUN.** Mechanism table above is provisional;
  the quantitative checker run vs both testing families is a required
  preflight.
- **(c) Cost / overfit: LOW turnover, honest low power.** Long/flat daily
  book on 2 liquid majors → low fee drag but real funding drag (accounted).
  4-combo grid with 2 free parameters keeps selection risk low; the binding
  risk is breadth (2 names), stated above and accepted ex-ante.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-013` (`F-VRP-TIMING`), status `proposed`, family
  cumulative n_trials 0; this spec is its source.
- EXPERIMENT_REGISTRY: `E-038` reserved for the formal Stage-2 feasibility
  probe; the Stage-3 run gets a new experiment id at run time per existing
  convention.

## Hand-off to Stage 3 (Codex) — Stage 2 is the next separately scoped task

1. **Stage-2 preflight:** run the standard feasibility probe over
   `dvol_deribit_{btc,eth}_1h` + canonical candles (coverage, staleness,
   zero-Δ frozen-feed count) and record `stage2_feasibility.json` + `E-038`.
2. **Family-minting preflight:** distinctness checker (constructed VRP
   signal vs F-FUNDING-XS-DISPERSION and F-OI-POSITIONING references);
   record `family_minting.json`; on `ASSIGN`, fold per I27 and update
   `H-013` before any grid run.
3. Implement as a **new research backtest module** patterned on
   `backtesting/oi_positioning_backtest.py` (params dataclass, daily
   vectorized loop, corrected vol-target path, t+1 shift, published_at
   as-of DVOL sampling). Do not modify existing backtest modules or any
   `src/okx_quant/strategies/` file.
4. Mandatory leak test (both classes); `REFERENCE_VALIDATION_CONTRACTS`
   entry; `ct_val` provenance (I16); R3.1 funding cashflow; fold-refit;
   retained `path_returns`; `n_trials=4`; register the runner in
   `backtesting/pipeline_stage3_registry.py`.
5. Stop at checkpoint ①; no adapter, promotion, demo, shadow, or live work
   until Claude/user review of the Stage-3 evidence.

## Scope / role

This spec is research/design output, Claude-authored, docs-only. Stage-2 is now
approved as a separate task; Stage-3 still depends on Stage-2 and family-minting
evidence. No gate or trading-core file is changed by this sign-off.
