# Context Handoff: Market Data Queue + Delete Pair - 2026-06-22

## Goal (one sentence)
Implement Market Data Coverage fetch queueing plus guarded whole-pair deletion per `docs/superpowers/plans/2026-06-18-market-data-queue-and-delete.md`.

## Current state
- Branch: `codex/impl-multi-venue-instrument-specs`.
- Last known good commit / state: branch already carried ADR-0007 P1 and price-chart integration; this session adds uncommitted Market Data Coverage queue/delete changes.
- In-progress edits (files): `src/okx_quant/api/routes_data.py`, `frontend/view-config.js`, `frontend/data.js`, `tests/unit/test_routes_data_queue.py`, `tests/unit/test_routes_data_delete.py`, docs and manifest listed in the session handoff.
- What works right now: targeted backend tests pass; frontend modules pass `node --check`; docs metadata/link/impact checks pass or warn only on pre-existing lifecycle metadata gaps.
- What does not work / unfinished: no DB-backed browser smoke was run in this sandbox; `make` is unavailable in this shell, so Makefile targets were run via equivalent underlying commands.

## Decisions made (and why)
- Kept a single module-level fetch lock because the approved design chose sequential global fetches to avoid exchange rate-limit failures; would change if cross-exchange parallel fetches become a real need.
- Used native `window.confirm` / `window.alert` for deletion feedback because no modal component is needed for this local operations tool.
- Drove the frontend poller from active job-list state because the original plan's mount-only poller could miss a newly queued job when no job was active at page load.

## Open questions / unverified assumptions
- DB-backed browser smoke remains unverified: queue two real fetches, cancel a queued fetch, and delete a disposable pair.

## Rules in play (preserve verbatim)
- Invariants touched: R6.2 reviewed; no invariant text changed.
- Domain rules touched: R6 data provenance/source agreement, because DB rows and parquet mirrors must be removed together for a hard-delete.
- Do-not-touch: `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`, `backtesting/`, `scripts/market_data/manage_pairs.py`, existing result artifacts, deployment gates.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, and the queue/delete spec + plan under `docs/superpowers/`.
- Owning files / MODULE_BRIEFS: `src/okx_quant/api/routes_data.py`, `frontend/view-config.js`, `frontend/data.js`, `tests/unit/test_routes_data_queue.py`, `tests/unit/test_routes_data_delete.py`.
- Context Pack: no dedicated market-data pack exists; use `docs/CONTEXT_INDEX.md` plus the Market Data Ingestion row in `docs/FEATURE_MAP.md`.

## Checks run
- `python -m pytest -p no:cacheprovider tests/unit/test_routes_data_queue.py tests/unit/test_routes_data_delete.py tests/unit/test_routes_data_export.py -v` - passed, 18 tests.
- `node --check` on all Makefile `FRONTEND_JS` files - passed.
- `python scripts/docs/check_doc_metadata.py` - passed with 14 pre-existing metadata warnings.
- `python scripts/docs/check_feature_map_links.py` - passed.
- `python scripts/docs/check_doc_impact.py` with `GIT_CONFIG_* safe.directory` env - passed, 13 changed files and no impact-matrix violations.

## Approvals
- Human approval needed / obtained: scope was explicitly provided by the user via approved spec and plan; human still needs to approve merge and manual DB smoke evidence.

## Next action (single, concrete)
- Run a DB-backed browser smoke: queue two fetches, cancel one queued fetch, delete a disposable OHLCV/funding pair, and verify coverage/backtest pair lists refresh.

## Human Learning Notes
The plan was mostly executable, but the frontend poller needed one correction: a mount-only poller misses jobs submitted after the page initially has no active fetches. Also, `docs-impact` can silently see no changed files if裸 `git` hits safe-directory protection; injecting `GIT_CONFIG_* safe.directory` lets the script inspect the actual working tree without writing global config.
