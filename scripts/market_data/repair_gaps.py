"""
Targeted gap repair for a specific instrument+bar+time window.
Detects missing candles, fetches them from OKX, and marks resolved events.

Usage:
    python scripts/market_data/repair_gaps.py \\
        --inst BTC-USDT-SWAP --bar 1m \\
        --start 2026-05-01 --end 2026-05-04
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore
from okx_quant.data.exchange_clients.okx_public import OKXPublicClient


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


async def repair_gaps(
    dsn: str,
    inst_id: str,
    bar: str,
    start: datetime,
    end: datetime,
    max_retries: int,
    backoff_secs: list[int],
) -> None:
    store = await CandleStore.from_dsn(dsn)
    client = OKXPublicClient()

    try:
        job_id = await store.start_job(
            job_type="repair_gap", source="okx",
            inst_id=inst_id, bar=bar, start_ts=start, end_ts=end,
        )

        initial_gaps = await store.detect_gaps(inst_id, bar, start, end)
        if not initial_gaps:
            click.echo(f"No gaps found in {inst_id} {bar} {start.date()} → {end.date()}")
            await store.finish_job(job_id, "success")
            return

        click.echo(f"Found {len(initial_gaps)} gap range(s) in {inst_id} {bar}")

        repaired = 0
        persistent = 0

        for gap_start, gap_end in initial_gaps:
            click.echo(f"  Repairing {gap_start} → {gap_end}")
            gstart_ms = int(gap_start.timestamp() * 1000)
            gend_ms   = int(gap_end.timestamp() * 1000)

            success = False
            for attempt in range(max_retries):
                sleep_s = backoff_secs[attempt] if attempt < len(backoff_secs) else backoff_secs[-1]
                time.sleep(sleep_s)
                try:
                    rows = client.paginate_history(inst_id, bar, gstart_ms, gend_ms)
                    if rows:
                        await store.upsert_raw_candles(rows, "okx", inst_id, bar)
                        await store.canonicalize_from_raw("okx", inst_id, bar, gap_start, gap_end)
                    remaining = await store.detect_gaps(inst_id, bar, gap_start, gap_end)
                    if not remaining:
                        success = True
                        break
                except Exception as exc:
                    click.echo(f"    Attempt {attempt+1} failed: {exc}")

            if success:
                repaired += 1
                # Resolve any open quality events for this window
                resolved = await store.resolve_quality_events(
                    inst_id, bar, gap_start, gap_end, issue_type="gap"
                )
                click.echo(f"    Repaired. Resolved {resolved} quality event(s).")
            else:
                persistent += 1
                await store.log_quality_event(
                    inst_id=inst_id, bar=bar, issue_type="gap",
                    severity="critical", window_start=gap_start, window_end=gap_end,
                    retry_count=max_retries, job_id=job_id,
                    notes="Persistent after repair attempts",
                )
                click.echo(f"    WARN: gap persists after {max_retries} attempts.")

        await store.update_instrument_bar_bounds(inst_id, bar)
        status = "success" if persistent == 0 else "partial"
        await store.finish_job(
            job_id, status=status,
            gaps_found=persistent,
            details={"repaired": repaired, "persistent": persistent},
        )
        click.echo(f"\nRepair complete: {repaired} fixed, {persistent} persistent.")

    finally:
        client.close()
        await store.close()


@click.command()
@click.option("--inst", required=True, help="OKX instrument ID, e.g. BTC-USDT-SWAP")
@click.option("--bar", required=True, help="Bar size, e.g. 1m, 1H")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD (exclusive)")
@click.option("--config", default="config/settings.yaml", show_default=True)
def cli(inst: str, bar: str, start: str, end: str, config: str) -> None:
    """Detect and repair gaps in canonical_candles for a specific window."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)

    asyncio.run(repair_gaps(
        dsn=dsn,
        inst_id=inst,
        bar=bar,
        start=_parse_dt(start),
        end=_parse_dt(end),
        max_retries=cfg.market_data.ingestion.max_retries,
        backoff_secs=cfg.market_data.ingestion.retry_backoff_seconds,
    ))


if __name__ == "__main__":
    cli()
