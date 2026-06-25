---
status: current
type: runbook
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Strategy Research Pipeline Stage 1 Driver

- Spec: `docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md`
- Plan: `docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md`

The driver is one Claude session. One kickoff runs a pre-registered batch of
backlog candidates through Stages 1, 2, and 3, stops once for Claude evidence
review, emits a shortlist, then stops for the user's publish decision.

## Kickoff Inputs

```text
{
  candidates: [ordered backlog ids, e.g. S7, S5, S6],
  K: family retry limit, default 2,
  runtime_cap: required wall-clock budget, no silent default,
  data_tier: two-pass, parquet pre-screen then DB venue-scoped CPCV
}
```

## Procedure

1. Pre-register the whole batch in the ledgers before running.
   Ensure each candidate has a `HYPOTHESIS_LEDGER.md` family row and an
   `EXPERIMENT_REGISTRY.md` planned row with `family_id` and planned grid size.
   This is the anti-cheat anchor: trials are committed before results are seen.
2. For each candidate in order:
   Run Stage 1 with `stage1-hypothesis.md`.
   Run Stage 2 with `stage2-feasibility.md`.
   If Stage 2 fails, skip the candidate, record the reason in the ledger with 0
   grid trials, and continue.
   If Stage 2 passes, read this family's cumulative `n_trials` from
   `EXPERIMENT_REGISTRY.md` and pass it to Stage 3 as
   `prior_family_n_trials`.
   Run Stage 3 with `stage3-implement-backtest.md`.
3. Stop at the Claude evidence checkpoint.
   Review each candidate's gate-evidence artifact with
   `docs/REVIEW_QUESTIONS.md`, `docs/CRITIQUE_PROTOCOL.md`, and the gate clauses
   in `docs/ai_collaboration.md`.
   Classify `supported`, `refuted`, or `shelved`, and classify each follow-up as
   retry versus new family.
   Update both ledgers with verdicts and recorded `n_trials`.
4. Write `shortlist-template.md` to `results/<batch_id>/`.
5. Stop for the user's publish decision.

## Stop Conditions

- Batch candidates exhausted.
- `runtime_cap` hit; abort the batch cleanly.
- A family hits retry limit `K`; stop retrying it and escalate to the user.

## Retry vs New Family

Same economic mechanism tweaked or bugfixed = retry. It keeps the same family
budget and counts toward `K`.

Genuinely different economic mechanism = new family. It gets a fresh budget and
`K` resets.

Relabeling a retry as a new family to dodge `K` or DSR deflation is forbidden.

## Hard Rules

- Never relax the gate: DSR >= 0.95 and PSR >= 0.95, honest family-cumulative
  `n_trials`, leak-free, differential-validation portable gate, and ct_val
  provenance.
- Publish means `enabled:false` vetted candidate only.
- Never touch demo, shadow, live, or deployment gates from this driver.
- Durable record is `HYPOTHESIS_LEDGER.md` plus `EXPERIMENT_REGISTRY.md`.
  `results/<batch_id>/` is scratch that must reconcile into the ledgers.
