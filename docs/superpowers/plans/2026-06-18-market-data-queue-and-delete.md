# Market Data Coverage — Fetch Queue + Delete Pair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Implementer:** Codex (per `AGENTS.md` ownership of frontend + `src/okx_quant/api/`). Commit messages use the `AI-Origin: Codex` trailer.

**Goal:** Let the Market Data Coverage card (a) queue multiple "fetch to DB" jobs that run one-at-a-time instead of blocking, and (b) delete an outdated trading pair and all its data.

**Architecture:** Backend already runs fetch jobs as FastAPI background tasks keyed in an in-memory `_jobs` dict; serialize them behind a single module-level `asyncio.Lock` and expose status via the existing `/fetch/jobs` endpoint. Add a `DELETE /pairs/{inst_id}` route that purges the pair across all DB tables + the local parquet directory. Frontend renders the job list and a per-row delete button; no new dependencies, no modal components.

**Tech Stack:** Python 3 / FastAPI / asyncpg (backend), Preact `htm` no-build frontend (`frontend/view-config.js`, `frontend/data.js`), pytest + `pytest.mark.asyncio` (tests).

## Global Constraints

- PERMITTED files (edit only these): `src/okx_quant/api/routes_data.py`, `frontend/view-config.js`, `frontend/data.js`, `tests/unit/test_routes_data_queue.py` (new), `tests/unit/test_routes_data_delete.py` (new), and the docs listed in Task 5.
- FORBIDDEN (do not touch): `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, `config/`, `backtesting/`, `scripts/market_data/manage_pairs.py`, any backtest result artifact.
- SCOPE LIMIT: implement only queue + delete. Do not refactor adjacent code in `routes_data.py` or `view-config.js` beyond what these two features need.
- Queue is **sequential** — exactly one fetch executes at a time across all sessions (single global lock).
- Delete is **whole-pair** and **irreversible**; it must be guarded by a UI confirm and a backend 409 when an active fetch references the pair.
- Delete must purge, by `inst_id`: `canonical_candles`, `raw_candles`, `funding_rates`, `instrument_bars`, `instruments`, plus `market_klines`, `market_funding_rates`, `market_instruments` (FK order: klines/funding before `market_instruments`), plus the parquet directory `data/ticks/<inst_id with "-"→"_">/`.

---

## File Structure

- `src/okx_quant/api/routes_data.py` — add `_fetch_lock`; split worker into `_run_fetch` (queue wrapper) + `_run_fetch_body` (existing body, renamed); change `POST /fetch` initial status to `queued`; add delete helpers `_pair_delete_statements`, `_remove_pair_parquet`, `_active_job_for_symbol` and route `DELETE /pairs/{inst_id}`.
- `frontend/data.js` — add `deleteDataPair` client method.
- `frontend/view-config.js` (`MarketDataCard`) — track `fetchJobs` array via `/fetch/jobs`; remove the `fetchBusy` submit gate; render job list; add per-row delete button + handler.
- `tests/unit/test_routes_data_queue.py` (new) — queue serialization + cancel-while-queued.
- `tests/unit/test_routes_data_delete.py` (new) — delete SQL plan order, parquet removal, active-job guard.
- Docs (Task 5).

---

### Task 1: Backend — sequential fetch queue

**Files:**
- Modify: `src/okx_quant/api/routes_data.py` (`_jobs` block near line 22; `POST /fetch` handler near lines 287-305; `_run_fetch` at line 1263)
- Test: `tests/unit/test_routes_data_queue.py` (create)

**Interfaces:**
- Produces: `routes_data._fetch_lock: asyncio.Lock`; `async def _run_fetch(job_id, req, db_dsn)` (queue wrapper — sets `queued`, awaits lock, sets `running`, calls body); `async def _run_fetch_body(job_id, req, db_dsn)` (the existing worker, unchanged internals).
- Consumes (existing, unchanged): `_jobs`, `_job_cancel_requested`, `_mark_fetch_cancelled`, `FetchRequest`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_routes_data_queue.py`:

