# Design: Market Data Coverage — fetch queue + delete pair

Date: 2026-06-18
Owner of implementation: **Codex** (frontend + API). Claude authored this spec/plan.
Status: approved design, pending implementation plan.

## Problem

In the **Market Data Coverage** card the user can only have one "fetch to DB" job
in flight. Two gaps:

- **(a) Delete outdated pairs.** Exchanges rename/delist (e.g. Binance MATIC → POL).
  There is no UI/API to remove a stale pair; only the `manage_pairs.py purge` CLI.
- **(b) Queue multiple fetches.** Submitting a second fetch is blocked while the first
  runs, because the frontend disables the submit buttons whenever any job is non-terminal
  and only tracks a single `fetchJob`. The backend already runs jobs as background tasks,
  so the block is purely frontend.

## Decisions (locked with user 2026-06-18)

1. **Queue semantics:** sequential — one fetch runs at a time, others wait as `queued`.
   Rationale: concurrent multi-year 1m fetches against the same exchange's public kline
   endpoint risk rate-limit failures.
2. **Delete scope:** whole pair — purge all data for the `inst_id` (all bars), including
   `market_klines` and the local parquet directory, so neither the coverage table nor the
   backtest exchange dropdown shows a ghost pair.
3. **Implementer:** Codex, per `AGENTS.md` ownership (frontend + `src/okx_quant/api/`).

## Scope

Touched files only:

- `src/okx_quant/api/routes_data.py` — queue lock + new delete route.
- `frontend/view-config.js` — `MarketDataCard`: job list + per-row delete button.
- `frontend/data.js` — one new API client method (`deleteDataPair`).
- Tests + docs (see below).

Explicitly **not** touched: any `src/okx_quant/strategies|signals|risk|portfolio|execution`,
`config/`, backtesting engine, `scripts/market_data/manage_pairs.py` (CLI stays as-is; the
new endpoint reuses its SQL shape but does not import it).

## Architecture

Two independent features, both inside `MarketDataCard` (frontend) and `routes_data.py` (API).
No new modules, no new dependencies.

### Feature B — sequential fetch queue

**Backend** (`routes_data.py`):

- Add module-level `_fetch_lock = asyncio.Lock()`.
- `POST /fetch`: initial job status becomes `"queued"` (was `"running"`); message
  "Queued — waiting for running fetch…". Everything else unchanged.
- `_run_fetch(job_id, req, db_dsn)`: wrap the existing body so it acquires the lock first:
  - check `_raise_if_fetch_cancelled(job_id)` (cancel while queued → mark cancelled, never run),
  - `async with _fetch_lock:` then re-check cancel, flip status to `"running"`, run the
    existing fetch body unchanged.
  - The first job acquires immediately; later jobs await the lock and stay `"queued"`.
- `# ponytail: global single fetch lock — one fetch at a time across all sessions; split
  into per-exchange locks only if OKX+Binance parallelism is ever needed.`
- No change to `FETCH_TERMINAL_STATUSES` (`done|error|cancelled`); `queued` is non-terminal.

**Frontend** (`MarketDataCard`):

- Replace single `fetchJob` state with `fetchJobs` (array). Source of truth is
  `GET /fetch/jobs` (already exists). Poll every 2s while any job is non-terminal; stop when
  all terminal. Reuse/extend the existing reconnect effect (it already calls `fetchDataFetchJobs`).
- Submit handlers (`triggerFetch`, `triggerExistingOnlyFetch`): drop the `fetchBusy` disable
  condition on both buttons — keep only `fetchStartPending` (the brief in-flight POST) plus
  form validity (`symbols`/`existingDbFetchSymbols` length, `start < end`). After POST resolves,
  refresh the job list and keep polling.
- Render the job list (replaces the single-job block): one row per job with status chip +
  `ProgressStage` + Cancel (when `running`/`queued`) + the existing results summary line.
  Order: newest first (the endpoint already sorts by `updated_at` desc).
- Skipped: a "clear finished" control — add only if the list gets noisy (client-side filter).

### Feature A — delete pair

**Backend** (`routes_data.py`): new `DELETE /pairs/{inst_id}`.

- Guard 1: `db_dsn` configured, else 503 (match existing routes).
- Guard 2: if any job in `_jobs` is non-terminal and references `inst_id` in its `symbols`,
  return 409 "Pair has an active fetch job; cancel it first." (avoid delete-during-fetch).
