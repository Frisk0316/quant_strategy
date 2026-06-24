# Session Handoff: XS momentum universe scaffold - 2026-06-23

## Implementation summary

Implemented the local research scaffold for a point-in-time Binance USDT-perp
universe and disabled XS momentum target-weight construction. The work covers
A1, A3, and B1-B5 locally, plus D1 governance. It does not complete A2 or C1-C3.

## Diff scope

- Files added: `config/universe.yaml`,
  `scripts/build_universe_membership.py`,
  `src/okx_quant/strategies/xs_momentum.py`,
  `tests/unit/test_universe_membership.py`,
  `tests/unit/test_xs_momentum.py`,
  `docs/ADR/0009-xs-momentum-research-strategy.md`,
  `docs/change_manifests/2026-06-23-xs-momentum-universe.md`,
  `tasks/2026-06-23-xs-momentum-universe-context-handoff.md`,
  `tasks/2026-06-23-xs-momentum-universe-session-handoff.md`.
- Files changed: `.gitignore`, `backtesting/replay.py`, `config/strategies.yaml`,
  `docs/ADR/README.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `docs/DATA_FLOW.md`, `docs/DOC_IMPACT_MATRIX.md`,
  `docs/FAILURE_MODES.md`, `docs/FEATURE_MAP.md`, `docs/INVARIANTS.md`,
  `scripts/docs/check_doc_impact.py`, `src/okx_quant/core/config.py`,
  `src/okx_quant/portfolio/allocation.py`.
- Files deleted: none.

## Business-rule change?

- Yes. Change Manifest:
  `docs/change_manifests/2026-06-23-xs-momentum-universe.md`; DOC_IMPACT_MATRIX
  checked rows A1, A2, A4, and reviewed A5.

## Source-of-truth updates

- research/strategy_synthesis.md: N/A, Claude-owned D2 task.
- config/: updated `config/universe.yaml` and disabled
  `config/strategies.yaml::xs_momentum`.
- ADR: added ADR-0009.

## Experiments

- HYPOTHESIS_LEDGER entries: none; Claude-owned D2 remains pending.
- EXPERIMENT_REGISTRY entries: none; Claude-owned D2 remains pending.

## Tests / checks run

- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_universe_membership.py -v` - 9 passed.
- `python scripts/validate_pipeline.py --check-config-only` - PASS
  `config_thresholds` and `strategy_symbol_overlap`.
- `python scripts/docs/check_doc_metadata.py` - passed with 15 pre-existing
  lifecycle metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py` with temporary git safe.directory
  env - passed with no impact-matrix violations across 24 changed files.
- `make docs-check` - not run because `make` is not installed in this Windows
  shell; component scripts above were run directly.

## Docs updated

- `docs/ADR/0009-xs-momentum-research-strategy.md`
- `docs/ADR/README.md`
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/DATA_FLOW.md`
- `docs/DOC_IMPACT_MATRIX.md`
- `docs/FAILURE_MODES.md`
- `docs/FEATURE_MAP.md`
- `docs/INVARIANTS.md`
- `docs/change_manifests/2026-06-23-xs-momentum-universe.md`

## Known limitations / risks

- A2 bulk data and DB coverage are not done.
- C1-C3 validation/backtest work is not done.
- The plan's C1 short-leg positive-funding sign expectation conflicts with
  `docs/DOMAIN_RULES.md` R3.1.
- Generated `data/universe/universe_membership.parquet` is local research-tier
  data and ignored by git.

## Rollback plan

- Remove the added files listed above, revert the changed files listed above,
  and delete `data/universe/universe_membership.parquet` if the local artifact
  should be discarded.

## Context Handoff

- See `tasks/2026-06-23-xs-momentum-universe-context-handoff.md`.

## Questions for human review

- Should C1 implement funding cashflows under current R3.1 semantics, or should
  the XS momentum plan/spec be corrected with an explicit funding-rule change?
- Which exact Binance candidate universe should A2 use for coverage verification?

## Next recommended task

- Resolve the funding sign conflict, then implement C1 with a synthetic funding
  cashflow regression test before running any smoke artifact.

## Human Learning Notes (required)

The harness caught a genuine spec conflict before PnL code was written. Treating
`docs/DOMAIN_RULES.md` as the authority prevented a quiet accounting change from
slipping into a backtest runner.