```python
from __future__ import annotations

import asyncio

import pytest

import okx_quant.api.routes_data as routes_data
from okx_quant.api.routes_data import FetchRequest

_REQ = FetchRequest(
    exchange="binance",
    symbols=["BTC-USDT-SWAP"],
    bar="1m",
    start="2024-01-01",
    end="2024-01-02",
)


def _seed_job(job_id: str) -> None:
    routes_data._jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "symbols": ["BTC-USDT-SWAP"],
        "progress": 0,
    }


@pytest.mark.asyncio
async def test_second_fetch_waits_as_queued_until_first_releases(monkeypatch):
    routes_data._jobs.clear()
    gate = asyncio.Event()
    started: list[str] = []

    async def fake_body(job_id, req, db_dsn):
        started.append(job_id)
        await gate.wait()

    monkeypatch.setattr(routes_data, "_run_fetch_body", fake_body)
    _seed_job("job_a")
    _seed_job("job_b")

    ta = asyncio.create_task(routes_data._run_fetch("job_a", _REQ, "postgresql://unused"))
    tb = asyncio.create_task(routes_data._run_fetch("job_b", _REQ, "postgresql://unused"))
    await asyncio.sleep(0.05)

    assert routes_data._jobs["job_a"]["status"] == "running"
    assert routes_data._jobs["job_b"]["status"] == "queued"
    assert started == ["job_a"]

    gate.set()
    await asyncio.gather(ta, tb)
    assert started == ["job_a", "job_b"]


@pytest.mark.asyncio
async def test_cancel_while_queued_skips_execution(monkeypatch):
    routes_data._jobs.clear()
    gate = asyncio.Event()
    started: list[str] = []

    async def fake_body(job_id, req, db_dsn):
        started.append(job_id)
        await gate.wait()

    monkeypatch.setattr(routes_data, "_run_fetch_body", fake_body)
    _seed_job("job_a")
    _seed_job("job_b")

    ta = asyncio.create_task(routes_data._run_fetch("job_a", _REQ, "x"))
    tb = asyncio.create_task(routes_data._run_fetch("job_b", _REQ, "x"))
    await asyncio.sleep(0.05)

    routes_data._jobs["job_b"]["cancel_requested"] = True  # cancel while queued
    gate.set()
    await asyncio.gather(ta, tb)

    assert "job_b" not in started
    assert routes_data._jobs["job_b"]["status"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_routes_data_queue.py -v`
Expected: FAIL — `AttributeError: module 'okx_quant.api.routes_data' has no attribute '_run_fetch_body'`.

- [ ] **Step 3: Add the lock next to `_jobs`**

In `src/okx_quant/api/routes_data.py`, just below `_jobs: dict[str, dict] = {}` (line 22):

```python
_jobs: dict[str, dict] = {}

# ponytail: global single fetch lock — one fetch runs at a time across all
# sessions. Split into per-exchange locks only if OKX+Binance parallelism is
# ever needed.
_fetch_lock = asyncio.Lock()
```

- [ ] **Step 4: Rename the worker and add the queue wrapper**

Rename the existing worker `async def _run_fetch(job_id: str, req: FetchRequest, db_dsn: str) -> None:` (line 1263) to `async def _run_fetch_body(...)` — change ONLY the function name, leave its body unchanged. Then add this wrapper immediately above it:

```python
async def _run_fetch(job_id: str, req: FetchRequest, db_dsn: str) -> None:
    """Queue wrapper: serialize fetches so only one runs at a time."""
    if _job_cancel_requested(job_id):
        _mark_fetch_cancelled(job_id)
        return
    job = _jobs.get(job_id)
    if job is not None:
        job.update({
            "status": "queued",
            "message": "Queued - waiting for running fetch...",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    async with _fetch_lock:
        if _job_cancel_requested(job_id):
            _mark_fetch_cancelled(job_id)
            return
        if job is not None:
            job.update({
                "status": "running",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        await _run_fetch_body(job_id, req, db_dsn)
```

- [ ] **Step 5: Make `POST /fetch` start jobs as `queued`**

In the `trigger_fetch` handler (lines 288-303), change the seeded job's `"status": "running"` to `"status": "queued"` and the `"message"` to reflect queueing:

