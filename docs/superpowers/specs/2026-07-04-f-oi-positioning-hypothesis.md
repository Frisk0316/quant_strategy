---
status: draft
type: design
owner: claude
created: 2026-07-04
last_reviewed: 2026-07-04
expires: none
superseded_by: null
---

# F-OI-POSITIONING — Stage 1 Hypothesis (taxonomy-sourced frontier candidate)

Strategy Research Pipeline Stage 1 output for `H-012`. Not a promotion claim;
nothing here is wired into any gate. Second taxonomy-sourced frontier candidate
(`docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md`) to clear Stage-2
data availability (E-034, 2026-07-04).

- **family_id:** `F-OI-POSITIONING` (new family; `prior_family_n_trials = 0` —
  E-034 was a 0-trial data probe)
- **Backlog source:** mechanism-taxonomy row「未平倉量 × 價格背離」/「持倉解單 /
  逼倉」(B-taxonomy source; `research/strategy_synthesis.md` has no OI
  strategy entry, so per the taxonomy's own rule this Stage-1 spec is the
  required upgrade of the frontier entry to *documented* before Stage 3).

## Design-space expansion (per `docs/DESIGN_SPACE.md`)

**Problem:** turn the taxonomy's OI×price-divergence mechanism into ONE
falsifiable, small-grid hypothesis testable on the data we actually have
(Binance 5m OI, BTC/ETH only).

**Constraints:** hard — 2 symbols only (no cross-sectional book); OI
`value_num` is USDT *notional* (mechanically price-correlated; contract count
lives in `fields.open_interest_contracts`); DSR/PSR ≥ 0.95 gates; family
budget K=0/2, small pre-registered grid. Soft — reuse existing daily
vectorized runner mechanics; docs-only at this stage.

**Option A — divergence-fade (unwind/squeeze reversal):** fade an L-day price
move that happened on *falling* contract-count OI (de-positioning: long
liquidation on the way down, short covering on the way up); flat when OI is
rising. Assumes de-positioning moves are transient flow, not information.
Wrong if falling-OI moves are actually informed exits. Blast radius: one new
research module.

**Option B — OI-confirmed trend filter:** trade *with* the L-day move only
when OI is rising (new positioning = informed flow). Assumes rising OI is
informed. Wrong the same way momentum is wrong — and its return source is
trend-following, which collides with `F-XS-MOMENTUM` / Strategy-6 TSMOM at
family-minting distinctness. High risk of `ASSIGN` instead of `MINT`.

**Option C — OI-level crowding extreme:** fade price when normalized OI level
hits an extreme percentile (crowding → forced unwind). Assumes OI level is
stationary enough to normalize; it is not (contract count trends structurally
with market growth over 2024–2026), so the normalization window eats history
and adds a hidden parameter.

**Option D — do nothing / wait for more symbols:** wait until other symbols'
OI is ingested and build a cross-sectional OI book. Preserves budget, but the
gate is open now, the TS test is cheap, and an XS-OI variant remains available
later as an explicit family twist.

**User sign-off (2026-07-04):** Option A approved, with one directed change —
do not accept the 2-name power ceiling; **backfill Binance Vision OI for the
rest of the PIT universe first** (the taxonomy row already notes the same
source extends to other symbols) and run the same TS divergence-fade signal
per symbol across the OI-good universe subset. This keeps Option A's
mechanism and adopts only the data-backfill half of Option D.

**Axis:** which reading of "positioning" implements the taxonomy mechanism
(持倉解單/逼倉) while staying mechanically distinct from the already-occupied
momentum and funding families.

**Decision:** Option A — it is the *direct* implementation of unwind/squeeze,
and the only option whose return source is transient-flow reversal rather
than trend continuation (B) or a nonstationary level bet (C).

**Would change if:** the Stage-3 family-minting checker returns `ASSIGN`
against `F-FUNDING-XS-DISPERSION` (fold into that family per I27), or the
contract-count series proves unusable (frozen/degenerate — see data-integrity
check below).

## Hypothesis (falsifiable)

A daily-rebalanced time-series book over the OI-good point-in-time USDT-perp
universe that, per symbol, **fades L-day price moves occurring on falling
contract-count open interest** (price up + OI down → short; price down + OI
down → long) and stays **flat when OI is rising or the OI decline is inside a
deadband**, vol-targeted at the portfolio level, earns a positive net-of-cost
Sharpe surviving WF and CPCV with **DSR ≥ 0.95 and PSR ≥ 0.95**. Beating
buy-hold is *not* the bar (the book is long/short/flat, not directional);
buy-hold is reported for context only.

## Testable spec

