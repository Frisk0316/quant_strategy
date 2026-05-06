"""
One-click update: fetch all active instrument+bar pairs to the current time.
Picks up from the last stored canonical candle and fetches forward.

Usage:
    python scripts/market_data/update_all.py
    python scripts/market_data/update_all.py --config config/settings.yaml
    python scripts/market_data/update_all.py --dry-run
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
from okx_quant.data.exchange_clients.okx_public import OKXPublicClient, _BAR_MS


def _now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


async def update_all(dsn: str, max_retries: int, backoff_secs: list[int],
                     dry_run: bool) -> None:
    store = await CandleStore.from_dsn(dsn)
    client = OKXPublicClient()

    try:
        active_pairs = await store.get_active_instrument_bars()
        if not active_pairs:
            click.echo("No active instrument_bars found. Run init_db.py first.")
            return

        job_id = await store.start_job(
            job_type="update_all", source="okx",
            details={"dry_run": dry_run, "pairs": len(active_pairs)},
        )

        now_ms = _now_ms()
        total_inserted = 0
        total_gaps = 0
        skipped = 0
        summary_rows = []

        click.echo(f"Updating {len(active_pairs)} active (inst_id, bar) pairs...\n")

        for pair in active_pairs:
            inst_id = pair["inst_id"]
            bar     = pair["bar"]
            bar_ms  = _BAR_MS.get(bar, 60_000)

            last_ts_ms = await store.get_last_canonical_ts(inst_id, bar)
            if last_ts_ms is None:
                click.echo(f"  SKIP {inst_id} {bar}: no canonical data. Run backfill first.")
                skipped += 1
                summary_rows.append((inst_id, bar, "no_data", 0, 0))
                continue

            start_ms = last_ts_ms + bar_ms
            if start_ms >= now_ms:
                click.echo(f"  OK   {inst_id} {bar}: already up to date.")
                summary_rows.append((inst_id, bar, "up_to_date", 0, 0))
                continue

            start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
            end_dt   = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)

            if dry_run:
                lag_min = (now_ms - last_ts_ms) / 60_000
                click.echo(f"  DRY  {inst_id} {bar}: would fetch ~{lag_min:.0f} min of data")
                summary_rows.append((inst_id, bar, "dry_run", 0, 0))
                continue

            # Decide which endpoint to use: recent (<300 bars) vs history (>300)
            bars_needed = (now_ms - start_ms) // bar_ms
            try:
                if bars_needed <= 280:
                    rows = client.get_recent_candles(inst_id, bar, limit=300)
                    rows = [r for r in rows if r["ts_ms"] >= start_ms]
                else:
                    rows = client.paginate_history(inst_id, bar, start_ms, now_ms)
            except Exception as exc:
                click.echo(f"  WARN {inst_id} {bar}: fetch failed: {exc}")
                await store.log_quality_event(
                    inst_id=inst_id, bar=bar, issue_type="fetch_failed",
                    severity="warning", job_id=job_id, notes=str(exc),
                )
                summary_rows.append((inst_id, bar, "fetch_failed", 0, 0))
                continue

            if not rows:
                click.echo(f"  WARN {inst_id} {bar}: no new rows returned")
                summary_rows.append((inst_id, bar, "no_rows", 0, 0))
                continue

            result = await store.upsert_raw_candles(rows, "okx", inst_id, bar)
            await store.canonicalize_from_raw("okx", inst_id, bar, start_dt, end_dt)

            # Gap detection + retry
            chunk_gaps = 0
            for attempt in range(max_retries):
                gaps = await store.detect_gaps(inst_id, bar, start_dt, end_dt)
                if not gaps:
                    break
                sleep_s = backoff_secs[attempt] if attempt < len(backoff_secs) else backoff_secs[-1]
                time.sleep(sleep_s)
                for gap_start, gap_end in gaps:
                    gstart_ms = int(gap_start.timestamp() * 1000)
                    gend_ms   = int(gap_end.timestamp() * 1000)
                    try:
                        gap_rows = client.paginate_history(inst_id, bar, gstart_ms, gend_ms)
                        if gap_rows:
                            await store.upsert_raw_candles(gap_rows, "okx", inst_id, bar)
                            await store.canonicalize_from_raw("okx", inst_id, bar, gap_start, gap_end)
                    except Exception:
                        pass
            else:
                gaps = await store.detect_gaps(inst_id, bar, start_dt, end_dt)
                for gap_start, gap_end in gaps:
                    chunk_gaps += 1
                    await store.log_quality_event(
                        inst_id=inst_id, bar=bar, issue_type="gap",
                        severity="warning", window_start=gap_start, window_end=gap_end,
                        retry_count=max_retries, job_id=job_id,
                    )

            await store.update_instrument_bar_bounds(inst_id, bar)
            inserted = result["inserted"]
            total_inserted += inserted
            total_gaps += chunk_gaps

            click.echo(f"  OK   {inst_id} {bar}: +{inserted} rows, {chunk_gaps} gaps")
            summary_rows.append((inst_id, bar, "updated", inserted, chunk_gaps))

        status = "success" if total_gaps == 0 and skipped == 0 else "partial"
        await store.finish_job(
            job_id, status=status,
            rows_inserted=total_inserted, gaps_found=total_gaps,
        )

        click.echo(f"\n{'='*60}")
        click.echo(f"Update complete: {total_inserted} rows inserted, "
                   f"{total_gaps} persistent gaps, {skipped} skipped.")

    finally:
        client.close()
        await store.close()


@click.command()
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--dry-run", is_flag=True, default=False,
              help="Show what would be fetched without writing to DB")
def cli(config: str, dry_run: bool) -> None:
    """Fetch new candles for all active (inst_id, bar) pairs."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)

    asyncio.run(update_all(
        dsn=dsn,
        max_retries=cfg.market_data.ingestion.max_retries,
        backoff_secs=cfg.market_data.ingestion.retry_backoff_seconds,
        dry_run=dry_run,
    ))


if __name__ == "__main__":
    cli()
