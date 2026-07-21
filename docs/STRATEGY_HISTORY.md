---
status: current
type: reference
owner: human
created: 2026-07-17
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# Strategy History

This document is the human-readable history of the hypotheses registered in
the [Hypothesis Ledger](HYPOTHESIS_LEDGER.md) and their runs in the
[Experiment Registry](EXPERIMENT_REGISTRY.md). Those ledgers remain
authoritative. Strategy wording is expanded from the falsifiable ledger claim
and, where a matching entry exists, from
[`research/strategy_synthesis.md`](../research/strategy_synthesis.md). Metrics
are transcribed from registry notes or the artifact named beside them; missing
metrics are written as `n/a (not recorded)`.

## Research pipeline architecture

The pipeline rejects weak or untestable ideas before expensive validation. The
Stage-2 statistical-power check from [ADR-0013](ADR/0013-stage2-statistical-power-triage.md)
is advisory triage: it may stop work early but cannot turn a later Stage-3
failure into a pass or relax any promotion gate.

```text
idea batch + falsifiable family hypothesis
  -> Stage 2: data availability + distinctness + cost-after-edge
  -> Stage 2: advisory statistical-power triage (honest cumulative n_trials)
  -> Stage 3: full-PnL fold-refit walk-forward + CPCV
  -> DSR >= 0.95 and PSR >= 0.95 + unchanged validation/promotion gates
  -> checkpoint: accept evidence or stop; retries require ex-ante rationale and K
```

Family-cumulative parameter trials feed DSR; the separate retry budget is
`K_limit = 2`. A disappointing run is not permission to tune toward the gate.
See the [Stage-2 template](superpowers/pipeline/stage2-feasibility.md),
[ADR-0013](ADR/0013-stage2-statistical-power-triage.md), and the two ledgers for
the exact contracts.

## H-000 — Funding-carry template (`F-000`)

- **Status:** `proposed` template; not a real strategy record.
- **Ideation source:** `DESIGN_SPACE` supplied an example of how to phrase a
  falsifiable funding-carry claim; it was retained as the ledger template.
- **Strategy logic:** Test whether BTC swap funding carry remains positive after
  fees and funding across a complete settlement window. No entry, exit, sizing,
  or execution contract was registered for this placeholder.
- **Instruments / universe and window:** Example `BTC-SWAP`, `1H`; real data
  window `n/a (not recorded)`.
- **Recorded results:** WF `n/a (not recorded)`; CPCV `n/a (not recorded)`; DSR
  `n/a (not recorded)`; PSR `n/a (not recorded)`; annualized return
  `n/a (not recorded)`; benchmark `n/a (not recorded)`.
- **Iteration chain:**
  - `E-000` (2026-06-12) — placeholder setup and artifact only; it explicitly
    says to replace the row and is not evidence.
- **Outcome / lesson:** Preserve templates as non-evidence; do not mistake them
  for a tested funding-carry family.
- **Trace:** Hypothesis Ledger `H-000`; Experiment Registry `E-000`.

## H-001 — Cross-venue `ct_val` convergence (`F-001`)

- **Status:** `supported` system-behavior hypothesis; not alpha evidence.
- **Ideation source:** ADR-0007's multi-venue instrument-spec decision motivated
  a golden test that isolates contract multiplier differences under identical
  notional sizing.
- **Strategy logic:** Run the same MA-crossover parameters on two fixed venue
  specifications. If notional sizing correctly cancels `ct_val`, PnL metrics
  should differ only by venue lot rounding.
- **Instruments / universe and window:** Synthetic `BTC-USDT-SWAP` `1H` parquet
  fixture under OKX `ctVal=0.01` and Binance `ctVal=1.0`; calendar window
  `n/a (not recorded)`.
