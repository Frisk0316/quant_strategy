"""
Historical OHLCV backfill for a single instrument+bar.
Fetches from OKX, writes to raw_candles, promotes to canonical_candles,
detects gaps and retries up to max_retries times.

Usage:
    python scripts/market_data/backfill.py \\
        --inst BTC-USDT-SWAP --bar 1H \\
        --start 2024-01-01 --end 2026-05-04

    python scripts/market_data/backfill.py \\
        --inst BTC-USDT-SWAP --bar 1m \\
        --start 2025-01-01 --end 2026-05-04 \\
        --chunk-days 7
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore
from okx_quant.data.exchange_clients.okx_public import OKXPublicClient


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _chunk_ranges(
    start: datetime, end: datetime, chunk_days: int
) -> list[tuple[datetime, datetime]]:
    chunks = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks


async def backfill_single(
    dsn: str,
    inst_id: str,
    bar: str,
    start: datetime,
    end: datetime,
    chunk_days: int,
    max_retries: int,
    backoff_secs: list[int],
) -> None:
    store = await CandleStore.from_dsn(dsn)
    client = OKXPublicClient()

    try:
        # Register instrument and bar
        parts = inst_id.split("-")
        base_ccy = parts[0]
        await store.register_instrument(inst_id=inst_id, base_ccy=base_ccy)
        await store.register_instrument_bar(inst_id=inst_id, bar=bar)

        job_id = await store.start_job(
            job_type="backfill",
            source="okx",
            inst_id=inst_id,
            bar=bar,
            start_ts=start,
            end_ts=end,
            details={"chunk_days": chunk_days},
        )

        chunks = _chunk_ranges(start, end, chunk_days)
        total_inserted = 0
        total_gaps = 0
        status = "success"

        click.echo(f"Backfilling {inst_id} {bar}: {start.date()} → {end.date()} "
                   f"({len(chunks)} chunks of {chunk_days}d)")

        for chunk_start, chunk_end in chunks:
            start_ms = int(chunk_start.timestamp() * 1000)
            end_ms   = int(chunk_end.timestamp() * 1000)

            # Fetch from OKX
            try:
                rows = client.paginate_history(
                    inst_id=inst_id,
                    bar=bar,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            except Exception as exc:
                click.echo(f"  WARN: fetch failed for chunk {chunk_start.date()}: {exc}")
                await store.log_quality_event(
                    inst_id=inst_id, bar=bar, issue_type="fetch_failed",
                    severity="warning", window_start=chunk_start, window_end=chunk_end,
                    job_id=job_id, notes=str(exc),
                )
                status = "partial"
                continue

            if not rows:
                click.echo(f"  INFO: no data for chunk {chunk_start.date()} → {chunk_end.date()}")
                continue

            # Write raw candles
            result = await store.upsert_raw_candles(rows, source="okx", inst_id=inst_id, bar=bar)
            total_inserted += result["inserted"]

            # Promote to canonical
            await store.canonicalize_from_raw(
                source="okx", inst_id=inst_id, bar=bar,
                start=chunk_start, end=chunk_end,
            )

            # Gap detection + retry
            for attempt in range(max_retries):
                gaps = await store.detect_gaps(inst_id, bar, chunk_start, chunk_end)
                if not gaps:
                    break

                click.echo(f"  Attempt {attempt + 1}/{max_retries}: {len(gaps)} gap(s) in "
                           f"{chunk_start.date()}")
                sleep_secs = backoff_secs[attempt] if attempt < len(backoff_secs) else backoff_secs[-1]
                time.sleep(sleep_secs)

                for gap_start, gap_end in gaps:
                    gstart_ms = int(gap_start.timestamp() * 1000)
                    gend_ms   = int(gap_end.timestamp() * 1000)
                    try:
                        gap_rows = client.paginate_history(inst_id, bar, gstart_ms, gend_ms)
                        if gap_rows:
                            await store.upsert_raw_candles(gap_rows, "okx", inst_id, bar)
                            await store.canonicalize_from_raw("okx", inst_id, bar, gap_start, gap_end)
                    except Exception as exc:
                        click.echo(f"    Gap retry failed: {exc}")
            else:
                # Exhausted retries; log persistent gaps
                gaps = await store.detect_gaps(inst_id, bar, chunk_start, chunk_end)
                for gap_start, gap_end in gaps:
                    total_gaps += 1
                    await store.log_quality_event(
                        inst_id=inst_id, bar=bar, issue_type="gap",
                        severity="warning", window_start=gap_start, window_end=gap_end,
                        retry_count=max_retries, job_id=job_id,
                    )
                    click.echo(f"  WARN: persistent gap {gap_start} → {gap_end}")
                if gaps:
                    status = "partial"

            click.echo(f"  chunk {chunk_start.date()} → {chunk_end.date()}: "
                       f"{len(rows)} fetched, {total_gaps} persistent gaps so far")

        # Update bounds
        await store.update_instrument_bar_bounds(inst_id, bar)
        await store.finish_job(
            job_id, status=status,
            rows_inserted=total_inserted, gaps_found=total_gaps,
        )
        click.echo(f"\nBackfill complete: {total_inserted} rows inserted, "
                   f"{total_gaps} persistent gaps. Status: {status}")

    except Exception as exc:
        click.echo(f"ERROR: {exc}", err=True)
        if "job_id" in dir():
            await store.finish_job(job_id, status="failed", error_message=str(exc))
        raise
    finally:
        client.close()
        await store.close()


@click.command()
@click.option("--inst", required=True, help="OKX instrument ID, e.g. BTC-USDT-SWAP")
@click.option("--bar", required=True, help="Bar size, e.g. 1m, 1H")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD (exclusive)")
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--chunk-days", default=None, type=int,
              help="Chunk size in days (default from config ingestion.chunk_days)")
def cli(inst: str, bar: str, start: str, end: str, config: str,
        chunk_days: Optional[int]) -> None:
    """Backfill historical OHLCV for a single instrument+bar."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)

    effective_chunk = chunk_days or cfg.market_data.ingestion.chunk_days.get(bar, 7)
    backoff = cfg.market_data.ingestion.retry_backoff_seconds
    max_retries = cfg.market_data.ingestion.max_retries

    asyncio.run(backfill_single(
        dsn=dsn,
        inst_id=inst,
        bar=bar,
        start=_parse_dt(start),
        end=_parse_dt(end),
        chunk_days=effective_chunk,
        max_retries=max_retries,
        backoff_secs=backoff,
    ))


if __name__ == "__main__":
    cli()