```python
        _jobs[job_id] = {
            "job_id": job_id,
            "exchange": exchange,
            "existing_only": bool(req.existing_only),
            "status": "queued",
            "progress": 0,
            "message": (
                f"Queued: {exchange.upper()} {len(symbols)} existing DB symbol update..."
                if req.existing_only
                else f"Queued: {exchange.upper()} {len(symbols)} symbol fetch..."
            ),
            "symbols": symbols,
            "symbol_count": len(symbols),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        bg.add_task(_run_fetch, job_id, req, db_dsn)
        return _jobs[job_id]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_routes_data_queue.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Run the existing route tests to confirm no regression**

Run: `python -m pytest tests/unit/test_routes_data_export.py -v`
Expected: PASS (all existing tests still pass).

- [ ] **Step 8: Commit**

```bash
git add src/okx_quant/api/routes_data.py tests/unit/test_routes_data_queue.py
git commit -m "feat(data): serialize market-data fetch jobs behind a queue lock

AI-Origin: Codex"
```

---

### Task 2: Frontend — render job list and unblock submission

**Files:**
- Modify: `frontend/view-config.js` (`MarketDataCard`, lines 1137-1709)

**Interfaces:**
- Consumes: `window.API.fetchDataFetchJobs()` (existing → `GET /api/data/fetch/jobs`, returns job array sorted newest-first), `window.API.triggerDataFetch`, `window.API.cancelDataFetch`, `FETCH_TERMINAL_STATUSES`, `ProgressStage`.
- Produces: a `fetchJobs` array state replacing the single `fetchJob`; submit buttons no longer gated by job activity.

- [ ] **Step 1: Replace single-job state with a job list + poller**

In `MarketDataCard`, replace `const [fetchJob, setFetchJob] = useConfigState(null);` (line 1140) with:

```javascript
  const [fetchJobs, setFetchJobs] = useConfigState([]);
```

Replace the derived flags (lines 1194-1195):

```javascript
  const anyFetchActive = (fetchJobs || []).some((j) => !FETCH_TERMINAL_STATUSES.has(j.status));
```

Replace the reconnect effect (lines 1264-1300) and the per-submit interval logic with a single list poller. Add this effect (keep it near the other `useConfigEffect`s):

```javascript
  function refreshFetchJobs() {
    return window.API.fetchDataFetchJobs?.()
      .then((jobs) => { setFetchJobs(jobs || []); return jobs || []; })
      .catch(() => []);
  }

  useConfigEffect(() => {
    let stopped = false;
    let intervalId = null;
    const tick = () => {
      refreshFetchJobs().then((jobs) => {
        if (stopped) return;
        const active = (jobs || []).some((j) => !FETCH_TERMINAL_STATUSES.has(j.status));
        if (active && intervalId == null) {
          intervalId = setInterval(tick, 2000);
        } else if (!active && intervalId != null) {
          clearInterval(intervalId);
          intervalId = null;
          refreshCoverage();
        }
      });
    };
    tick();
    return () => {
      stopped = true;
      if (intervalId != null) clearInterval(intervalId);
    };
  }, []);
```

- [ ] **Step 2: Simplify `startFetch` to enqueue and refresh the list**

Replace `startFetch` (lines 1310-1348) with:

```javascript
  function startFetch(body) {
    setFetchStartPending(true);
    window.API.triggerDataFetch(body)
      .then(() => refreshFetchJobs())
      .catch((err) => {
        setFetchJobs((jobs) => [
          { job_id: `err-${Date.now()}`, status: "error", progress: 0,
            message: err?.message || "Fetch request failed" },
          ...(jobs || []),
        ]);
      })
      .finally(() => {
        setFetchStartPending(false);
        // ensure the 2s poller is running for the newly queued job
        refreshFetchJobs();
      });
  }
```

Remove the now-unused `localStorage` `activeDataFetchJobId` reads/writes inside this component (they referenced the single-job model). Leave `FETCH_TERMINAL_STATUSES` as-is.

- [ ] **Step 3: Point cancel at a specific job id**

Replace `cancelFetchJob` (lines 1350-1370) with a version that takes a `jobId`:

```javascript
  function cancelFetchJob(jobId) {
    if (!jobId || !window.API.cancelDataFetch) return;
    window.API.cancelDataFetch(jobId)
      .then(() => refreshFetchJobs())
      .catch(() => refreshFetchJobs());
  }