- **Recorded results:** `total_return` and Sharpe matched within `1e-6`; WF
  `n/a (not recorded)`; CPCV `n/a (not recorded)`; DSR `n/a (not recorded)`;
  PSR `n/a (not recorded)`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`.
- **Iteration chain:**
  - `E-001` (2026-06-17) — one deterministic golden test established the
    convergence invariant without DB or network input.
- **Outcome / lesson:** The multiplier cancellation is supported for this
  fixture, but a unit golden case does not establish deployability.
- **Trace:** Hypothesis Ledger `H-001`; Experiment Registry `E-001`;
  `tests/unit/test_multi_venue_convergence.py::test_swap_ct_val_cancels_under_notional_sizing`.

## H-002 — Cross-sectional momentum (`F-XS-MOMENTUM`)

- **Status:** `refuted / shelved`.
- **Ideation source:** Strategy 11 in `research/strategy_synthesis.md` combined
  the crypto momentum literature with a 2026-06-23 point-in-time-universe
  design for a survivorship-controlled, market-neutral book.
- **Strategy logic:** Rank a point-in-time liquid USDT-perp universe by
  volatility-normalized trailing return; hold equal-gross long winners and
  short losers with a one-day signal lag, weekly rebalance, portfolio-vol
  targeting, and crash controls.
- **Instruments / universe and window:** 27 non-stable Binance USDT perps,
  canonical `1m` aggregated to `1H`, 2024-01-01 through
  2026-06-16T16:00Z; point-in-time membership and Binance funding.
- **Recorded results:** Latest valid `E-005`: WF `1.2412`, CPCV `0.6027`, DSR
  `0.7823`, PSR `0.8234`; combined WF OOS annualized return
  `0.13660270880170589`; equal-weight universe/BTC benchmark
  `n/a (not recorded)`. Artifacts:
  `results/xs_momentum_validation_20260624_portfoliovol/summary.json` and
  `results/xs_momentum_validation_20260624_portfoliovol/walk_forward.json::combined_oos_perf.annualized_return`.
- **Iteration chain:**
  - `E-002` (2026-06-23) — registered the planned grid and OOS path before a
    run existed.
  - `E-003` (2026-06-23) — first run looked strong but was invalidated by a
    daily-target lookahead leak and broken DSR evidence.
  - `E-004` (2026-06-24) — shifted targets one full day; PSR fell below the
    gate and the stored DSR remained untrusted.
  - `E-005` (2026-06-24) — fixed DSR basis and portfolio-vol sizing; both
    anti-overfit probabilities still failed, taking the family to 24 trials.
- **Outcome / lesson:** Correcting leakage and sizing removed the apparent edge.
  The family is a disabled research baseline at its retry limit; no gate-chasing
  tuning.
- **Trace:** Hypothesis Ledger `H-002`; Experiment Registry `E-002`–`E-005`.

## H-003 — Perp/spot basis mean reversion (`F-S7-BASIS-MEANREV`)

- **Status:** `shelved`.
- **Ideation source:** Strategy 7 in `research/strategy_synthesis.md` and the
  2026-06-25 S7 spec turned basis convergence plus funding carry into the first
  batch's highest-priority mean-reversion candidate.
- **Strategy logic:** Form delta-neutral BTC/ETH spot-versus-perp spreads; enter
  at extreme basis z-scores only when the estimated OU half-life is finite, then
  exit on convergence, a funding flip, or the holding limit.
- **Instruments / universe and window:** Binance BTC/ETH spot and USDT perps,
  canonical `1m` plus funding, 2024-01-01 through 2026-06-16 23:59Z.
- **Recorded results:** Latest valid `E-016`: WF `-0.4359`, CPCV `-1.1124`, DSR
  approximately `0`, PSR approximately `0`; annualized return
  `n/a (not recorded)`; static funding-carry benchmark `n/a (not recorded)`.
  Artifact: `results/pipeline_batch1_20260625/s7/summary.json`.
- **Iteration chain:**
  - `E-006` (2026-06-25) — pre-registered the 72-cell S7 grid with spot data
    still gated.
  - `E-011` (2026-06-25) — spot coverage passed, but missing ETH perp data
    blocked validation.
  - `E-013` (2026-06-25) — repaired data produced an all-zero, no-trade result
    under a degenerate half-life grid.
  - `E-016` (2026-06-25) — replaced only that grid with finite 7/14-day
    half-lives and fold refitting; activity returned but performance was negative.
- **Outcome / lesson:** The non-degenerate implementation failed rather than the
  earlier no-trade artifact; the family is shelved.
- **Trace:** Hypothesis Ledger `H-003`; Experiment Registry `E-006`, `E-011`,
  `E-013`, `E-016`.

## H-004 — Factor-residual mean reversion (`F-S5-RESIDUAL-MEANREV`)

- **Status:** `inconclusive`.
- **Ideation source:** Strategy 5 in `research/strategy_synthesis.md` and the S5
  spec adapted equity statistical-arbitrage ideas to residuals after removing
  common BTC/ETH crypto beta.
- **Strategy logic:** Estimate common BTC/ETH factors across a liquid perp
  universe, trade residual z-score mean reversion with market-neutral sizing,
  and suppress trades whose expected edge does not clear costs.
- **Instruments / universe and window:** Latest run used 19 complete-window
  Binance USDT perps including ETH plus point-in-time membership; exact start
  and end are `n/a (not recorded)` in `E-014` Setup.
- **Recorded results:** `E-014`: WF `0.0`, CPCV `0.0`, DSR `0.0`, PSR `0.0`,
  with `nonzero_grid_activity:false`; annualized return `n/a (not recorded)`;
  equal-weight-universe benchmark `n/a (not recorded)`. Artifact:
  `results/pipeline_batch1_20260625_refit/s5/summary.json`.
- **Iteration chain:**
  - `E-007` (2026-06-25) — planned a 72-cell residual grid and marked family
    distinctness conditional on true reversion behavior.
  - `E-009` (2026-06-25) — first checkpoint lacked ETH and degraded the factor
    model to BTC-only, so its metrics were non-passing evidence.
  - `E-014` (2026-06-25) — restored ETH and fold-local refitting, but the
    membership/coverage intersection emitted no trades.
- **Outcome / lesson:** Zero returns came from a data-universe interaction, not
  a clean strategy test; retain the `inconclusive` label.
- **Trace:** Hypothesis Ledger `H-004`; Experiment Registry `E-007`, `E-009`,
  `E-014`.

## H-005 — Slow time-series momentum (`F-S6-TS-MOMENTUM`)

- **Status:** `inconclusive`.
- **Ideation source:** Strategy 6 in `research/strategy_synthesis.md` and the S6
  spec translated the trend-following literature into a low-turnover BTC/ETH
  perp sleeve with volatility and crash controls.
- **Strategy logic:** Trade each asset from its own slow trend, target portfolio
  volatility, reduce exposure in momentum-crash regimes, and rebalance on a
  fixed daily/weekly/monthly schedule after costs.
- **Instruments / universe and window:** Binance BTC/ETH USDT perps with
  canonical `1m` and funding, 2024-01-01 through 2026-06-16 23:59Z.
- **Recorded results:** Valid fold-refit `E-015`: WF `0.0088`, CPCV `0.5422`,
  DSR `0.1963`, PSR `0.7387`; annualized return `n/a (not recorded)`; BTC
  buy-and-hold benchmark `n/a (not recorded)`. Artifact:
  `results/pipeline_batch1_20260625_refit/s6/summary.json`.
- **Iteration chain:**
  - `E-008` (2026-06-25) — planned the 48-cell BTC/ETH trend grid.
  - `E-010` (2026-06-25) — blocked rather than substituting for missing ETH
    perp history.
  - `E-012` (2026-06-25) — repaired data appeared to pass, but the validation
    callback did not refit parameters inside folds.
  - `E-015` (2026-06-25) — added fold-local selection; the apparent pass
    disappeared and path results became dispersed.
- **Outcome / lesson:** Non-refitting validation overstated the strategy. The
  honest fold-refit evidence fails the statistical gate.
- **Trace:** Hypothesis Ledger `H-005`; Experiment Registry `E-008`, `E-010`,
  `E-012`, `E-015`.

## H-006 — OU-gated BTC/ETH pairs (`F-PAIRS-OU`)

- **Status:** `refuted`.
- **Ideation source:** Strategy 4 in `research/strategy_synthesis.md` and the C1
  spec formalized the existing `pairs_trading` mechanism rather than relabeling
  it as a new family.
- **Strategy logic:** Estimate the BTC/ETH hedge ratio and OU half-life, open a
  dollar-neutral relative-value position only at spread z-score extremes, and
  exit on convergence, a half-life break, or maximum holding time.
- **Instruments / universe and window:** Binance BTC/ETH USDT perps, canonical
  `1m`-derived daily closes and funding, 2024-01-01 through
  2026-06-16 23:59Z.
- **Recorded results:** `E-025`: WF `-1.2584`, CPCV `-0.9097`, DSR `0.0079`,
  PSR `0.0994`; annualized return `n/a (not recorded)`; BTC buy-and-hold and
  static 50/50 benchmarks `n/a (not recorded)`. Artifact:
  `results/pipeline_batch2_20260625/c1_pairs_ou/summary.json`.
- **Iteration chain:**
  - `E-017` (2026-06-25) — pre-registered the 24-cell OU grid.
  - `E-022` (2026-06-29) — failed closed when the DB probe could not run.
  - `E-025` (2026-06-29) — ran the complete venue-scoped fold-refit setup and
    retained CPCV paths; all four headline statistics failed.
- **Outcome / lesson:** This was the first proper validation of the existing
  pair mechanism, and the evidence refuted it on the tested window.
- **Trace:** Hypothesis Ledger `H-006`; Experiment Registry `E-017`, `E-022`,
  `E-025`.

## H-007 — Filtered funding carry (`F-FUNDING-CARRY`)

- **Status:** `refuted / shelved`.
- **Ideation source:** Strategy 3 in `research/strategy_synthesis.md`, the C2
  spec, and the realism follow-up combined funding carry with basis and crowding
  filters while preserving the existing economic family.
- **Strategy logic:** Hold long spot/short perp only when trailing funding APR
  clears a threshold and basis is not in a blowout regime; keep the book
  delta-neutral and charge both-leg turnover, basis execution, and carry drag.
- **Instruments / universe and window:** Binance BTC/ETH spot, USDT perps, and
  funding, 2024-01-01 through 2026-06-16 23:59Z.
- **Recorded results:** Realism re-cost `E-026`: WF `-1.5093`, CPCV `-0.2349`,
  DSR `0.0041`, PSR `0.4457`; annualized return `n/a (not recorded)`;
  buy-and-hold benchmark `n/a (not recorded)`. Artifact:
  `results/pipeline_batch2_20260625/c2_funding_carry_realism/summary.json`.
- **Iteration chain:**
  - `E-018` (2026-06-25) — registered the 24-cell filtered-carry grid.
  - `E-021` (2026-06-29) — DB probe was unavailable, so Stage 2 failed closed.
  - `E-024` (2026-06-29) — idealized two-leg checkpoint printed very high
    Sharpe but was flagged as an implausibly calm hedge artifact.
  - `E-026` (2026-06-29) — added fixed carry drag and realistic two-leg/basis
    costs; the family failed and cumulative trials rose to 48.
- **Outcome / lesson:** The apparent pass was model realism, not robust edge.
  Re-costing reversed it, so adapter and promotion work remain shelved.
- **Trace:** Hypothesis Ledger `H-007`; Experiment Registry `E-018`, `E-021`,
  `E-024`, `E-026`.

## H-008 — Fear & Greed long/flat (`F-SENTIMENT`)

- **Status:** `refuted`.
- **Ideation source:** Strategy 9 in `research/strategy_synthesis.md` and the C3
  spec framed Alternative.me sentiment as a behavioral research baseline, not
  a validated live signal.
- **Strategy logic:** Enter BTC long on Extreme Fear, hold through Fear and
  Neutral, and exit only on Greed/Extreme Greed; use point-in-time external
  observations and refuse stale or missing features.
- **Instruments / universe and window:** Binance `BTC-USDT-SWAP`, canonical
  `1m`, funding, and `fear_greed_btc`, 2024-01-01 through 2026-06-17.
- **Recorded results:** `E-027`: WF `-0.2556`, CPCV `0.1315`, DSR `0.4532`, PSR
  `0.5806`; annualized return `n/a (not recorded)`; BTC buy-and-hold benchmark
  `n/a (not recorded)`. Artifact:
  `results/pipeline_batch2_20260625/c3_sentiment/summary.json`.
- **Iteration chain:**
  - `E-019` (2026-06-25) — planned the nine-cell sentiment thresholds.
  - `E-020` (2026-06-29) — failed closed because the DB probe could not run.
  - `E-023` (2026-06-29) — DB became reachable but the required dataset was
    absent.
  - `E-027` (2026-06-29) — after ingestion, coverage passed and Stage 3 ran;
    nonzero activity still failed every statistical threshold.
- **Outcome / lesson:** Data availability was fixed without changing the thesis;
  the completed experiment refuted the daily sentiment rule.
- **Trace:** Hypothesis Ledger `H-008`; Experiment Registry `E-019`, `E-020`,
  `E-023`, `E-027`.

## H-009 — Cross-sectional funding dispersion (`F-FUNDING-XS-DISPERSION`)

- **Status:** `testing`.
- **Ideation source:** The taxonomy_002 idea batch and mechanism taxonomy
  proposed cross-sectional funding-level dispersion; the later family spec
  distinguished it from time-series funding carry.
- **Strategy logic:** Each week rank a point-in-time liquid USDT-perp universe by
  trailing funding APR, buy the lowest-funding quartile, short the
  highest-funding quartile, and keep the book dollar neutral after costs.
- **Instruments / universe and window:** 28 Stage-2-good Binance USDT perps from
  the DB-rebuilt point-in-time universe, canonical `1m` and funding,
  2024-01-01 through 2026-06-17.
- **Recorded results:** `E-031`: WF `1.1812`, CPCV `0.9553`, DSR `0.9346`, PSR
  `0.9346`; annualized return `n/a (not recorded)`; equal-weight-universe
  benchmark `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/summary.json`.
- **Iteration chain:**
  - `E-028` (2026-07-01) — failed data breadth because the universe artifact
    came from a thin parquet mirror.
  - `E-030` (2026-07-04) — rebuilt membership from canonical DB data; data
    availability passed without changing thresholds.
  - `E-031` (2026-07-03) — minted the distinct family and ran the four-cell
    grid; the result narrowly missed both `0.95` probabilities.
- **Outcome / lesson:** This is a marginal statistical miss, not a pass or a
  refutation. Keep it `testing`; any retry needs a new ex-ante rationale and K.
- **Ordering note:** The registry dates `E-031` one day before `E-030`; the
  iteration list follows the ledger's recorded `E-028` → `E-030` → `E-031`
  chain rather than inventing a corrected chronology.
- **Trace:** Hypothesis Ledger `H-009`; Experiment Registry `E-028`, `E-030`,
  `E-031`.

## H-010 — Binance/OKX lead-lag prerequisite (`F-XVENUE-LEADLAG`)

- **Status:** `proposed` and data-blocked.
- **Ideation source:** The taxonomy_002 idea batch and mechanism taxonomy raised
  cross-venue lead/lag, while invariant I19 made simultaneous venue-scoped
  candles a prerequisite rather than allowing a proxy substitution.
- **Strategy logic:** No directional rule is authorized yet. First prove that
  aligned Binance and OKX `1m` candles exist for both BTC and ETH over the same
  window with source identity preserved.
- **Instruments / universe and window:** Binance and OKX `BTC-USDT-SWAP` and
  `ETH-USDT-SWAP`, canonical `1m`, 2024-01-01 through 2026-06-16.
- **Recorded results:** WF `n/a (not recorded)`; CPCV `n/a (not recorded)`; DSR
  `n/a (not recorded)`; PSR `n/a (not recorded)`; annualized return
  `n/a (not recorded)`; benchmark `n/a (not recorded)`. Both probes saw zero
  aligned OKX canonical rows.
- **Iteration chain:**
  - `E-029` (2026-07-01) — first Stage-2 probe found complete Binance but zero
    OKX canonical coverage.
  - `E-035` (2026-07-04) — repeated the same read-only check; the gap remained
    and the attempted network ingest could not run.
- **Outcome / lesson:** Do not write a Stage-1 trading spec until the canonical
  identity/consumer boundary can represent both venues; Binance substitution is
  forbidden.
- **Trace:** Hypothesis Ledger `H-010`; Experiment Registry `E-029`, `E-035`.

## H-011 — Turtle sweep reference parity (`F-TURTLE-REFERENCE-PARITY`)

- **Status:** `supported` research-runner parity; not alpha evidence.
- **Ideation source:** The Turtle follow-up task and the verbatim legacy
  `trading_target_func.py` established a deterministic port-parity requirement.
- **Strategy logic:** Run the repository Turtle sweep aggregation and the
  verbatim reference over identical daily OHLC and parameter cells; compare
  every emitted metric rather than evaluating trading edge.
- **Instruments / universe and window:** 898 daily Binance
  `BTC-USDT-SWAP` fixture bars, 2024-01-01 through 2026-06-16.
- **Recorded results:** 270 parameter combinations and all 27 sweep columns
  matched at `1e-9`; WF `n/a (not recorded)`; CPCV `n/a (not recorded)`; DSR
  `n/a (not recorded)`; PSR `n/a (not recorded)`; annualized return
  `n/a (not recorded)`; benchmark `n/a (not recorded)`.
- **Iteration chain:**
  - `E-032` (2026-07-04) — Tier A passed, while a longer DB-synthesized input
    failed the user-CSV fingerprint because the date range differed.
  - `E-033` (2026-07-04) — reran Tier B on the exact repo fixture; both the
    verbatim reference and the port reproduced all cells and superseded the
    data-mismatch interpretation.
- **Outcome / lesson:** The metric port is faithful on identical data. This says
  nothing about strategy profitability or promotion.
- **Trace:** Hypothesis Ledger `H-011`; Experiment Registry `E-032`, `E-033`.

## H-012 — Open-interest positioning fade (`F-OI-POSITIONING`)

- **Status:** `shelved`.
- **Ideation source:** The taxonomy_002 idea batch, mechanism taxonomy, staged
  OI data probes, and the final OI hypothesis spec proposed a price-reversal
  signal conditioned on falling contract-count open interest.
- **Strategy logic:** Across the OI-good point-in-time universe, fade recent
  price moves only when contract-count OI is falling; lag positions and funding
  to the next day and rebalance daily after costs.
- **Instruments / universe and window:** 31 OI-good Binance USDT perps,
  canonical `1m`, funding, and Binance Vision 5-minute contract-count OI,
  2024-01-01 through 2026-06-17.
- **Recorded results:** `E-037`: WF `0.6034`, CPCV `0.7240`, DSR `0.7220`, PSR
  `0.8484`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260701_taxonomy_002/f_oi_positioning/summary.json`.
