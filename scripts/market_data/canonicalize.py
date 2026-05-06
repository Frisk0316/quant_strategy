"""
Promote market_klines data into canonical_candles.

For each (canonical_inst_id, bar, ts), picks the highest-priority exchange
from --prefer list. Uses ON CONFLICT DO NOTHING so already-validated
canonical rows are never overwritten.

Processes the time range in monthly chunks and prints per-chunk progress.

Usage:
    python scripts/market_data/canonicalize.py \
        --canonical-inst BTC-USDT-SWAP \
        --bar 1H \
        --prefer okx,binance,bybit \
        --start 2020-01-01 --end 2026-05-01

    # Canonicalize all symbols in config using default preference
    python scripts/market_data/canonicalize.py --all
"""
from __future__ import annotations

import asyncio
import sys
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    import pandas as pd
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.to_pydatetime()


def _month_chunks(
    start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    """Split [start, end) into monthly windows."""
    chunks: list[tuple[datetime, datetime]] = []
    cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while cursor < end:
        days_in_month = monthrange(cursor.year, cursor.month)[1]
        if cursor.month == 12:
            next_month = cursor.replace(year=cursor.year + 1, month=1, day=1)
        else:
            next_month = cursor.replace(month=cursor.month + 1, day=1)
        chunk_start = max(cursor, start)
        chunk_end = min(next_month, end)
        chunks.append((chunk_start, chunk_end))
        cursor = next_month
    return chunks


async def _canonicalize_one(
    store: CandleStore,
    canonical_inst_id: str,
    bar: str,
    prefer_exchanges: list[str],
    start: Optional[datetime],
    end: Optional[datetime],
    dry_run: bool,
) -> None:
    start_str = start.strftime("%Y-%m-%d") if start else "beginning"
    end_str   = end.strftime("%Y-%m-%d")   if end   else "now"

    if dry_run:
        click.echo(
            f"[dry-run] Would canonicalize {canonical_inst_id}/{bar} "
            f"prefer={prefer_exchanges}  {start_str} → {end_str}"
        )
        return

    # Use full-range defaults when start/end not given
    range_start = start or datetime(2018, 1, 1, tzinfo=timezone.utc)
    range_end   = end   or datetime.now(tz=timezone.utc)

    chunks = _month_chunks(range_start, range_end)
    total_chunks = len(chunks)
    total_promoted = 0
    all_source_counts: dict[str, int] = {}

    click.echo(
        f"Canonicalizing  {canonical_inst_id} / {bar}"
        f"  prefer={prefer_exchanges}"
        f"  {start_str} → {end_str}"
        f"  ({total_chunks} monthly chunks)"
    )

    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        month_label = chunk_start.strftime("%Y-%m")
        result = await store.canonicalize_from_market_klines(
            canonical_inst_id=canonical_inst_id,
            bar=bar,
            prefer_exchanges=prefer_exchanges,
            start=chunk_start,
            end=chunk_end,
        )
        promoted = result["promoted"]
        counts   = result["source_counts"]
        total_promoted += promoted
        for ex, n in counts.items():
            all_source_counts[ex] = all_source_counts.get(ex, 0) + n

        counts_str = " ".join(f"{ex}={n}" for ex, n in sorted(counts.items()))
        pct = i / total_chunks * 100
        status = f"+{promoted:,}" if promoted else "skip"
        click.echo(
            f"  [{i:3d}/{total_chunks}]  {month_label}  {status:<10s}"
            f"  {counts_str or '(no data)'}   {pct:5.1f}% done"
        )

    summary_str = "  ".join(f"{ex}={n:,}" for ex, n in sorted(all_source_counts.items()))
    click.echo(
        f"\nDONE  {canonical_inst_id}/{bar}"
        f"  total promoted: {total_promoted:,}"
        f"  [{summary_str or 'none'}]"
    )


async def main(
    canonical_inst: Optional[str],
    bar: str,
    prefer: str,
    start: Optional[str],
    end: Optional[str],
    all_symbols: bool,
    config_path: str,
    dry_run: bool,
) -> None:
    cfg = load_config(settings_path=config_path, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn is not set", err=True)
        sys.exit(1)

    prefer_exchanges = [e.strip() for e in prefer.split(",") if e.strip()]
    start_dt = _parse_dt(start)
    end_dt   = _parse_dt(end)

    async with await CandleStore.from_dsn(dsn, min_size=1, max_size=4) as store:
        if all_symbols:
            instruments = cfg.market_data.instruments
            bars = [bar] if bar else cfg.market_data.bars
            click.echo(
                f"Canonicalizing {len(instruments)} instruments"
                f" × {len(bars)} bars  prefer={prefer_exchanges}\n"
            )
            for inst_id in instruments:
                for b in bars:
                    await _canonicalize_one(
                        store, inst_id, b, prefer_exchanges, start_dt, end_dt, dry_run
                    )
                    click.echo()
        elif canonical_inst:
            await _canonicalize_one(
                store, canonical_inst, bar, prefer_exchanges, start_dt, end_dt, dry_run
            )
        else:
            click.echo("ERROR: Provide --canonical-inst or --all", err=True)
            sys.exit(1)


@click.command()
@click.option("--canonical-inst", default=None,
              help="canonical instruments.inst_id, e.g. BTC-USDT-SWAP")
@click.option("--bar", default="1m", show_default=True,
              help="Bar size, e.g. 1m, 1H")
@click.option("--prefer", default="okx,binance,bybit", show_default=True,
              help="Comma-separated exchange preference order")
@click.option("--start", default=None, help="Start date (UTC), e.g. 2020-01-01")
@click.option("--end", default=None, help="End date (UTC), e.g. 2026-05-01")
@click.option("--all", "all_symbols", is_flag=True, default=False,
              help="Canonicalize all instruments listed in config")
@click.option("--config", "config_path", default="config/settings.yaml",
              show_default=True, help="Path to settings.yaml")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print what would be done without writing to DB")
def cli(
    canonical_inst: Optional[str],
    bar: str,
    prefer: str,
    start: Optional[str],
    end: Optional[str],
    all_symbols: bool,
    config_path: str,
    dry_run: bool,
) -> None:
    """Bridge market_klines → canonical_candles with configurable exchange preference."""
    asyncio.run(main(canonical_inst, bar, prefer, start, end, all_symbols, config_path, dry_run))


if __name__ == "__main__":
    cli()