```

- [ ] **Step 4: Unblock the submit buttons**

In the buttons (lines 1650-1668), change the `disabled` expressions to drop the `fetchBusy` term:

```javascript
            <button class="btn primary sm"
              disabled=${fetchStartPending || !(fetchForm.symbols || []).length || fetchForm.start >= fetchForm.end}
              onClick=${triggerFetch}>
              Confirm and Fetch to DB
            </button>
            <button class="btn sm"
              disabled=${fetchStartPending || !existingDbFetchSymbols.length || fetchForm.start >= fetchForm.end}
              onClick=${triggerExistingOnlyFetch}>
              Update DB Pairs Only (${existingDbFetchSymbols.length})
            </button>
```

Delete the old single-`fetchJob` `${fetchCanCancel && ...}` cancel button block (it is replaced by per-job cancel in Step 5).

- [ ] **Step 5: Render the job list (replaces the single-job block)**

Replace the single-job progress block (lines 1642-1649) and the single results block (lines 1669-1673) with a list:

```javascript
          ${(fetchJobs || []).length > 0 && html`
            <div class="field" style=${{ marginTop: 12 }}>
              <div class="field-label">Fetch jobs</div>
              ${fetchJobs.map((job) => html`
                <div key=${job.job_id} class="row" style=${{ gap: 12, alignItems: "center", marginBottom: 6, flexWrap: "wrap" }}>
                  <span class=${`chip ${job.status === "done" ? "profit" : job.status === "error" ? "loss" : "warn"}`}>
                    ${job.status}
                  </span>
                  <${ProgressStage} job=${job} />
                  ${["running", "queued", "cancelling"].includes(job.status) && html`
                    <button class="btn ghost sm"
                      disabled=${job.status === "cancelling"}
                      onClick=${() => cancelFetchJob(job.job_id)}>
                      ${job.status === "cancelling" ? "Cancelling..." : "Cancel"}
                    </button>
                  `}
                  ${job.results?.length > 0 && html`
                    <span class="field-hint">
                      ${job.results.map((r) => `${(r.exchange || "").toUpperCase()} ${r.symbol}: ${r.rows?.toLocaleString?.() ?? r.rows} rows`).join(" - ")}
                    </span>
                  `}
                </div>
              `)}
            </div>
          `}
```

- [ ] **Step 6: Static check**

Run: `make frontend-check`
Expected: PASS (no syntax/lint errors reported for `view-config.js`).

- [ ] **Step 7: Manual smoke (record result in the commit body)**

With a DB-backed server running: open Config → Market Data Coverage → + Add Pair Data. Search POL, select, Confirm and Fetch. While it shows `running`, search SHIB, select 1000SHIB, Confirm and Fetch again. Expected: second job appears as `queued`, the submit button was NOT disabled, and the second job flips to `running` only after the first reaches a terminal status. If no DB is available, note "manual smoke skipped: no DB" explicitly.

- [ ] **Step 8: Commit**

```bash
git add frontend/view-config.js
git commit -m "feat(frontend): show market-data fetch job queue, allow stacking jobs

AI-Origin: Codex"
```

---

### Task 3: Backend — delete pair endpoint

**Files:**
- Modify: `src/okx_quant/api/routes_data.py` (add route in `make_data_router` after the `fetch/jobs` route ~line 334; add module helpers near the other `_*` helpers)
- Test: `tests/unit/test_routes_data_delete.py` (create)

**Interfaces:**
- Produces:
  - `def _pair_delete_statements(inst_id: str) -> list[tuple[str, list]]` — ordered `(sql, params)` deletes, FK-safe.
  - `def _active_job_for_symbol(inst_id: str) -> bool` — True if any non-terminal job in `_jobs` lists `inst_id` in its `symbols`.
  - `def _remove_pair_parquet(inst_id: str, ticks_dir) -> tuple[bool, str | None]` — `(removed, error)`; deletes `ticks_dir/<inst_id with "-"→"_">/` recursively, non-fatal.
  - Route `DELETE /pairs/{inst_id}` returning `{"inst_id", "deleted": {table: count}, "parquet_removed": bool, "parquet_error": str | None}`.
- Consumes: `_jobs`, `FETCH_TERMINAL_STATUSES`-equivalent terminal set (define `_TERMINAL_FETCH_STATUSES = {"done", "error", "cancelled"}` at module scope), `_project_root_path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_routes_data_delete.py`:

```python
from __future__ import annotations

import pytest

import okx_quant.api.routes_data as routes_data


