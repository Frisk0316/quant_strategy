"""
Initialize the TimescaleDB schema and seed instruments from config.

Usage:
    python scripts/market_data/init_db.py
    python scripts/market_data/init_db.py --config config/settings.yaml
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg
import click

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config


async def _apply_migration(conn: asyncpg.Connection, sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    sql_without_comments = "\n".join(
        line.split("--", 1)[0] for line in sql.splitlines()
    )
    statements = [s.strip() for s in sql_without_comments.split(";") if s.strip()]
    for stmt in statements:
        try:
            if stmt.lstrip().upper().startswith("SELECT"):
                await conn.fetch(stmt)
            else:
                await conn.execute(stmt)
        except Exception as exc:
            # Idempotent: skip "already exists" errors from IF NOT EXISTS
            msg = str(exc).lower()
            if "already exists" in msg or "duplicate" in msg:
                continue
            raise


async def _seed_instruments(conn: asyncpg.Connection, instruments: list[str]) -> int:
    count = 0
    for inst_id in instruments:
        parts = inst_id.split("-")
        base_ccy = parts[0] if parts else inst_id
        inst_type = parts[2] if len(parts) >= 3 else "SWAP"
        quote_ccy = parts[1] if len(parts) >= 2 else "USDT"

        result = await conn.execute(
            """
            INSERT INTO instruments (inst_id, exchange, inst_type, base_ccy, quote_ccy, settle_ccy)
            VALUES ($1, 'okx', $2, $3, $4, $4)
            ON CONFLICT (inst_id) DO NOTHING
            """,
            inst_id, inst_type, base_ccy, quote_ccy,
        )
        if result.endswith("1"):
            count += 1
    return count


async def _seed_instrument_bars(
    conn: asyncpg.Connection, instruments: list[str], bars: list[str]
) -> int:
    count = 0
    for inst_id in instruments:
        for bar in bars:
            result = await conn.execute(
                """
                INSERT INTO instrument_bars (inst_id, bar)
                VALUES ($1, $2)
                ON CONFLICT (inst_id, bar) DO NOTHING
                """,
                inst_id, bar,
            )
            if result.endswith("1"):
                count += 1
    return count


async def main(config_path: str) -> None:
    cfg = load_config(settings_path=config_path, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn is not set in settings.yaml", err=True)
        sys.exit(1)

    migrations_dir = (
        Path(__file__).parent.parent.parent
        / "src" / "okx_quant" / "data" / "migrations"
    )
    migration_paths = sorted(migrations_dir.glob("*.sql"))
    if not migration_paths:
        click.echo(f"ERROR: No migration files found in: {migrations_dir}", err=True)
        sys.exit(1)

    instruments = cfg.market_data.instruments
    bars = cfg.market_data.bars

    click.echo(f"Connecting to {dsn.split('@')[-1]}...")
    conn = await asyncpg.connect(dsn)
    try:
        for migration_path in migration_paths:
            click.echo(f"Applying migration {migration_path.name}...")
            await _apply_migration(conn, migration_path)
            click.echo("  Migration applied.")

        click.echo(f"Seeding {len(instruments)} instruments...")
        seeded_insts = await _seed_instruments(conn, instruments)
        click.echo(f"  Inserted {seeded_insts} new instruments ({len(instruments)} total).")

        click.echo(f"Seeding instrument bars ({len(instruments)} x {len(bars)})...")
        seeded_bars = await _seed_instrument_bars(conn, instruments, bars)
        click.echo(f"  Inserted {seeded_bars} new instrument_bars rows.")

        click.echo("\nDatabase initialization complete.")
        click.echo(f"  Instruments: {len(instruments)}")
        click.echo(f"  Bars per instrument: {bars}")
        click.echo(f"  Total instrument_bars: {len(instruments) * len(bars)}")
    finally:
        await conn.close()


@click.command()
@click.option("--config", default="config/settings.yaml", show_default=True,
              help="Path to settings.yaml")
def cli(config: str) -> None:
    """Initialize TimescaleDB schema and seed instruments from config."""
    asyncio.run(main(config))


if __name__ == "__main__":
    cli()
