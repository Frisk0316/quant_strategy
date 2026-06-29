"""Vectorized S6 slow time-series momentum research backtest."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from backtesting.data_loader import load_candles, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from okx_quant.strategies.s6_ts_momentum import S6TSMomentumParams

TRADING_DAYS_PER_YEAR = 365.0


def _daily_close(close: pd.DataFrame) -> pd.DataFrame:
    return close.sort_index().resample("1D").last().dropna(how="all")


def _funding_returns(positions: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    rates = funding.reindex(index=positions.index, columns=positions.columns).fillna(0.0)
    return -(positions * rates)


def _rebalance_mask(index: pd.DatetimeIndex, rebalance: str) -> pd.Series:
    if rebalance.lower() == "monthly":
        return pd.Series(index.day == 1, index=index)
    if rebalance.lower() == "weekly":
        return pd.Series(index.weekday == 0, index=index)
    return pd.Series(True, index=index)


def _target_weights(close_daily: pd.DataFrame, params: S6TSMomentumParams) -> pd.DataFrame:
    returns = close_daily.pct_change()
    trailing = close_daily / close_daily.shift(params.lookback_days) - 1.0
    vol = returns.rolling(params.vol_window_days, min_periods=2).std()
    scale = params.vol_target_annual / (vol.replace(0.0, np.nan) * np.sqrt(TRADING_DAYS_PER_YEAR))
    weights = (np.sign(trailing) * scale).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    weights = weights.clip(lower=-params.max_leverage, upper=params.max_leverage)
    weights = weights.div(max(1, len(close_daily.columns)))
    if params.crash_filter:
        market = close_daily.mean(axis=1)
        drawdown = market / market.cummax() - 1.0
        weights = weights.mul((drawdown > -0.20).astype(float), axis=0)
    return weights.where(_rebalance_mask(close_daily.index, params.rebalance), np.nan).ffill().fillna(0.0)


def run_s6_ts_momentum_backtest(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    params: S6TSMomentumParams,
) -> BacktestResult:
    close = close.sort_index()
    target_daily = _target_weights(_daily_close(close), params)
    target = target_daily.shift(1).reindex(close.index).ffill().fillna(0.0)
    positions = target.shift(1).fillna(0.0)
    gross_returns = (positions * close.pct_change().fillna(0.0)).sum(axis=1)
    funding_return = _funding_returns(positions, funding).sum(axis=1)
    cost = compute_turnover(target) * (params.fee_bps + params.slippage_bps) / 10_000
    returns = gross_returns + funding_return - cost
    equity = (1.0 + returns).cumprod()
    daily_returns = (1.0 + returns).resample("1D").prod() - 1.0
    metrics = compute_metrics(equity, returns, target, pd.DataFrame(), params.bar)
    metrics.update({
        "validation_status": "research_backtest",
        "idealized_fill": False,
        "funding_cashflow": float(funding_return.sum()),
    })
    return BacktestResult(equity, daily_returns, positions, target_daily, pd.DataFrame(), metrics)


def scan_s6_ts_momentum(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    params: S6TSMomentumParams,
    grid: dict[str, list[Any]],
    prior_family_n_trials: int = 0,
) -> pd.DataFrame:
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]
    total_n_trials = int(prior_family_n_trials) + len(combos)
    fields = set(S6TSMomentumParams.__dataclass_fields__)
    rows = []
    for combo in combos:
        run_params = replace(params, **{k: v for k, v in combo.items() if k in fields})
        result = run_s6_ts_momentum_backtest(close, funding, run_params)
        rows.append({**combo, "n_trials": total_n_trials, **result.metrics})
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    return out


def load_s6_inputs(
    symbols: list[str],
    *,
    bar: str = "1m",
    data_dir: str = "data/ticks",
    start: str | None = None,
    end: str | None = None,
    backend: str = "postgres",
    dsn: str | None = None,
    exchange: str = "binance",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candles = {
        symbol: load_candles(symbol, bar=bar, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn, exchange=exchange)  # type: ignore[arg-type]
        for symbol in symbols
    }
    funding = {
        symbol: load_funding(symbol, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn)["rate"]
        for symbol in symbols
    }
    return pd.DataFrame({symbol: df["close"] for symbol, df in candles.items()}), pd.DataFrame(funding)