def test_pair_delete_statements_order_and_keys():
    stmts = routes_data._pair_delete_statements("MATIC-USDT-SWAP")
    tables = [sql.split("FROM")[1].split()[0] for sql, _ in stmts]
    # market_klines and market_funding_rates must be deleted before market_instruments (FK).
    assert tables.index("market_klines") < tables.index("market_instruments")
    assert tables.index("market_funding_rates") < tables.index("market_instruments")
    # All canonical/raw/funding/registry tables present.
    for t in ("canonical_candles", "raw_candles", "funding_rates",
              "instrument_bars", "instruments", "market_instruments"):
        assert t in tables
    # Every statement is parameterized with the inst_id.
    for _sql, params in stmts:
        assert params == ["MATIC-USDT-SWAP"]


def test_active_job_for_symbol_detects_running_job():
    routes_data._jobs.clear()
    routes_data._jobs["j1"] = {"job_id": "j1", "status": "running", "symbols": ["MATIC-USDT-SWAP"]}
    assert routes_data._active_job_for_symbol("MATIC-USDT-SWAP") is True
    assert routes_data._active_job_for_symbol("BTC-USDT-SWAP") is False
    routes_data._jobs["j1"]["status"] = "done"
    assert routes_data._active_job_for_symbol("MATIC-USDT-SWAP") is False


def test_remove_pair_parquet_deletes_inst_directory(tmp_path):
    inst_dir = tmp_path / "MATIC_USDT_SWAP"
    inst_dir.mkdir()
    (inst_dir / "candles_1m.parquet").write_bytes(b"x")
    removed, error = routes_data._remove_pair_parquet("MATIC-USDT-SWAP", tmp_path)
    assert removed is True
    assert error is None
    assert not inst_dir.exists()


def test_remove_pair_parquet_missing_dir_is_non_fatal(tmp_path):
    removed, error = routes_data._remove_pair_parquet("GHOST-USDT-SWAP", tmp_path)
    assert removed is False
    assert error is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_routes_data_delete.py -v`
Expected: FAIL — `AttributeError: ... has no attribute '_pair_delete_statements'`.

- [ ] **Step 3: Add the helpers**

In `src/okx_quant/api/routes_data.py`, near the other module helpers (e.g. after `_project_root_path`, ~line 1052), add:

```python
_TERMINAL_FETCH_STATUSES = {"done", "error", "cancelled"}


def _pair_delete_statements(inst_id: str) -> list[tuple[str, list]]:
    sub = (
        "instrument_id IN (SELECT instrument_id FROM market_instruments "
        "WHERE canonical_inst_id=$1 OR normalized_symbol=$1)"
    )
    return [
        (f"DELETE FROM market_klines WHERE {sub}", [inst_id]),
        (f"DELETE FROM market_funding_rates WHERE {sub}", [inst_id]),
        ("DELETE FROM market_instruments WHERE canonical_inst_id=$1 OR normalized_symbol=$1", [inst_id]),
        ("DELETE FROM canonical_candles WHERE inst_id=$1", [inst_id]),
        ("DELETE FROM raw_candles WHERE inst_id=$1", [inst_id]),
        ("DELETE FROM funding_rates WHERE inst_id=$1", [inst_id]),
        ("DELETE FROM instrument_bars WHERE inst_id=$1", [inst_id]),
        ("DELETE FROM instruments WHERE inst_id=$1", [inst_id]),
    ]


def _active_job_for_symbol(inst_id: str) -> bool:
    target = str(inst_id or "").upper()
    for job in _jobs.values():
        if job.get("status") in _TERMINAL_FETCH_STATUSES:
            continue
        symbols = [str(s or "").upper() for s in (job.get("symbols") or [])]
        if target in symbols:
            return True
    return False


def _remove_pair_parquet(inst_id: str, ticks_dir) -> tuple[bool, str | None]:
    import shutil
    from pathlib import Path as _Path

    inst_dir = _Path(ticks_dir) / str(inst_id).replace("-", "_")
    if not inst_dir.exists():
        return (False, None)
    try:
        shutil.rmtree(inst_dir)
        return (True, None)
    except Exception as exc:  # non-fatal — surfaced in the response
        return (False, str(exc))