- **Iteration chain:**
  - `E-034` (2026-07-04) — BTC/ETH OI coverage passed a narrow Stage-2 probe.
  - `E-036` (2026-07-05) — expanded history to the PIT universe and passed
    breadth with 31 usable symbols.
  - `E-037` (2026-07-07) — minted the mechanism and ran the four-cell fold-refit
    grid; statistical evidence failed, and later hygiene found turnover cost on
    signal day rather than the position day.
- **Outcome / lesson:** The signal was weak even before resolving the cost-lag
  defect. The user shelved it with no retry; the immutable artifact is not
  promotion evidence.
- **Trace:** Hypothesis Ledger `H-012`; Experiment Registry `E-034`, `E-036`,
  `E-037`.

## H-013 — Perp volatility-risk-premium timing (`F-VRP-TIMING`)

- **Status:** `shelved`.
- **Ideation source:** C1 in `research/deribit_data_strategy_research.md` and the
  H-013 spec adapted the volatility-risk-premium return relation into a
  daily BTC/ETH perp timing rule.
- **Strategy logic:** Compute hourly Deribit DVOL minus trailing realized
  volatility from canonical candles, standardize it over 90 days, and hold
  BTC/ETH perps long only in high-VRP states with t+1 execution and vol targeting.
- **Instruments / universe and window:** Binance BTC/ETH USDT perps plus hourly
  Deribit DVOL, 2024-01-01 through 2026-07-10.