- **Instruments:** the point-in-time USDT-perp universe
  (`data/universe/universe_membership.parquet`, same PIT discipline as I20),
  restricted to symbols whose Binance Vision OI passes the extended Stage-2
  probe (per-symbol coverage evaluated over each symbol's PIT-eligible span,
  mirroring the funding probe's warmup-aware pattern). **Gate: ≥ 10 OI-good
  symbols required to run the grid** (funding-probe precedent
  `min_good_symbols=10`); if the backfill leaves fewer, stop and return to
  the user — do not silently run a narrow book. BTC/ETH OI is already
  ingested (E-034); the remaining universe symbols require backfill first
  (user-directed 2026-07-04, dataset-id convention `oi_binance_hist_<base>`).
  Window `2024-01-01` → `2026-06-17` end-exclusive — identical to the E-034
  probe window.
- **Price series:** Binance venue-scoped canonical 1m closes collapsed to
  daily last close (same loader/collapse as
  `backtesting/funding_xs_dispersion_backtest.py`). `ct_val` provenance
  venue-matched per I16.
- **OI series (the correctness trap, mandatory):** use
  `fields.open_interest_contracts` (contract count) from
  `external_observations` datasets `oi_binance_hist_{btc,eth}` — **never
  `value_num`**, which is USDT notional = contracts × price and is therefore
  mechanically correlated with the price leg of the signal (price up would
  fake "OI confirmation"). Exclude `quality_status='suspect'` rows. Daily OI
  sample = last 5m observation with `observed_at` ≤ that day's daily-close
  timestamp; if a day has no observation, carry the previous day's *position*
  (no fabricated signal, no forward-fill of the OI value across >1 day).
- **Signal (per symbol, at day t, from data ≤ t):**
  - `r_L` = L-day log return of daily close.
  - `d_L` = L-day change in log contract-count OI.
  - `z_L` = `d_L` divided by the rolling 90-day std of daily Δlog-OI (fixed
    90-day normalization window, not a grid dimension).
  - Position: if `z_L ≤ −z_min` (OI falling beyond deadband): `−sign(r_L)`
    (fade the move). Else (OI rising or inside deadband): flat. `r_L = 0`
    degenerate case: flat.
- **Leak guard (mandatory, known failure class):** the day-t target trades at
  t+1, same shift discipline as the fixed
  `test_daily_close_target_is_not_traded_on_same_day` pattern in
  `xs_momentum_backtest.py`. The t+1 trade shift also covers Binance Vision
  publication lag for the OI observations. Reuse the existing pattern; do not
  re-derive.
- **Construction/sizing:** inverse-vol weights across the active legs,
  standard `max_name_weight = 0.10` (fixed), portfolio vol-targeting reusing
  the corrected annualized vol-target path (`vol_target_annual = 0.175`,
  `vol_window_days = 28`, both fixed). A symbol is only signal-eligible on
  days it is PIT-eligible (I20) *and* has OI data. Daily rebalance
  (unwind/squeeze dynamics are days-scale; weekly would blur them; intraday
  5m would need fill realism this pipeline does not claim).
- **Costs:** `fee_bps = 2.0`, `slippage_bps = 2.0` per side, same defaults as
  the F-FUNDING-XS-DISPERSION runner. No spot leg, no funding-signal channel;
  funding *cashflow* on held perp positions must still be accounted per R3.1
  (positions are held overnight across settlement windows).
- **Data-integrity check (new, advisory):** E-034's `stale_ratio` measured
  *incomplete days*, not frozen values. Stage 3 must additionally report the
  count of days with exactly zero Δ contract-count per symbol; if > 5% of
  days, stop and flag before trusting the signal (a frozen OI feed would
  silently push the book to all-flat or all-fade).

## Distinctness vs `F-FUNDING-XS-DISPERSION` (H-009, testing)

The taxonomy flags F-FUNDING-XS-DISPERSION as the neighbor to rule out. The
mechanism-level case for MINT:

| | F-FUNDING-XS-DISPERSION (H-009) | F-OI-POSITIONING (this spec) |
|---|---|---|
| Data | Funding rates (8H), 28 symbols | Contract-count OI (5m→daily), 2 symbols |
| Construction | Cross-sectional dollar-neutral rank book, weekly | Per-symbol time-series long/short/flat, daily |
| Signal | *Relative level* of trailing funding APR across the universe | *Change* in OI interacted with own-price direction |
| Return source | Persistent dispersion/positioning premium harvested across names | Transient reversal of de-positioning flow (unwind/squeeze) |
| Holding logic | Always fully invested both legs | Mostly flat; active only after falling-OI moves |

Both are "positioning" families, so correlation is plausible — which is why
this argument is provisional. **Hand-off requirement (same as H-009's):** run
`backtesting/pipeline_family_minting.py` with the constructed OI-fade signal
against the `F-FUNDING-XS-DISPERSION` reference series (E-031 artifacts)
before or alongside the WF/CPCV grid. `ASSIGN`/`SKIP_RECOMMENDED` → fold into
F-FUNDING-XS-DISPERSION's trial/K budget per I27 and correct `H-012`'s ledger
row; do not keep a fresh `n_trials=0` budget if the checker disagrees.

## Planned grid (pre-registered, deliberately small)

`{lookback_days L ∈ [3, 7], deadband z_min ∈ [0.0, 0.5]}` → **4 combos**.
`prior_family_n_trials = 0` → CPCV `n_trials = 4`.

Rebalance frequency, vol-target, vol window, name cap, 90-day OI
normalization window, and cost assumptions are fixed, not grid dimensions.
Power note: the user-directed OI backfill (see Design-space sign-off) exists
precisely to buy breadth — target is the funding-good universe scale (~28
names) rather than 2 correlated majors; at `n_trials=4` the observed-Sharpe
bar is ≈1.7 (see `2026-07-03-statistical-power-gates.md`). The realized
breadth is whatever the extended OI probe certifies (≥ 10 gate above), and
must be reported in the Stage-3 artifact.

## Validation path

DB CPCV `N=6/k=2/embargo=2%/purge=1`, fold-refit harness
(`backtesting/pipeline_refit.py`, not the superseded full-sample-select-then-
slice path). Mandatory leak test per the guard above. Retain CPCV
`path_returns` (I25). Caller-declared family-cumulative `n_trials=4` (I23).
No idealized fill (I17). Stop at checkpoint ① per
`docs/superpowers/specs/2026-06-30-checkpoint1-automation-contract.md`.

## Stage 2 feasibility findings

- **(a) Data availability: PASS for BTC/ETH (E-034, 2026-07-04); NOT YET RUN
  for the rest of the universe.** `oi_binance_hist_{btc,eth}`: 258,493 /
  258,624 expected 5m rows, coverage 0.999493, missing_ratio 0.000507,
  stale_ratio 0.004454 (= 4 incomplete days of 898; both symbols share the
  same gaps, consistent with venue-side publishing outages). The user-directed
  universe-wide OI backfill plus an extended, PIT-aware Stage-2 probe (new
  E-row) must pass the ≥ 10 good-symbol gate **before** the Stage-3 grid runs.
  Caveat carried into the spec: probe `stale_ratio` does not detect frozen
  values — see the data-integrity check above.
- **(b) Distinctness: NOT YET RUN.** Mechanism argument above supports a
  provisional MINT; the quantitative checker run vs F-FUNDING-XS-DISPERSION
  is a required Stage-3 preflight (see table above). This spec's table is not
  a substitute for running it.
- **(c) Cost / overfit: LOW-MEDIUM, unverified.** Mostly-flat daily book on 2
  liquid majors → low turnover cost; public OI data → medium crowding/decay
  risk (taxonomy capacity rating 中). 4-combo grid with 2 free parameters
  keeps selection risk low; the real statistical risk is low breadth (2
  names), stated honestly above.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-012` (`F-OI-POSITIONING`), status `proposed`
  (unchanged — Stage 3 has not run); this spec added to its sources.
- EXPERIMENT_REGISTRY: `E-034` recorded (Stage-2 data probe). The Stage-3 run
  gets a new experiment id at run time per existing convention.

## Hand-off to Stage 3 (Codex)

0. **Data prerequisite (user-directed):** backfill Binance Vision 5m OI for
   the remaining PIT-universe symbols with the existing
   `scripts/market_data/download_binance_vision_metrics.py` path (extend its
   `DATASETS` symbol→dataset-id mapping; no new ingestion design), then
   extend and run the Stage-2 OI probe PIT-aware over the universe and record
   a new E-row. The ≥ 10 good-symbol gate must pass before any grid run.
1. **Family-minting preflight:** run the distinctness checker (constructed
   OI-fade signal vs F-FUNDING-XS-DISPERSION reference) and record
   `family_minting.json`; on `ASSIGN`/`SKIP_RECOMMENDED`, fold budgets per
   I27 and update `H-012` before any grid run.
2. Implement as a **new research backtest module** patterned on
   `backtesting/funding_xs_dispersion_backtest.py` (params dataclass, daily
   vectorized loop, corrected vol-target path, t+1 shift). Do not modify
   `xs_momentum_backtest.py`, `funding_xs_dispersion_backtest.py`, or any
   `src/okx_quant/strategies/` module.
3. OI loading: contract count from `fields.open_interest_contracts` (not
   `value_num`), `quality_status != 'suspect'`, daily sample = last
   observation ≤ daily close ts, no cross-day forward fill. Add the
   zero-ΔOI-days data-integrity report.
4. Mandatory leak test; `REFERENCE_VALIDATION_CONTRACTS` entry; `ct_val`
   provenance per leg (I16); R3.1 funding cashflow on held positions;
   fold-refit; retained `path_returns`; `n_trials=4`.
5. Stop at checkpoint ①; no adapter, promotion, demo, shadow, or live work
   until Claude/user review of the Stage-3 evidence.

## Scope / role

This spec is research/design output, Claude-authored, docs-only. Stage-3
implementation, the family-minting checker run, and any backtest are Codex's
responsibility. No gate, ledger verdict, or trading-core file is changed by
this document.
