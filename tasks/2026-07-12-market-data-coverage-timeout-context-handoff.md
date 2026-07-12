---
status: current
type: handoff
owner: codex
created: 2026-07-12
last_reviewed: 2026-07-12
expires: 2026-10-12
superseded_by: null
---

# Context Handoff: Market Data Coverage timeout - 2026-07-12

## Goal (one sentence)
Make Market Data Coverage load reliably without hiding existing DB data behind the frontend's 10-second timeout.

## Current state
- Branch: `codex/pipeline-batch1-stage3`.
- Last known good state: dirty working tree contained unrelated Deribit/OI/Turtle work before this session; no commit made.
- In-progress edits: `src/okx_quant/api/routes_data.py`, `tests/unit/test_routes_data_delete.py`, current-state docs, failure-mode registry, workstream sync, and this handoff pair.
- What works: real-DB in-process `GET /api/data/coverage` returns 133 rows in 2.23 seconds; targeted tests pass.
- What works now: the stale `127.0.0.1:8080` process was stopped; localhost reaches the current engine and coverage returns HTTP 200 in 2.33 seconds.
- External export filters the refresh pre-step to selected `yahoo_finance` datasets; DB-only selections download existing rows directly with no skipped count.
- Unfinished: demo private-WS authentication returns OKX `60005 Invalid apiKey`; a valid Demo Trading API key is required before engine restart.

## Decisions made (and why)
- Keep the frontend timeout unchanged and optimize the shared API query because raising the timeout would retain the full-table bottleneck.
- Reuse the existing `(dataset_id, observed_at)` index with a LATERAL aggregate; no cache, schema, migration, or dependency was added.
- Treat private authentication errors as terminal because retrying the same invalid credentials cannot recover and incorrectly consumes reconnect-breaker attempts.

## Open questions / unverified assumptions
- None for correctness; production timing after the user's API restart should remain below 10 seconds under normal DB load.

## Rules in play (preserve verbatim)
- Invariants touched: none; returned coverage semantics and exact row counts are unchanged.
- Domain rules touched: none.
- Do-not-touch: `research/`, `results/**`, strategy/signal/risk/portfolio/execution code, DB schema, differential validation, and demo/shadow/live gates.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`.
- Owning files: `docs/FEATURE_MAP.md` Market Data Ingestion / Backtest Run UI; `src/okx_quant/api/routes_data.py`.
- Context Pack: no dedicated data/API context pack exists; `docs/CONTEXT_PACKS/README.md` was read.

## Checks run
- Targeted pytest: 10 passed; one non-fatal `.pytest_cache` permission warning.
- Real-DB baseline: running API 9.41-9.78 seconds; query segments 0.016s OHLCV, 0.400s funding, 5.037s current external aggregate.
- Real-DB candidate external query: 1.756 seconds.
- Real-DB in-process fixed endpoint: HTTP 200, 2.231 seconds, 133 rows.
- Old/new external coverage payload parity: 44 datasets exact.
- Duplicate-server check: stale PID 24156 owned `127.0.0.1:8080`; current engine owned `0.0.0.0:8080`. After stopping the stale PID, localhost status reports demo mode and coverage is HTTP 200 in 2.33 seconds.
- Read-only OKX demo WS login probe: both URL variants returned `60005 Invalid apiKey`; no order was submitted.
- Private auth regression: `tests/unit/test_market_data_handler.py` - 3 passed.
- Real corrected-handler probe: logged `code=60005 msg=Invalid apiKey` once, returned with zero reconnects, and submitted no order.
- External export regression: targeted frontend test passed and `node --check frontend/view-config.js` passed.
- Combined frontend/backend external-export refresh tests: 6 passed / 44 deselected; served `view-config.js` contains the new DB-only branch.

## Approvals
- User explicitly requested diagnosis and repair. No deployment, schema, strategy, or destructive action was taken.

## Next action (single, concrete)
- Reload Market Data Coverage now; before restarting trading-engine mode, create/configure a valid OKX Demo Trading API key.

## Human Learning Notes
The browser message had two operational causes: a slow aggregate and a stale duplicate server. Separately, private WS `60005` is a credential/environment error and must never be handled as a transient reconnect.