- **Recorded results:** `E-050`: WF `0.0543`, CPCV `0.5588`, DSR `0.5999`, PSR
  `0.7845`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`. Artifact: `results/h013_vrp_timing_20260714/summary.json`.
- **Iteration chain:**
  - `E-038` (2026-07-14) — Stage-2 coverage and frozen-feed checks passed.
  - `E-050` (2026-07-14) — the frozen four-cell Stage-3 grid minted as distinct
    but had flat WF and weak-positive CPCV, below both probability gates.
- **Outcome / lesson:** The traditional VRP relation did not translate into a
  robust daily crypto-major timing edge on this window; no gate-chasing retry.
- **Trace:** Hypothesis Ledger `H-013`; Experiment Registry `E-038`, `E-050`.

## H-014 — Deribit options volatility-regime overlay (`F-VOL-REGIME-OPT`)

- **Status:** `supported` for the RICH short-premium branch only, still
  promotion-blocked; the original two-sided hypothesis is only partially
  supported.
- **Ideation source:** A 2026-07-13 user strategy request and the H-014 spec
  defined a new options-premium family, distinct from perp VRP timing despite a
  shared volatility state variable.
- **Strategy logic:** In RICH regimes, sell 30-day approximately 25-delta
  covered calls plus a bounded put spread in 1/30-unit tranches; the proposed
  CHEAP-regime long-straddle leg remained off after its probe failed. Use
  coin-denominated inverse-option accounting and t+1 entries.
- **Instruments / universe and window:** Deribit BTC/ETH inverse options with
  BTC/ETH volatility state; latest extension 2020-05-11 through 2026-02-27.
- **Recorded results:** `E-051`: WF `1.3049`, CPCV `1.1326`, DSR `0.9845`, PSR
  `0.9845`. Latest `E-052`: WF `0.8818`, CPCV `1.0098`, DSR `0.9746`, PSR
  `0.9904`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`. Artifacts: `results/h014_stage3_20260714/summary.json`
  and `results/h014_e052_20260714/summary.json`.