```

Note for the implementer: `_pair_delete_statements` uses table names immediately after `FROM` so the test's `split("FROM")[1].split()[0]` extracts them — keep `DELETE FROM <table> WHERE ...` shape.

- [ ] **Step 4: Add the route**

Inside `make_data_router`, after the `fetch_jobs` route (line 334, before `return router`):

```python
    @router.delete("/pairs/{inst_id}")
    async def delete_pair(inst_id: str):
        if not db_dsn:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        inst_id = str(inst_id or "").strip()
        if not inst_id:
            raise HTTPException(status_code=400, detail="inst_id is required")
        if _active_job_for_symbol(inst_id):
            raise HTTPException(status_code=409, detail="Pair has an active fetch job; cancel it first")
        import asyncpg

        deleted: dict[str, int] = {}
        conn = await asyncpg.connect(db_dsn)
        try:
            async with conn.transaction():
                for sql, params in _pair_delete_statements(inst_id):
                    table = sql.split("FROM")[1].split()[0]
                    status = await conn.execute(sql, *params)
                    deleted[table] = int(status.rsplit(" ", 1)[-1]) if status.startswith("DELETE") else 0
        finally:
            await conn.close()
        ticks_dir = _project_root_path() / "data" / "ticks"
        parquet_removed, parquet_error = _remove_pair_parquet(inst_id, ticks_dir)
        return {
            "inst_id": inst_id,
            "deleted": deleted,
            "parquet_removed": parquet_removed,
            "parquet_error": parquet_error,
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_routes_data_delete.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Run the full route test set for no regressions**

Run: `python -m pytest tests/unit/test_routes_data_export.py tests/unit/test_routes_data_queue.py tests/unit/test_routes_data_delete.py -v`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add src/okx_quant/api/routes_data.py tests/unit/test_routes_data_delete.py
git commit -m "feat(data): add DELETE /api/data/pairs/{inst_id} to purge a trading pair

AI-Origin: Codex"
```

---

### Task 4: Frontend — delete button + confirm

**Files:**
- Modify: `frontend/data.js` (API map, near `deleteRun` line 396)
- Modify: `frontend/view-config.js` (`MarketDataCard` coverage table, lines 1677-1706)

**Interfaces:**
- Produces: `window.API.deleteDataPair(instId)` → `DELETE /api/data/pairs/{instId}`, resolves to the response JSON or throws `Error(detail)`.
- Consumes: `refreshCoverage()` (existing).

- [ ] **Step 1: Add the API client method**

In `frontend/data.js`, in the returned object near `deleteRun` (line 396):

```javascript
    deleteDataPair: async (instId) => {
      const r = await fetch("/api/data/pairs/" + encodeURIComponent(instId), { method: "DELETE" });
      const payload = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(payload.detail || ("HTTP " + r.status));
      return payload;
    },
```

- [ ] **Step 2: Add a delete handler in `MarketDataCard`**

Add near the other handlers (e.g. after `refreshCoverage`, line 1199):

```javascript
  const [deletePending, setDeletePending] = useConfigState("");

  function deletePair(instId) {
    if (!instId || !window.API.deleteDataPair) return;
    if (!window.confirm(`Delete ALL data for ${instId} across all bars? This cannot be undone.`)) return;
    setDeletePending(instId);
    window.API.deleteDataPair(instId)
      .then(() => refreshCoverage())
      .catch((err) => window.alert(`Delete failed: ${err?.message || "request failed"}`))
      .finally(() => setDeletePending(""));
  }
```

- [ ] **Step 3: Add a delete column to the coverage table**

In the coverage table header (lines 1680-1684), add a trailing header cell:

```javascript
              <th class="num">Gaps</th>
              <th></th>
```

In each coverage row (lines 1687-1699), add a trailing cell with a delete button for ohlcv/funding rows only:

```javascript
                <td class="num" style=${{ color: row.gap_count > 0 ? "var(--warn)" : "var(--profit)" }}>
                  ${row.gap_count ?? "-"}
                </td>
                <td class="num">
                  ${["ohlcv", "funding"].includes(row.data_kind || (row.bar === "funding" ? "funding" : "ohlcv")) && html`
                    <button class="btn ghost sm"
                      title="Delete all data for this pair"
                      disabled=${deletePending === row.inst_id}
                      onClick=${() => deletePair(row.inst_id)}>
                      ${deletePending === row.inst_id ? "Deleting..." : "Delete"}
                    </button>
                  `}
                </td>
```

Update the empty-state `colSpan` (line 1702) from `8` to `9`.

- [ ] **Step 4: Static check**

Run: `make frontend-check`
Expected: PASS.

- [ ] **Step 5: Manual smoke (record result in the commit body)**

With a DB-backed server: in Market Data Coverage, click Delete on a disposable pair row, confirm the dialog. Expected: the pair disappears from the coverage table on refresh, and it no longer appears in the Run Backtest pair/exchange dropdown. If no DB is available, note "manual smoke skipped: no DB".

- [ ] **Step 6: Commit**

```bash
git add frontend/data.js frontend/view-config.js
git commit -m "feat(frontend): add delete-pair button to Market Data Coverage

AI-Origin: Codex"
```

---

### Task 5: Docs, Change Manifest, and impact check

**Files:**
- Modify: `docs/DATA_FLOW.md`, `docs/UI_MAP.md`, `docs/FEATURE_MAP.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`
- Create: `docs/CHANGE_MANIFESTS/2026-06-18-delete-trading-pair.md` (from `docs/CHANGE_MANIFEST_TEMPLATE.md`)

**Interfaces:** none (documentation).

- [ ] **Step 1: Update the data/UI/feature docs**

- `docs/DATA_FLOW.md`: add the delete path — `DELETE /api/data/pairs/{inst_id}` purges `canonical_candles`, `raw_candles`, `funding_rates`, `instrument_bars`, `instruments`, `market_klines`, `market_funding_rates`, `market_instruments`, and the `data/ticks/<inst>/` parquet directory.
- `docs/UI_MAP.md`: Market Data Coverage now lists fetch jobs (queued/running/done/error/cancelled, per-job cancel) and has a per-row Delete button with a confirm dialog.
- `docs/FEATURE_MAP.md`: note the queue + delete behavior and the owning files (`routes_data.py`, `view-config.js`, `data.js`).
- `docs/AI_HANDOFF.md` and `docs/CURRENT_STATE.md`: record current state + next actions.

- [ ] **Step 2: Create the Change Manifest**

Copy `docs/CHANGE_MANIFEST_TEMPLATE.md` to `docs/CHANGE_MANIFESTS/2026-06-18-delete-trading-pair.md` and fill it: the rule change is "operators can hard-delete a trading pair and all its data via the API/UI" (destructive data-provenance path); list affected tables + parquet; reference the 409 active-job guard and the UI confirm as safeguards.

- [ ] **Step 3: Run the doc impact check**

Run: `make docs-impact`
Expected: advisory output clean, or the delete rows acknowledged by the new manifest. If it flags missing rows, add them to `docs/DOC_IMPACT_MATRIX.md` and re-run.

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs(data): record fetch queue + delete-pair behavior and manifest

AI-Origin: Codex"
```

---

## Self-Review

**Spec coverage:**
- Queue (sequential lock, queued status, cancel-while-queued) → Task 1. ✓
- Frontend stacking + job list + per-job cancel → Task 2. ✓
- Delete endpoint (all tables FK-safe + parquet + 409 guard + 503) → Task 3. ✓
- Frontend delete button + confirm + external-row exclusion → Task 4. ✓
- Tests (queue serialization, cancel, delete SQL order, parquet, active-job) → Tasks 1 & 3. ✓
- `make frontend-check` → Tasks 2 & 4. ✓
- Doc impact + Change Manifest → Task 5. ✓
- Error handling: 409/503, transactional deletes, non-fatal parquet → Task 3 route + helpers. ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code; commands have expected output. ✓

**Type consistency:** `_run_fetch`/`_run_fetch_body`, `_pair_delete_statements` (`list[tuple[str, list]]`), `_remove_pair_parquet` (`tuple[bool, str|None]`), `_active_job_for_symbol` (`bool`), `deleteDataPair`, `fetchJobs`, `refreshFetchJobs`, `deletePair`, `deletePending` — names used consistently across tasks. ✓

**Known minor:** Task 2 removes the `localStorage.activeDataFetchJobId` single-job reconnect; the new `/fetch/jobs` poller supersedes it (jobs survive refresh server-side as long as the process lives). No behavior lost.
