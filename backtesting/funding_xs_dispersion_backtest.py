"""Vectorized funding cross-sectional dispersion research backtest."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from itertools import product
from typing import Any
import asyncio
import concurrent.futures

import numpy as np
import pandas as pd

from backtesting.data_loader import load_candles, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from backtesting.xs_momentum_backtest import _daily_close, _funding_returns
from okx_quant.strategies.xs_momentum import XSMomentumParams, target_weights as build_target_weights

TRADING_DAYS_PER_YEAR = 365.0


@dataclass
class FundingXSDispersionParams:
    universe: list[str] = field(default_factory=list)
    bar: str = "1m"
    rebalance: str = "weekly"
    lookback_days: int = 7
    quantile: float = 0.20
    vol_window_days: int = 28
    inverse_vol: bool = True
    vol_target_annual: float = 0.175
    max_name_weight: float = 0.10
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


def trailing_funding_apr(funding: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    daily_rate = funding.sort_index().resample("1D").mean()
    trailing_8h = daily_rate.rolling(max(1, int(lookback_days)), min_periods=1).mean()
    return (1.0 + trailing_8h).pow(3.0 * TRADING_DAYS_PER_YEAR) - 1.0


def _xs_params(params: FundingXSDispersionParams) -> XSMomentumParams:
    return XSMomentumParams(
        universe=params.universe,
        bar=params.bar,
        rebalance=params.rebalance,
        lookback_days=params.lookback_days,
        skip_days=0,
        quantile=params.quantile,
        vol_window_days=params.vol_window_days,
        inverse_vol=params.inverse_vol,
        vol_target_annual=params.vol_target_annual,
        max_name_weight=params.max_name_weight,
        fee_bps=params.fee_bps,
        slippage_bps=params.slippage_bps,
    )


def _scores(funding: pd.DataFrame, params: FundingXSDispersionParams) -> pd.DataFrame:
    # Lower funding APR is the long leg, so negate before reusing XS target weights.
    return -trailing_funding_apr(funding, params.lookback_days)


def run_funding_xs_dispersion_backtest(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: FundingXSDispersionParams,
    market_close: pd.Series | None = None,
) -> BacktestResult:
    del high, low, vol
    close = close.sort_index()
    close_daily = _daily_close(close)
    scores = _scores(funding, params).reindex(close_daily.index).ffill()
    realized_vol = close_daily.pct_change(fill_method=None).rolling(params.vol_window_days, min_periods=2).std()
    market_daily = market_close.resample("1D").last() if market_close is not None else None
    target_daily = build_target_weights(scores, membership, _xs_params(params), realized_vol, market_close=market_daily)
    target = target_daily.shift(1).reindex(close.index).ffill().fillna(0.0)
    positions = target.shift(1).fillna(0.0)

    bar_returns = close.pct_change(fill_method=None).fillna(0.0)
    gross_returns = (positions * bar_returns).sum(axis=1)
    funding_by_symbol = _funding_returns(positions, funding)
    funding_return = funding_by_symbol.sum(axis=1)
    cost = compute_turnover(target) * (params.fee_bps + params.slippage_bps) / 10_000
    returns = gross_returns + funding_return - cost
    equity = (1.0 + returns).cumprod()
    daily_returns = (1.0 + returns).resample("1D").prod() - 1.0
    trades = pd.DataFrame()
    metrics = compute_metrics(equity, returns, target, trades, params.bar)
    metrics.update(
        {
            "validation_status": "research_backtest",
            "idealized_fill": False,
            "funding_cashflow": float(funding_return.sum()),
            "funding_settlement_count": int((funding.reindex(close.index).fillna(0.0) != 0.0).any(axis=1).sum()),
            "long_low_funding_short_high_funding": True,
        }
    )
    return BacktestResult(equity, daily_returns, positions, target_daily, trades, metrics)


def scan_funding_xs_dispersion(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: FundingXSDispersionParams,
    grid: dict[str, list[Any]],
    market_close: pd.Series | None = None,
    prior_family_n_trials: int = 0,
    researched_n_trials: int | None = None,
) -> pd.DataFrame:
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]
    if researched_n_trials is None:
        total_n_trials = int(prior_family_n_trials) + len(combos)
        n_trials_provenance = "grid_size_floor"
        n_trials_is_floor = True
    else:
        total_n_trials = int(researched_n_trials)
        n_trials_provenance = "caller_declared"
        n_trials_is_floor = False

    fields = set(FundingXSDispersionParams.__dataclass_fields__)
    rows = []
    for combo in combos:
        run_params = replace(params, **{key: value for key, value in combo.items() if key in fields})
        result = run_funding_xs_dispersion_backtest(
            close,
            high,
            low,
            vol,
            funding,
            membership,
            run_params,
            market_close=market_close,
        )
        rows.append(
            {
                **combo,
                "n_trials": total_n_trials,
                "n_trials_provenance": n_trials_provenance,
                "n_trials_is_floor": n_trials_is_floor,
                **result.metrics,
            }
        )
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    out.attrs["n_trials_provenance"] = n_trials_provenance
    out.attrs["n_trials_is_floor"] = n_trials_is_floor
    return out


def load_funding_xs_dispersion_inputs(
    symbols: list[str],
    *,
    bar: str = "1m",
    data_dir: str = "data/ticks",
    start: str | None = None,
    end: str | None = None,
    backend: str = "postgres",
    dsn: str | None = None,
    exchange: str = "binance",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if backend == "postgres" and dsn and exchange:
        if bar == "1D":
            return _load_postgres_daily_close_and_funding(symbols, start=start, end=end, dsn=dsn, exchange=exchange)
        return _load_postgres_close_and_funding(symbols, bar=bar, start=start, end=end, dsn=dsn, exchange=exchange)

    closes = {}
    funding = {}
    for symbol in symbols:
        candles = load_candles(
            symbol,
            bar=bar,
            data_dir=data_dir,
            start=start,
            end=end,
            backend=backend,  # type: ignore[arg-type]
            dsn=dsn,
            exchange=exchange,
        )
        closes[symbol] = candles["close"]
        rates = load_funding(symbol, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn)["rate"]
        funding[symbol] = rates[~rates.index.duplicated(keep="last")]
    close = pd.DataFrame(closes)
    # The runner reuses the XS momentum call shape; this strategy only needs close.
    return close, close, close, close, pd.DataFrame(funding)


def _to_utc_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        return asyncio.run(coro)


def _rows_to_series(rows: list[Any], value_col: str) -> pd.Series:
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame([dict(row) for row in rows])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    out = df.set_index("ts").sort_index()[value_col].astype(float)
    if out.index.tz is not None:
        out.index = out.index.tz_convert("UTC").tz_localize(None)
    return out[~out.index.duplicated(keep="last")]


def _load_postgres_close_and_funding(
    symbols: list[str],
    *,
    bar: str,
    start: str | None,
    end: str | None,
    dsn: str,
    exchange: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    async def fetch() -> tuple[pd.DataFrame, pd.DataFrame]:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        start_dt = _to_utc_dt(start)
        end_dt = _to_utc_dt(end)
        closes: dict[str, pd.Series] = {}
        funding: dict[str, pd.Series] = {}
        try:
            for symbol in symbols:
                candle_rows = await conn.fetch(
                    """
                    SELECT ts, close
                    FROM canonical_candles
                    WHERE inst_id = $1
                      AND bar = $2
                      AND source_primary = $3
                      AND quality_status != 'suspect'
                      AND ($4::timestamptz IS NULL OR ts >= $4)
                      AND ($5::timestamptz IS NULL OR ts <  $5)
                    ORDER BY ts
                    """,
                    symbol,
                    bar,
                    exchange,
                    start_dt,
                    end_dt,
                )
                close = _rows_to_series(candle_rows, "close")
                if close.empty:
                    raise ValueError(f"no venue-scoped candles for {symbol} exchange={exchange}")
                closes[symbol] = close
                funding_rows = await conn.fetch(
                    """
                    SELECT ts, funding_rate AS rate
                    FROM funding_rates
                    WHERE inst_id = $1
                      AND ($2::timestamptz IS NULL OR ts >= $2)
                      AND ($3::timestamptz IS NULL OR ts <  $3)
                    ORDER BY ts
                    """,
                    symbol,
                    start_dt,
                    end_dt,
                )
                funding[symbol] = _rows_to_series(funding_rows, "rate")
        finally:
            await conn.close()
        return pd.DataFrame(closes), pd.DataFrame(funding)

    close, funding = _run_sync(fetch())
    return close, close, close, close, funding


def _load_postgres_daily_close_and_funding(
    symbols: list[str],
    *,
    start: str | None,
    end: str | None,
    dsn: str,
    exchange: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    async def fetch() -> tuple[pd.DataFrame, pd.DataFrame]:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        start_dt = _to_utc_dt(start)
        end_dt = _to_utc_dt(end)
        try:
            candle_rows = await conn.fetch(
                """
                WITH daily AS (
                    SELECT inst_id, date_trunc('day', ts) AS day, ts, close
                    FROM canonical_candles
                    WHERE inst_id = ANY($1::text[])
                      AND bar = '1m'
                      AND source_primary = $2
                      AND quality_status != 'suspect'
                      AND ($3::timestamptz IS NULL OR ts >= $3)
                      AND ($4::timestamptz IS NULL OR ts <  $4)
                )
                SELECT DISTINCT ON (inst_id, day) inst_id, day AS ts, close
                FROM daily
                ORDER BY inst_id, day, ts DESC
                """,
                symbols,
                exchange,
                start_dt,
                end_dt,
            )
            funding_rows = await conn.fetch(
                """
                SELECT inst_id, date_trunc('day', ts) AS ts, AVG(funding_rate)::float AS rate
                FROM funding_rates
                WHERE inst_id = ANY($1::text[])
                  AND ($2::timestamptz IS NULL OR ts >= $2)
                  AND ($3::timestamptz IS NULL OR ts <  $3)
                GROUP BY inst_id, date_trunc('day', ts)
                ORDER BY inst_id, ts
                """,
                symbols,
                start_dt,
                end_dt,
            )
        finally:
            await conn.close()

        close_df = pd.DataFrame([dict(row) for row in candle_rows])
        funding_df = pd.DataFrame([dict(row) for row in funding_rows])
        if close_df.empty:
            raise ValueError("no daily venue-scoped close rows loaded")
        close = close_df.pivot(index="ts", columns="inst_id", values="close").sort_index().astype(float)
        if funding_df.empty:
            funding = pd.DataFrame(index=close.index, columns=symbols, dtype=float)
        else:
            funding = funding_df.pivot(index="ts", columns="inst_id", values="rate").sort_index().astype(float)
        for frame in (close, funding):
            frame.index = pd.to_datetime(frame.index, utc=True)
            if frame.index.tz is not None:
                frame.index = frame.index.tz_convert("UTC").tz_localize(None)
        return close, funding

    close, funding = _run_sync(fetch())
    return close, close, close, close, funding


def json_signal(series: pd.Series) -> dict[str, float]:
    clean = series.dropna().astype(float)
    return {pd.Timestamp(ts).date().isoformat(): float(value) for ts, value in clean.items() if np.isfinite(value)}