- **Iteration chain:**
  - `E-039` (2026-07-13) — synthetic Stage-1 pricing separated RICH short
    premium from normal states and rejected the CHEAP long-vol leg.
  - `E-040` (2026-07-13) — real-chain calibration failed closed at the fixed
    compressed-data ceiling before the sample completed.
  - `E-041` (2026-07-13) — moved the guard to bytes read and required hourly
    DVOL as-of the snapshot; missing pre-2024 DVOL failed closed before download.
  - `E-043` (2026-07-14) — after authorized DVOL backfill, all 12 calibration
    pairs completed and real/synthetic premium ratios passed the fixed bar.
  - `E-051` (2026-07-14) — first full-PnL Stage-3 run passed statistically, but
    identical fold selections made its DSR penalty degenerate.
  - `E-052` (2026-07-14) — extended the history across more stress regimes;
    varied fold selections produced a real multiple-testing penalty and still
    passed, consuming one K retry.
- **Outcome / lesson:** The RICH short-premium branch is supported; the CHEAP
  long-straddle branch is not. Neither conclusion makes the family live-ready.
  ADR-0011's manual shadow duration and bias report remain the next gate,
  followed by explicit review and approval.
- **Trace:** Hypothesis Ledger `H-014`; Experiment Registry `E-039`–`E-041`,
  `E-043`, `E-051`, `E-052`.

