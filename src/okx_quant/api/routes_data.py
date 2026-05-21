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
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

_jobs: dict[str, dict] = {}


class FetchRequest(BaseModel):
    symbol: str | None = None
    symbols: list[str] = Field(default_factory=list)
    bar: str
    start: str
    end: str


class ExternalRefreshRequest(BaseModel):
    dataset_id: str | None = None
    dataset_ids: list[str] = Field(default_factory=list)
    start: str = ""
    end: str = ""


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
            external = await _fetch_external_coverage(conn)
            return [
                {**dict(r), "gap_count": 0, "data_kind": "ohlcv", "provider": "canonical"}
                for r in rows
            ] + [
                {**dict(r), "gap_count": 0, "data_kind": "funding", "provider": "okx"}
                for r in fr
            ] + external
        finally:
            await conn.close()

    @router.get("/exchanges")
    async def get_exchanges():
        """List exchanges that have OHLCV data ingested into market_klines.

        Frontend uses this to populate the Run Backtest exchange dropdown.
        Falls back to a hardcoded default list when the DB is not configured,
        so the dropdown still works on parquet-only environments.
        """
        default = [
            {"exchange": "binance", "available": False, "row_count": 0},
            {"exchange": "okx", "available": False, "row_count": 0},
            {"exchange": "bybit", "available": False, "row_count": 0},
        ]
        if not db_dsn:
            return default
        import asyncpg
        try:
            conn = await asyncpg.connect(db_dsn)
        except Exception:
            return default
        try:
            rows = await conn.fetch(
                """
                SELECT exchange, COUNT(*)::bigint AS row_count
                FROM market_klines
                GROUP BY exchange
                ORDER BY exchange
                """
            )
            seen = {r["exchange"]: int(r["row_count"]) for r in rows}
            out = [
                {"exchange": ex, "available": ex in seen, "row_count": seen.get(ex, 0)}
                for ex in ("binance", "okx", "bybit", "coinbase", "kraken")
            ]
            # Surface any extra exchanges the DB knows about that aren't in our defaults.
            for extra in sorted(set(seen) - {row["exchange"] for row in out}):
                out.append({"exchange": extra, "available": True, "row_count": seen[extra]})
            return out
        except Exception:
            return default
        finally:
            await conn.close()

    @router.get("/export")
    async def export_data(
        symbols: str = "",
        bar: str = "1m",
        start: str = "",
        end: str = "",
        format: str = "xlsx",
        kind: str = "ohlcv",
        datasets: str = "",
    ):
        if not db_dsn:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        data_kind = (kind or "ohlcv").strip().lower()
        if data_kind not in {"ohlcv", "funding", "external"}:
            raise HTTPException(status_code=400, detail="kind must be one of: ohlcv, funding, external")
        if not start or not end:
            raise HTTPException(status_code=400, detail="start and end are required")
        start_dt = _parse_utc(start)
        end_dt = _parse_utc(end)
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="start must be earlier than end")
        fmt = "xlsx" if format == "xlsx" else "csv"

        if data_kind == "external":
            dataset_ids = [s.strip() for s in datasets.split(",") if s.strip()]
            if not dataset_ids:
                raise HTTPException(status_code=400, detail="At least one dataset is required")
            filename = _export_filename(dataset_ids, "external", start_dt, end_dt, fmt=fmt)
            headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
            if fmt == "xlsx":
                content = await _build_external_xlsx(db_dsn, dataset_ids, start_dt, end_dt)
                return Response(
                    content,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers,
                )
            return StreamingResponse(
                _stream_external_csv(db_dsn, dataset_ids, start_dt, end_dt),
                media_type="text/csv",
                headers=headers,
            )

        inst_ids = [s.strip() for s in symbols.split(",") if s.strip()]
        if not inst_ids:
            raise HTTPException(status_code=400, detail="At least one symbol is required")
        filename = _export_filename(inst_ids, bar if data_kind == "ohlcv" else "funding", start_dt, end_dt, fmt=fmt)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        if data_kind == "funding":
            if fmt == "xlsx":
                content = await _build_funding_xlsx(db_dsn, inst_ids, start_dt, end_dt)
                return Response(
                    content,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers,
                )
            return StreamingResponse(
                _stream_funding_csv(db_dsn, inst_ids, start_dt, end_dt),
                media_type="text/csv",
                headers=headers,
            )
        if fmt == "xlsx":
            content = await _build_ohlcv_xlsx(db_dsn, inst_ids, bar, start_dt, end_dt)
            return Response(
                content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers=headers,
            )
        return StreamingResponse(
            _stream_ohlcv_csv(db_dsn, inst_ids, bar, start_dt, end_dt),
            media_type="text/csv",
            headers=headers,
        )

    @router.post("/external/refresh")
    async def refresh_external_data(req: ExternalRefreshRequest):
        if not db_dsn:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        dataset_ids = _request_dataset_ids(req)
        if not dataset_ids:
            raise HTTPException(status_code=400, detail="At least one dataset is required")
        if not req.start or not req.end:
            raise HTTPException(status_code=400, detail="start and end are required")
        start_dt = _parse_utc(req.start)
        end_dt = _parse_utc(req.end)
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="start must be earlier than end")
        return await _refresh_external_datasets(db_dsn, dataset_ids, start_dt, end_dt)

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


