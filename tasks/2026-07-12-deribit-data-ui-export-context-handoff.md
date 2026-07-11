---
status: current
type: handoff
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: 2026-10-12
superseded_by: null
---

# Context Handoff: Deribit data UI/export fixes - 2026-07-12

## Goal (one sentence)
Finish the three user-requested Deribit/data-UI items: external export should not be blocked by refresh, Deribit manual docs should exist, and coverage exchange labels should reflect external dataset providers.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good commit / state: dirty working tree had unrelated Deribit/OI/Turtle changes before this session; no commit made.
- In-progress edits (files): `src/okx_quant/api/routes_data.py`, `frontend/view-config.js`, `tests/unit/test_routes_data_export.py`, `tests/unit/test_routes_data_delete.py`, `docs/manual/40-data-pipeline.md`, `docs/manual/60-frontend-views.md`, `docs/manual/80-glossary.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/FAILURE_MODES.md`, plus this handoff pair.
- What works right now: targeted Python tests pass; `node --check frontend/view-config.js` passes; browser check with mocked coverage shows `DERIBIT` in the Exchange filter dropdown.
- Follow-up fix: unsupported/on-demand refresh HTTP failures are now displayed as `Refresh unavailable; downloading existing rows` instead of `Refresh failed: ...`, so the UI no longer presents expected Deribit skip/fallback as an error.
- What does not work / unfinished: full `make` harness unavailable in this Windows sandbox; existing unrelated dirty files remain untouched.

## Decisions made (and why)
- Refresh is best-effort for external export because DB export is the primary action and already reads existing rows.
- Non-yfinance adapters and DB-known/yaml-missing datasets return `status: "skipped"` because they cannot be refreshed on demand but are valid export targets.
- Provider-to-exchange label is generic, with `binance*` collapsed to `binance`, because Deribit should not be a one-off special case.

## Open questions / unverified assumptions
- None for this task. No strategy/research assumptions were changed.

## Rules in play (preserve verbatim)
- Do-not-touch: `research/`, `results/**`, `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, differential-validation implementation, deployment/shadow/demo/live gates.
- Failure mode added: F27 optional pre-step blocks primary action.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `tasks/2026-07-11-deribit-data-ingestion-tasks.md`, `config/external_data.yaml`.
- Owning files: `docs/FEATURE_MAP.md` Market Data Ingestion and In-Dashboard User Manual; `docs/UI_MAP.md` Market Data Coverage.
- Context Pack: no dedicated Deribit pack exists; `docs/CONTEXT_PACKS/README.md` was read.

## Checks run
- `python -m pytest ...` via `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe` targeted route/manual tests - 36 passed, 1 pytest cache permission warning.
- `node --check frontend\view-config.js` - passed.
- `python scripts/docs/check_doc_metadata.py` - passed.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py --strict` - passed, reported no changed files detected.
- Playwright browser check with mocked API - passed, `DERIBIT option count=1`.
- Follow-up: `python -m pytest tests\unit\test_backtest_visual_fallbacks.py -k external_export_refresh_unavailable` - red first, then 1 passed.
- Follow-up: `node --check frontend\view-config.js` - passed.
- Follow-up: `python -m pytest tests\unit\test_routes_data_export.py -k refresh_external_datasets` - 4 passed.
- Follow-up: `python scripts\docs\check_doc_metadata.py` - passed.

## Approvals
- User approved the task scope in the prompt and explicitly requested no commit. Escalation was used only for npm/Playwright package use and stopping the temporary local server.

## Next action (single, concrete)
- Claude/human can review the diff for the three requested items; do not commit unless the user asks.

## Human Learning Notes
Optional UI pre-steps should not own the success/failure of the primary action. Here, refresh was useful for yfinance freshness, but export correctness depends on DB rows, so refresh needed skip/failure semantics rather than acting as a gate.
