"""Backfill Deribit option-flow hourly aggregates.

Aggregation definitions:
value_num = pc_taker_premium_imbalance = (put_taker_buy_premium - call_taker_buy_premium) / max(total_taker_buy_premium, EPSILON);
fields = {call_buy_amt, call_sell_amt, put_buy_amt, put_sell_amt,
premium_volume, premium_unit (BTC/ETH for inverse; USDC for linear -- aggregate inverse instruments only in v1 and record the exclusion),
avg_trade_iv, trade_count, liq_trade_count, unit: "imbalance_ratio"}.
Direction = taker side from `direction`; put/call parsed from instrument name.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import asyncpg

from okx_quant.core.config import load_config
from okx_quant.data.external_clients.deribit_option_flow import (
    DeribitOptionFlowClient,
    aggregate_hourly_option_flow,
)
from okx_quant.data.external_store import ExternalDataStore
from scripts.market_data.ingest_external import _load_external_config


def resume_start(requested_start: datetime, checkpoint_cursor: datetime | None) -> datetime:
    if checkpoint_cursor is None:
        return requested_start
    cursor = checkpoint_cursor if checkpoint_cursor.tzinfo else checkpoint_cursor.replace(tzinfo=timezone.utc)
    return max(requested_start, cursor.astimezone(timezone.utc) + timedelta(hours=1))


def _empty_chunk_error(dataset_id: str, cfg: dict[str, Any], rows: list[dict[str, Any]]) -> str | None:
    return None


def _parse_dt(value: str) -> datetime:
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    if ts.minute or ts.second or ts.microsecond:
        raise ValueError(f"{value} must be hour-aligned")
    return ts


def _dataset_id(currency: str) -> str:
    return f"optflow_deribit_{currency.lower()}"


def _chunks(start: datetime, end: datetime, *, days: int) -> list[tuple[datetime, datetime]]:
    out = []
    cursor = start
    while cursor < end:
        nxt = min(cursor + timedelta(days=days), end)
        out.append((cursor, nxt))
        cursor = nxt
    return out


async def _checkpoint_cursor(dsn: str, dataset_id: str) -> datetime | None:
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            """
            SELECT cursor_time
            FROM external_ingestion_checkpoints
            WHERE dataset_id=$1 AND direction='backfill'
            """,
            dataset_id,
        )
        return row["cursor_time"] if row else None
    finally:
        await conn.close()


async def _coverage_report(dsn: str, dataset_id: str, *, gap_hours: int) -> dict[str, Any]:
    conn = await asyncpg.connect(dsn)
    try:
        summary = await conn.fetchrow(
            """
            SELECT COUNT(*)::int AS rows, MIN(observed_at) AS first, MAX(observed_at) AS last
            FROM external_observations
            WHERE dataset_id=$1
            """,
            dataset_id,
        )
        gaps = await conn.fetch(
            """
            WITH ordered AS (
                SELECT observed_at, LAG(observed_at) OVER (ORDER BY observed_at) AS prev_ts
                FROM external_observations
                WHERE dataset_id=$1
            )
            SELECT prev_ts, observed_at, observed_at-prev_ts AS gap
            FROM ordered
            WHERE prev_ts IS NOT NULL AND observed_at-prev_ts > ($2::text || ' hours')::interval
            ORDER BY gap DESC
            LIMIT 20
            """,
            dataset_id,
            str(gap_hours),
        )
    finally:
        await conn.close()
    return {
        "dataset_id": dataset_id,
        "rows": int(summary["rows"] or 0),
        "first": summary["first"].isoformat() if summary["first"] else None,
        "last": summary["last"].isoformat() if summary["last"] else None,
        "gap_hours_threshold": gap_hours,
        "gaps": [
            {
                "prev": row["prev_ts"].isoformat(),
                "observed_at": row["observed_at"].isoformat(),
                "gap": str(row["gap"]),
            }
            for row in gaps
        ],
    }


async def _backfill(args: argparse.Namespace) -> None:
    start = _parse_dt(args.start)
    end = _parse_dt(args.end)
    if start >= end:
        raise SystemExit("start must be earlier than end")
    settings = load_config(settings_path=args.settings, require_secrets=False)
    dsn = args.dsn or settings.storage.timescale_dsn
    if not dsn:
        raise SystemExit("storage.timescale_dsn is not set")
    configs = _load_external_config(args.config)
    currencies = [currency.upper() for currency in args.currency]
    reports = []
    async with await ExternalDataStore.from_dsn(dsn, min_size=1, max_size=2) as store:
        for currency in currencies:
            dataset_id = _dataset_id(currency)
            if dataset_id not in configs:
                raise SystemExit(f"{dataset_id} missing from {args.config}")
            cfg = configs[dataset_id]
            await store.upsert_dataset(dataset_id, cfg)
            cursor = await _checkpoint_cursor(dsn, dataset_id) if args.resume else None
            run_start = resume_start(start, cursor)
            client = DeribitOptionFlowClient(endpoint=DeribitOptionFlowClient.history_endpoint)
            for chunk_start, chunk_end in _chunks(run_start, end, days=args.chunk_days):
                trades = client.fetch_trades(currency=currency, start=chunk_start, end=chunk_end)
                rows = aggregate_hourly_option_flow(currency, trades)
                job_id = await store.start_fetch_job(dataset_id, str(cfg["provider"]), chunk_start, chunk_end)
                try:
                    empty_error = _empty_chunk_error(dataset_id, cfg, rows)
                    if empty_error:
                        await store.finish_fetch_job(job_id, status="failed", error_message=empty_error)
                        await store.update_checkpoint(
                            dataset_id,
                            direction="backfill",
                            cursor_time=None,
                            request_count=max(client.last_page_count, 1),
                            row_count=0,
                            status="failed",
                            last_error=empty_error,
                        )
                        raise RuntimeError(empty_error)
                    stats = await store.upsert_observations(dataset_id, rows)
                    await store.finish_fetch_job(
                        job_id,
                        status="success",
                        rows_fetched=len(rows),
                        rows_inserted=stats["inserted"],
                        rows_updated=stats["updated"],
                    )
                    cursor_time = max((row["observed_at"] for row in rows), default=chunk_end - timedelta(hours=1))
                    await store.update_checkpoint(
                        dataset_id,
                        direction="backfill",
                        cursor_time=cursor_time,
                        request_count=max(client.last_page_count, 1),
                        row_count=len(rows),
                        status="success",
                    )
                except Exception as exc:
                    await store.finish_fetch_job(job_id, status="failed", error_message=str(exc))
                    await store.update_checkpoint(
                        dataset_id,
                        direction="backfill",
                        cursor_time=None,
                        request_count=max(client.last_page_count, 1),
                        row_count=0,
                        status="failed",
                        last_error=str(exc),
                    )
                    raise
                print(
                    f"[deribit_option_flow] {currency} {chunk_start.isoformat()} -> {chunk_end.isoformat()} "
                    f"pages={client.last_page_count} trades={len(trades)} hours={len(rows)} "
                    f"inserted={stats['inserted']} updated={stats['updated']} cursor={cursor_time.isoformat()}",
                    flush=True,
                )
            reports.append(await _coverage_report(dsn, dataset_id, gap_hours=args.gap_hours))
    print(json.dumps({"coverage": reports}, indent=2, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--currency", action="append", choices=["BTC", "ETH"], default=None)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--chunk-days", type=int, default=1)
    parser.add_argument("--gap-hours", type=int, default=6)
    parser.add_argument("--config", default="config/external_data.yaml")
    parser.add_argument("--settings", default="config/settings.yaml")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args()
    if not args.currency:
        args.currency = ["BTC", "ETH"]
    if args.chunk_days <= 0:
        raise SystemExit("chunk-days must be positive")
    asyncio.run(_backfill(args))


if __name__ == "__main__":
    main()
