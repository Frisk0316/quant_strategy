---
status: current
type: research
owner: claude
created: 2026-08-06
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# Candidate admission packets — VIX term structure and COT positioning

First real use of the Candidate Admission Form
(`tasks/2026-08-05-candidate-input-quality-review.md`), on the two most
promising unconsumed data families from `tasks/2026-08-06-data-inventory.md`.

Both candidates are **BLOCKED**, both at B1, and neither has received an
H-number. No experiment ran, no family trial or K was consumed, no `results/**`
file changed, no gate moved. This is the form working as designed: two
candidates are stopped for the cost of a document instead of the cost of a
runner and a terminal artifact.

The form is a manual review step, not a gate. Authority remains R6.3/R6.8 and
I49/I68.

## Result summary

| # | Candidate | A1 | A2 | B1 | B2 | B3 | C1 | C2 | D | E | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 001 | VIX term-structure slope → crypto timing | PASS | PASS with limit | **BLOCKED** | PASS | n/a | PASS (=1) | PASS | PASS | PASS | **BLOCKED** |
| 002 | COT positioning composition → crypto weekly | PASS | **BLOCKED** | **BLOCKED** | PASS | n/a | PASS (=1) | PASS | PASS | PASS | **BLOCKED** |

## The bar both candidates must clear, known before spending anything

`backtesting/pipeline_power_screen.py::min_detectable_sharpe`, evaluated on each
candidate's real observation count rather than an assumed one:

| Shape | breadth | n_obs | trials | Min annualized net Sharpe |
| --- | ---: | ---: | ---: | ---: |
| 001 daily, single directional bet | 1 | 898 | 1 | **1.0500** |
| 001 daily, if breadth 3 were derivable | 3 | 898 | 1 | 0.6057 |
| 001 daily, at family trials 8 | 1 | 898 | 8 | 1.9828 |
| 002 weekly, single directional bet | 1 | 128 | 1 | **1.0582** |
| 002 weekly, if breadth 4 were derivable | 4 | 128 | 1 | 0.5254 |
| 002 weekly, at family trials 8 | 1 | 128 | 8 | 2.0063 |

This is the number the eight historical gross/cost pairs never had ex ante. A
breadth-1 crypto timing signal must produce a **net** annualized Sharpe above
about 1.05 to survive Stage-2 power on the first trial. Any B1 estimate that
cannot plausibly reach that, after B2 costs, should not be admitted at all.

## Candidate 001 — VIX term-structure slope → crypto directional timing

Mechanism sketch: the VIX9D / VIX / VIX3M / VIX6M slope is a term-structure
signal about the price of near-dated equity variance, distinct from the VIX
*level* that H-033/H-036 used and that H-045/H-046 closed on power.

