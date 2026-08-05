---
status: current
type: review
owner: codex
created: 2026-08-05
last_reviewed: 2026-08-05
expires: none
superseded_by: null
---

# Candidate input-quality review — 2026-08-05

This is the input-quality review requested when ADR-0016 was deferred on
2026-08-04 (`tasks/2026-08-04-public-status-and-decision-batch-handoff.md`). It
answers what a candidate must carry before it receives an H-number and tests the
proposal against the repository's historical Stage-2 evidence.

**Validation assessment: ready to share with the caveats below.** The original
draft's main diagnosis was directionally right, but its artifact counts mixed
two schemas, its retrospective omitted missing B1/B2 evidence as a blocker, and
its B3 sensitivity contained an arithmetic error. Those points are corrected
here.

No experiment ran, no family trial or K was consumed, and no `results/**`
artifact was modified.

## Scope and calculation grain

The mechanical scan read all 44
`results/**/stage2_feasibility.json` files, representing 30 distinct hypotheses,
and reconciled their hypothesis IDs to the 47 rows in
`docs/HYPOTHESIS_LEDGER.md`.

The scan separates:

- **artifact grain:** all 44 immutable files, including retries and superseded
  attempts;
- **hypothesis grain:** the 30 distinct H-IDs represented by those files;
- **standard schema:** 40 files with a `checks[]` list and named
  `data_availability` check; and
- **legacy candidate-specific schema:** H-013/E-038 plus the three H-014
  calibration artifacts, whose data result lives under `probe.status`,
  `probe_status`, and `verdict` instead.

The review is a snapshot of what the artifacts record now. It cannot prove the
counterfactual claim that a pre-admission form would have prevented a spec or
runner from being built, because historical candidate-at-birth packets do not
exist.

## What the artifacts actually contain

| Question | Measured result | Safe reading |
| --- | ---: | --- |
| Standard `data_availability == PASS` | 23/44 | 17 standard checks fail and 4 legacy artifacts have no such field |
| Data confirmed after normalizing the 4 legacy schemas | **25/44** | H-013/E-038 and H-014/E-043 are real passes; 19 artifacts do not confirm the full required input |
| Hypotheses that never confirm data in any artifact | **9/30** | H-010, H-024, H-025, H-031, H-033, H-035, H-036, H-037, H-042 |
| Direct candidate-level gross-bps/cost-bps summary pair | **8/44** | Two additional H-021 artifacts contain nested per-cell gross/cost bps, not one candidate-level pair |
| Numeric `statistical_power.details.breadth` | **27/44** | The remaining files either predate the power check or fail before a usable value |
| Exact `breadth_provenance` field | **0/44** | This is schema absence, not total evidence absence: E-095 embeds `breadth_derivation`; E-094 has a `breadth_provenance.json` sidecar |

The ledger has 47 rows, but H-000 is explicitly a template. Therefore **16 of
46 non-template hypotheses** have no file named `stage2_feasibility.json`, not
17 of 47 registered candidates. Several predate the current Stage-2 convention
or were intentionally data-blocked, so absence of that filename is descriptive
only; it is not itself an input-quality failure.

### Economic summaries

The eight directly comparable summary pairs are:

| Hypothesis / artifact | Gross bps | Modelled cost bps | Gross / cost |
| --- | ---: | ---: | ---: |
| H-022 / E-058 | 52.8051 | 10.1107 | 5.2227 |
| H-022 / E-059 | 42.7529 | 9.9160 | 4.3115 |
| H-010 / E-057 | 1.3636 | 8.0000 | 0.1704 |
| H-024 / E-064 | 1.3817 | 0.5564 | 2.4833 |
| H-025 / E-065 | -1.0808 | 0.4628 | -2.3354 |
| H-026 / E-067 | -1.5811 | 0.1959 | -8.0728 |
| H-027 / E-066 | -0.3689 | 0.2409 | -1.5315 |
| H-030 / E-069 | 0.1517 | 8.0000 | 0.0190 |

