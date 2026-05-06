"""Import existing Parquet funding-rate history into TimescaleDB."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore


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
    if "rate" not in df.columns:
        raise ValueError(f"{path} missing required funding column: rate")

    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["ts", "rate"]).sort_values("ts")

    next_col = "nextFundingTime" if "nextFundingTime" in df.columns else "next_funding_time"
    rows = []
    for item in df.to_dict("records"):
        next_value = item.get(next_col)
        if pd.notna(next_value):
            if isinstance(next_value, (int, float)):
                next_ts_ms = int(next_value)
            else:
                next_ts_ms = int(pd.Timestamp(next_value, tz="UTC").timestamp() * 1000)
        else:
            next_ts_ms = None

        rows.append({
            "ts_ms": int(pd.Timestamp(item["ts"]).timestamp() * 1000),
            "funding_rate": float(item["rate"]),
            "realized_rate": (
                float(item["realized_rate"])
                if item.get("realized_rate") is not None and pd.notna(item.get("realized_rate"))
                else None
            ),
            "next_funding_ts_ms": next_ts_ms,
            "raw_payload": {"source_path": str(path)},
        })
    return rows


async def import_parquet_funding(
    *,
    dsn: str,
    data_dir: Path,
    inst_filter: tuple[str, ...],
) -> None:
    store = await CandleStore.from_dsn(dsn)
    try:
        files = sorted(data_dir.glob("*/funding.parquet"))
        if inst_filter:
            allowed = set(inst_filter)
            files = [path for path in files if _inst_from_dir(path.parent) in allowed]
        if not files:
            click.echo(f"No funding parquet files found under {data_dir}")
            return

        total_rows = 0
        for path in files:
            inst_id = _inst_from_dir(path.parent)
            base_ccy = inst_id.split("-")[0]
            await store.register_instrument(inst_id=inst_id, base_ccy=base_ccy)

            rows = _rows_from_parquet(path)
            job_id = await store.start_job(
                job_type="backfill",
                source="parquet",
                inst_id=inst_id,
                details={"source_path": str(path), "mode": "funding_parquet_import"},
            )
            result = await store.upsert_funding_rates(rows, source="okx", inst_id=inst_id)
            await store.finish_job(
                job_id,
                status="success",
                rows_fetched=len(rows),
                rows_inserted=int(result.get("inserted", 0)),
            )
            total_rows += len(rows)
            click.echo(f"Imported {inst_id} funding: {len(rows):,} rows from {path}")

        click.echo(f"\nParquet funding import complete: {total_rows:,} rows scanned.")
    finally:
        await store.close()


@click.command()
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--data-dir", default="data/ticks", show_default=True)
@click.option("--inst", multiple=True, help="Optional instrument filter, e.g. BTC-USDT-SWAP")
def cli(config: str, data_dir: str, inst: tuple[str, ...]) -> None:
    """Import local funding.parquet files into funding_rates."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)
    asyncio.run(import_parquet_funding(
        dsn=dsn,
        data_dir=Path(data_dir),
        inst_filter=inst,
    ))


if __name__ == "__main__":
    cli()
