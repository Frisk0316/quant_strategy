---
status: current
type: research
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# Candidate admission packets — S-001 multi-week reversal, S-002 jump-variance XS

Second use of the Candidate Admission Form
(`tasks/2026-08-05-candidate-input-quality-review.md`), on the two
admission-worthy survivors of the 2026-08-07 four-axis literature sweep
(`tasks/2026-08-07-literature-sweep-candidate-shortlist.md`).

## Result summary

| # | Candidate | A1 | A2 | B1 | B2 | B3 | C1 | C2 | D | E | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S-001 | Multi-week XS reversal (8–10wk) | PASS | PASS | PASS | PASS | **PASS 10.6** | PASS (=1) | PASS | PASS with limit | **RULING NEEDED** | **ADMISSIBLE pending family ruling** |
| S-002 | Positive-jump-variance XS short | — | — | — | — | — | — | — | — | **BLOCKED** | **CLOSED at E** |

## S-002 — CLOSED at selection accounting, before any other gate

The sweep resurfaced "Variance Decomposition and Cryptocurrency Return
Prediction" (Lee & Wang, JFQA 2025) as a new candidate. It is not new:

- **H-034/E-075 (2026-07-29) already consumed this exact paper and
  construction**: frozen 7d/quintile positive-jump-variance, weekly
  low-minus-high XS on the 31-symbol PIT universe. Outcome: data PASS
  (24,745/24,745 member-days), decisive distinctness FAIL (abs corr
  0.494810 vs E-062/F-XS-IDIOVOL over 898 days, gate 0.30), cost FAIL and
  power FAIL at annualized net Sharpe **−0.971150**. Terminal artifact
  `results/slate_stage2_20260729/f_variance_decomp/stage2_feasibility.json`
  (SHA-256 `d3592e0e…56fe5`). Claude I27 ruling dissolved the provisional
  family into F-XS-IDIOVOL.
- A rerun would be an F-XS-IDIOVOL iteration requiring a material ex-ante
  change (R6.3). The sweep supplies none: Lee-Wang IS what E-075 executed,
  and the measured net Sharpe was not merely underpowered but negative.
  Zhang & Zhao's RSJ variant is an estimator change of the same mechanism,
  not a new one.
