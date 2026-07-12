---
status: archived
type: handoff
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Context Handoff: Backtest Chart Loading - 2026-06-22

## Goal (one sentence)
Fix the Backtest detail UI so BTC price/marker and technical charts do not get stuck loading when selected symbols change mid-request, and confirm where `ui_ema_crossover_a986588f` is stored.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: working tree had no tracked changes at task start; Git needed `-c safe.directory=C:/quant_strategy` due sandbox ownership.
- In-progress edits (files): `frontend/view-backtest.js`, `frontend/data.js`, `tests/unit/test_backtest_visual_fallbacks.py`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `tasks/2026-06-22-backtest-chart-loading-context-handoff.md`, `tasks/2026-06-22-backtest-chart-loading-session-handoff.md`.
- What works right now: targeted frontend regression tests pass; all static `node --check` frontend commands pass.
- What does not work / unfinished: no browser-level interaction smoke was run in this sandbox.

## Decisions made (and why)
- Guard per-symbol market/indicator fetch callbacks by `runId`, not by effect cleanup, because selected-symbol changes are valid within the same run and the state is keyed by symbol.
- Use `chart-wrap fluid` for equity and drawdown, because the price panels already use fluid wrappers and the shorter charts came from the default `.chart-wrap { max-width: 960px; }`.
- Use the existing long frontend timeout for `/api/backtest/runs`, because live HTTP checks against the running server showed 3-5s responses and the old 10s timeout is brittle when WS reconnect work or cold requests add delay.
- Do not change artifact writing, because DB inspection showed `ui_ema_crossover_a986588f` is already recorded in `backtest_runs` and `backtest_artifacts`.

## Open questions / unverified assumptions
- Browser-level UI behavior should be smoke-tested manually or with a future Preact/browser harness.

## Rules in play (preserve verbatim)
- Invariants touched: none.
- Domain rules touched: none.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, DB schema, config, deployment gates, and existing `results/` artifacts.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Owning files / MODULE_BRIEFS: Backtest Result Charts and Backtest API in `docs/FEATURE_MAP.md`.
- Context Pack: no dedicated pack exists for Backtest Result Charts; use `docs/CONTEXT_INDEX.md`.

## Checks run
- `pytest tests/unit/test_backtest_visual_fallbacks.py -q` before fix - failed on the two new regression tests.
- `pytest tests/unit/test_backtest_visual_fallbacks.py -q` after fix - 13 passed, 1 `.pytest_cache` permission warning.
- `node --check frontend/view-backtest.js` - passed.
- `node --check frontend/data.js` - passed.
- `node -e "...fetch('http://127.0.0.1:8080/api/backtest/runs',{signal:AbortSignal.timeout(60000)})..."` - HTTP 200 in 4741ms.
- Manual Makefile `frontend-check` equivalent: `node --check` passed for `frontend/data.js`, `frontend/charts.js`, `frontend/view-config.js`, `frontend/view-backtest.js`, `frontend/view-results.js`, `frontend/view-validation.js`, `frontend/view-trades.js`, `frontend/view-glossary.js`, and `frontend/app.js`.
- `make frontend-check` - not run; `make` is unavailable in this Windows shell.
- DB/API investigation confirmed `/api/backtest/runs` returns `ui_ema_crossover_a986588f`.

## Approvals
- Human approval needed / obtained: user explicitly requested the bug investigation and fix.

## Next action (single, concrete)
- Open the backtest detail page for `ui_ema_crossover_a986588f`, select BTC and ADA in quick succession, and confirm both symbol panels load.

## Human Learning Notes
This run is DB-backed, not missing: `BACKTEST_ARTIFACT_MODE` defaults to `db` when a DSN is configured, so `results/<run_id>/result.json` can be absent while the backend still has a complete run. The stuck BTC chart was a frontend lifecycle bug: cancelling on selection change is too broad when fetch results are stored by symbol. The run list timeout was a frontend resilience issue around a slow running server, not evidence that the DB row was absent.