Five of the eight have gross capture at or below cost: H-010, H-025, H-026,
H-027, and H-030. Computing those numbers earlier would have identified the
economic problem before a full runner and terminal artifact were built.

The recurring `8.0` is a base round-trip fee-plus-slippage assumption, not by
itself proof that no cost model exists. H-022 adds funding to the hurdle,
H-024..H-027 turn the base rate into different realized daily turnover costs,
and the paper-data artifacts record turnover/funding aggregates. The real gap
is that most candidates lack one **ex-ante, same-unit gross and total-cost
summary with holding-period and turnover provenance**. Equality of the base
rate across candidates is valid when venue, fee tier, and slippage assumptions
are genuinely the same.

### Breadth provenance

No standard Stage-2 artifact has a first-class `breadth_provenance` field. That
does not mean all provenance is absent:

- E-095 embeds the formula and the complete daily non-zero-position count
  series in `data_availability.details.breadth_derivation`.
- E-094 writes `results/h038_stage2_20260804/breadth_provenance.json`, including
  the parent artifact hash, position source, fail-closed reason, and breadth
  used.

The gap is therefore **unstandardized and unvalidated provenance**, not zero
evidence. A required free-form string would be too weak; the future contract
needs a structured locator/hash/field/formula/window object or equivalent
self-contained evidence.

## Candidate Admission Form

The following is the proposed manual form, not a new validator or gate. Current
authority remains R6.3/R6.8 and I49/I68. Before an H-number is assigned, the
candidate receives a temporary identifier inside the discovery funnel and a
plain JSON admission packet beside its draft spec. Any `BLOCKED` item keeps it
`unadmitted`. It consumes no K. If B1 is estimated from repository data and
influences selection, that screen must still be recorded for R6.3/I13
trial-accounting review; calling it pre-registration does not erase
data-dependent selection.

| # | Required field | Minimum evidence | Fail-closed result |
| --- | --- | --- | --- |
| A1 | `datasets[]` | dataset/source identity; DB table/view; grain and key; timezone; unique row count; first/last timestamp; expected rows; coverage; query-as-of and query text/hash | BLOCKED if absent from DB, wrong-grain, duplicate at the declared key, or below the candidate's threshold |
| A2 | `coverage_contract` | threshold, denominator, intended window, calendar, and provenance path/rule ID | BLOCKED if the threshold or denominator is unprovenanced |
| B1 | `expected_gross` | finite value, unit, event/period horizon, derivation, and paper/artifact provenance; repository-data estimates are labelled data-dependent | BLOCKED if absent, non-finite, or not translatable into the candidate's execution units |
| B2 | `modelled_cost` | fee, slippage, funding/borrow where applicable, expected turnover, holding period, total in B1's unit, and provenance | BLOCKED if absent, non-finite, non-positive without an explicit rebate case, or missing turnover/holding-period treatment |
| B3 | `gross_over_cost` | B1/B2, computed only after unit equality and positive denominator are verified | Record always; BLOCKED if `gross_over_cost < 2.0`. **User ruling 2026-08-05: 2.0 is the admission bar.** It governs this manual pre-admission form only; it is not a Stage-2 gate and changes no existing artifact or verdict |
| C1 | `breadth` | finite positive value derived from a realized position series on confirmed data; fail closed to 1 when no admissible series exists | BLOCKED if asserted from asset/leg count rather than derived positions |
| C2 | `breadth_provenance` | path + SHA-256 + field/JSON pointer + formula + window + `n_obs`, or equivalent self-contained evidence | BLOCKED if the evidence is absent, unreadable, mutable without a hash, or does not reproduce C1 |
| D | `reference_artifacts[]` | path + SHA-256 + dated-return field + first/last date + row count + required common observations + maximum possible overlap | BLOCKED if a dated series is absent or the declared overlap cannot meet the check, per I49 |
| E | `selection_accounting` | whether admission used repository outcomes, number of screened variants, family linkage, prospective `n_trials`, and K impact | BLOCKED if a data-dependent selection step would become a hidden trial; an unadmitted candidate still uses K=0 |

