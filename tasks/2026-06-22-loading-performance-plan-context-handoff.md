---
status: current
type: handoff
owner: codex
created: 2026-06-22
last_reviewed: 2026-06-22
expires: none
superseded_by: null
---

# Context Handoff: Loading Performance Plan - 2026-06-22

## Goal (one sentence)
Plan a safe, staged fix for slow loading across DB data, saved backtest artifacts, validation views, and chart time series.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`
- Last known good commit / state: current branch carries ADR-0007 P1 plus prior chart-loading fixes documented in `docs/CURRENT_STATE.md`.
- In-progress edits (files): pre-existing dirty files before this planning pass: `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `frontend/data.js`, `frontend/view-backtest.js`, `tests/unit/test_backtest_visual_fallbacks.py`, plus two untracked backtest chart-loading handoffs.
- What works right now: backtest chart frontend loads result first, then equity/ledger/validation and selected chart symbols progressively.
- What does not work / unfinished: `/api/backtest/runs` and several artifact endpoints can take seconds because endpoints open new DB connections, load whole JSONB/CSV artifacts, then filter/downsample in Python. No code fix was implemented in this planning session.

## Decisions made (and why)
- Recommended first move: cache DB connections and run summaries, then push artifact filtering/downsampling toward the read path because this gives the largest user-facing speedup without changing trading semantics.
- Recommended deeper move: migrate large time-series artifacts from single JSONB payload rows to row-oriented/read-optimized storage only after user approval, because that is a DB schema/data-provenance contract change.

## Open questions / unverified assumptions
- Assumption: the worst stalls are dominated by per-request `asyncpg.connect()` and whole-artifact JSONB/CSV reads. Verify with route timings before implementation.
- Assumption: existing DB artifact rows may not have corresponding file artifacts because DB mode is default when `DATABASE_URL` is set.

## Rules in play (preserve verbatim)
- Invariants touched: I12 if DB/parquet/source-read behavior changes; otherwise none for P0 cache/query work.
- Domain rules touched: R6.2 only if source-read semantics or artifact storage migration changes; P0 should not change business rules.
- Do-not-touch: `research/`, trading-core (`strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`), PnL/fee/funding/sizing/fills, deployment gates, existing result artifacts, differential-validation implementation unless explicitly approved.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, `docs/FEATURE_MAP.md`, `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/DESIGN_SPACE.md`, `docs/ADR/0002-backtest-result-schema.md`, `docs/ADR/0004-frontend-module-loading.md`, `docs/ADR/0007-multi-venue-instrument-specs.md`, `config/settings.yaml`.
- Owning files / MODULE_BRIEFS: `frontend/data.js`, `frontend/view-backtest.js`, `frontend/app.js`, `src/okx_quant/api/routes_backtest.py`, `src/okx_quant/api/routes_data.py`, `backtesting/artifacts.py`, `src/okx_quant/data/candle_store.py`, `sql/migrations/0010_backtest_runs.sql`.
- Context Pack: only `docs/CONTEXT_PACKS/harness-scaffolding.md` exists today; no dedicated performance pack yet.

## Checks run
- `git status --short` -> dirty tree with pre-existing frontend/docs/test changes.
- `git -c safe.directory=C:/quant_strategy branch --show-current` -> `codex/impl-multi-venue-instrument-specs`.
- Read required harness/collaboration/navigation docs and relevant ADRs.
- Static code inspection of API/frontend/data artifact read paths.
- `& 'C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe' scripts/docs/check_doc_metadata.py` -> passed with 14 pre-existing warnings.

## Approvals
- Human approval needed before implementation, especially for any DB schema/storage migration.

## Next action (single, concrete)
- If approved, write the formal design spec under `docs/superpowers/specs/` and implementation plan under `docs/superpowers/plans/`, then implement P0 route timing + pooled DB connection + run-list cache first.

## Human Learning Notes
The slow loading appears systemic rather than one chart bug: many endpoints repeatedly connect to DB and load full artifact payloads before filtering. The smallest useful fix is to stop paying that cost per request; the durable fix is row-oriented artifact reads for time-series data.
