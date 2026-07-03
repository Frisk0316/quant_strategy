---
status: current
type: manifest
owner: codex
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# Change Manifest: Funding XS Dispersion Stage 3 Checkpoint

## Summary

Added a research-only F-FUNDING-XS-DISPERSION Stage-3 runner, executed the
family-minting distinctness checker before the 4-combo grid, and stopped at
checkpoint 1. The checkpoint is not promotion evidence.

## Business rule(s) affected

No rule text changed. Rules reviewed: R3.1 funding sign convention, R6.1
leakage, R6.3 honest `n_trials`, R7.1 idealized-fill exclusion, R7.4 DSR/PSR
gate interpretation.

## Trigger area(s) (DOC_IMPACT_MATRIX)

A5 backtesting workflow and A11 experiments / research runs.

## Files changed

- `backtesting/funding_xs_dispersion_backtest.py` - research-only vectorized
  funding cross-sectional dispersion backtest with one-day target lag, funding
  cashflow, DB daily loader, and JSON signal helper.
- `scripts/run_funding_xs_dispersion_checkpoint.py` - reproducible
  family-minting plus Stage-3 checkpoint runner for F-FUNDING-XS-DISPERSION.
- `backtesting/pipeline_stage3_registry.py` - registers the funding-xs Stage-3
  runner.
- `tests/unit/test_funding_xs_dispersion_backtest.py` and
  `tests/unit/test_pipeline_stage3_registry.py` - target direction, lag, trial
  accounting, and registry coverage.
- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/FEATURE_MAP.md` - checkpoint evidence, trial accounting, and ownership.
- `results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/**` -
  generated family-minting, summary, and checkpoint1 sidecars.

## Behavior delta

- Before: F-FUNDING-XS-DISPERSION had Stage-2 data availability but no
  distinctness sidecar, Stage-3 runner, WF/CPCV checkpoint artifact, or durable
  experiment row.
- After: family minting returns provisional `MINT` versus F-FUNDING-CARRY, and
  the 4-combo Stage-3 grid has a checkpoint summary with family-cumulative
  `n_trials=4`. Checkpoint 1 fails because DSR/PSR are below 0.95.
- Money/risk impact: none. No live, demo, shadow, config gate, strategy, risk,
  portfolio, execution, or deployment behavior changed.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A; Claude-owned and not modified.
- config/: N/A; avoided because another Turtle session owns dirty config/docs
  state.
- ADR: N/A; no result schema, gate policy, or deployment rule changed.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/HYPOTHESIS_LEDGER.md` - updated H-009 to family cumulative trials 4
  and checkpoint1 statistical-fail state.
- [x] `docs/EXPERIMENT_REGISTRY.md` - added F-FUNDING-XS-DISPERSION K-budget row
  and E-031.
- [x] `docs/FEATURE_MAP.md` - added funding-xs research candidate ownership.
- [x] `docs/DATA_FLOW.md` - reviewed; existing PIT universe, canonical candle,
  and funding flows cover this runner, so no text change needed.
- [x] `docs/GOLDEN_CASES.md` - reviewed; no golden case change for this
  research-only candidate.
- [x] `docs/INVARIANTS.md` - reviewed; I13/I23/I27 already cover trial
  accounting and family minting, and the new lag test covers same-day leakage.
- [x] ADR-0002/0005 - reviewed; no schema or gate policy change.

## Invariants / golden cases

- Invariants checked: I13 hidden trials, I23 family-cumulative `n_trials`, I27
  family minting, and the existing DSR sanity invariant.
- Golden cases affected: N/A.

## Tests / checks run

- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_funding_xs_dispersion_backtest.py tests\unit\test_pipeline_stage3_registry.py -q`
  - 7 passed; pytest emitted a cache write warning due `.pytest_cache`
    permissions.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\run_funding_xs_dispersion_checkpoint.py`
  - Completed DB-backed family-minting plus 4-combo Stage-3 run.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m scripts.run_pipeline_checkpoint1_check --summary results\idea_batch_20260701_taxonomy_002\f_funding_xs_dispersion\summary.json --output results\idea_batch_20260701_taxonomy_002\f_funding_xs_dispersion\checkpoint1_auto.json`
  - Expected nonzero checkpoint stop: `checkpoint1_auto_status: FAIL` because
    DSR/PSR are below 0.95.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py`
  - Passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py`
  - Failed on unrelated concurrent Turtle feature-map text referencing missing
    `surface.html`; not modified here to avoid conflicting with the Turtle
    session.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py --strict` with temporary safe.directory env
  - Passed.

## Risks and rollback

- Risks: family minting is provisional and requires Claude/human mechanism
  novelty review; checkpoint1 statistical gate fails; portable validation is
  adapter-required/absent; the runner is vectorized research code, not live
  strategy wiring.
- Rollback: revert the listed code/test/doc files and remove the generated
  `results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/` sidecars
  if this checkpoint should be discarded.

## Approval

- Human approval required before any strategy promotion, demo, shadow, live, or
  config-gate change. Not requested or obtained in this session.
