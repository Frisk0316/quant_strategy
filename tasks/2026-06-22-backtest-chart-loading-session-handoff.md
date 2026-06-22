---
status: current
type: handoff
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Session Handoff: Backtest Chart Loading - 2026-06-22

## Implementation summary
Fixed `frontend/view-backtest.js` so in-flight per-symbol market and indicator fetches are discarded only when the run changes, not when selected chart symbols change. Also made the equity and drawdown chart wrappers fluid-width so they match the price chart panel width. `frontend/data.js` now gives `/api/backtest/runs` the same long timeout as heavy DB-backed artifact reads, because the running local server responded in 3-5s during WS reconnect noise and the old 10s timeout was brittle. Confirmed `ui_ema_crossover_a986588f` is present in local Postgres and returned by `/api/backtest/runs`; the missing local `results/<run_id>/result.json` is expected under DB artifact mode.

## Diff scope
- Files added: `tasks/2026-06-22-backtest-chart-loading-context-handoff.md`, `tasks/2026-06-22-backtest-chart-loading-session-handoff.md`.
- Files changed: `frontend/view-backtest.js`, `frontend/data.js`, `tests/unit/test_backtest_visual_fallbacks.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Files deleted: none.

## Business-rule change?
- No. No Change Manifest or DOC_IMPACT business-rule rows required.

## Source-of-truth updates
- `research/strategy_synthesis.md`: N/A.
- `config/`: N/A.
- ADR: N/A.

## Experiments
- HYPOTHESIS_LEDGER entries: none.
- EXPERIMENT_REGISTRY entries: none.

## Tests / checks run
- `pytest tests/unit/test_backtest_visual_fallbacks.py -q` before fix - failed on the two new regression tests.
- `pytest tests/unit/test_backtest_visual_fallbacks.py -q` after chart fix - 13 passed, 1 `.pytest_cache` permission warning.
- `pytest tests/unit/test_backtest_visual_fallbacks.py -q` after run-list timeout fix - 14 passed, 1 `.pytest_cache` permission warning.
- `node --check frontend/view-backtest.js` - passed.
- `node --check frontend/data.js` - passed.
- `node -e "...fetch('http://127.0.0.1:8080/api/backtest/runs',{signal:AbortSignal.timeout(60000)})..."` - HTTP 200 in 4741ms.
- Manual Makefile `frontend-check` equivalent: `node --check` passed for `frontend/data.js`, `frontend/charts.js`, `frontend/view-config.js`, `frontend/view-backtest.js`, `frontend/view-results.js`, `frontend/view-validation.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`, and `frontend/app.js`.
- `make frontend-check` - not run; `make` is unavailable in this Windows shell.
- DB check: `ui_ema_crossover_a986588f` exists in `backtest_runs` with display name `2026/06/21_ema_crossover_btc_usdt_swap_ada_usdt_swap`.
- DB artifact check: price series has 21,552 rows each for BTC and ADA; execution markers have 20 BTC rows and 422 ADA rows.
- API check: `/api/backtest/runs` returned `ui_ema_crossover_a986588f` with HTTP 200.

## Docs updated
- `docs/AI_HANDOFF.md`: recorded the UI-only fix and DB artifact-mode investigation.
- `docs/CURRENT_STATE.md`: recorded the current short-state conclusion for chart loading and the DB-backed run.

## Known limitations / risks
- No browser-level automated interaction test exists for fast symbol toggling or run-list load under WS reconnect noise.
- `make` is unavailable in this Windows shell, so the equivalent frontend syntax commands were run manually.

## Rollback plan
- Revert this session's edits to `frontend/view-backtest.js`, `frontend/data.js`, `tests/unit/test_backtest_visual_fallbacks.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, and the two added handoff files. No data migration or artifact cleanup is required.

## Context Handoff
- See `tasks/2026-06-22-backtest-chart-loading-context-handoff.md`.

## Questions for human review
- Should we add a browser-level regression harness for Backtest chart symbol toggling, or keep this as a manual smoke until a frontend test harness exists?

## Next recommended task
- Manual browser smoke for `ui_ema_crossover_a986588f`: select BTC and ADA quickly and verify both price and indicator panels render.

## Human Learning Notes (required)
DB-backed artifact mode means a run can be real and listable even when `results/<run_id>/result.json` is absent. For frontend fetch effects, cleanup is too blunt when the dependency change is a selection within the same run; guard by the owning entity (`runId`) instead. The frontend run list needs a timeout budget that matches DB-backed local server behavior, especially while unrelated WS reconnects are noisy.