## H-015 — Options-flow positioning (`F-OPTFLOW-POSITIONING`)

- **Status:** `refuted`.
- **Ideation source:** The top taxonomy_003 idea, Deribit research C2, and the
  H-015 spec proposed hourly put/call taker-premium imbalance as a daily risk-off
  positioning signal.
- **Strategy logic:** Average the Deribit put/call taker-buy premium imbalance,
  standardize it against its 90-day history, hold BTC/ETH perps flat at high
  put-flow extremes, and otherwise stay long with t+1 execution.
- **Instruments / universe and window:** Binance BTC/ETH USDT perps plus Deribit
  BTC/ETH hourly option flow, 2024-01-01 through 2026-07-09.
- **Recorded results:** `E-044`: WF `-1.1177`, CPCV `-0.3314`, DSR `0.2176`, PSR
  `0.3044`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260713_taxonomy_003/f_optflow_positioning/summary.json`.
- **Iteration chain:**
  - `E-042` (2026-07-13) — data availability passed, leaving distinctness and
    cost checks for the signed-off run.
  - `E-044` (2026-07-14) — minted the family and ran the frozen four-cell grid;
    the ex-ante direction produced negative WF/CPCV evidence.
- **Outcome / lesson:** Daily put-flow extremes did not carry a tradable risk-off
  signal on the tested window; no retry.
- **Trace:** Hypothesis Ledger `H-015`; Experiment Registry `E-042`, `E-044`.

## H-016 — Cross-sectional illiquidity premium (`F-XS-ILLIQUIDITY`)

- **Status:** `shelved`.
- **Ideation source:** Taxonomy_003's second-ranked candidate and its shared
  Stage-3 spec applied the Amihud illiquidity premium to a point-in-time perp
  universe.
- **Strategy logic:** Rebalance weekly, buying the most Amihud-illiquid eligible
  names and shorting the most liquid names in an equal-gross dollar-neutral
  book, with lagged volatility targeting and per-name caps.
- **Instruments / universe and window:** 34 canonical Binance USDT perps with
  point-in-time membership; same protocol window as `E-044`, 2024-01-01 through
  2026-07-09.
- **Recorded results:** `E-045`: WF `0.9662`, CPCV `0.5398`, DSR `0.7042`, PSR
  `0.7981`; annualized return `n/a (not recorded)`; equal-weight benchmark
  `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260713_taxonomy_003/f_xs_illiquidity/summary.json`.
- **Iteration chain:**
  - `E-045` (2026-07-14) — first frozen four-cell fold-refit run minted as
    distinct and was the batch's best, but remained clearly below the gate.
- **Outcome / lesson:** A positive WF sign was insufficient. Revisit only with
  materially longer history or a pre-run refinement that consumes K.
- **Trace:** Hypothesis Ledger `H-016`; Experiment Registry `E-045`.

## H-017 — Stablecoin-supply liquidity (`F-STABLECOIN-LIQUIDITY`)

- **Status:** `inconclusive`.
- **Ideation source:** Taxonomy_003's third candidate and the shared Stage-3
  specification treated aggregate stablecoin-supply growth as a crypto-liquidity
  state variable.
- **Strategy logic:** Compute lagged aggregate stablecoin-supply growth,
  standardize it over 365 days, and hold BTC/ETH perps long only when growth is
  sufficiently strong; otherwise remain flat.
- **Instruments / universe and window:** Binance BTC/ETH USDT perps plus
  DefiLlama aggregate stablecoin supply; 2024-01-01 through 2026-07-09.
- **Recorded results:** `E-046`: WF `-0.9056`, CPCV `0.3884`, DSR `0.6892`, PSR
  `0.7307`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260713_taxonomy_003/f_stablecoin_liquidity/summary.json`.
