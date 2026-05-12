"""Export canonical OHLCV candles to CSV.

Examples:
    python scripts/market_data/export_ohlcv_csv.py --inst BTC-USDT-SWAP --start 2024-01-01 --end 2024-01-02 --out btc.csv
    python scripts/market_data/export_ohlcv_csv.py --inst BTC-USDT-SWAP --inst ETH-USDT-SWAP --start 2024-01-01 --end 2024-02-01 --out ohlcv.csv
    python scripts/market_data/export_ohlcv_csv.py --inst BTC-USDT-SWAP --inst ETH-USDT-SWAP --start 2024-01-01 --end 2026-05-11 --split-dir results/market_data/excel_chunks --split-by-inst
"""
from __future__ import annotations

import asyncio
import csv
import os
import re
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


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


async def _export_split_by_inst(
    *,
    dsn: str,
    inst_ids: list[str],
    bar: str,
    start: datetime,
    end: datetime,
    split_dir: Path,
    max_rows_per_file: int,
    batch_size: int,
) -> int:
    split_dir.mkdir(parents=True, exist_ok=True)
    conn = await asyncpg.connect(dsn)
    rows_written = 0
    try:
        for inst_id in inst_ids:
            part = 1
            current_rows = 0
            current_file = None
            writer = None

            def open_part():
                nonlocal current_file, writer, current_rows, part
                if current_file:
                    current_file.close()
                filename = (
                    f"{_safe_name(inst_id)}_{_safe_name(bar)}_"
                    f"{start.date()}_{end.date()}_part{part:03d}.csv"
                )
                current_file = open(split_dir / filename, "w", newline="", encoding="utf-8")
                writer = csv.writer(current_file)
                writer.writerow(CSV_COLUMNS)
                current_rows = 0
                part += 1

            open_part()
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
                    WHERE inst_id = $1
                      AND bar = $2
                      AND ts >= $3
                      AND ts < $4
                    ORDER BY ts
                    """,
                    inst_id,
                    bar,
                    start,
                    end,
                    prefetch=batch_size,
                ):
                    if current_rows >= max_rows_per_file:
                        open_part()
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
                    current_rows += 1
                    rows_written += 1
            if current_file:
                current_file.close()
    finally:
        await conn.close()
    return rows_written


@click.command()
@click.option("--inst", "inst_ids", multiple=True, required=True, help="Canonical instrument id.")
@click.option("--bar", default="1m", show_default=True)
@click.option("--start", required=True, help="Inclusive ISO start date/time.")
@click.option("--end", required=True, help="Exclusive ISO end date/time.")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), help="Single CSV output path.")
@click.option("--split-dir", type=click.Path(file_okay=False, path_type=Path), help="Directory for split CSV output.")
@click.option("--split-by-inst", is_flag=True, help="Write one or more chunked CSV files per instrument.")
@click.option("--max-rows-per-file", default=1_000_000, show_default=True, type=int)
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--batch-size", default=10_000, show_default=True, type=int)
def cli(
    inst_ids: tuple[str, ...],
    bar: str,
    start: str,
    end: str,
    out: Path | None,
    split_dir: Path | None,
    split_by_inst: bool,
    max_rows_per_file: int,
    config: str,
    batch_size: int,
) -> None:
    """Export one or more canonical OHLCV instruments from TimescaleDB."""
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)
    if start_dt >= end_dt:
        raise click.ClickException("--start must be earlier than --end")
    if not out and not split_dir:
        raise click.ClickException("Either --out or --split-dir is required")
    if split_dir and not split_by_inst:
        raise click.ClickException("--split-dir currently requires --split-by-inst")
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = os.environ.get("DATABASE_URL") or cfg.storage.timescale_dsn
    if not dsn:
        raise click.ClickException("storage.timescale_dsn is not set")
    if split_dir:
        rows = asyncio.run(
            _export_split_by_inst(
                dsn=dsn,
                inst_ids=list(inst_ids),
                bar=bar,
                start=start_dt,
                end=end_dt,
                split_dir=split_dir,
                max_rows_per_file=max_rows_per_file,
                batch_size=batch_size,
            )
        )
        click.echo(f"Exported {rows:,} rows to split CSV files under {split_dir}")
    else:
        assert out is not None
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
