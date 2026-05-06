"""
Manual cross-exchange validation of canonical OHLCV data.
Compares OKX canonical candles against Binance and Bybit.
Flags outliers (z-score > threshold). Optionally replaces with median.

Usage:
    python scripts/market_data/validate.py \\
        --inst BTC-USDT-SWAP --bar 1H --window-days 7

    # With replacement of detected outliers:
    python scripts/market_data/validate.py \\
        --inst BTC-USDT-SWAP --bar 1H --window-days 7 --replace
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore
from okx_quant.data.validators.cross_exchange import CrossExchangeValidator


async def run_validate(
    dsn: str,
    inst_id: str,
    bar: str,
    window_days: int,
    sigma_threshold: float,
    replace: bool,
) -> None:
    store = await CandleStore.from_dsn(dsn)
    validator = CrossExchangeValidator(
        store=store,
        sigma_threshold=sigma_threshold,
        replace_outliers=replace,
    )

    try:
        end   = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=window_days)

        click.echo(f"Validating {inst_id} {bar}: {start.date()} → {end.date()}")
        click.echo(f"  sigma_threshold={sigma_threshold}, replace={replace}")

        job_id = await store.start_job(
            job_type="validate", source="cross_exchange",
            inst_id=inst_id, bar=bar, start_ts=start, end_ts=end,
            details={"sigma_threshold": sigma_threshold, "replace": replace},
        )

        result = await validator.validate_window(
            inst_id=inst_id,
            bar=bar,
            start=start,
            end=end,
            replace=replace,
            job_id=job_id,
        )

        await store.finish_job(
            job_id,
            status="success",
            outliers_found=result["flagged"],
            details=result,
        )

        click.echo(f"\nValidation complete:")
        click.echo(f"  Candles checked : {result['checked']}")
        click.echo(f"  Outliers flagged: {result['flagged']}")
        click.echo(f"  Outliers replaced: {result['replaced']}")
        if result["partial_sources"]:
            click.echo(f"  Partial sources : {result['partial_sources']}")
        if result.get("skipped_no_map"):
            click.echo(f"  NOTE: {inst_id} has no cross-exchange mapping.")

    finally:
        validator.close()
        await store.close()


@click.command()
@click.option("--inst", required=True, help="OKX instrument ID, e.g. BTC-USDT-SWAP")
@click.option("--bar", required=True, help="Bar size, e.g. 1H, 1m")
@click.option("--window-days", default=7, show_default=True,
              help="Number of days to validate")
@click.option("--sigma-threshold", default=3.0, show_default=True,
              help="Z-score threshold for outlier detection")
@click.option("--replace", is_flag=True, default=False,
              help="Replace outliers in canonical_candles with cross-exchange median")
@click.option("--config", default="config/settings.yaml", show_default=True)
def cli(inst: str, bar: str, window_days: int, sigma_threshold: float,
        replace: bool, config: str) -> None:
    """Validate canonical OHLCV against Binance and Bybit. Manual-only."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)

    effective_sigma = sigma_threshold or cfg.market_data.validation.sigma_threshold

    asyncio.run(run_validate(
        dsn=dsn,
        inst_id=inst,
        bar=bar,
        window_days=window_days,
        sigma_threshold=effective_sigma,
        replace=replace,
    ))


if __name__ == "__main__":
    cli()
