# Session Handoff: XS Momentum Phase C Research Runner - 2026-06-23

## Implementation summary
Committed the XS scaffold on an independent branch, then added a research-only
XS momentum vectorized backtest runner with R3.1 funding signs, annualized
vol-target sizing, optional `market_close` crash filtering, honest parameter
trial counts, and a DB-backed smoke artifact for review.

## Diff scope
- Files added: `backtesting/xs_momentum_backtest.py`,
  `tests/unit/test_xs_momentum_backtest.py`,
  `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`,
  `tasks/2026-06-23-xs-momentum-phase-c-context-handoff.md`,
  `tasks/2026-06-23-xs-momentum-phase-c-session-handoff.md`.
- Files changed: `src/okx_quant/strategies/xs_momentum.py`,
  `tests/unit/test_xs_momentum.py`, `docs/FEATURE_MAP.md`,
  `docs/DATA_FLOW.md`, `docs/INVARIANTS.md`.
- Files deleted: none.

## Business-rule change?
- Yes. Change Manifest at
  `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`; DOC_IMPACT_MATRIX
  rows A1 and A5 checked.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A, Claude-owned; not touched.
- config/: unchanged.
- ADR: ADR-0009 reviewed; unchanged.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `python -m pytest tests/unit/test_xs_momentum.py tests/unit/test_xs_momentum_backtest.py tests/unit/test_universe_membership.py -v` - 13 passed; `.pytest_cache` permission warning only.
- `python scripts/validate_pipeline.py --check-config-only` - PASS
  `config_thresholds` and `strategy_symbol_overlap`.
- `python scripts/docs/check_feature_map_links.py` - passed, 116 concrete paths
  checked.
- `python scripts/docs/check_doc_metadata.py` - passed with 15 existing
  lifecycle metadata warnings.
- `python scripts/docs/check_doc_impact.py` with one-command Git safe.directory
  env - passed, 19 changed files, no impact-matrix violations.

## Docs updated
- `docs/FEATURE_MAP.md`
- `docs/DATA_FLOW.md`
- `docs/INVARIANTS.md`
- `docs/change_manifests/2026-06-23-xs-momentum-phase-c.md`
- `tasks/2026-06-23-xs-momentum-phase-c-context-handoff.md`

## Known limitations / risks
- Smoke artifact `results/xs_momentum_db_smoke_20260623.json` is
  `db_smoke_not_promotion`, not promotion evidence.
- Smoke used 22 included Binance symbols, not the >=25-symbol target.
- `SOL-USDT-SWAP` was excluded by a strict venue gap.
- Crash-filter wiring is tested, but the smoke artifact disabled `market_close`
  because the ETH proxy zeroed exposure across the run.
- WF/CPCV, DSR/PSR, and human review are still required before any promotion
  decision.

## Rollback plan
- Revert the Phase C commit or remove the files listed in Diff scope. Delete
  local `results/xs_momentum_db_smoke_20260623.json` if the smoke output should
  not be kept.

## Context Handoff
- See `tasks/2026-06-23-xs-momentum-phase-c-context-handoff.md`.

## Questions for human review
- Which market proxy should be canonical for XS momentum crash filtering?
- Should the Phase C runner remain a local research module, or should a later
  task wire it into the validation harness after coverage is promotion-grade?

## Next recommended task
- Backfill/verify canonical DB coverage for >=25 Binance USDT-perp symbols over
  >=12 months, then run WF/CPCV plus DSR/PSR with recorded trial accounting.

## Human Learning Notes (required)
The fastest safe path was to commit the scaffold first, then keep Phase C narrow:
accounting sign, vol annualization, crash proxy plumbing, and one honest smoke.
The smoke is useful because it proves data plumbing and funding settlements, but
its limits matter more than its Sharpe.