```json
{
  "candidate_id": "unadmitted-2026-08-06-001",
  "datasets": [
    {"dataset_id": "cboe_vix9d", "source": "db", "locator": "external_observations",
     "grain": "daily", "key": ["dataset_id", "observed_at"], "timezone": "UTC",
     "unique_rows": 3916, "first_ts": "2011-01-04", "last_ts": "2026-07-31",
     "max_gap_days": 5, "gaps_over_7d": 0, "query_as_of": "2026-08-06T01:00:00Z"},
    {"dataset_id": "cboe_vix", "source": "db", "locator": "external_observations",
     "grain": "daily", "key": ["dataset_id", "observed_at"], "timezone": "UTC",
     "unique_rows": 9241, "first_ts": "1990-01-02", "last_ts": "2026-07-31",
     "max_gap_days": 7, "gaps_over_7d": 0, "query_as_of": "2026-08-06T01:00:00Z"},
    {"dataset_id": "cboe_vix3m", "source": "db", "locator": "external_observations",
     "grain": "daily", "key": ["dataset_id", "observed_at"], "timezone": "UTC",
     "unique_rows": 4242, "first_ts": "2009-09-18", "last_ts": "2026-07-31",
     "max_gap_days": 5, "gaps_over_7d": 0, "query_as_of": "2026-08-06T01:00:00Z"}
  ],
  "coverage_contract": {
    "threshold": 0.95,
    "denominator": "US equity trading days in 2024-01-01..2026-06-16 that also have a canonical crypto daily return",
    "intended_window": ["2024-01-01", "2026-06-16"],
    "calendar": "NYSE trading days; crypto is 24/7 so every crypto day without a Cboe print must carry the last published value forward, never a future one",
    "provenance": "MIN_MEMBER_DAY_COVERAGE=0.95, E-095 user ruling 2026-08-04"
  },
  "expected_gross": {
    "value": null, "unit": "bps_per_day", "horizon": "1 day",
    "provenance": "", "data_dependent": false,
    "admission_note": "BLOCKED - no verified paper provenance supplied"
  },
  "modelled_cost": {
    "fee_bps": 5.0, "slippage_bps": 3.0, "funding_bps": null,
    "expected_turnover": "2 round trips per month at a 3-day median holding period",
    "holding_period": "3 days", "total_value": 5.33, "unit": "bps_per_day",
    "provenance": "8.0 bps round trip is the repository's recurring Binance perp assumption (E-057, E-069, E-064..E-067); amortized over a 3-day hold"
  },
  "gross_over_cost": null,
  "breadth": 1.0,
  "breadth_provenance": {
    "formula": "one directional crypto exposure driven by one shared signal; BTC and ETH are not independent bets",
    "fail_closed_to": 1,
    "note": "No realized position series exists pre-admission, so C1 fails closed to 1 per the form. A higher breadth must be derived from actual positions, never declared."
  },
  "reference_artifacts": [
    {"path": "results/pipeline_batch2_20260625/c1_pairs_ou/combo_daily_returns.csv",
     "sha256": "115b128cc84860c43f219ac61c98706b058da29fb779f2eb40f5b66c67bf15bb",
     "field": "lookback_days=14|max_half_life_days=3.0|z_enter=2.5|z_exit=0.0",
     "first_date": "2024-01-01", "last_date": "2026-06-16", "rows": 898,
     "required_common_observations": 365, "max_possible_overlap": 898}
  ],
  "selection_accounting": {
    "uses_repository_outcomes": true,
    "screened_variants": 1,
    "family_id": "",
    "prospective_n_trials": 1,
    "k_consumed": 0,
    "note": "Surfaced by a repository data scan that also considered which families are exhausted. Declared, not hidden. An unadmitted candidate uses K=0."
  },
  "admission_status": "BLOCKED"
}
```

**A2 limitation (not blocking, but it governs the live path):** `cboe_*` has no
registered recurring ingest. A research backtest is possible today; a deployable
strategy is not, until a scheduled incremental ingest exists. Record this before
building, not at deployment.

**What would unblock 001:** a verified paper (normalized DOI/arXiv identity) that
states an expected gross for an equity-variance-term-structure signal applied to
crypto, in units translatable to bps per day. Absent that, B1 stays null and B3
cannot be computed — and a B1 estimated by running the backtest first would be a
data-dependent selection step that R6.3/I13 requires be counted as a trial.

## Candidate 002 — COT trader-category composition → crypto weekly positioning

Mechanism sketch: the composition across COT trader categories in ES, gold, USD
index, and 10Y is a positioning-structure signal, distinct from the macro
*levels* (DGS2/VIXCLS/DTWEXBGS) that H-045/H-046 closed.

