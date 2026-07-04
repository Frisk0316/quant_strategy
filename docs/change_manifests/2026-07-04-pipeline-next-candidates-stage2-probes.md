---
status: current
type: manifest
owner: codex
created: 2026-07-04
last_reviewed: 2026-07-04
expires: none
superseded_by: null
---

# Change Manifest: Pipeline Next-Candidate Stage-2 Probes

## Summary
Added a read-only Stage-2 data-availability probe for `F-OI-POSITIONING` and
recorded the 2026-07-04 `F-XVENUE-LEADLAG` coverage recheck/backfill block.
This is pipeline feasibility instrumentation and documentation only.

## Business rule(s) affected
None. No PnL, fee, funding, sizing, fill, risk, portfolio, execution, or gate
semantic changed.

## Trigger area(s) (DOC_IMPACT_MATRIX)
A5 backtesting/report harness touched because
`backtesting/pipeline_stage2_registry.py` now owns the OI data probe logic.

## Files changed
- `backtesting/pipeline_stage2_registry.py` - add OI dataset thresholds, data
  coverage query, probe runner, and registry entry.
- `scripts/run_pipeline_stage2_data_probe.py` - expose the OI probe helpers
  through the CLI wrapper.
- `tests/unit/test_pipeline_stage2_registry.py` - assert OI probe registration.
- `tests/unit/test_pipeline_stage2_data_probe.py` - assert OI coverage/missing
  / stale-ratio check behavior.
- `docs/EXPERIMENT_REGISTRY.md` - add E-034/E-035 and K-budget rows.
- `docs/HYPOTHESIS_LEDGER.md` - add H-012 and refresh H-010 with E-035.
- `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `config/workstreams.yaml` - update owner/state/navigation context.
- `results/stage2_probe_20260704_oi/.../stage2_feasibility.json` - new OI
  Stage-2 data-availability artifact.
- `results/stage2_reprobe_20260704_xvenue/.../stage2_feasibility.json` - new
  XVenue recheck artifact.

## Behavior delta
- Before: Stage-2 pipeline probe CLI supported the existing candidates but had
  no `F-OI-POSITIONING` data-availability probe; `F-XVENUE-LEADLAG` status
  depended on the earlier E-029 artifact.
- After: The CLI can run `--candidate oi` and produces an OI coverage artifact;
  XVenue has an updated E-035 artifact showing OKX 1m coverage is still absent.
- Money/risk impact: none.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A - research ownership remains Claude.
- config/: updated `config/workstreams.yaml` progress text only.
- ADR: N/A - no major rule or policy change.

## Docs updated (from DOC_IMPACT_MATRIX row)
- [x] `docs/EXPERIMENT_REGISTRY.md` - E-034/E-035 recorded.
- [x] `docs/HYPOTHESIS_LEDGER.md` - H-010 refreshed; H-012 added.
- [x] `docs/FEATURE_MAP.md` - Stage-2 OI probe ownership added.
- [x] `docs/AI_HANDOFF.md` and `docs/CURRENT_STATE.md` - current-state
  guidance refreshed.

## Invariants / golden cases
- Invariants checked: I13 (trail truth), I19 (no cross-venue substitution), I29
  (pipeline ledger/trial honesty) by documentation and probe artifact behavior.
- Golden cases affected: N/A.

## Tests / checks run
- `python -m pytest tests/unit/test_pipeline_stage2_registry.py tests/unit/test_pipeline_stage2_data_probe.py -q` - 7 passed.
- `python -m pytest tests/unit -k "stage2 or pipeline" -q -p no:cacheprovider` - 100 passed, 509 deselected.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate oi --output-root results/stage2_probe_20260704_oi` - OI data availability PASS; overall Stage-2 status remains FAIL because only data availability ran.
- `python scripts/run_pipeline_stage2_data_probe.py --candidate xvenue --output-root results/stage2_reprobe_20260704_xvenue` - data availability FAIL; OKX rows remain 0.
- `python scripts/market_data/ingest.py --exchange okx --dataset klines_1m --symbols BTC-USDT-SWAP,ETH-USDT-SWAP --start 2024-01-01T00:00:00Z --end 2026-06-17T00:00:00Z --direction backward` - blocked by sandbox network (`WinError 10013`); escalated rerun rejected by approval/usage layer.
- `python scripts/validate_pipeline.py --check-config-only` - passed.
- `python scripts/docs/check_doc_metadata.py` - passed with 0 warnings.
- `python scripts/docs/check_feature_map_links.py` - passed, 194 concrete paths checked.
- `python scripts/docs/check_doc_impact.py --strict` with process-local
  `safe.directory` - passed, 29 changed files and no impact-matrix violations.

## Risks and rollback
- Risks: OI probe thresholds are advisory and only validate data availability;
  treating E-034 as strategy evidence would be a process error.
- Rollback: revert this manifest plus the OI registry/script/test/doc/result
  additions; leave existing Turtle follow-up work unchanged unless explicitly
  rolling back that separate scope.

## Approval
- Human approval required: yes; user requested this task and requested commit
  and push after completion on 2026-07-04.
