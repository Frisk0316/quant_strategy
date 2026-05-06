"""Import existing Parquet OHLCV candles into TimescaleDB.

This is the offline bridge from the legacy `data/ticks/*/candles_*.parquet`
layout into the raw/canonical OHLCV pipeline. It avoids re-downloading data
when local Parquet history already exists.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import click
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore


_CANDLE_RE = re.compile(r"candles_(?P<bar>.+)\.parquet$")


def _inst_from_dir(path: Path) -> str:
    parts = path.name.split("_")
    if len(parts) >= 3 and parts[-1] in {"SWAP", "FUTURES", "OPTION"}:
        return "-".join(parts)
    if len(parts) >= 2:
        return "-".join(parts)
    return path.name.replace("_", "-")


def _rows_from_parquet(path: Path) -> list[dict]:
    df = pd.read_parquet(path)
    if "ts" not in df.columns:
        df = df.reset_index(names="ts")
    required = {"ts", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing required OHLCV columns: {sorted(missing)}")

    ts = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.assign(ts=ts).dropna(subset=["ts"]).sort_values("ts")

    rows = []
    for row in df.itertuples(index=False):
        item = row._asdict()
        vol = item.get("vol")
        rows.append({
            "ts_ms": int(pd.Timestamp(item["ts"]).timestamp() * 1000),
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "vol_contract": float(vol) if vol is not None and pd.notna(vol) else None,
            "vol_base": None,
            "vol_quote": None,
            "is_closed": True,
            "raw_payload": None,
        })
    return rows


async def import_parquet_ohlcv(
    *,
    dsn: str,
    data_dir: Path,
    inst_filter: tuple[str, ...],
    bar_filter: tuple[str, ...],
) -> None:
    store = await CandleStore.from_dsn(dsn)
    try:
        files = sorted(data_dir.glob("*/candles_*.parquet"))
        if inst_filter:
            allowed = set(inst_filter)
            files = [path for path in files if _inst_from_dir(path.parent) in allowed]
        if bar_filter:
            allowed_bars = set(bar_filter)
            files = [
                path for path in files
                if (match := _CANDLE_RE.match(path.name)) and match.group("bar") in allowed_bars
            ]
        if not files:
            click.echo(f"No candle parquet files found under {data_dir}")
            return

        total_rows = 0
        for path in files:
            match = _CANDLE_RE.match(path.name)
            if not match:
                continue
            inst_id = _inst_from_dir(path.parent)
            bar = match.group("bar")
            base_ccy = inst_id.split("-")[0]

            await store.register_instrument(inst_id=inst_id, base_ccy=base_ccy)
            await store.register_instrument_bar(inst_id=inst_id, bar=bar)
            rows = _rows_from_parquet(path)
            job_id = await store.start_job(
                job_type="backfill",
                source="parquet",
                inst_id=inst_id,
                bar=bar,
                details={"source_path": str(path), "mode": "parquet_import"},
            )
            result = await store.upsert_raw_candles(rows, source="okx", inst_id=inst_id, bar=bar)
            promoted = await store.canonicalize_from_raw("okx", inst_id, bar)
            await store.update_instrument_bar_bounds(inst_id, bar)
            await store.finish_job(
                job_id,
                status="success",
                rows_fetched=len(rows),
                rows_inserted=int(result.get("inserted", 0)),
                details={"promoted": int(promoted.get("promoted", 0))},
            )
            total_rows += len(rows)
            click.echo(
                f"Imported {inst_id} {bar}: {len(rows):,} rows "
                f"from {path.relative_to(data_dir)}"
            )

        click.echo(f"\nParquet OHLCV import complete: {total_rows:,} rows scanned.")
    finally:
        await store.close()


@click.command()
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--data-dir", default="data/ticks", show_default=True)
@click.option("--inst", multiple=True, help="Optional instrument filter, e.g. BTC-USDT-SWAP")
@click.option("--bar", "bars", multiple=True, help="Optional bar filter, e.g. 1H")
def cli(config: str, data_dir: str, inst: tuple[str, ...], bars: tuple[str, ...]) -> None:
    """Import local Parquet OHLCV into raw_candles and canonical_candles."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)
    asyncio.run(import_parquet_ohlcv(
        dsn=dsn,
        data_dir=Path(data_dir),
        inst_filter=inst,
        bar_filter=bars,
    ))


if __name__ == "__main__":
    cli()
