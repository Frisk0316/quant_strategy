# Task: Fix Self-Contradictory C3 Stage 2 PASS Summary

Owner: Codex
Author: Claude (review finding from Stage 2 feasibility automation review, 2026-06-29)
Date: 2026-06-29
Source: Stage 2 review Finding 1 — `docs/superpowers/plans/2026-06-29-strategy-research-pipeline-stage2.md`

## Task

The C3 PASS branch in `run_c3()` produces a summary whose overall `status` contradicts its
`stage2_status`. Make the PASS-but-Stage-3-not-run state internally consistent and honestly
labelled in both the summary and the batch shortlist.

## Strategy/spec source

- `docs/superpowers/pipeline/stage2-feasibility.md` (Stage 2 gate semantics — unchanged by this task)
- `scripts/run_pipeline_batch2_checkpoint.py` (offline checkpoint helper)

## Required behavior

In `run_c3()` the feature-gate **PASS** branch seeds its summary from
`_stage2_fail_payload(...)`, which hardcodes `"status": "stage2_failed"`. After
`summary.update(_write_stage2_feasibility("c3_sentiment", stage2))` overwrites the Stage 2
fields with the PASS result, the summary ends up with:

- `status: "stage2_failed"` **and** `stage2_status: "PASS"` (contradiction), and
- `stage2_reason: "all required Stage 2 checks passed"`, silently discarding the informative
  `"...data gate passed but replay-backed Stage 3 was not run by this offline helper"` reason.

Downstream, `_shortlist_reason()` then mislabels this row as
`"statistical fail: DSR/PSR below gate and promotion gate false"` because it falls through to the
statistical branch.

Required after the fix:

1. The C3 PASS branch summary has a single coherent overall status that does **not** read
   `stage2_failed`. Use `status: "stage2_passed_stage3_not_run"` (align with an existing ledger
   vocabulary value instead only if one already exists; otherwise use this literal).
2. `stage2_status` for that branch stays `"PASS"` and `stage2_checks` stays all-PASS.
3. `_shortlist_reason()` returns an honest Stage-2-passed / Stage-3-not-run message for that
   status (e.g. `"Stage-2 passed; Stage-3 replay not run by offline helper"`), not the
   statistical-fail fallback.
4. The C3 **FAIL** branch and both data-probe failure paths are unchanged: they keep
   `status: "stage2_failed"` and `stage2_status: "FAIL"`.

Suggested minimal change (Codex owns exact implementation):

- In `run_c3()` PASS branch, after the `summary.update(_write_stage2_feasibility(...))` line, set
  `summary["status"] = "stage2_passed_stage3_not_run"`.
- In `_shortlist_reason()`, add an early branch: if
  `row.get("status") == "stage2_passed_stage3_not_run"`, return the Stage-2-passed message.

Do not introduce a new computed check, do not change PASS/FAIL gate logic, and do not touch the
shared schema in `backtesting/pipeline_feasibility.py`.

## PERMITTED FILES (only edit these)

- `scripts/run_pipeline_batch2_checkpoint.py`
- `tests/unit/test_pipeline_batch2_checkpoint_runner.py`

## FORBIDDEN (do not touch)

- `backtesting/pipeline_feasibility.py`
- `scripts/run_pipeline_stage2_check.py`
- `research/**`
- `src/okx_quant/strategies/**`, `src/okx_quant/signals/**`, `src/okx_quant/risk/**`, `src/okx_quant/portfolio/**`, `src/okx_quant/execution/**`
- `config/risk.yaml`, `config/strategies.yaml`, `config/settings.yaml`
- existing `results/**` artifacts
- backtest engine files under `backtesting/` other than none (this task edits no `backtesting/` files)

## SCOPE LIMIT

Fix only the C3 PASS-branch status contradiction and its shortlist reason. Do not refactor the
summary builders, do not collapse `_stage2_fail_payload`/`_base_summary`, and do not add the
computed `cost_after_edge`/`distinctness` smell tests (that is a separately tracked known gap, not
this task).

## Notes on harness obligations

- **No Change Manifest / ADR required.** This does not change any PnL/fee/funding/sizing/fills/gate
  business rule; Stage 2 PASS/FAIL semantics are untouched. It only fixes an internal status label
  on an offline checkpoint helper. Confirm with `make docs-impact` (advisory) that no impact-matrix
  row is triggered.
- No live/shadow/demo/deployment behavior is affected.

## REQUIRED ON COMPLETION

- List changed files.
- Run the test/verification commands below and paste results.
- Extend `tests/unit/test_pipeline_batch2_checkpoint_runner.py`:
  - In `test_c3_feature_gate_pass_writes_stage2_feasibility_artifact`, capture
    `summary = run_c3()` and assert the summary is non-contradictory:
    `summary["stage2_status"] == "PASS"` and `summary["status"] == "stage2_passed_stage3_not_run"`.
  - Add a `_shortlist_reason()` test asserting the new status yields the Stage-2-passed message
    (and that a `stage2_status == "FAIL"` row still yields the Stage-2-failed message).
- Update `docs/AI_HANDOFF.md` only if the workstream status line changes.
- Commit with an `AI-Origin: Codex` trailer when committing is requested.

## Verification commands

```bash
python -m pytest tests/unit/test_pipeline_batch2_checkpoint_runner.py tests/unit/test_pipeline_feasibility.py tests/unit/test_pipeline_stage2_check.py -q
python scripts/docs/check_doc_impact.py
```

Expected: all tests pass; `doc impact check passed ... no impact-matrix violations`.

## ACCEPTANCE CRITERIA

- [ ] `run_c3()` PASS branch returns a summary with `status == "stage2_passed_stage3_not_run"` and
      `stage2_status == "PASS"` — no `status: "stage2_failed"` alongside `stage2_status: "PASS"`.
- [ ] `stage2_checks` for that branch are all PASS and `stage2_feasibility.json` still validates as
      `stage2_status: "PASS"`.
- [ ] `_shortlist_reason()` returns the Stage-2-passed / Stage-3-not-run message for the new status,
      not `"statistical fail: ..."`.
- [ ] C3 FAIL branch and both data-probe failure paths are unchanged (`status: "stage2_failed"`,
      `stage2_status: "FAIL"`).
- [ ] New/extended tests assert the non-contradiction and the shortlist reason; the three test files
      above all pass.
- [ ] No edits outside the two permitted files.

## Rollback plan

Revert the diffs to `scripts/run_pipeline_batch2_checkpoint.py` and
`tests/unit/test_pipeline_batch2_checkpoint_runner.py`.

## Out of scope (tracked separately, do not fix here)

- Finding 2: `distinctness` and `cost_after_edge` are asserted-PASS prose, not computed; only
  `data_availability` can auto-FAIL. This is the plan's deliberate minimal scope — document as a
  known gap in `docs/CURRENT_STATE.md` in a separate change, not a code fix here.
- Minor: the machine-readable contract doc should state Stage 2 statuses are uppercase-only
  (`PASS`/`FAIL`). Doc-only, separate change.
