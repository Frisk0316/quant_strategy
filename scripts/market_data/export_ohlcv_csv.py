"""Export canonical OHLCV candles to CSV.

Examples:
    python scripts/market_data/export_ohlcv_csv.py --inst BTC-USDT-SWAP --start 2024-01-01 --end 2024-01-02 --out btc.csv
    python scripts/market_data/export_ohlcv_csv.py --inst BTC-USDT-SWAP --inst ETH-USDT-SWAP --start 2024-01-01 --end 2024-02-01 --out ohlcv.csv
"""
from __future__ import annotations

import asyncio
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import click

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from okx_quant.core.config import load_config


CSV_COLUMNS = [
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


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def _export(
    *,
    dsn: str,
    inst_ids: list[str],
    bar: str,
    start: datetime,
    end: datetime,
    out: Path,
    batch_size: int,
) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = await asyncpg.connect(dsn)
    rows_written = 0
    try:
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            async with conn.transaction():
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
                    prefetch=batch_size,
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
                    rows_written += 1
    finally:
        await conn.close()
    return rows_written


@click.command()
@click.option("--inst", "inst_ids", multiple=True, required=True, help="Canonical instrument id.")
@click.option("--bar", default="1m", show_default=True)
@click.option("--start", required=True, help="Inclusive ISO start date/time.")
@click.option("--end", required=True, help="Exclusive ISO end date/time.")
@click.option("--out", required=True, type=click.Path(dir_okay=False, path_type=Path))
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--batch-size", default=10_000, show_default=True, type=int)
def cli(
    inst_ids: tuple[str, ...],
    bar: str,
    start: str,
    end: str,
    out: Path,
    config: str,
    batch_size: int,
) -> None:
    """Export one or more canonical OHLCV instruments from TimescaleDB."""
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)
    if start_dt >= end_dt:
        raise click.ClickException("--start must be earlier than --end")
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = os.environ.get("DATABASE_URL") or cfg.storage.timescale_dsn
    if not dsn:
        raise click.ClickException("storage.timescale_dsn is not set")
    rows = asyncio.run(
        _export(
            dsn=dsn,
            inst_ids=list(inst_ids),
            bar=bar,
            start=start_dt,
            end=end_dt,
            out=out,
            batch_size=batch_size,
        )
    )
    click.echo(f"Exported {rows:,} rows to {out}")


if __name__ == "__main__":
    cli()
