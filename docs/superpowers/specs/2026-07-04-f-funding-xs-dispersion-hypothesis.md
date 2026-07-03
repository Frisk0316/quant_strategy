---
status: draft
type: design
owner: claude
created: 2026-07-04
last_reviewed: 2026-07-04
expires: none
superseded_by: null
---

# F-FUNDING-XS-DISPERSION — Stage 1 Hypothesis (taxonomy-sourced frontier candidate)

Strategy Research Pipeline Stage 1 output for `H-009`. Not a promotion claim;
nothing here is wired into any gate. This is the first taxonomy-sourced
frontier candidate (`docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md`)
to clear Stage-2 data availability.

- **family_id:** `F-FUNDING-XS-DISPERSION` (new family; `prior_family_n_trials
  = 0` — no prior recorded pipeline trials)
- **Backlog source:** `docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md`
  row "橫斷 funding 排序" (B-taxonomy source, not `research/strategy_synthesis.md`
  — this candidate has no numbered Strategy entry there). Per the Stage 1
  template's Autonomous Mode Appendix, mechanism-taxonomy entries are a valid
  B-half source.

## Hypothesis (falsifiable)

A dollar-neutral cross-sectional book that goes **long the lowest-trailing-
funding-APR quartile and short the highest-trailing-funding-APR quartile** of
a point-in-time liquid USDT-perp universe, rebalanced weekly, earns a positive
net-of-cost Sharpe that beats an equal-weight universe basket, surviving WF
and CPCV with **DSR ≥ 0.95 and PSR ≥ 0.95**.

## Testable spec

- **Signal:** trailing `L`-day average annualized funding APR per symbol
  (8H funding rate compounded/annualized), computed only from funding data
  observed strictly before the rebalance timestamp.
- **Universe:** the same point-in-time top-`N` liquid USDT-perp universe used
  by `xs_momentum` (`data/universe/universe_membership.parquet`,
  `config/universe.yaml`: `top_n=30`, `rebalance=weekly`, `warmup_days=30`).
  No new universe-construction logic — reuse as-is.
- **Rank & construct:** at each weekly rebalance, rank the PIT-eligible
  universe by trailing funding APR; go long the bottom quantile `Q`, short
  the top quantile `Q`; dollar-neutral, equal-weight within each leg.
- **Entry/exit:** positions reset each weekly rebalance to the current
  quantile membership (no separate entry/exit threshold beyond the rank
  cutoff — a name simply rotates out if it leaves its quantile or the PIT
  universe).
- **Sizing:** portfolio-level vol-targeting, reusing the corrected sizing
  path from `backtesting/xs_momentum_backtest.py` (the 2026-06-24 D3 fix that
  made vol-targeting annualized instead of a no-op) rather than re-deriving
  it — this is a **known-correct pattern to reuse, not a new design**.
- **Execution:** perp-only on both legs (no spot leg) — see Distinctness
  below for why this matters mechanically, not just as an implementation
  convenience.
- **Funding accounting (two channels, both R3.1):** (a) the ranking *signal*
  is the trailing funding APR itself; (b) the *position* also generates real
  funding cashflow while held — short the high-funding leg **pays** funding
  out under R3.1's "short receives positive funding" convention only if the
  leg's sign is negative funding, so the actual cashflow direction must be
  computed per R3.1 for each leg each period, not assumed. Do not conflate
  the ranking signal with the realized funding cashflow in the backtest
  code — they use the same underlying series but are two separate
  accounting steps.
- **Leak guard (mandatory, known failure class):** the same look-ahead class
  that `xs_momentum_backtest.py` was fixed for
  (`test_daily_close_target_is_not_traded_on_same_day`) applies here
  structurally, since this is also a daily/weekly-rebalanced cross-sectional
  rank book: the rebalance-day target must be built from funding data known
  strictly before that day's trade, shifted the same way. Reuse the existing
  fixed pattern; do not re-derive the shift logic from scratch.

## Distinctness vs `F-FUNDING-CARRY` (H-007, refuted/shelved)