The form is intentionally evidence-oriented rather than a copy of today's
Stage-2 schema. I68 currently requires DB confirmation for execution-ready
candidates. The older Stage-2 template also permits immutable files for a
research-tier pre-screen, but such evidence does not satisfy A1 without an
explicit future rule change or candidate-specific human ruling.

Illustrative shape only — no validator is authorized yet:

```json
{
  "candidate_id": "unadmitted-001",
  "datasets": [
    {
      "dataset_id": "example",
      "source": "db",
      "locator": "canonical_candles",
      "grain": "1m",
      "key": ["source_primary", "inst_id", "bar", "ts"],
      "timezone": "UTC",
      "unique_rows": 0,
      "first_ts": null,
      "last_ts": null,
      "expected_rows": 0,
      "coverage": 0.0,
      "query_as_of": "2026-08-05T00:00:00Z",
      "evidence_sha256": ""
    }
  ],
  "coverage_contract": {
    "threshold": 0.95,
    "denominator": "expected unique member-time keys in the intended window",
    "provenance": "named prior artifact or explicit user ruling"
  },
  "expected_gross": {
    "value": null,
    "unit": "bps_per_event",
    "horizon": "",
    "provenance": "",
    "data_dependent": false
  },
  "modelled_cost": {
    "fee_bps": null,
    "slippage_bps": null,
    "funding_bps": null,
    "expected_turnover": null,
    "holding_period": "",
    "total_value": null,
    "unit": "bps_per_event",
    "provenance": ""
  },
  "gross_over_cost": null,
  "breadth": null,
  "breadth_provenance": {
    "path": "",
    "sha256": "",
    "field": "",
    "formula": "",
    "window": ["", ""],
    "n_obs": 0
  },
  "reference_artifacts": [],
  "selection_accounting": {
    "uses_repository_outcomes": false,
    "screened_variants": 1,
    "family_id": "",
    "prospective_n_trials": 1,
    "k_consumed": 0
  },
  "admission_status": "BLOCKED"
}
```

## Retrospective result

The original raw counts can be reproduced only with a narrow field-presence
rule:

- A1: 21 artifacts do not have a standard `data_availability == PASS` result.
- B3: 5 of the 8 direct pairs have gross/cost below 2.
- C1: 5 of the 27 numeric breadth values are <=1.
- Those sets overlap; their union is 25 artifacts, leaving 19.
- D adds H-038/E-095 as one additional contract failure.

That is **not a literal application of the admission form**:

1. Normalizing H-013/H-014 reduces A1 non-passes from 21 to 19; the A1/B3/C1
   union becomes 23, leaving 21 before D and 20 after D.
2. B1 and B2 are required, so an artifact with no comparable summary cannot
   survive merely because its ratio was never computed.
3. Historical artifacts hold mostly post-run measurements, not the ex-ante
   estimates the form requires. The repository cannot reconstruct whether that
   evidence existed at birth.
4. An absent exact C2 field is not equivalent to absent provenance, as E-094
   and E-095 demonstrate.

Therefore no defensible single number answers "how many of the 44 would have
been admitted." The supported retrospective conclusion is narrower and still
important: nine of 30 represented hypotheses never confirmed their required
data, only eight artifacts expose a direct gross/cost summary pair, and breadth
provenance has no common machine-validated contract.

Claims that the form definitely would or would not have admitted H-009 or
H-014 are not supported by this artifact-only scan. Those candidates need the
same admission packet built from their actual pre-result evidence before they
can serve as worked examples.

## B3 threshold sensitivity

On the eight direct pairs:

| Minimum ratio | Passing artifacts | Reading |
| ---: | ---: | --- |
| 1.0 | 3 | H-022/E-058, H-022/E-059, H-024/E-064 |
| 1.5 | 3 | no historical change |
| 2.0 | 3 | no historical change |
| 3.0 | 2 | excludes H-024/E-064; both H-022 artifacts still pass |

H-022's 52.8/10.1 ratio is about 5.22, so a 3× threshold does **not** exclude
it. The sample contains repeated attempts and post-run realized estimates; it
does not identify 2× as an optimal universal cutoff.

