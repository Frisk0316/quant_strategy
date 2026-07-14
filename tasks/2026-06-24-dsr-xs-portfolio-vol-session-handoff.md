---
status: archived
type: handoff
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Session Handoff: DSR Harness + XS Portfolio Vol - 2026-06-24

## Implementation summary

Fixed DSR/CPCV basis mismatch, added hard DSR <= PSR invariant coverage, changed
XS momentum sizing to portfolio book-vol targeting with a 2.0 max-gross cap, and
generated a correctness-only portfolio-vol validation artifact. Promotion remains
blocked.

## Diff scope

- Files added: `tests/unit/test_dsr.py`, `tests/unit/test_cpcv.py`,
  two Change Manifests, this handoff pair, and
  `results/xs_momentum_validation_20260624_portfoliovol/`.
- Files changed: `src/okx_quant/analytics/dsr.py`, `backtesting/cpcv.py`,
  `src/okx_quant/strategies/xs_momentum.py`,
  `tests/unit/test_backtesting.py`, `tests/unit/test_xs_momentum.py`,
  `tests/unit/test_xs_momentum_backtest.py`, and governance/current-state docs.
- Files deleted: none.

## Business-rule change?

- Yes. Change Manifests:
  `docs/change_manifests/2026-06-24-dsr-computation-fix.md` and
  `docs/change_manifests/2026-06-24-xs-momentum-portfolio-vol.md`.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A, Claude-owned and not edited.
- config/: unchanged; `xs_momentum.enabled` remains false.
- ADR: ADR-0009 updated for portfolio-vol targeting and max-gross cap.

## Experiments

- HYPOTHESIS_LEDGER entries: H-002 correction note added; current evidence
  refutes the promotion hypothesis.
- EXPERIMENT_REGISTRY entries: E-004 leakfix and E-005 portfolio-vol rerun.

## Tests / checks run

- `python -m pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py -v` - 3 passed.
- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_xs_momentum_backtest.py -v` - 12 passed.
- `python -m pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py tests/unit/test_backtesting.py tests/unit/test_parameter_sweep.py -v` - 70 passed.
- `python scripts/docs/check_doc_impact.py` with process-local `safe.directory`
  - passed.
- `make docs-impact` - failed because `make` is unavailable in this Windows shell.

## Docs updated

- `docs/DOMAIN_RULES.md`
- `docs/INVARIANTS.md`
- `docs/FAILURE_MODES.md`
- `docs/ADR/0009-xs-momentum-research-strategy.md`
- `docs/DATA_FLOW.md`
- `docs/FEATURE_MAP.md`
- `docs/HYPOTHESIS_LEDGER.md`
- `docs/EXPERIMENT_REGISTRY.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`

## Known limitations / risks

- Portfolio-vol estimate is diagonal only and ignores covariance.
- Portfolio-vol rerun did not keep WF Sharpe perfectly flat versus leakfix;
  PSR stayed below the promotion threshold.
- Generated result artifacts are ignored by `results/*/` unless force-added.

## Rollback plan

- Revert the DSR/CPCV files, XS sizing file, tests, manifests/docs, and remove
  `results/xs_momentum_validation_20260624_portfoliovol/`.

## Context Handoff

- See `tasks/2026-06-24-dsr-xs-portfolio-vol-context-handoff.md`.

## Questions for human review

- Should diagonal book-vol be accepted, or should Claude request covariance
  targeting before any future sizing evidence?

## Next recommended task

- Claude review of DSR basis, `n_trials` behavior, and portfolio-vol artifact.

## Human Learning Notes (required)

The DSR defect was not XS-specific; any CPCV artifact that used the old
annualized-SR/overlapping-path DSR can be too optimistic. Leverage-only changes
are only perfectly Sharpe-invariant before practical caps, costs, and funding.
