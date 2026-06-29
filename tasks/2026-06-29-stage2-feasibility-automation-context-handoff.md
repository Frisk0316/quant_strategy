# Context Handoff: Stage 2 Feasibility Automation - 2026-06-29

## Goal

Make Strategy Research Pipeline Stage 2 feasibility checks machine-readable and fail-closed before Stage 3.

## Current state

- Branch: `codex/pipeline-batch1-stage3`
- Last known good commit / state: `960ef66` before closeout docs; code tasks through `e60c55f` reviewed.
- In-progress edits: closeout docs in `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `config/workstreams.yaml`, plus this handoff pair.
- What works right now: `backtesting/pipeline_feasibility.py`, `scripts/run_pipeline_stage2_check.py`, and `scripts/run_pipeline_batch2_checkpoint.py` emit/validate Stage 2 feasibility artifacts.
- What does not work / unfinished: existing `results/pipeline_batch2_20260625/**` artifacts were not regenerated or migrated.

## Decisions made

- Stage 2 PASS requires `data_availability`, `distinctness`, and `cost_after_edge` checks to be present and PASS.
- Malformed feasibility JSON fails closed via `ValueError` in `result_from_dict`.
- The batch-2 runner writes `stage2_feasibility.json` for C1/C2/C3 pass, fail, and data-probe exception paths.
- C3 feature-gate PASS still does not run Stage 3 in the offline helper; it writes a PASS Stage 2 artifact and keeps promotion false.

## Open questions / unverified assumptions

- Claude should review whether the distinctness and cost-after-edge reason text is strict enough for future candidate review.
- Existing on-disk batch artifacts do not include the new feasibility JSON unless the runner is rerun.

## Rules in play

- Do-not-touch: `research/**`, live/shadow/demo gates, strategy/risk/portfolio behavior, existing result artifacts.
- No live-trading readiness claim was made.
- This was not a business-rule change to PnL, fees, funding, sizing, fills, or gates.

## Context to load next

- Source of truth: `docs/superpowers/pipeline/stage2-feasibility.md`
- Plan: `docs/superpowers/plans/2026-06-29-strategy-research-pipeline-stage2.md`
- Owning files: `backtesting/pipeline_feasibility.py`, `scripts/run_pipeline_stage2_check.py`, `scripts/run_pipeline_batch2_checkpoint.py`
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`

## Checks run

- `Python312/python.exe -m pytest tests/unit/test_pipeline_feasibility.py tests/unit/test_pipeline_stage2_check.py tests/unit/test_pipeline_batch2_checkpoint_runner.py -q` -> `22 passed`, pytest cache warning only.
- `Python312/python.exe scripts/docs/check_doc_metadata.py` -> passed with existing warnings.
- `Python312/python.exe scripts/docs/check_feature_map_links.py` -> passed.
- `Python312/python.exe scripts/docs/check_doc_impact.py` -> passed.

## Approvals

- Human selected Subagent-Driven execution option `1`.

## Next action

- Ask Claude to review the Stage 2 check wording, then decide whether to rerun `scripts/run_pipeline_batch2_checkpoint.py` to materialize `stage2_feasibility.json` under `results/pipeline_batch2_20260625/**`.

## Human Learning Notes

Stage 2 is not a backtest. It is a cheap evidence gate; the JSON artifact makes missing feasibility checks visible before any Stage 3 grid trials spend time or inflate family trial counts.
