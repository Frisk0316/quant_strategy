# Context Handoff: Fill-all replay, Y zoom, sparse-trading diagnosis - 2026-06-22

## Goal (one sentence)
Make research-only `fill_all_signals` replay later generated signals after risk stops, expose visible vertical zoom controls on Backtest charts, and explain why the cited default MA run stops trading after early 2024.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`
- Last known good commit / state: working tree already contained unrelated data-layer edits before this task; do not revert them.
- In-progress edits (files): `backtesting/replay.py`, `backtesting/research_controls.py`, `frontend/view-backtest.js`, `frontend/view-config.js`, `frontend/data.js`, `frontend/styles.css`, targeted tests, docs, and this handoff.
- What works right now: targeted pytest covers fill-all drawdown-stop bypass, config-copy semantics, visible Y-scale controls, signal-gap wiring, and DB-only Validation Lab regression. Frontend JS syntax checks pass via the Makefile-equivalent `node --check` set.
- What does not work / unfinished: no browser smoke against the live UI was run in this sandbox; `make` is unavailable here, so Makefile targets were run as direct equivalent commands where possible.

## Decisions made (and why)
- Extend `fill_all_signals` to lift max daily loss, soft drawdown, and hard drawdown thresholds because DB evidence showed later signals existed but entry conversion stopped after a drawdown kill.
- Keep the change research-only and record effective controls under `result.validation.fill_all_signals_controls` because idealized-fill artifacts remain inadmissible for live/promotion evidence.
- Reuse the existing Y zoom state and `MAX_Y_ZOOM` behavior, adding visible slider wiring, because the chart model already supported vertical scaling.

## Open questions / unverified assumptions
- Browser-level layout and slider interaction still need a manual smoke on the user's viewport.
- The exact user-facing wording for "all triggered indicator signals" should remain "generated strategy signals"; raw indicator crossovers that the strategy intentionally suppresses are not converted into orders.

## Rules in play (preserve verbatim)
- Invariants touched: none.
- Domain rules touched: idealized-fill admissibility only; no live/default risk rule changed.
- Do-not-touch: `research/`, `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`, DB schema, existing `results/` artifacts, validation gate/tolerance semantics.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/ai_collaboration.md`.
- Owning files / MODULE_BRIEFS: Backtest Result Charts, Backtest API, Backtesting Engine/Report in `docs/FEATURE_MAP.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `make frontend-check` - not run; `make` is unavailable in this Windows sandbox.
- `make docs-check` - not run; `make` is unavailable in this Windows sandbox.
- `make docs-impact` - not run; `make` is unavailable in this Windows sandbox.
- Makefile-equivalent frontend check: `node --check` on `frontend/data.js`, `frontend/charts.js`, `frontend/view-config.js`, `frontend/view-backtest.js`, `frontend/view-results.js`, `frontend/view-validation.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`, and `frontend/app.js` - passed.
- Docs-check equivalent: `scripts/docs/check_doc_metadata.py` - passed with 13 existing metadata warnings; `scripts/docs/check_feature_map_links.py` - passed.
- Docs-impact equivalent: `scripts/docs/check_doc_impact.py` - exited 0 and reported `no changed files detected; nothing to verify`.
- `python -m pytest tests\unit\test_parameter_sweep.py::test_fill_all_signal_controls_copy_config_without_mutating_base tests\integration\test_replay_engine.py::test_fill_all_signals_keeps_later_signals_after_drawdown_stop tests\unit\test_backtest_visual_fallbacks.py::test_price_and_indicator_panels_expose_vertical_zoom_sliders tests\unit\test_backtest_visual_fallbacks.py::test_risk_tab_loads_signals_for_signal_to_fill_gap tests\unit\test_differential_validation.py::test_backtest_api_triggers_db_only_differential_validation tests\unit\test_backtest_visual_fallbacks.py::test_validation_lab_can_run_saved_backtest_records_directly -q` - passed with a pytest cache permission warning.

## Approvals
- Human approval obtained in chat to implement the plan and then reported missing fill-all/Y zoom behavior.

## Next action (single, concrete)
- Browser-smoke the cited run in Backtest view: verify Price and indicator Y sliders visibly rescale charts, then inspect the Risk tab signal/fill gap for the default run.

## Human Learning Notes
The sparse-trading symptom was not missing indicators: local DB showed `ui_ma_crossover_c9acab8e` had 809 signal rows through 2026-06-11 but only 90 orders/fills through 2024-03-11, followed by a hard-drawdown event. After a drawdown kill, later entries were suppressed before order/risk-event creation, so the UI needed signal/fill gap visibility and fill-all needed to lift drawdown stops for research replay.