- Process root cause: the intraday sweep agent's burned-list briefing
  omitted variance decomposition (it was listed only in the derivatives
  agent's brief). The form caught it at zero cost. Lesson recorded in
  `docs/ai/LESSONS.md`: exclusion lists for sweep agents must be generated
  from `docs/HYPOTHESIS_LEDGER.md` + spec titles, not recalled from memory.

No dataset query, gross/cost estimate, H-number, trial, or K was spent.

## The ex-ante bar for S-001 (computed before anything else)

Same window and observation count as E-095: 898 daily calendar-time L/S
return observations, 2024-01-01..2026-06-16. `min_detectable_sharpe`
(trials=1) — same function and shape as the 2026-08-06 packets:

| breadth | floor (net annualized Sharpe) |
| ---: | ---: |
| 1 (fail-closed) | 1.0500 |
| 3 | 0.6057 |
| 6 (E-075 precedent) | ~0.70 at its inputs; lower at trials=1 |

Paper baseline gross Sharpe 0.96 (t = 2.10). Costs are negligible at this
turnover (below), so net ≈ gross × (1 − attenuation). The binding gate is
therefore POWER via derived breadth, not B3:

| top-30 attenuation | plausible net Sharpe | survives at breadth 1? | at breadth ≥ 3? |
| ---: | ---: | :--: | :--: |
| 0% | ~0.91 | NO | YES |
| 25% | ~0.69 | NO | YES (margin thin) |
| 50% | ~0.46 | NO | NO |

Recorded ex ante: S-001 cannot pass Stage-2 power at fail-closed breadth 1.
It is only viable if the deterministic runner derives breadth ≥ ~3 from
actual positions AND top-30 attenuation is ≤ ~25%. If the runner's realized
breadth comes back < 3, stop at power without consuming a grid.

## S-001 packet

```json
{
  "candidate_id": "unadmitted-2026-08-07-S001",
  "mechanism": "Multi-week cross-sectional reversal: rank on trailing 8-10 week return, long losers / short winners, weekly-rebalanced overlapping calendar-time portfolios (Jegadeesh-Titman)",
  "datasets": [
    {"dataset_id": "canonical_candles bar=1m (daily closes derived)", "source": "db",
     "locator": "canonical_candles", "grain": "1m", "key": ["inst_id", "bar", "ts"],
     "timezone": "UTC", "unique_rows": 43587613, "distinct_inst": 36,
     "first_ts": "2024-01-01T00:00:00Z", "last_ts": "2026-06-16T23:59:00Z",
     "coverage_precedent": "E-095 data gate: 17,271/17,272 PIT member-days at MIN_MEMBER_DAY_COVERAGE=0.95 on this exact window/universe",
     "query_as_of": "2026-08-07",
     "query": "select count(*), count(distinct inst_id), min(ts), max(ts) from canonical_candles where ts >= '2024-01-01' and ts < '2026-06-17' and bar='1m'"},
    {"dataset_id": "universe_membership.parquet", "source": "file",
     "locator": "data/universe/universe_membership.parquet", "grain": "daily",
     "key": ["date", "symbol"], "unique_rows": 101910, "distinct_symbols": 43,
     "first_ts": "2020-01-01", "last_ts": "2026-06-27",
     "columns": ["date", "symbol", "eligible", "adv_usd", "listing_ts", "source"],
     "query_as_of": "2026-08-07"}
  ],
  "coverage_contract": {
    "threshold": 0.95,
    "denominator": "PIT member-days in 2024-01-01..2026-06-16 (E-095 precedent)",
    "intended_window": ["2024-01-01", "2026-06-16"],
    "note": "Formation needs 63 trading days of history; first tradable date ≈ 2024-04; effective L/S observation count ≈ 820, floors above computed at 898 are slightly optimistic — re-floor at the runner's actual n_obs.",
    "provenance": "MIN_MEMBER_DAY_COVERAGE=0.95, E-095 user ruling 2026-08-04"
  },
  "expected_gross": {
    "value": 38.0, "unit": "bps_per_week_on_one_side_notional", "horizon": "1 week slice of a 9-week overlapping book",
    "derivation": "Paper baseline 39.6%/yr on the L/S decile book = 76.2 bps/wk; conservative 50% haircut for a top-30 liquid universe (the paper's ex-largest-caps Sharpe 1.69 > baseline 0.96 implies large caps carry a weaker effect). Range recorded: 38.1 (conservative) to 76.2 (baseline).",
    "provenance": "Kiefer & Nowotny 2026, SSRN 6703978, baseline table (70 Binance USDT tokens, 2021-01..2026-03, Sharpe 0.96, NW t 2.10); corroboration Dobrynskaya SSRN 3913263 (2014-2020)",
    "data_dependent": false
  },
  "modelled_cost": {
    "fee_bps": 5.0, "slippage_bps": 3.0,
    "funding_bps": null,
    "funding_note": "dollar-neutral perp L/S: pays/receives the cross-sectional funding SPREAD, not the level; bounded residual, direction unknown ex ante; must be measured in the runner, not assumed away",
    "expected_turnover": "9-week overlapping holding: ~2/9 of each side's notional traded per week (in+out), both sides ≈ 4/9 of one-side notional",
    "holding_period": "9 weeks (overlapping)", "total_value": 3.6,
    "unit": "bps_per_week_on_one_side_notional",
    "provenance": "repository 8.0 bps round-trip assumption (E-057, E-064..E-067, E-075) × 4/9 weekly traded fraction"
  },
  "gross_over_cost": 10.6,
  "gross_over_cost_note": "conservative 38.1/3.6; baseline 21.2; still 3.2 at an 85% haircut — B3 ≥ 2.0 PASS. Power, not B3, is the binding gate (table above).",
  "breadth": 1.0,
  "breadth_provenance": {
    "formula": "mean_d(count_i(abs(position[d,i]) > 0)) aligned to daily return observations (E-095 formula)",
    "fail_closed_to": 1,
    "note": "No realized position series exists pre-registration; C1 fails closed to 1. The paired runner spec below is the only sanctioned way to derive it. A quintile book on ~30 names holds ~6/side × 9 overlapping sub-books, so derived breadth ≥ 3 is plausible but must be measured, never declared."
  },
  "reference_artifacts": [
    {"path": "results/pipeline_batch2_20260625/c1_pairs_ou/combo_daily_returns.csv",
     "sha256": "115b128cc84860c43f219ac61c98706b058da29fb779f2eb40f5b66c67bf15bb",
     "sha256_reverified": "2026-08-07",
     "field": "lookback_days=14|max_half_life_days=3.0|z_enter=2.5|z_exit=0.0",
     "first_date": "2024-01-01", "last_date": "2026-06-16", "rows": 898,
     "required_common_observations": 365, "max_possible_overlap": 898}
  ],
  "reference_limit": "F-XS-MOMENTUM (E-003/004/005) and F-S5 saved no raw dated returns (E-005 registry note), so return-level distinctness against the two nearest families is impossible from artifacts. Pre-registered replacement, following the E-075 precedent: DECISIVE signal-level checks inside the runner — abs rank-corr of the S-001 formation signal vs (a) the H-002 momentum signal reconstructed at its registered params and (b) the H-038 residual-meanrev z reconstructed per its spec, both over the common window, gate 0.30 abs corr (E-075 gate). Either breach = distinctness FAIL, stop.",
  "selection_accounting": {
    "uses_repository_outcomes": true,
    "screened_variants": 1,
    "family_id": "PROPOSED NEW: F-XS-REVERSAL-MW",
    "family_ruling_needed": "I27: nearest families are F-XS-MOMENTUM (K 2/2, at limit) and F-S5-RESIDUAL-MEANREV (K 2/2, terminal). Claude's recommendation: NEW family — opposite sign to momentum (overreaction correction vs continuation), raw returns not factor residuals, multi-week horizon not days, and the anomaly literature treats intermediate-horizon reversal as distinct from both STR and momentum. If the user rules it into either adjacent family, the candidate is DEAD (no K remains) — that is the honest consequence and the packet stands either way.",
    "prospective_n_trials": 1,
    "k_consumed": 0,
    "note": "Sweep was literature-first; ledger consulted only for exclusions. One spec, no variant screening, no grid at admission."
  },
  "paired_runner_spec": {
    "frozen_single_cell": "formation = trailing 63 trading days ending 7 days before rebalance (8-10wk window, 1wk skip vs STR); quintile sort on PIT-eligible members; equal-weight long bottom / short top quintile; 9-week overlapping sub-books, weekly rebalance; lagged 17.5% vol target (E-075 precedent); 8 bps round trip",
    "outputs_required": ["daily L/S return series (dated)", "daily position matrix for C1 breadth derivation", "signal series for the two decisive distinctness checks"],
    "grid": "NONE at Stage 2 first cell; any grid extension consumes family trials per R6.3",
    "stage3": "not requested; separate authorization"
  },
  "admission_status": "ADMISSIBLE pending user family ruling (E); all computable gates pass; power viability pre-registered as breadth-≥3 AND attenuation-≤25% conditional"
}
```

## What the user must decide (single question)

**Family ruling for S-001** (I27): mint `F-XS-REVERSAL-MW` as a new family
(→ candidate proceeds to registration: H-047, spec + deterministic runner,
Stage-2 first cell with the two decisive signal-corr checks and derived
breadth), or rule it an iteration of F-XS-MOMENTUM / F-S5 (→ CLOSED, no K
remains in either). No other decision is pending; S-002 is closed without
needing one.

## RULED 2026-08-07 (user): new family — S-001 ADMITTED

`F-XS-REVERSAL-MW` minted; H-047 + planned E-096 registered; spec at
`docs/superpowers/specs/2026-08-07-f-xs-reversal-mw-hypothesis.md`; runner
build + single frozen-cell Stage-2 execution dispatched via
`tasks/2026-08-07-h047-stage2-codex-tasks.md`. Formula-string note: the
breadth formula in this packet's C2 JSON is a paraphrase; the spec and any
manifest entry must use the canonical `BREADTH_FORMULAS` string verbatim.
This packet's JSON stays as filed at admission time.

Related: `tasks/2026-08-07-literature-sweep-candidate-shortlist.md`,
`tasks/2026-08-06-vix-cot-candidate-packets.md`,
`docs/EXPERIMENT_REGISTRY.md` E-075, `docs/HYPOTHESIS_LEDGER.md`.
