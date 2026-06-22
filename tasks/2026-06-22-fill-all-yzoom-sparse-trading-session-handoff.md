# Session Handoff: Fill-all replay, Y zoom, sparse-trading diagnosis - 2026-06-22

## Implementation summary
Research-only `fill_all_signals` now lifts capacity plus daily-loss/drawdown stops in copied configs and replay-engine effective limits, so later generated strategy signals can continue through submitted orders/fills after a realistic drawdown kill. Backtest Price and technical indicator panels now show visible vertical Y scale controls, and the Risk tab loads `signals` alongside fills/risk events to display signal-to-fill gaps. The cited MA run was diagnosed from local DB artifacts as risk-stop/sizing suppression after 2024-03-11, not missing indicator signals.

## Diff scope
- Files added: `tasks/2026-06-22-fill-all-yzoom-sparse-trading-context-handoff.md`, `tasks/2026-06-22-fill-all-yzoom-sparse-trading-session-handoff.md`
- Files changed: `backtesting/replay.py`, `backtesting/research_controls.py`, `frontend/view-backtest.js`, `frontend/view-config.js`, `frontend/data.js`, `frontend/styles.css`, `tests/unit/test_parameter_sweep.py`, `tests/integration/test_replay_engine.py`, `tests/unit/test_backtest_visual_fallbacks.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`
- Files deleted: none

## Business-rule change?
- No live/default business-rule change. This changes only the already-research-only `fill_all_signals` idealized replay path and docs its inadmissibility for promotion/live evidence. The direct `docs-impact` script exited 0 but reported no changed files detected, so treat it as advisory rather than a strict changed-file audit.

## Source-of-truth updates
- research/strategy_synthesis.md: N/A
- config/: N/A
- ADR: N/A

## Experiments
- HYPOTHESIS_LEDGER entries: none
- EXPERIMENT_REGISTRY entries: none

## Tests / checks run
- `make frontend-check` - not run; `make` is unavailable in this Windows sandbox.
- `make docs-check` - not run; `make` is unavailable in this Windows sandbox.
- `make docs-impact` - not run; `make` is unavailable in this Windows sandbox.
- Makefile-equivalent frontend check: `node --check` on `frontend/data.js`, `frontend/charts.js`, `frontend/view-config.js`, `frontend/view-backtest.js`, `frontend/view-results.js`, `frontend/view-validation.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`, and `frontend/app.js` - passed.
- Docs-check equivalent: `scripts/docs/check_doc_metadata.py` - passed with 13 existing metadata warnings; `scripts/docs/check_feature_map_links.py` - passed.
- Docs-impact equivalent: `scripts/docs/check_doc_impact.py` - exited 0 and reported `no changed files detected; nothing to verify`.
- `python -m pytest tests\unit\test_parameter_sweep.py::test_fill_all_signal_controls_copy_config_without_mutating_base tests\integration\test_replay_engine.py::test_fill_all_signals_keeps_later_signals_after_drawdown_stop tests\unit\test_backtest_visual_fallbacks.py::test_price_and_indicator_panels_expose_vertical_zoom_sliders tests\unit\test_backtest_visual_fallbacks.py::test_risk_tab_loads_signals_for_signal_to_fill_gap tests\unit\test_differential_validation.py::test_backtest_api_triggers_db_only_differential_validation tests\unit\test_backtest_visual_fallbacks.py::test_validation_lab_can_run_saved_backtest_records_directly -q` - passed with a pytest cache permission warning.

## Docs updated
- `docs/AI_HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/UI_MAP.md`
- `docs/DATA_FLOW.md`

## Known limitations / risks
- No browser smoke was run in this sandbox.
- `fill_all_signals` is idealized research-only evidence; it must not be used for live, promotion, or edge claims.
- "All signals" means generated strategy signals submitted by the replay strategy path. It does not fabricate orders from raw indicator crossings the strategy logic intentionally ignores.

## Rollback plan
- Revert the listed code/doc/test files and the two new task handoffs. This removes the expanded fill-all controls, Y-scale sliders, signal-gap risk summary, docs updates, and tests without touching strategy implementations, config, live gates, DB schema, or existing result artifacts.

## Context Handoff
- See `tasks/2026-06-22-fill-all-yzoom-sparse-trading-context-handoff.md`.

## Questions for human review
- Confirm whether the UI wording should say "generated strategy signals" rather than "indicator signals" wherever users may expect raw crossovers to become orders.

## Next recommended task
- Run a browser smoke on the cited DB-backed MA crossover run and, if default realistic trading is still too sparse for research, tune sizing first: lower realistic order/position pressure or enable `Fill all signals` only for idealized signal-side sensitivity.

## Human Learning Notes (required)
The quiet-later-run symptom can hide behind a single early risk event. Because later entries may be suppressed before creating more risk-event rows, the UI must compare signal rows to fill rows rather than relying only on the risk-event table.
