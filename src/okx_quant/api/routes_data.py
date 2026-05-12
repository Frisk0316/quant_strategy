"""
Market data coverage and fetch endpoints.

GET  /api/data/coverage
POST /api/data/fetch
GET  /api/data/fetch/status/{job_id}
"""
from __future__ import annotations

import asyncio
import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

_jobs: dict[str, dict] = {}


class FetchRequest(BaseModel):
    symbol: str | None = None
    symbols: list[str] = Field(default_factory=list)
    bar: str
    start: str
    end: str


def make_data_router(db_dsn: str | None = None) -> APIRouter:
    router = APIRouter()

    @router.get("/instruments")
    async def get_instruments(inst_type: str = "SWAP", quote_ccy: str = "USDT"):
        from okx_quant.data.exchange_clients.okx_public import OKXPublicClient

        client = OKXPublicClient()
        try:
            raw = await asyncio.to_thread(client.get_instruments, inst_type)
        finally:
            client.close()
        rows = []
        for item in raw:
            inst_id = item.get("instId") or ""
            inferred_quote = item.get("quoteCcy") or item.get("settleCcy")
            if quote_ccy and inferred_quote != quote_ccy and f"-{quote_ccy}-" not in inst_id:
                continue
            list_time_ms = _safe_int(item.get("listTime"))
            base_ccy = item.get("baseCcy") or inst_id.split("-")[0]
            rows.append({
                "inst_id": inst_id,
                "inst_type": item.get("instType"),
                "base_ccy": base_ccy,
                "quote_ccy": inferred_quote,
                "settle_ccy": item.get("settleCcy"),
                "state": item.get("state"),
                "list_time_ms": list_time_ms,
                "list_date": _ms_to_date(list_time_ms),
            })
        rows.sort(key=lambda r: r["inst_id"] or "")
        return rows

    @router.get("/coverage")
    async def get_coverage():
        if not db_dsn:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        import asyncpg

        conn = await asyncpg.connect(db_dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT inst_id, bar,
                       MIN(ts) AS first_ts, MAX(ts) AS last_ts,
                       COUNT(*) AS row_count
                FROM canonical_candles
                GROUP BY inst_id, bar
                ORDER BY inst_id, bar
                """
            )
            fr = await conn.fetch(
                """
                SELECT inst_id, 'funding' AS bar,
                       MIN(ts) AS first_ts, MAX(ts) AS last_ts,
                       COUNT(*) AS row_count
                FROM funding_rates
                GROUP BY inst_id
                ORDER BY inst_id
                """
            )
            return [{**dict(r), "gap_count": 0} for r in rows] + [
                {**dict(r), "gap_count": 0} for r in fr
            ]
        finally:
            await conn.close()

    @router.get("/export")
    async def export_ohlcv(symbols: str, bar: str = "1m", start: str = "", end: str = ""):
        if not db_dsn:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        inst_ids = [s.strip() for s in symbols.split(",") if s.strip()]
        if not inst_ids:
            raise HTTPException(status_code=400, detail="At least one symbol is required")
        if not start or not end:
            raise HTTPException(status_code=400, detail="start and end are required")
        start_dt = _parse_utc(start)
        end_dt = _parse_utc(end)
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="start must be earlier than end")

        filename = _export_filename(inst_ids, bar, start_dt, end_dt)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(
            _stream_ohlcv_csv(db_dsn, inst_ids, bar, start_dt, end_dt),
            media_type="text/csv",
            headers=headers,
        )

    @router.post("/fetch")
    async def trigger_fetch(req: FetchRequest, bg: BackgroundTasks):
        if not db_dsn:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        symbols = _request_symbols(req)
        if not symbols:
            raise HTTPException(status_code=400, detail="At least one symbol is required")
        job_id = str(uuid.uuid4())[:8]
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 0,
            "message": f"Starting {len(symbols)} symbol fetch...",
            "symbols": symbols,
        }
        bg.add_task(_run_fetch, job_id, req, db_dsn)
        return {"job_id": job_id, "status": "running"}

    @router.get("/fetch/status/{job_id}")
    async def fetch_status(job_id: str):
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return _jobs[job_id]

    return router


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ms_to_date(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _export_filename(inst_ids: list[str], bar: str, start: datetime, end: datetime) -> str:
    symbol_part = inst_ids[0].replace("-", "")
    if len(inst_ids) > 1:
        symbol_part = f"{symbol_part}_plus{len(inst_ids) - 1}"
    return f"ohlcv_{symbol_part}_{bar}_{start.date()}_{end.date()}.csv"


async def _stream_ohlcv_csv(
    db_dsn: str,
    inst_ids: list[str],
    bar: str,
    start: datetime,
    end: datetime,
):
    import asyncpg

    conn = await asyncpg.connect(db_dsn)
    output = io.StringIO()
    writer = csv.writer(output)
    columns = [
        "ts",
        "inst_id",
        "bar",
        "open",
        "high",
        "low",
        "close",
        "vol_contract",
        "vol_base",
        "vol_quote",
        "source_primary",
        "quality_status",
    ]
    try:
        writer.writerow(columns)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        async with conn.transaction():
            pending = 0
            async for row in conn.cursor(
                """
                SELECT
                    ts,
                    inst_id,
                    bar,
                    open,
                    high,
                    low,
                    close,
                    vol_contract,
                    vol_base,
                    vol_quote,
                    source_primary,
                    quality_status
                FROM canonical_candles
                WHERE inst_id = ANY($1::text[])
                  AND bar = $2
                  AND ts >= $3
                  AND ts < $4
                ORDER BY inst_id, ts
                """,
                inst_ids,
                bar,
                start,
                end,
                prefetch=10_000,
            ):
                writer.writerow([
                    row["ts"].isoformat(),
                    row["inst_id"],
                    row["bar"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["vol_contract"],
                    row["vol_base"],
                    row["vol_quote"],
                    row["source_primary"],
                    row["quality_status"],
                ])
                pending += 1
                if pending >= 10_000:
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)
                    pending = 0
            if pending:
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
    finally:
        await conn.close()


def _request_symbols(req: FetchRequest) -> list[str]:
    symbols = list(req.symbols or [])
    if req.symbol:
        symbols.append(req.symbol)
    seen = set()
    return [s for s in symbols if s and not (s in seen or seen.add(s))]


def _instrument_map(raw: list[dict]) -> dict[str, dict]:
    return {r.get("instId"): r for r in raw if r.get("instId")}


async def _run_fetch(job_id: str, req: FetchRequest, db_dsn: str) -> None:
    try:
        import asyncpg

        from okx_quant.data.candle_store import CandleStore
        from okx_quant.data.exchange_clients.okx_public import OKXPublicClient

        symbols = _request_symbols(req)
        requested_start_dt = datetime.fromisoformat(req.start).replace(tzinfo=timezone.utc)
        end_dt = datetime.fromisoformat(req.end).replace(tzinfo=timezone.utc)
        end_ms = int(end_dt.timestamp() * 1000)

        _jobs[job_id]["message"] = f"Loading OKX instrument metadata..."
        client = OKXPublicClient()
        try:
            instruments = _instrument_map(await asyncio.to_thread(client.get_instruments, "SWAP"))
            fetched: list[dict] = []
            total = len(symbols)
            for idx, symbol in enumerate(symbols, start=1):
                meta = instruments.get(symbol, {})
                list_time_ms = _safe_int(meta.get("listTime"))
                list_dt = (
                    datetime.fromtimestamp(list_time_ms / 1000, tz=timezone.utc)
                    if list_time_ms else requested_start_dt
                )
                start_dt = max(requested_start_dt, list_dt)
                if start_dt >= end_dt:
                    fetched.append({
                        "symbol": symbol,
                        "status": "skipped",
                        "rows": 0,
                        "list_date": _ms_to_date(list_time_ms),
                        "message": "Listing date is after requested end date",
                    })
                    continue

                start_ms = int(start_dt.timestamp() * 1000)
                _jobs[job_id].update({
                    "progress": int(((idx - 1) / total) * 90),
                    "message": f"Fetching {symbol} {req.bar} from OKX ({idx}/{total})...",
                    "current_symbol": symbol,
                })
                candles = await asyncio.to_thread(
                    client.paginate_history,
                    symbol,
                    req.bar,
                    start_ms,
                    end_ms,
                )

                pool = await asyncpg.create_pool(db_dsn, min_size=1, max_size=3)
                try:
                    store = CandleStore(pool)
                    base_ccy = symbol.split("-")[0]
                    await store.register_instrument(inst_id=symbol, base_ccy=base_ccy)
                    await store.register_instrument_bar(inst_id=symbol, bar=req.bar)
                    await store.upsert_raw_candles(candles, source="okx", inst_id=symbol, bar=req.bar)
                    await store.canonicalize_from_raw(
                        source="okx",
                        inst_id=symbol,
                        bar=req.bar,
                        start=start_dt,
                        end=end_dt,
                    )
                    await store.update_instrument_bar_bounds(symbol, req.bar)
                finally:
                    await pool.close()

                fetched.append({
                    "symbol": symbol,
                    "status": "done",
                    "rows": len(candles),
                    "list_date": _ms_to_date(list_time_ms),
                    "effective_start": start_dt.date().isoformat(),
                })
        finally:
            client.close()

        _jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": f"Fetched {len(fetched)} symbol(s) for {req.bar}",
            "results": fetched,
        })
    except Exception as exc:
        _jobs[job_id].update({"status": "error", "message": str(exc)})