```json
{
  "candidate_id": "unadmitted-2026-08-06-002",
  "datasets": [
    {"dataset_id": "cot_es", "source": "db", "locator": "external_observations",
     "grain": "weekly", "key": ["dataset_id", "observed_at"], "timezone": "UTC",
     "unique_rows": 1051, "first_ts": "2006-06-13", "last_ts": "2026-07-28",
     "max_gap_days": 8, "gaps_over_7d": 11, "avg_gap_days": 7.00,
     "query_as_of": "2026-08-06T01:00:00Z"},
    {"dataset_id": "cot_gold", "source": "db", "unique_rows": 1051, "same_shape_as": "cot_es"},
    {"dataset_id": "cot_usd_index", "source": "db", "unique_rows": 1051, "same_shape_as": "cot_es"},
    {"dataset_id": "cot_ust10y", "source": "db", "unique_rows": 1051, "same_shape_as": "cot_es"}
  ],
  "coverage_contract": {
    "threshold": 0.95,
    "denominator": "CFTC report weeks in 2024-01-01..2026-06-16 with a matching crypto weekly return",
    "intended_window": ["2024-01-01", "2026-06-16"],
    "calendar": "Tuesday report date, Friday 15:30 ET scheduled release",
    "provenance": "MIN_MEMBER_DAY_COVERAGE=0.95, E-095 user ruling 2026-08-04",
    "admission_note": "BLOCKED - published_at is the scheduled Friday 15:30 ET, not a historical holiday-release calendar (docs/KNOWN_ISSUES.md). Measured lag spans 2d20:30 to 4d20:30, so some weeks would be joined with an assumed rather than an actual release time."
  },
  "expected_gross": {
    "value": null, "unit": "bps_per_week", "horizon": "1 week",
    "provenance": "", "data_dependent": false,
    "admission_note": "BLOCKED - no verified paper provenance supplied"
  },
  "modelled_cost": {
    "fee_bps": 5.0, "slippage_bps": 3.0, "funding_bps": null,
    "expected_turnover": "1 round trip per week", "holding_period": "7 days",
    "total_value": 8.0, "unit": "bps_per_week",
    "provenance": "same 8.0 bps round-trip assumption, one full turn per weekly rebalance"
  },
  "gross_over_cost": null,
  "breadth": 1.0,
  "breadth_provenance": {
    "formula": "four COT inputs produce one composite weekly crypto exposure; input count is not bet count",
    "fail_closed_to": 1,
    "note": "Four datasets do not make breadth 4. That inference is the exact defect ADR-0013 caught in H-041/H-045/H-046."
  },
  "reference_artifacts": [
    {"path": "results/pipeline_batch2_20260625/c1_pairs_ou/combo_daily_returns.csv",
     "sha256": "115b128cc84860c43f219ac61c98706b058da29fb779f2eb40f5b66c67bf15bb",
     "field": "lookback_days=14|max_half_life_days=3.0|z_enter=2.5|z_exit=0.0",
     "first_date": "2024-01-01", "last_date": "2026-06-16", "rows": 898,
     "required_common_observations": 365, "max_possible_overlap": 128,
     "admission_note": "Daily reference resampled to weekly gives 128 common observations, below the 365 daily bar. A weekly candidate needs a weekly-grain distinctness contract or an explicit ruling before D can be judged on the same terms."
  }],
  "selection_accounting": {
    "uses_repository_outcomes": true, "screened_variants": 1, "family_id": "",
    "prospective_n_trials": 1, "k_consumed": 0
  },
  "admission_status": "BLOCKED"
}
```

## Reading

The packets took a document to produce and blocked two candidates that would
otherwise have consumed a spec, a runner, a Stage-2 execution, and an immutable
terminal artifact each — the exact sequence that produced E-057 (gross/cost
0.1704) and E-069 (0.0190).

Two things surfaced that no previous candidate recorded before its runner
existed:

1. **The power bar is knowable in advance.** 1.05 net annualized Sharpe at
   breadth 1. Historically this was discovered only after the artifact was
   frozen.
2. **Candidate 002 has a grain mismatch in the distinctness contract.** The
   available dated reference is daily; a weekly candidate cannot meet a 365
   daily-observation bar. That is a contract question for the user, not a
   research finding, and it would have surfaced as a late failure.

Neither candidate should proceed without B1 from verified literature. If no such
paper exists, that is itself the answer: the mechanism is not
literature-supported and does not belong in an ADR-0016 round's eight
paper-backed slots.

## User rulings 2026-08-06

1. **Candidate 002 weekly distinctness grain mismatch:** no data → do not
   proceed. 002 stays BLOCKED and additionally data-gated; it may be revisited
   only if sufficient weekly-grain evidence becomes obtainable (a weekly dated
   reference series, or an extended canonical crypto history that raises the
   overlap materially above 128 weeks). No weekly-grain contract amendment is
   authorized now.
2. **B1 literature search authorized:** Claude searches for verified-paper
   provenance for both mechanisms. A search that finds nothing closes the
   candidate as not literature-supported rather than lowering the B1 bar.

Related: `tasks/2026-08-05-candidate-input-quality-review.md`,
`tasks/2026-08-06-data-inventory.md`, `docs/ADR/0016-genai-discovery-deterministic-strategy-evaluation.md`.