- **Iteration chain:**
  - `E-046` (2026-07-14) — first four-cell run minted as distinct but produced
    mixed-sign OOS metrics over essentially one supply regime.
- **Outcome / lesson:** One liquidity regime cannot fairly settle the thesis;
  retain `inconclusive`, and require longer history before any K-consuming test.
- **Trace:** Hypothesis Ledger `H-017`; Experiment Registry `E-046`.

## H-018 — Coinbase premium continuation (`F-COINBASE-PREMIUM`)

- **Status:** `refuted`.
- **Ideation source:** Taxonomy_003's fourth candidate and the shared Stage-3
  spec proposed Coinbase-versus-Binance premium as a US-demand proxy.
- **Strategy logic:** Measure the lagged daily Coinbase/Binance premium,
  standardize it over 90 days, and hold BTC/ETH perps long when the premium is
  positive enough; the continuation direction was fixed before evaluation.
- **Instruments / universe and window:** Binance BTC/ETH USDT perps plus the
  Coinbase/Binance daily premium feature, 2024-01-01 through 2026-07-09.
- **Recorded results:** `E-047`: WF `-0.2606`, CPCV `-0.1933`, DSR `0.3794`, PSR
  `0.3794`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260713_taxonomy_003/f_coinbase_premium/summary.json`.
- **Iteration chain:**
  - `E-047` (2026-07-14) — first frozen four-cell run minted as distinct and
    directly refuted the positive-premium continuation direction.
- **Outcome / lesson:** The daily continuation rule failed; any future
  cross-venue variant must remain separate from the still-blocked H-010 family.
- **Trace:** Hypothesis Ledger `H-018`; Experiment Registry `E-047`.

## H-019 — Hash-ribbon on-chain flow (`F-ONCHAIN-FLOW`)

- **Status:** `shelved`.
- **Ideation source:** Taxonomy_003's fifth candidate and its Stage-3 spec
  translated the hash-ribbon miner-capitulation heuristic into a falsifiable
  BTC-only rule.
- **Strategy logic:** Lag daily hashrate, go flat when the fast SMA falls below
  the slow SMA, and otherwise hold BTC long; compare only pre-registered fast
  and slow windows under the shared cost/validation protocol.
- **Instruments / universe and window:** Binance `BTC-USDT-SWAP` plus
  blockchain.info daily hashrate, 2024-01-01 through 2026-07-09.
- **Recorded results:** `E-048`: WF `-0.2158`, CPCV `0.6670`, DSR `0.7971`, PSR
  `0.8524`; annualized return `n/a (not recorded)`; benchmark
  `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260713_taxonomy_003/f_onchain_flow/summary.json`.
- **Iteration chain:**
  - `E-048` (2026-07-14) — first four-cell run minted as distinct but failed,
    with the pre-registered breadth-one power caveat realized.
- **Outcome / lesson:** Keep it only as a research baseline; a single-asset book
  did not provide enough robust evidence.
- **Trace:** Hypothesis Ledger `H-019`; Experiment Registry `E-048`.

## H-020 — Weekday/weekend seasonality (`F-CALENDAR-SEASONALITY`)

- **Status:** `refuted`.
- **Ideation source:** Taxonomy_003's sixth candidate and the shared Stage-3 spec
  reduced calendar seasonality to exactly two frozen exposure cells.
- **Strategy logic:** Compare holding BTC/ETH perps only on weekdays with holding
  them only on weekends, using the same lagged leverage, funding, and cost
  treatment; no calendar feature is estimated from returns.
- **Instruments / universe and window:** Binance BTC/ETH USDT perps,
  2024-01-01 through 2026-07-09.
- **Recorded results:** `E-049`: WF `-2.0903`, CPCV `-0.3386`, DSR `0.2292`, PSR
  `0.3507`; annualized return `n/a (not recorded)`; buy-and-hold benchmark
  `n/a (not recorded)`. Artifact:
  `results/idea_batch_20260713_taxonomy_003/f_calendar_seasonality/summary.json`.
- **Iteration chain:**
  - `E-049` (2026-07-14) — the only registered run evaluated both frozen cells;
    neither produced positive net-of-cost OOS evidence.
- **Outcome / lesson:** Both calendar variants are refuted; there is no unused
  cell to retry after seeing the result.
- **Trace:** Hypothesis Ledger `H-020`; Experiment Registry `E-049`.

## H-021 — Cross-venue funding spread (`F-XVENUE-FUNDING-SPREAD`)

- **Status:** `refuted`.
- **Ideation source:** C4 in `research/deribit_data_strategy_research.md`, the
  H-021 spec, and taxonomy_004 proposed cross-venue funding capture after the
  neighboring VRP/option-flow candidates had closed.
- **Strategy logic:** For each BTC/ETH pair, forecast lagged Deribit-versus-
  Binance funding, hold equal-USD delta long on the lower-funding venue and
  short on the higher-funding venue, and charge full two-leg turnover plus exact
  inverse-perpetual coin PnL.
- **Instruments / universe and window:** Deribit `BTC-PERPETUAL` /
  `ETH-PERPETUAL` paired with Binance BTC/ETH USDT perps,
  `2024-01-02 <= t < 2026-07-03`.
- **Recorded results:** Full-PnL `E-056`: WF `-0.2158`, CPCV `-0.0375`, DSR
  `0.2357`, PSR `0.4818`; annualized return `n/a (not recorded)`; funding-carry
  and funding-dispersion benchmarks `n/a (not recorded)`. Artifact:
  `results/h021_stage3_20260715/summary.json`.
- **Iteration chain:**
  - `E-053` (2026-07-15) — first four-cell funding proxy was invalid because
    exact timestamp equality dropped jittered settlements; inspected cells still
    counted as trials.
  - `E-054` (2026-07-15) — bounded timestamp canonicalization restored funding
    alignment, but missing Deribit prices and conservative costs failed Stage 2.
  - `E-055` (2026-07-15) — Deribit perpetual backfill fixed price availability;
    the unchanged funding-only robust-cost check still failed.
  - `E-056` (2026-07-15) — separately authorized full-PnL Stage 3 added basis
    and inverse accounting without retuning; statistical and stress gates failed.
- **Outcome / lesson:** Better data and the full economic PnL model did not
  rescue the frozen thesis. Stop with no retry, retune, or deployment claim.
- **Trace:** Hypothesis Ledger `H-021`; Experiment Registry `E-053`–`E-056`.

## Known gaps

Benchmark-versus-buy-and-hold (or another family-specific benchmark) and
annualized return are not systematically recorded in the current ledgers or
Stage-3 summaries. They are therefore `n/a (not recorded)` above rather than
being inferred from Sharpe, total return, or date ranges. Adding those fields to
the experiment/artifact contract is a future, separately approved change.

Source-record caveats also remain: `H-009` has a registry-date/ledger-order
conflict; several old experiment rows reuse an artifact path now containing a
later run; and historical trial columns are not consistently per-run versus
family-cumulative. This document therefore preserves registry notes and
declared values without recomputing chronology or trial totals. Strategy
synthesis text supplies design logic, while current status always comes from
the two ledgers.