Mechanism-taxonomy explicitly flags this pair: "⚠ F-FUNDING-CARRY（須證明與
單名 carry 機制不同，否則歸 F-FUNDING-CARRY）". This section makes that case;
per `pipeline_family_minting.py`, a MINT verdict is **always provisional**
pending the quantitative distinctness check below.

| | F-FUNDING-CARRY (H-007, refuted) | F-FUNDING-XS-DISPERSION (this spec) |
|---|---|---|
| Construction | Single-name (BTC/ETH), **spot + perp** delta-neutral basis trade | Perp-only, **cross-sectional** long/short across the full PIT universe |
| Signal | **Absolute** funding APR vs a fixed threshold, single symbol | **Relative** rank of funding APR across ~28+ symbols each rebalance |
| Return source | Harvest one symbol's funding level while hedged | Spread/dispersion in relative funding + relative return premium across many symbols |
| Cost exposure that killed it | Spot financing cost, two-leg spot↔perp rebalance slippage, basis-execution slippage between two different instruments | No spot leg at all — no spot financing, no cross-instrument basis-execution slippage; only inter-perp rebalance turnover |
| Refutation mechanism (E-026) | Realistic re-costing crushed a thin absolute-level edge; realized modeled vol only 0.247% (the hedge was too calm to be real) | Different cost surface entirely (perp-vs-perp only), so E-026's specific refutation mechanism does not mechanically transfer |
| Breadth / statistical power | Effectively 1-2 names, one bet per period | Up to ~28 symbols, dollar-neutral across many names — more independent-ish exposure per period (see `docs/superpowers/specs/2026-07-03-statistical-power-gates.md`: breadth is the lever that makes a given true Sharpe easier to detect at N-trial DSR gates) |

**What this argument is, and is not:** this is a defensible *mechanism-level*
case for MINT, not a proof. The mechanism-taxonomy's own rule requires the
**quantitative** family-minting distinctness check
(`backtesting/pipeline_family_minting.py` — pairwise correlation of the
candidate's realized signal/return series against a `F-FUNDING-CARRY`
reference series) before Stage 3 may proceed under a new family budget. That
check needs an actual constructed candidate signal, which is Stage 2(b)/Stage
3 work (Codex), not something this docs-only Stage 1 spec can compute.
**Hand-off requirement:** run the family-minting checker with the constructed
XS-dispersion signal against the existing `F-FUNDING-CARRY` reference before
or alongside the WF/CPCV grid; if it returns `ASSIGN` or `SKIP_RECOMMENDED`
instead of `MINT`, this family folds into `F-FUNDING-CARRY`'s trial/K budget
per I27, and `H-009`'s ledger row must be corrected accordingly — do not
silently keep a fresh `n_trials=0` budget if the checker disagrees with this
spec's qualitative call.

## Planned grid (pre-registered, deliberately small)

`{lookback_days L ∈ [7, 14], quantile Q ∈ [0.20, 0.30]}` → **4 combos**.
`prior_family_n_trials = 0` → CPCV `n_trials = 4`.

Kept small on purpose: per the 2026-07-03 statistical-power analysis, at
~2.5 years of history a family at `n_trials=4` needs an observed annualized
Sharpe of only ≈1.7 to clear `DSR ≥ 0.95` (vs ≈2.3 at `n_trials=24`) — a much
more achievable bar, and it leaves 20 of the `K_limit=2` retries' worth of
grid room unspent if a genuine second attempt is later warranted. Rebalance
frequency (weekly) and the vol-target level are fixed, not grid dimensions,
to avoid inflating `n_trials` on parameters this family does not need to
search over.

## Validation path

DB CPCV `N=6/k=2/embargo=2%/purge=1`, fold-refit harness (reuse
`backtesting/pipeline_refit.py`, not the superseded full-sample-select-then-
slice harness). Mandatory leak test per the guard above. Retain CPCV
`path_returns` (per I24/T2 convention already standard in this pipeline).

## Stage 2 feasibility findings