def _export_filename(inst_ids: list[str], bar: str, start: datetime, end: datetime, fmt: str = "xlsx") -> str:
    bar = _normalize_output_bar(bar)
    ext = "xlsx" if fmt == "xlsx" else "csv"
    prefix = "ohlcv_export"
    if bar == "funding":
        prefix = "funding_export"
    elif bar == "external":
        prefix = "external_export"
    return f"{prefix}_{bar}_{start.date()}_{end.date()}.{ext}"


def _is_hourly_aggregate(bar: str) -> bool:
    return bar.lower() in {"1h", "1hr", "1hour"}


def _normalize_output_bar(bar: str) -> str:
    return "1H" if _is_hourly_aggregate(bar) else bar


def _export_select_sql(hourly: bool) -> str:
    if hourly:
        return """
            WITH hourly AS (
                SELECT
                    date_trunc('hour', ts) AS ts,
                    inst_id,
                    (array_agg(open ORDER BY ts))[1] AS open,
                    MAX(high) AS high,
                    MIN(low) AS low,
                    (array_agg(close ORDER BY ts DESC))[1] AS close,
                    SUM(vol_contract) AS vol_contract,
                    SUM(vol_base) AS vol_base,
                    SUM(vol_quote) AS vol_quote,
                    CASE
                        WHEN COUNT(DISTINCT source_primary) = 1 THEN MIN(source_primary)
                        ELSE 'mixed'
                    END AS source_primary,
                    CASE
                        WHEN BOOL_OR(quality_status = 'suspect') THEN 'suspect'
                        ELSE 'raw'
                    END AS quality_status
                FROM canonical_candles
                WHERE inst_id = ANY($1::text[])
                  AND bar = '1m'
                  AND ts >= $3
                  AND ts < $4
                GROUP BY inst_id, date_trunc('hour', ts)
            )
            SELECT
                ts,
                inst_id,
                $2::text AS bar,
                open,
                high,
                low,
                close,
                vol_contract,
                vol_base,
                vol_quote,
                source_primary,
                quality_status
            FROM hourly
            ORDER BY inst_id, ts
        """
    return """
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
    """


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
    output_bar = _normalize_output_bar(bar)
    hourly = _is_hourly_aggregate(bar)
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
                _export_select_sql(hourly),
                inst_ids,
                output_bar,
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


