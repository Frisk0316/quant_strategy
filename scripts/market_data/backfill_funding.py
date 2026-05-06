"""Backfill OKX funding-rate history directly into TimescaleDB."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore
from okx_quant.data.exchange_clients.okx_public import OKXPublicClient


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


async def backfill_funding(
    *,
    dsn: str,
    inst_id: str,
    start: datetime,
    end: datetime,
) -> None:
    store = await CandleStore.from_dsn(dsn)
    client = OKXPublicClient()
    try:
        base_ccy = inst_id.split("-")[0]
        await store.register_instrument(inst_id=inst_id, base_ccy=base_ccy)

        job_id = await store.start_job(
            job_type="backfill",
            source="okx",
            inst_id=inst_id,
            start_ts=start,
            end_ts=end,
            details={"mode": "funding_backfill"},
        )

        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        click.echo(f"Backfilling funding {inst_id}: {start.date()} -> {end.date()}")

        rows = client.paginate_funding_history(inst_id, start_ms=start_ms, end_ms=end_ms)
        result = await store.upsert_funding_rates(rows, source="okx", inst_id=inst_id)
        await store.finish_job(
            job_id,
            status="success",
            rows_fetched=len(rows),
            rows_inserted=int(result.get("inserted", 0)),
        )
        click.echo(f"Funding backfill complete: {len(rows):,} rows fetched.")
    except Exception as exc:
        click.echo(f"ERROR: {exc}", err=True)
        if "job_id" in locals():
            await store.finish_job(job_id, status="failed", error_message=str(exc))
        raise
    finally:
        client.close()
        await store.close()


@click.command()
@click.option("--inst", required=True, help="OKX SWAP instrument ID, e.g. BTC-USDT-SWAP")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD (exclusive)")
@click.option("--config", default="config/settings.yaml", show_default=True)
def cli(inst: str, start: str, end: str, config: str) -> None:
    """Backfill funding-rate history into funding_rates."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)
    asyncio.run(backfill_funding(
        dsn=dsn,
        inst_id=inst,
        start=_parse_dt(start),
        end=_parse_dt(end),
    ))


if __name__ == "__main__":
    cli()