- **(a) Data availability: PASS (E-030, 2026-07-04).** Point-in-time universe
  rebuilt from `canonical_candles` (32 eligible symbols across the window,
  up from an 8-symbol artifact caused by a thin local-parquet membership
  mirror — see E-028/E-030 notes). 28/32 symbols meet the funding
  coverage/stale threshold (1.0 coverage, 0 stale); the 4 with zero funding
  rows (`CC`, `FIL`, `M`, `SHIB`-USDT-SWAP) only became PIT-eligible under
  the rebuilt universe and were outside the original funding backfill's
  22-symbol union — they do not block the good-symbol (28 ≥ 10) or breadth
  (min 24, median 27 ≥ 10) thresholds. Funding history for these 4 can be
  backfilled the same way as the other 28 if they matter to a later grid;
  not required for this Stage-1 pass.
- **(b) Distinctness: NOT YET RUN — mechanism argument above supports a
  provisional MINT; quantitative family-minting check against
  `F-FUNDING-CARRY` is a required Stage-2(b)/Stage-3 hand-off step (see
  table above).** Do not treat this spec's table as a substitute for running
  the checker.
- **(c) Cost / overfit: LOW-MEDIUM, unverified.** Perp-only cross-sectional
  rebalancing has real turnover cost (weekly rebalance across up to ~56
  legs at 4 combos), but no spot financing or cross-instrument basis
  slippage. Structural concern to flag for Stage 3: funding-rate
  cross-sectional dispersion is a "crowding" signal that other cross-venue
  arbitrageurs also watch — decay/crowding risk should be assessed the same
  way `F-XS-MOMENTUM` and `F-SENTIMENT` were (both flagged "high crowding/
  decay" in the taxonomy). Small grid (4 combos, 2 free params) keeps
  overfit risk low relative to prior families in this ledger.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-009` (`F-FUNDING-XS-DISPERSION`), status `proposed`
  (unchanged — Stage 3 has not run).
- EXPERIMENT_REGISTRY: `E-030` (Stage-2 re-probe, data-availability PASS,
  recorded); Stage-3 run gets a new experiment id when Codex runs it (not
  pre-assigned here — assign at run time per existing convention).

## Hand-off to Stage 3 (Codex)

1. **Run the family-minting distinctness checker first** (or as an explicit
   pre-flight step before the WF/CPCV grid) against a constructed
   XS-dispersion candidate signal vs. the `F-FUNDING-CARRY` reference. Record
   the verdict in `family_minting.json` and update this spec / `H-009` if it
   disagrees with the provisional MINT call above.
2. Implement as a **research backtest module**, reusing
   `backtesting/xs_momentum_backtest.py` as the implementation skeleton: same
   PIT-universe loader, same corrected annualized vol-targeting, same
   lookahead-safe daily/weekly target-shift pattern, same R3.1 funding-sign
   discipline — only the ranking signal changes (trailing funding APR
   instead of trailing return). Do **not** modify
   `xs_momentum_backtest.py` itself or any live
   `src/okx_quant/strategies/` module; this is a new, separate research
   module.
3. Mandatory leak test (see Leak guard above); `REFERENCE_VALIDATION_CONTRACTS`
   entry; `ct_val` provenance for every leg; no idealized-fill; fold-refit
   harness; retained CPCV `path_returns`; caller-declared family-cumulative
   `n_trials=4`.
4. Funding cashflow accounting must be verified against R3.1 explicitly for
   this construction (see the two-channel note above) — do not assume the
   sign convention from a single-name carry book transfers unexamined to a
   cross-sectional long/short book.
5. Stop at checkpoint ① per the existing contract
   (`docs/superpowers/specs/2026-06-30-checkpoint1-automation-contract.md`);
   no adapter, promotion, demo, shadow, or live work until Claude/user review
   of the Stage-3 evidence.

## Scope / role

This spec is research/design output, Claude-authored, docs-only. Stage-3
implementation, the family-minting checker run, and any backtest are Codex's
responsibility. No gate, ledger verdict, or trading-core file is changed by
this document.