async def _build_ohlcv_xlsx(
    db_dsn: str,
    inst_ids: list[str],
    bar: str,
    start: datetime,
    end: datetime,
) -> bytes:
    import asyncpg
    import openpyxl

    conn = await asyncpg.connect(db_dsn)
    output_bar = _normalize_output_bar(bar)
    hourly = _is_hourly_aggregate(bar)
    columns = [
        "ts", "inst_id", "bar", "open", "high", "low", "close",
        "vol_contract", "vol_base", "vol_quote", "source_primary", "quality_status",
    ]

    wb = openpyxl.Workbook(write_only=True)
    sheets: dict[str, Any] = {}
    for inst_id in inst_ids:
        ws = wb.create_sheet(title=inst_id[:31])
        ws.append(columns)
        sheets[inst_id] = ws

    try:
        async with conn.transaction():
            async for row in conn.cursor(
                _export_select_sql(hourly),
                inst_ids,
                output_bar,
                start,
                end,
                prefetch=10_000,
            ):
                sheets[row["inst_id"]].append([
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
    finally:
        await conn.close()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


FUNDING_EXPORT_COLUMNS = [
    "ts",
    "source",
    "inst_id",
    "funding_rate",
    "realized_rate",
    "mark_price",
    "funding_interval_hours",
    "next_funding_ts",
    "apr",
]


EXTERNAL_EXPORT_COLUMNS = [
    "dataset_id",
    "observed_at",
    "published_at",
    "value_num",
    "value_text",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "ticker",
    "interval",
    "quality_status",
    "provider",
    "attribution",
    "research_only",
    "source_caveat",
]


def _funding_select_sql() -> str:
    return """
        SELECT
            ts,
            source,
            inst_id,
            funding_rate,
            realized_rate,
            mark_price,
            funding_interval_hours,
            next_funding_ts,
            funding_rate * (365 * 24 / COALESCE(NULLIF(funding_interval_hours, 0), 8.0)) AS apr
        FROM funding_rates
        WHERE inst_id = ANY($1::text[])
          AND ts >= $2
          AND ts < $3
        ORDER BY inst_id, ts
    """


async def _stream_funding_csv(
    db_dsn: str,
    inst_ids: list[str],
    start: datetime,
    end: datetime,
):
    import asyncpg

    conn = await asyncpg.connect(db_dsn)
    output = io.StringIO()
    writer = csv.writer(output)
    try:
        writer.writerow(FUNDING_EXPORT_COLUMNS)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        async with conn.transaction():
            pending = 0
            async for row in conn.cursor(_funding_select_sql(), inst_ids, start, end, prefetch=10_000):
                writer.writerow(_funding_export_row(row))
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


async def _build_funding_xlsx(
    db_dsn: str,
    inst_ids: list[str],
    start: datetime,
    end: datetime,
) -> bytes:
    import asyncpg
    import openpyxl

    conn = await asyncpg.connect(db_dsn)
    wb = openpyxl.Workbook(write_only=True)
    sheets: dict[str, Any] = {}
    for inst_id in inst_ids:
        ws = wb.create_sheet(title=_sheet_title(inst_id))
        ws.append(FUNDING_EXPORT_COLUMNS)
        sheets[inst_id] = ws
    try:
        async with conn.transaction():
            async for row in conn.cursor(_funding_select_sql(), inst_ids, start, end, prefetch=10_000):
                sheets[row["inst_id"]].append(_funding_export_row(row))
    finally:
        await conn.close()
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _funding_export_row(row: Any) -> list[Any]:
    return [
        row["ts"].isoformat(),
        row["source"],
        row["inst_id"],
        row["funding_rate"],
        row["realized_rate"],
        row["mark_price"],
        row["funding_interval_hours"],
        row["next_funding_ts"].isoformat() if row["next_funding_ts"] else None,
        row["apr"],
    ]


def _external_select_sql() -> str:
    return """
        SELECT
            o.dataset_id,
            o.observed_at,
            o.published_at,
            o.value_num,
            o.value_text,
            o.fields,
            o.quality_status,
            d.provider,
            d.attribution,
            COALESCE((d.metadata->>'research_only')::boolean, false) AS research_only
        FROM external_observations o
        JOIN external_datasets d ON d.dataset_id = o.dataset_id
        WHERE o.dataset_id = ANY($1::text[])
          AND o.observed_at >= $2
          AND o.observed_at < $3
        ORDER BY o.dataset_id, o.observed_at
    """


async def _stream_external_csv(
    db_dsn: str,
    dataset_ids: list[str],
    start: datetime,
    end: datetime,
):
    import asyncpg

    conn = await asyncpg.connect(db_dsn)
    output = io.StringIO()
    writer = csv.writer(output)
    try:
        writer.writerow(EXTERNAL_EXPORT_COLUMNS)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        async with conn.transaction():
            pending = 0
            async for row in conn.cursor(_external_select_sql(), dataset_ids, start, end, prefetch=10_000):
                writer.writerow(_external_export_row(row))
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


async def _build_external_xlsx(
    db_dsn: str,
    dataset_ids: list[str],
    start: datetime,
    end: datetime,
) -> bytes:
    import asyncpg
    import openpyxl

    conn = await asyncpg.connect(db_dsn)
    wb = openpyxl.Workbook(write_only=True)
    sheets: dict[str, Any] = {}
    for dataset_id in dataset_ids:
        ws = wb.create_sheet(title=_sheet_title(dataset_id))
        ws.append(EXTERNAL_EXPORT_COLUMNS)
        sheets[dataset_id] = ws
    try:
        async with conn.transaction():
            async for row in conn.cursor(_external_select_sql(), dataset_ids, start, end, prefetch=10_000):
                sheets[row["dataset_id"]].append(_external_export_row(row))
    finally:
        await conn.close()
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _external_export_row(row: Any) -> list[Any]:
    fields = row["fields"] or {}
    if isinstance(fields, str):
        import json as _json
        try:
            fields = _json.loads(fields)
        except Exception:
            fields = {}
    return [
        row["dataset_id"],
        row["observed_at"].isoformat(),
        row["published_at"].isoformat() if row["published_at"] else None,
        row["value_num"],
        row["value_text"],
        fields.get("open"),
        fields.get("high"),
        fields.get("low"),
        fields.get("close"),
        fields.get("volume"),
        fields.get("ticker"),
        fields.get("interval"),
        row["quality_status"],
        row["provider"],
        row["attribution"],
        row["research_only"],
        fields.get("source_caveat"),
    ]


def _sheet_title(value: str) -> str:
    return re.sub(r"[\[\]:*?/\\]", "_", value)[:31] or "sheet"


async def _refresh_external_datasets(
    db_dsn: str,
    dataset_ids: list[str],
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    from okx_quant.data.external_clients.yfinance_client import YFinanceClient
    from okx_quant.data.external_store import ExternalDataStore
    import yaml

    config_path = _project_root_path() / "config" / "external_data.yaml"
    with config_path.open("r", encoding="utf-8") as fh:
        datasets = (yaml.safe_load(fh) or {}).get("datasets") or {}

    refreshed: list[dict[str, Any]] = []
    async with await ExternalDataStore.from_dsn(db_dsn, min_size=1, max_size=2) as store:
        for dataset_id in dataset_ids:
            cfg = datasets.get(dataset_id)
            if not cfg:
                raise HTTPException(status_code=400, detail=f"Unknown external dataset: {dataset_id}")
            if str(cfg.get("adapter") or "") != "yfinance":
                raise HTTPException(status_code=400, detail=f"Dataset does not support on-demand refresh: {dataset_id}")
            await store.upsert_dataset(dataset_id, cfg)
            job_id = await store.start_fetch_job(dataset_id, str(cfg.get("provider") or "yfinance"), start, end)
            try:
                client = YFinanceClient(publish_lag_days=int(cfg.get("publish_lag_days", 1)))
                rows = await asyncio.to_thread(
                    client.fetch,
                    ticker=str(cfg.get("ticker") or "BTC=F"),
                    start=start,
                    end=end,
                    interval=str(cfg.get("interval") or "1d"),
                )
                if not rows and bool(cfg.get("fail_on_empty_fetch", False)):
                    raise RuntimeError(f"{dataset_id}: empty yfinance fetch")
                stats = await store.upsert_observations(dataset_id, rows)
                await store.finish_fetch_job(
                    job_id,
                    status="success",
                    rows_fetched=len(rows),
                    rows_inserted=stats["inserted"],
                    rows_updated=stats["updated"],
                    details={"on_demand_export_refresh": True},
                )
                await store.update_checkpoint(
                    dataset_id,
                    direction="backfill",
                    cursor_time=max((row["observed_at"] for row in rows), default=end),
                    request_count=1,
                    row_count=len(rows),
                    status="success",
                )
                refreshed.append({
                    "dataset_id": dataset_id,
                    "status": "success",
                    "rows_fetched": len(rows),
                    "rows_inserted": stats["inserted"],
                    "rows_updated": stats["updated"],
                    "research_only": bool(cfg.get("research_only", False)),
                    "attribution": cfg.get("attribution"),
                })
            except Exception as exc:
                await store.finish_fetch_job(job_id, status="failed", error_message=str(exc))
                await store.update_checkpoint(
                    dataset_id,
                    direction="backfill",
                    cursor_time=start,
                    request_count=1,
                    row_count=0,
                    status="failed",
                    last_error=str(exc),
                )
                raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "done", "datasets": refreshed}


def _project_root_path():
    from pathlib import Path as _Path

    return _Path(__file__).resolve().parents[3]


async def _write_fetched_to_parquet(
    db_dsn: str,
    inst_id: str,
    bar: str,
    start_dt: datetime,
    end_dt: datetime,
) -> int:
    """
    Read freshly-canonicalized candles from DB and upsert into the local parquet file.
    Returns the number of rows written.  Non-fatal — caller should catch exceptions.
    """
    import sys
    from pathlib import Path as _Path

    import asyncpg
    import pandas as _pd

    _project_root = _Path(__file__).resolve().parents[3]
    _bt_path = str(_project_root / "backtesting")
    if _bt_path not in sys.path:
        sys.path.insert(0, _bt_path)
    from data_loader import write_candles_parquet  # type: ignore[import]

    conn = await asyncpg.connect(db_dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT ts,
                   open, high, low, close,
                   COALESCE(vol_quote, vol_base, vol_contract, 0.0) AS vol
            FROM canonical_candles
            WHERE inst_id = $1 AND bar = $2
              AND ts >= $3 AND ts < $4
            ORDER BY ts
            """,
            inst_id, bar, start_dt, end_dt,
        )
    finally:
        await conn.close()

    if not rows:
        return 0

    df = _pd.DataFrame([dict(r) for r in rows])
    df["ts"] = _pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.set_index("ts")

    data_dir = str(_project_root / "data" / "ticks")
    write_candles_parquet(inst_id, bar, df, data_dir)
    return len(rows)


def _request_symbols(req: FetchRequest) -> list[str]:
    symbols = list(req.symbols or [])
    if req.symbol:
        symbols.append(req.symbol)
    seen = set()
    return [s for s in symbols if s and not (s in seen or seen.add(s))]


def _request_dataset_ids(req: ExternalRefreshRequest) -> list[str]:
    dataset_ids = list(req.dataset_ids or [])
    if req.dataset_id:
        dataset_ids.append(req.dataset_id)
    seen = set()
    return [s for s in dataset_ids if s and not (s in seen or seen.add(s))]


async def _fetch_external_coverage(conn: Any) -> list[dict[str, Any]]:
    try:
        rows = await conn.fetch(
            """
            SELECT
                d.dataset_id AS inst_id,
                COALESCE(d.frequency, 'external') AS bar,
                MIN(o.observed_at) AS first_ts,
                MAX(o.observed_at) AS last_ts,
                COUNT(o.observed_at) AS row_count,
                d.provider,
                d.value_kind,
                d.frequency,
                d.source_url,
                d.attribution,
                COALESCE((d.metadata->>'research_only')::boolean, false) AS research_only
            FROM external_datasets d
            LEFT JOIN external_observations o
              ON o.dataset_id = d.dataset_id
            GROUP BY
                d.dataset_id, d.provider, d.value_kind, d.frequency,
                d.source_url, d.attribution, d.metadata
            ORDER BY d.dataset_id
            """
        )
    except Exception:
        return []
    return [
        {
            **dict(row),
            "gap_count": 0,
            "data_kind": "external",
        }
        for row in rows
    ]


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

                parquet_rows = 0
                parquet_error = None
                try:
                    parquet_rows = await _write_fetched_to_parquet(
                        db_dsn, symbol, req.bar, start_dt, end_dt
                    )
                except Exception as exc:
                    parquet_error = str(exc)

                fetched.append({
                    "symbol": symbol,
                    "status": "done",
                    "rows": len(candles),
                    "parquet_rows": parquet_rows,
                    "parquet_error": parquet_error,
                    "list_date": _ms_to_date(list_time_ms),
                    "effective_start": start_dt.date().isoformat(),
                })
        finally:
            client.close()

        parquet_total = sum(int(r.get("parquet_rows") or 0) for r in fetched)
        parquet_errors = [r for r in fetched if r.get("parquet_error")]
        parquet_summary = (
            f"parquet FAILED for {len(parquet_errors)} symbol(s): {parquet_errors[0]['parquet_error']}"
            if parquet_errors
            else f"parquet: {parquet_total} rows"
        )
        _jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "message": f"Fetched {len(fetched)} symbol(s) for {req.bar} ({parquet_summary})",
            "results": fetched,
        })
    except Exception as exc:
        _jobs[job_id].update({"status": "error", "message": str(exc)})
