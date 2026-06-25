---
status: current
type: template
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Stage 3 Template: Implement and Backtest

Role: Codex, trading-core implementation.

## Input

- The Stage 1 hypothesis spec.
- `prior_family_n_trials`: the family's cumulative trial count read from
  `docs/EXPERIMENT_REGISTRY.md` before the current run.

## Mandatory Work

- Implement only what the Stage 1 spec requires.
- Add a leak regression test, such as day-D target not traded on day-D close.
- Declare a `backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS`
  entry where the candidate reaches implementation scope.
- Treat `idealized_fill` artifacts as inadmissible evidence.
- Attach ct_val provenance and require `ct_val_all_authoritative` for
  promotion-grade evidence.
- Feed CPCV the family-cumulative `n_trials`, not a per-run grid count.

## Two-Pass Backtest

- Pass A pre-screen: parquet research-tier, coarse-grid walk-forward. This is
  not promotion evidence, but its trials still count toward the family.
- Pass B: survivors only, DB venue-scoped CPCV, with
  `prior_family_n_trials + grid_size_this_run` passed as CPCV `n_trials`.
  Report DSR and PSR.

## Gate Evidence

Emit these fields into `results/<batch_id>/<candidate>/summary.json`:

```text
candidate_id
family_id
batch_id
grid_size_this_run
family_cumulative_n_trials
wf_oos_sharpe
cpcv_oos_sharpe
dsr
psr
leak_test_passed
portable_validation_gate
idealized_fill
ct_val_all_authoritative
promotion_gate_passed
status
```

`promotion_gate_passed = true` only if all hold:

- DSR >= 0.95.
- PSR >= 0.95.
- `leak_test_passed`.
- `portable_validation_gate`.
- `ct_val_all_authoritative`.
- `idealized_fill == false`.

Otherwise set `status = review_required` or `refuted`.

The driver checkpoint still reviews this independently. A true value here is a
candidate for review, not an auto-publish decision.
