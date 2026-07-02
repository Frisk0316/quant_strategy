# Session Handoff: Project Maintenance M1-M5 - 2026-07-03

## Implementation summary
Completed M1-M5 in order: CI/static-check alignment, handoff preservation and
hot-doc slimming, real no-DB replay backtest smoke, monitoring unit coverage, and
stocks Option A research-only ownership mapping. No strategy, risk, execution,
deployment gate, or existing result artifact behavior was changed.

## Diff scope
- Files added: `tests/fixtures/backtest_smoke/BTC_USDT_SWAP/candles_1H.csv`,
  `tests/unit/test_monitoring.py`,
  `tasks/2026-07-03-project-maintenance-context-handoff.md`.
- Files changed: `.github/workflows/ci.yml`, `Makefile`, `docs/AI_HANDOFF.md`,
  `docs/CHANGELOG_AI.md`, `docs/CURRENT_STATE.md`, `docs/FEATURE_MAP.md`,
  `docs/KNOWN_ISSUES.md`, `docs/RUNBOOK.md`, `STATUS.md`,
  `config/workstreams.yaml`, `scripts/smoke/backtest_smoke.py`,
  `src/okx_quant/stocks/__init__.py`.
- Files deleted: none.

## Business-rule change?
- No. No PnL, fee, funding, sizing, risk, fill, data-provenance gate, or
  deployment policy rule changed.

## Source-of-truth updates
- `research/strategy_synthesis.md`: N/A.
- `config/`: `config/workstreams.yaml` updated for Progress panel maintenance
  status only.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `ruff check src tests backtesting scripts` - passed during M1.
- `pytest tests/unit -q` - passed, 575 tests after M4.
- `pytest tests/test_daily_winner_backtest.py tests/test_ohlcv_rotation.py -q`
  - passed, 32 tests during M1.
- `pytest research/crypto-alpha-lab/tests -q -p no:cacheprovider` - passed,
  18 tests during M1.
- Manual `node --check` commands from `make frontend-check` - passed during M1.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/smoke/backtest_smoke.py` - passed; emitted 2 fills and verified
  `result.json`, `metrics.json`, and `fills.csv` in a temp dir.
- Temporary broken-fixture probe for `scripts/smoke/backtest_smoke.py` - failed
  with exit 1, then fixture was restored and the smoke passed.
- `pytest tests/unit/test_monitoring.py -v` - passed, 4 tests.
- `ruff check scripts/smoke/backtest_smoke.py tests/unit/test_monitoring.py src/okx_quant/stocks/__init__.py`
  - passed.
- `pytest tests/unit/test_stock_system.py -q` - passed, 5 tests.
- `make backtest-smoke` and `make docs-check` - not runnable because `make` is
  unavailable in this Windows sandbox; equivalent Python commands passed.

## Docs updated
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/CHANGELOG_AI.md`,
  `docs/FEATURE_MAP.md`, `docs/KNOWN_ISSUES.md`, `docs/RUNBOOK.md`,
  `STATUS.md`, `config/workstreams.yaml`, and this paired handoff.

## Known limitations / risks
- The no-DB replay smoke uses `strategy_fill` / `idealized_fill`; it is not
  promotion evidence.
- Monitoring unit tests do not prove production alert routing or deployment
  readiness.
- `stocks/` remains a research-only sandbox; do not wire it into crypto UI/API or
  deployment gates without explicit approval.
- The working tree still has unrelated dirty pipeline/research/result files.

## Rollback plan
- Revert `df96682`, `0191c1d`, `2dea608`, and `5eb71f8` for maintenance changes.
  Keep `79c1ddc` unless the 7/3 handoff preservation commit is explicitly no
  longer desired.

## Context Handoff
- See `tasks/2026-07-03-project-maintenance-context-handoff.md`.

## Questions for human review
- Confirm M5 Option A is acceptable and no deletion of `src/okx_quant/stocks/`
  is desired.
- Decide which separate pipeline P1-P8 dirty files should be committed, revised,
  or discarded by that owning session.

## Next recommended task
- Claude/human review maintenance commits, then review the separate pipeline
  P1-P8 working tree and run DB/network backfill checks in a suitable environment.

## Human Learning Notes (required)
The most useful maintenance fix here was turning a placeholder smoke into a tiny
truthful check with artifact assertions and a deliberate failure probe. The
gotcha was documentation staging: `docs/FEATURE_MAP.md` already contained
unrelated pipeline edits, so only the monitoring/stocks hunk was staged for the
maintenance commit.
