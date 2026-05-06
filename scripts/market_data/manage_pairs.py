"""
Pair management CLI: add, remove, purge, list, and status for tracked instruments.

Usage:
    python scripts/market_data/manage_pairs.py list
    python scripts/market_data/manage_pairs.py status --inst-id BTC-USDT-SWAP
    python scripts/market_data/manage_pairs.py add --inst-ids BNB-USDT-SWAP --bars 1m 1H
    python scripts/market_data/manage_pairs.py remove --inst-id SHIB-USDT-SWAP
    python scripts/market_data/manage_pairs.py purge --inst-id SHIB-USDT-SWAP --confirm SHIB-USDT-SWAP
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore


def _get_dsn(config: str) -> str:
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)
    return dsn


@click.group()
def cli() -> None:
    """Manage tracked trading pairs in the OHLCV database."""


@cli.command("list")
@click.option("--config", default="config/settings.yaml", show_default=True)
def list_pairs(config: str) -> None:
    """List all instruments with their data coverage."""

    async def _run() -> None:
        dsn = _get_dsn(config)
        store = await CandleStore.from_dsn(dsn)
        try:
            rows = await store._pool.fetch(
                """
                SELECT
                    i.inst_id,
                    i.is_active,
                    array_agg(ib.bar ORDER BY ib.bar) AS bars,
                    MIN(ib.first_candle_ts) AS first_ts,
                    MAX(ib.last_candle_ts)  AS last_ts
                FROM instruments i
                LEFT JOIN instrument_bars ib ON ib.inst_id = i.inst_id AND ib.is_active = TRUE
                GROUP BY i.inst_id, i.is_active
                ORDER BY i.is_active DESC, i.inst_id
                """
            )
            if not rows:
                click.echo("No instruments registered. Run init_db.py first.")
                return

            click.echo(f"\n{'INST_ID':<20} {'ACTIVE':<8} {'BARS':<24} {'FIRST':<22} {'LAST':<22}")
            click.echo("-" * 100)
            for r in rows:
                bars = ",".join(b for b in (r["bars"] or []) if b)
                first = str(r["first_ts"])[:19] if r["first_ts"] else "—"
                last  = str(r["last_ts"])[:19]  if r["last_ts"]  else "—"
                active = "yes" if r["is_active"] else "no"
                click.echo(f"{r['inst_id']:<20} {active:<8} {bars:<24} {first:<22} {last:<22}")
        finally:
            await store.close()

    asyncio.run(_run())


@cli.command("status")
@click.option("--inst-id", required=True, help="OKX instrument ID")
@click.option("--config", default="config/settings.yaml", show_default=True)
def pair_status(inst_id: str, config: str) -> None:
    """Show data coverage and quality summary for one instrument."""

    async def _run() -> None:
        dsn = _get_dsn(config)
        store = await CandleStore.from_dsn(dsn)
        try:
            bars = await store._pool.fetch(
                """
                SELECT bar, is_active, first_candle_ts, last_candle_ts, last_checked_at
                FROM instrument_bars WHERE inst_id=$1 ORDER BY bar
                """,
                inst_id,
            )
            if not bars:
                click.echo(f"{inst_id}: not registered.")
                return

            click.echo(f"\n{inst_id}")
            click.echo("\nBars:")
            for b in bars:
                first = str(b["first_candle_ts"])[:19] if b["first_candle_ts"] else "—"
                last  = str(b["last_candle_ts"])[:19]  if b["last_candle_ts"]  else "—"
                active = "" if b["is_active"] else " [inactive]"
                click.echo(f"  {b['bar']:<6} first={first}  last={last}{active}")

            quality = await store.get_quality_summary(inst_id)
            click.echo("\nQuality events:")
            if not quality:
                click.echo("  (none)")
            else:
                for q in quality:
                    click.echo(f"  {q['bar']:<6} {q['issue_type']:<20} "
                               f"{q['severity']:<10} {q['status']:<10} count={q['count']}")

            last_backfill = await store.get_last_job(inst_id, "backfill")
            last_update   = await store.get_last_job(inst_id, "update_all")
            last_validate = await store.get_last_job(inst_id, "validate")

            click.echo("\nLast jobs:")
            for label, job in [("backfill", last_backfill),
                                ("update_all", last_update),
                                ("validate", last_validate)]:
                if job:
                    click.echo(f"  {label:<12} status={job['status']} "
                               f"started={str(job['started_at'])[:19]} "
                               f"inserted={job['rows_inserted']} gaps={job['gaps_found']}")
                else:
                    click.echo(f"  {label:<12} (never run)")
        finally:
            await store.close()

    asyncio.run(_run())


@cli.command("add")
@click.option("--inst-ids", required=True, multiple=True, help="OKX instrument IDs to add")
@click.option("--bars", multiple=True, default=["1m", "5m", "15m", "1H"],
              show_default=True, help="Bars to track")
@click.option("--backfill-days", default=None, type=int,
              help="If set, run backfill for this many days after adding")
@click.option("--config", default="config/settings.yaml", show_default=True)
def add_pairs(inst_ids: tuple, bars: tuple, backfill_days: int | None, config: str) -> None:
    """Add new instruments to the tracking registry."""

    async def _run() -> None:
        dsn = _get_dsn(config)
        store = await CandleStore.from_dsn(dsn)
        try:
            for inst_id in inst_ids:
                parts = inst_id.split("-")
                base_ccy = parts[0]
                await store.register_instrument(inst_id=inst_id, base_ccy=base_ccy)
                for bar in bars:
                    await store.register_instrument_bar(inst_id=inst_id, bar=bar)
                click.echo(f"Registered {inst_id} with bars: {', '.join(bars)}")
        finally:
            await store.close()

    asyncio.run(_run())

    if backfill_days:
        from datetime import datetime, timedelta, timezone
        end_str   = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        start_str = (datetime.now(tz=timezone.utc) - timedelta(days=backfill_days)).strftime("%Y-%m-%d")
        for inst_id in inst_ids:
            for bar in bars:
                click.echo(f"\nBackfilling {inst_id} {bar} last {backfill_days} days...")
                subprocess.run(
                    [sys.executable, str(Path(__file__).parent / "backfill.py"),
                     "--inst", inst_id, "--bar", bar,
                     "--start", start_str, "--end", end_str,
                     "--config", config],
                    check=False,
                )


@cli.command("remove")
@click.option("--inst-id", required=True, help="OKX instrument ID to archive")
@click.option("--config", default="config/settings.yaml", show_default=True)
def remove_pair(inst_id: str, config: str) -> None:
    """Archive an instrument (set is_active=False). Data is NOT deleted."""

    async def _run() -> None:
        dsn = _get_dsn(config)
        store = await CandleStore.from_dsn(dsn)
        try:
            await store.set_instrument_active(inst_id, active=False)
            # Also deactivate all bars
            bars = await store._pool.fetch(
                "SELECT bar FROM instrument_bars WHERE inst_id=$1", inst_id
            )
            for b in bars:
                await store.set_instrument_bar_active(inst_id, b["bar"], active=False)
            click.echo(f"Archived {inst_id}. Candle data retained. "
                       f"It will be excluded from future update_all runs.")
        finally:
            await store.close()

    asyncio.run(_run())


@cli.command("purge")
@click.option("--inst-id", required=True, help="OKX instrument ID to hard-delete")
@click.option("--confirm", required=True,
              help="Must match --inst-id exactly to confirm deletion")
@click.option("--config", default="config/settings.yaml", show_default=True)
def purge_pair(inst_id: str, confirm: str, config: str) -> None:
    """Hard-delete all data for an instrument. IRREVERSIBLE."""
    if confirm != inst_id:
        click.echo(f"ERROR: --confirm '{confirm}' does not match --inst-id '{inst_id}'", err=True)
        sys.exit(1)

    async def _run() -> None:
        dsn = _get_dsn(config)
        conn = await asyncpg.connect(dsn)
        try:
            click.echo(f"Purging all data for {inst_id}...")
            await conn.execute(
                "DELETE FROM canonical_candles WHERE inst_id=$1", inst_id
            )
            await conn.execute(
                "DELETE FROM raw_candles WHERE inst_id=$1", inst_id
            )
            await conn.execute(
                "DELETE FROM funding_rates WHERE inst_id=$1", inst_id
            )
            await conn.execute(
                "DELETE FROM instrument_bars WHERE inst_id=$1", inst_id
            )
            await conn.execute(
                "DELETE FROM instruments WHERE inst_id=$1", inst_id
            )
            click.echo(f"Purged {inst_id} and all associated data.")
        finally:
            await conn.close()

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
