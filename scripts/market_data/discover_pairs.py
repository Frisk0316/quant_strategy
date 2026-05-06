"""
Strategy-based pair discovery.

pairs_trading: Engle-Granger cointegration test on all active SWAP pairs,
               returns the top N pairs by half-life and p-value.

funding_carry: Ranks active SWAP instruments by current funding APR via
               live OKX API calls.

Usage:
    python scripts/market_data/discover_pairs.py \\
        --strategy pairs_trading --bar 1H --lookback-days 90 --top-n 10

    python scripts/market_data/discover_pairs.py \\
        --strategy funding_carry --min-apr 0.12 --top-n 10
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Optional

import click
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore
from okx_quant.data.exchange_clients.okx_public import OKXPublicClient


def _estimate_ou_half_life(spread: pd.Series) -> float:
    """Estimate Ornstein-Uhlenbeck half-life from a spread series."""
    spread = spread.dropna()
    if len(spread) < 10:
        return float("inf")
    lag = spread.shift(1).dropna()
    delta = spread.diff().dropna()
    try:
        beta = np.polyfit(lag, delta, 1)[0]
        if beta >= 0:
            return float("inf")
        return float(-np.log(2) / beta)
    except Exception:
        return float("inf")


async def discover_pairs_trading(
    dsn: str,
    bar: str,
    lookback_days: int,
    top_n: int,
    p_value_threshold: float,
    max_half_life: float,
) -> None:
    from statsmodels.tsa.stattools import coint

    store = await CandleStore.from_dsn(dsn)
    try:
        end   = datetime.now(tz=timezone.utc)
        start = end - timedelta(days=lookback_days)

        active = await store.get_active_instruments()
        inst_ids = [r["inst_id"] for r in active]

        if len(inst_ids) < 2:
            click.echo("Need at least 2 active instruments for pairs discovery.")
            return

        click.echo(f"Loading close prices for {len(inst_ids)} instruments "
                   f"({start.date()} → {end.date()}, bar={bar})...")

        prices: dict[str, pd.Series] = {}
        for inst_id in inst_ids:
            df = await store.get_canonical_candles(inst_id, bar, start=start, end=end)
            if not df.empty and "close" in df.columns:
                prices[inst_id] = np.log(df["close"].astype(float))

        if len(prices) < 2:
            click.echo("Insufficient price data. Run backfill first.")
            return

        click.echo(f"Testing {len(prices) * (len(prices)-1) // 2} pairs for cointegration...")

        results = []
        for sym_x, sym_y in combinations(prices.keys(), 2):
            px = prices[sym_x]
            py = prices[sym_y]
            aligned = pd.concat([px, py], axis=1, join="inner").dropna()
            if len(aligned) < lookback_days // 2:
                continue
            overlap = len(aligned) / max(len(px), len(py))
            try:
                score, pval, _ = coint(aligned.iloc[:, 0], aligned.iloc[:, 1])
            except Exception:
                continue
            if pval > p_value_threshold:
                continue
            # Estimate beta and spread for half-life
            beta = np.polyfit(aligned.iloc[:, 0], aligned.iloc[:, 1], 1)
            spread = aligned.iloc[:, 1] - beta[0] * aligned.iloc[:, 0]
            hl = _estimate_ou_half_life(spread)
            if hl > max_half_life:
                continue
            results.append({
                "symbol_x": sym_x,
                "symbol_y": sym_y,
                "p_value":  round(pval, 4),
                "half_life_h": round(hl, 1),
                "overlap":  round(overlap, 3),
                "beta":     round(float(beta[0]), 4),
            })

        if not results:
            click.echo("No cointegrated pairs found with current thresholds.")
            return

        df_results = (
            pd.DataFrame(results)
            .sort_values(["p_value", "half_life_h"])
            .head(top_n)
            .reset_index(drop=True)
        )
        click.echo(f"\nTop {min(top_n, len(df_results))} cointegrated pairs:")
        click.echo(df_results.to_string(index=False))

    finally:
        await store.close()


async def discover_funding_carry(
    min_apr: float,
    top_n: int,
    dsn: str,
) -> None:
    store = await CandleStore.from_dsn(dsn)
    client = OKXPublicClient()

    try:
        active = await store.get_active_instruments()
        inst_ids = [r["inst_id"] for r in active]

        click.echo(f"Fetching current funding rates for {len(inst_ids)} instruments...")

        rows = []
        for inst_id in inst_ids:
            data = client.get_funding_rate(inst_id)
            if not data:
                continue
            try:
                rate = float(data.get("fundingRate", 0))
                apr = rate * (365 * 24 / 8)  # 8-hour funding → annualized
                rows.append({
                    "inst_id": inst_id,
                    "funding_rate_8h": round(rate, 6),
                    "apr": round(apr, 4),
                    "next_funding_time": data.get("nextFundingTime", ""),
                })
            except (ValueError, TypeError):
                continue

        if not rows:
            click.echo("No funding rate data retrieved.")
            return

        df = (
            pd.DataFrame(rows)
            .query("apr >= @min_apr")
            .sort_values("apr", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

        if df.empty:
            click.echo(f"No instruments with APR >= {min_apr:.0%}")
            return

        click.echo(f"\nTop {len(df)} instruments by funding APR (min {min_apr:.0%}):")
        click.echo(df.to_string(index=False))

    finally:
        client.close()
        await store.close()


@click.command()
@click.option("--strategy", required=True,
              type=click.Choice(["pairs_trading", "funding_carry"]),
              help="Strategy type to discover pairs for")
@click.option("--bar", default="1H", show_default=True,
              help="Candle bar for pairs_trading analysis")
@click.option("--lookback-days", default=90, show_default=True,
              help="Lookback window in days for cointegration test")
@click.option("--top-n", default=10, show_default=True,
              help="Number of top results to show")
@click.option("--p-value", default=0.05, show_default=True,
              help="Cointegration p-value threshold")
@click.option("--max-half-life", default=48.0, show_default=True,
              help="Maximum OU half-life in hours")
@click.option("--min-apr", default=0.12, show_default=True,
              help="Minimum annualized APR for funding_carry filter")
@click.option("--config", default="config/settings.yaml", show_default=True)
def cli(
    strategy: str,
    bar: str,
    lookback_days: int,
    top_n: int,
    p_value: float,
    max_half_life: float,
    min_apr: float,
    config: str,
) -> None:
    """Discover suitable trading pairs based on strategy criteria."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)

    if strategy == "pairs_trading":
        asyncio.run(discover_pairs_trading(
            dsn=dsn, bar=bar, lookback_days=lookback_days, top_n=top_n,
            p_value_threshold=p_value, max_half_life=max_half_life,
        ))
    elif strategy == "funding_carry":
        asyncio.run(discover_funding_carry(
            min_apr=min_apr, top_n=top_n, dsn=dsn,
        ))


if __name__ == "__main__":
    cli()