**User ruling 2026-08-05: B3 = 2.0.** Recorded with its honest limits — on
these eight pairs every bar in `[1.0, 2.48]` blocks exactly the same five
candidates, so 2.0 is not *distinguished* by this evidence; it is a defensible
choice inside an indistinguishable range. The first bar that changes anything
is 2.5, which would additionally block H-024/E-064 (2.4833) — a candidate that
failed anyway on 0.77 data coverage and on power. Revisit once prospective
candidates supply ex-ante rather than post-run ratios.

## Finding surfaced during Claude's cross-check (2026-08-05)

`results/stage2_probe_20260714_f_vol_regime_opt_r2/stage2_feasibility.json`
declares `experiment_id: E-041`, but `docs/EXPERIMENT_REGISTRY.md:140`
attributes that 2026-07-14 post-backfill rerun to **E-043** ("Rerun of E-041
after the user-authorized hourly-DVOL backfill"). The file is the artifact
behind H-014's Stage-2 PASS (`verdict.status: PASS`, 12/12 pairs), so an
immutable artifact and the registry disagree about which experiment produced
the repository's only `supported` hypothesis.

`check_ledger_consistency.py` does not catch this: it reconciles the Markdown
ledgers to each other and states plainly that artifact existence is not
checked, so artifact `experiment_id` is never compared to the registry. This is
the same class the review is about — an identity nobody verified by opening the
file — and it is unguarded today.

Not resolved here (it touches an immutable artifact and a `supported`
hypothesis): the user rules whether the artifact is mislabelled, whether E-043
legitimately reuses E-041's identity, and whether the ledger checker should
gain an artifact-identity reconciliation. No artifact, ledger row, or verdict
was modified.

## Design-space decision and recommendation

**Problem:** prevent candidates with unverified data, uneconomic expected edge,
untraceable breadth, or impossible references from receiving an H-number.

**Constraints:** ADR-0016 is deferred; frozen artifacts are immutable; the 44
files span multiple schemas and producers; a new hard gate or Stage-2 schema
contract requires the A5/A9 doc-impact path, a Change Manifest, and ADR review.

- **Option A — add one required Stage-2 string now:** small diff, but too late
  in the lifecycle and too weak to prove provenance.
- **Option B — manual pre-admission JSON now:** no runtime change; exercises the
  real packet on the next candidate and drops into the future manifest.
- **Option C — build the full ADR-0016 validator now:** strongest enforcement,
  but contradicts the user's deferral and would target an unsettled format.

**Decision: Option B.** It is the smallest change at the correct boundary.
Would change if a candidate is about to be registered without a human review
step; then resume the ADR-0016 manifest validator rather than patching each
Stage-2 producer.

Do **not** add a required free-form `breadth_provenance` string to the current
Stage-2 schema. When ADR-0016 resumes, validate the structured admission object
in `round_manifest.json`, bind every evidence file by SHA-256, make the Stage-2
artifact echo the manifest hash/provenance pointer, version the schema, and keep
legacy artifacts readable. One manually completed packet for the next candidate
should precede that implementation.

## Checks run

- Enumerated `results/**/stage2_feasibility.json` with ignored files included:
  44 files.
- Parsed all 44 JSON files read-only; reconciled 30 distinct artifact H-IDs to
  47 ledger rows; no orphan artifact H-ID.
- Independently recomputed standard and legacy-normalized data counts, the
  eight direct gross/cost ratios, breadth population, overlap of A1/B3/C1
  blocker sets, and B3 threshold sensitivity.
- Inspected `backtesting/pipeline_feasibility.py`,
  `backtesting/pipeline_power_screen.py`, `backtesting/pipeline_round.py`, all
  relevant producer call sites, ADR-0013, ADR-0016, I45/I49/I53/I64/I68, and
  the H-038 breadth sidecar/inline evidence.
- No DB query was needed: this review checks persisted artifact content, not
  current source freshness.
- Tests and documentation harness checks are recorded in the paired session
  handoff after the final document edit.
