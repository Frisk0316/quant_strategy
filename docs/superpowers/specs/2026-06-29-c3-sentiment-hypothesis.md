---
status: draft
type: design
owner: claude
created: 2026-06-29
last_reviewed: 2026-06-29
expires: none
superseded_by: null
---

# C3 Fear & Greed Sentiment Long/Flat — Stage 1 Hypothesis (pipeline batch 2)

Strategy Research Pipeline Stage 1 output for batch-2 candidate **C3**. Not a
promotion claim; nothing here is wired into any gate.

- **family_id:** `F-SENTIMENT` (new family; `prior_family_n_trials = 0`)
- **Backlog source:** `research/strategy_synthesis.md` Strategy 9 (Baker & Wurgler
  2006 sentiment-as-mispricing; crypto retail-sentiment studies). Already
  implemented as `FearGreedSentimentStrategy` (`enabled:false`), never validated.

## Hypothesis (falsifiable)

A BTC **long/flat** book that goes long on **Extreme Fear** and holds through
**Fear/Neutral**, exiting only on **Greed/Extreme Greed**, earns a positive
net-of-cost Sharpe that beats BTC buy-and-hold, surviving WF and CPCV with
**DSR ≥ 0.95 and PSR ≥ 0.95**.

## Testable spec

- **Signal:** Alternative.me Crypto Fear & Greed Index (`fear_greed_btc`), daily;
  `value_num` + label.
- **Entry:** long when `value_num ≤ extreme_fear_threshold` (or label `Extreme Fear`).
- **Hold:** through `Fear` and `Neutral` (intentional non-exits — a mean-reversion
  bet that sentiment must rebound).
- **Exit:** flat when `value_num ≥ exit_value_threshold` (`Greed`/`Extreme Greed`).
- **Sizing:** fixed-fractional / vol-target (no sentiment-conditional sizing in v1).
- **Execution:** maker-only BTC-USDT-SWAP, long/flat.
- **Universe:** BTC-USDT-SWAP only (Alternative.me has no per-asset index).
- **Stale/missing:** `max_age_seconds = 172800`; stale or missing observation → no
  signal (already implemented; counters in `validation.external_features`).

## Planned grid (pre-registered)

`{extreme_fear_threshold ∈ [20,25,30], exit_value_threshold ∈ [50,55,60]}` →
**9 combos**. New family → `prior_family_n_trials = 0`; CPCV `n_trials = 9`.

## Validation path

WF/CPCV N=6/k=2/embargo=2%/purge=1, `n_trials = 9`, fold-refit harness. Daily
cadence; `published_at = observed_at` (no publish lag). Leak test: the day-D signal
uses only index values published ≤ D.

## Stage 2 feasibility findings

- **(a) Data availability: GATING — confirm before Stage 3.** `fear_greed_btc` must
  exist in `external_observations` with `event_count > 0` over the test window.
  Subject to the **External-Feature Coverage Gate** (stale-rate ≤ 10%, missing-rate
  ≤ 5%, label-stability + source-stability attestations).
- **(b) Distinctness: PASS (new family).** Behavioral / sentiment mean-reversion is
  mechanistically distinct from momentum, carry, and relative value.
- **(c) Cost / overfit: LOWEST in batch.** Single symbol, daily, 9 combos, already
  implemented, low turnover → low cost. Edge is **"Unknown"** per synthesis — a
  cheap probe. If it passes, the pass is trustworthy; the most likely honest outcome
  is a thin/insignificant edge the gate rejects.

## Caveats to carry (from synthesis, must surface in evidence)

- Label match is case-sensitive; mitigated by config-load allow-list + numeric
  `value_num` fallback. Any promotion ADR must state which path is canonical.
- The hold-through-`Fear`/`Neutral` assumption has never been tested at DSR ≥ 0.95.
- Coverage-gate thresholds must be measured on a full replay run.

## Pre-registration

- HYPOTHESIS_LEDGER: `H-008` (F-SENTIMENT), status `proposed`.
- EXPERIMENT_REGISTRY: `E-019` planned, grid 9.

## Hand-off to Stage 3 (Codex)

Reuse the implemented `FearGreedSentimentStrategy`. **Confirm data availability
first** (Stage-2 gate). Mandatory leak test; ensure a `REFERENCE_VALIDATION_CONTRACTS`
entry exists for `fear_greed_sentiment`; record External-Feature Coverage Gate
fields; ct_val provenance (BTC SWAP); no idealized-fill; fold-refit harness; stop at
checkpoint ①.
