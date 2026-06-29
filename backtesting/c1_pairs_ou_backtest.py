"""Vectorized C1 BTC/ETH OU-gated pairs research backtest."""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import math
from typing import Any

import numpy as np
import pandas as pd

from backtesting.data_loader import load_candles, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover


@dataclass
class C1PairsOUParams:
    symbol_y: str = "ETH-USDT-SWAP"
    symbol_x: str = "BTC-USDT-SWAP"
    bar: str = "1m"
    lookback_days: int = 14
    z_enter: float = 2.0
    z_exit: float = 0.5
    max_half_life_days: float = 7.0
    max_hold_days: int = 14
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


def _daily_close(close: pd.DataFrame) -> pd.DataFrame:
    return close.sort_index().resample("1D").last().dropna(how="all")


def _funding_returns(positions: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    rates = funding.reindex(index=positions.index, columns=positions.columns).fillna(0.0)
    return -(positions * rates)


def _spread(close_daily: pd.DataFrame, params: C1PairsOUParams) -> pd.Series:
    y = np.log(close_daily[params.symbol_y])
    x = np.log(close_daily[params.symbol_x])
    window = max(2, int(params.lookback_days) + 1)
    beta = y.rolling(window, min_periods=2).cov(x) / x.rolling(window, min_periods=2).var()
    beta = beta.replace([np.inf, -np.inf], np.nan).ffill().fillna(1.0)
    return (y - beta * x).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _spread_z(spread: pd.Series, lookback_days: int) -> pd.Series:
    window = max(2, int(lookback_days) + 1)
    mean = spread.rolling(window, min_periods=2).mean()
    std = spread.rolling(window, min_periods=2).std()
    return ((spread - mean) / std.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _half_life_days(spread: pd.Series, lookback_days: int) -> pd.Series:
    window = max(3, int(lookback_days) + 1)
    lagged = spread.shift(1)
    delta = spread.diff()
    beta = lagged.rolling(window, min_periods=3).cov(delta) / lagged.rolling(window, min_periods=3).var()
    half_life = -math.log(2.0) / beta
    return half_life.where((beta < 0.0) & half_life.gt(0.0), float("inf")).fillna(float("inf"))


def _target_weights(close_daily: pd.DataFrame, params: C1PairsOUParams) -> pd.DataFrame:
    spread = _spread(close_daily, params)
    z = _spread_z(spread, params.lookback_days)
    half_life = _half_life_days(spread, params.lookback_days)
    out = pd.DataFrame(0.0, index=close_daily.index, columns=[params.symbol_x, params.symbol_y])
    side = 0.0
    entered_at: pd.Timestamp | None = None
    for ts, z_value in z.items():
        held_days = (ts - entered_at).total_seconds() / 86_400 if entered_at is not None else 0.0
        hl = float(half_life.loc[ts])
        if side:
            if abs(z_value) <= params.z_exit or hl > params.max_half_life_days or held_days >= params.max_hold_days:
                side = 0.0
                entered_at = None
        elif abs(z_value) >= params.z_enter and hl <= params.max_half_life_days:
            side = -1.0 if z_value > 0.0 else 1.0
            entered_at = ts
        if side:
            out.loc[ts, params.symbol_y] = 0.5 * side
            out.loc[ts, params.symbol_x] = -0.5 * side
    return out


def run_c1_pairs_ou_backtest(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    params: C1PairsOUParams,
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


def scan_c1_pairs_ou(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    params: C1PairsOUParams,
    grid: dict[str, list[Any]],
    prior_family_n_trials: int = 0,
) -> pd.DataFrame:
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]
    total_n_trials = int(prior_family_n_trials) + len(combos)
    fields = set(C1PairsOUParams.__dataclass_fields__)
    rows = []
    for combo in combos:
        run_params = replace(params, **{k: v for k, v in combo.items() if k in fields})
        result = run_c1_pairs_ou_backtest(close, funding, run_params)
        rows.append({**combo, "n_trials": total_n_trials, **result.metrics})
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    return out


def load_c1_inputs(
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
