# Context Handoff: Pipeline Next Candidates - 2026-07-04

## Goal (one sentence)
Complete the Codex plan for the next pipeline candidates by adding the
`F-OI-POSITIONING` Stage-2 data probe, rechecking `F-XVENUE-LEADLAG`, and
leaving a resumable trail.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: pre-existing Turtle follow-up work was already
  in the working tree; this session added pipeline probe/docs/results and is
  preparing one user-requested commit/push.
- In-progress edits (files): `backtesting/pipeline_stage2_registry.py`,
  `scripts/run_pipeline_stage2_data_probe.py`,
  `tests/unit/test_pipeline_stage2_*`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/HYPOTHESIS_LEDGER.md`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`, `config/workstreams.yaml`, this handoff, the session
  handoff, and the two new Stage-2 result artifacts.
- What works right now: `--candidate oi` runs and writes E-034; BTC/ETH OI
  coverage passes at 258,493 / 258,624 rows per dataset with low missing/stale
  ratios. `--candidate xvenue` reruns and writes E-035.
- What does not work / unfinished: OKX BTC/ETH 1m backfill was not resumed
  because the sandbox blocked outbound OKX access (`WinError 10013`) and the
  escalated rerun was rejected by the approval/usage layer.

## Decisions made (and why)
- Use `H-012` / `E-034` for `F-OI-POSITIONING` because H-011/E-032/E-033 were
  already occupied by Turtle follow-up work in the local tree.
- Keep `F-OI-POSITIONING` as proposed only because E-034 is data availability,
  not a Stage-1 spec, backtest, WF/CPCV, or promotion result.
- Keep `F-XVENUE-LEADLAG` blocked because I19 forbids substituting Binance data
  for the missing OKX leg.

## Open questions / unverified assumptions
- Whether Claude wants to write the `F-OI-POSITIONING` Stage-1 spec immediately
  from E-034, or prioritize an out-of-sandbox OKX backfill first.

## Rules in play (preserve verbatim)
- Invariants touched: I13 (audit trail truth), I19 (no cross-venue substitution),
  I29 (pipeline ledger/trial honesty).
- Domain rules touched: none.
- Do-not-touch: `research/strategy_synthesis.md`; existing `results/**`
  artifacts; live/shadow/demo gates; differential-validation implementation.

## Context to load next (the reading list)
- Source of truth: `research/strategy_synthesis.md`,
  `docs/backtest_live_parity_plan.md`, `config/`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`,
  `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `backtesting/pipeline_stage2_registry.py`,
  `scripts/run_pipeline_stage2_data_probe.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python -m pytest tests/unit/test_pipeline_stage2_registry.py tests/unit/test_pipeline_stage2_data_probe.py -q` - 7 passed.
- `python -m pytest tests/unit -k "stage2 or pipeline" -q -p no:cacheprovider` - 100 passed, 509 deselected.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate oi --output-root results/stage2_probe_20260704_oi` - data availability PASS; overall Stage-2 status remains FAIL because only data availability ran.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate xvenue --output-root results/stage2_reprobe_20260704_xvenue` - data availability FAIL; OKX rows remain 0.
- OKX ingest command for BTC/ETH 1m backfill - blocked by sandbox network and
  escalation rejection.
- `python scripts/validate_pipeline.py --check-config-only` - passed.
- `python scripts/docs/check_doc_metadata.py` - passed with 0 warnings.
- `python scripts/docs/check_feature_map_links.py` - passed, 194 paths checked.
- `python scripts/docs/check_doc_impact.py --strict` with process-local
  `safe.directory` - passed, 29 changed files and no impact-matrix violations.

## Approvals
- Human approval needed / obtained: user explicitly requested the plan be
  completed and uncommitted content committed/pushed after completion.
- Escalated network approval for OKX backfill: requested and rejected by the
  approval/usage layer.

## Next action (single, concrete)
- Run the OKX BTC/ETH 1m backfill outside the sandbox, then rerun
  `python scripts/run_pipeline_stage2_data_probe.py --candidate xvenue --output-root <new-result-dir>`.

## Human Learning Notes
`F-OI-POSITIONING` was cheaper to unblock than expected because the Binance OI
observations are already present and pass coverage/staleness checks. The
cross-venue idea remains a pure data-ingestion problem: the probe is working,
but the OKX leg is empty and the current sandbox cannot reach OKX to repair it.