- Delete order (FK-safe), all by `inst_id`:
  1. `DELETE FROM market_klines WHERE instrument_id IN
       (SELECT instrument_id FROM market_instruments WHERE canonical_inst_id=$1 OR normalized_symbol=$1)`
  2. `DELETE FROM market_funding_rates WHERE instrument_id IN (… same subselect …)`
  3. `DELETE FROM market_instruments WHERE canonical_inst_id=$1 OR normalized_symbol=$1`
  4. `DELETE FROM canonical_candles WHERE inst_id=$1`
  5. `DELETE FROM raw_candles WHERE inst_id=$1`
  6. `DELETE FROM funding_rates WHERE inst_id=$1`
  7. `DELETE FROM instrument_bars WHERE inst_id=$1`
  8. `DELETE FROM instruments WHERE inst_id=$1`
- Parquet: remove the directory `data/ticks/<inst_id.replace("-", "_")>/` (non-fatal if missing;
  collect into the response like the fetch route handles parquet errors). data dir resolves the
  same way as `_write_fetched_to_parquet` (`_project_root_path() / "data" / "ticks"`).
- Return `{ "inst_id": …, "deleted": { table: rowcount, … }, "parquet_removed": bool,
  "parquet_error": str|None }`.

**Frontend**:

- `frontend/data.js`: `deleteDataPair: (instId) => _del("/api/data/pairs/" + encodeURIComponent(instId))`
  (add a `_del` helper if one is missing; otherwise reuse the existing delete verb).
- `MarketDataCard` coverage table: add a delete (✕/trash) button cell on rows whose
  `data_kind` is `ohlcv` or `funding` (not `external` — those are datasets, not pairs).
  On click: `window.confirm(`Delete ALL data for ${inst_id} across all bars? This cannot be
  undone.`)` → call `deleteDataPair` → on success `refreshCoverage()`; on 409/other show the
  error inline (reuse the existing job/error chip pattern or a small row-level message).
- `# ponytail: native window.confirm, no modal component.`

## Error handling

- Queue: cancel while `queued` must not start the fetch (cancel checked before and after lock
  acquire). Lock is always released via `async with` even on exception/cancel.
- Delete: 409 when an active job references the pair; 503 when no DSN; parquet removal failure
  is non-fatal and surfaced in the response. SQL runs in a single connection; wrap deletes in a
  transaction so a mid-way failure rolls back (no half-deleted pair).

## Testing

- Backend `pytest` (targeted, no live exchange — patch the fetch worker):
  - queue: submit two jobs; assert the second is `queued` while the first holds the lock, then
    runs after release; a `queued` job cancelled before acquire ends `cancelled` and never runs.
  - delete: with seeded rows, `DELETE /pairs/{inst_id}` removes them across all listed tables and
    coverage no longer lists the pair; delete with an active job for that symbol → 409.
- Frontend: `make frontend-check`.
- Manifest/impact: delete is a destructive data-provenance path — run `make docs-impact` and add a
  Change Manifest (`docs/CHANGE_MANIFEST_TEMPLATE.md`); check `docs/DOC_IMPACT_MATRIX.md` rows.

## Doc impact

- `docs/DATA_FLOW.md` — new delete data path (which tables + parquet).
- `docs/UI_MAP.md` — job queue list + per-row delete button + confirm.
- `docs/FEATURE_MAP.md` — Market Data Coverage gains delete + queue.
- `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md` — state/next actions.
- Change Manifest for the delete (data-removal) rule.

## Acceptance criteria

- [ ] While a fetch runs, a second submitted fetch is accepted and shown as `queued`, then runs
      after the first finishes (sequential, never concurrent).
- [ ] `queued` job can be cancelled before it starts and never executes.
- [ ] Each coverage row for an ohlcv/funding pair has a delete button; confirm → pair removed
      from `canonical_candles`, `raw_candles`, `funding_rates`, `instrument_bars`, `instruments`,
      `market_klines`, `market_instruments`, `market_funding_rates`, and its parquet directory.
- [ ] After delete, coverage table and backtest exchange/pair lists no longer show the pair.
- [ ] Deleting a pair with an active fetch job returns 409 and deletes nothing.
- [ ] `make frontend-check` passes; targeted backend pytest passes; `make docs-impact` clean with
      Change Manifest present.

## Risks / known limits

- Global fetch lock serializes ALL fetches (incl. cross-exchange). Acceptable for single-user
  local tool; upgrade path noted in the ponytail comment.
- `_jobs` is in-memory; a server restart loses queued/running state (already true today).
- Delete is irreversible; mitigated by the confirm dialog and the 409 active-job guard.
