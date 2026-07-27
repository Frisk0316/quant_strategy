"""Vectorized cross-sectional idiosyncratic-volatility research backtest.

Asset and BTC returns from day t are paired in the residual-volatility estimate.
The returned ``target_weights`` surface is the executable target shifted to t+1,
unlike FundingXS's decision-date target surface; positions add the existing
one-bar execution lag.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from backtesting.xs_momentum_backtest import _daily_close, _funding_returns
from okx_quant.strategies.xs_momentum import XSMomentumParams, target_weights as build_target_weights

MARKET_SYMBOL = "BTC-USDT-SWAP"
GRID_FIELDS = {"lookback_days", "quantile"}


@dataclass
class XSIdioVolParams:
    universe: list[str] = field(default_factory=list)
    bar: str = "1D"
    rebalance: str = "weekly"
    lookback_days: int = 28
    quantile: float = 0.30
    vol_window_days: int = 28
    vol_target_annual: float = 0.175
    max_name_weight: float = 0.10
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


def residual_volatility(
    close_daily: pd.DataFrame,
    lookback_days: int,
    market_close: pd.Series | None = None,
) -> pd.DataFrame:
    """Rolling OLS residual volatility versus same-day BTC returns."""
    if lookback_days < 2:
        raise ValueError("lookback_days must be at least 2")
    if market_close is None:
        if MARKET_SYMBOL not in close_daily:
            raise ValueError(f"{MARKET_SYMBOL} close is required as the market factor")
        market_close = close_daily[MARKET_SYMBOL]

    asset_close = close_daily.drop(columns=MARKET_SYMBOL, errors="ignore")
    if asset_close.empty:
        raise ValueError("at least one non-BTC asset is required")

    asset_returns = asset_close.pct_change(fill_method=None)
    market_returns = pd.to_numeric(
        market_close.reindex(close_daily.index),
        errors="coerce",
    ).pct_change(fill_method=None)
    rolling = asset_returns.rolling(lookback_days, min_periods=lookback_days)
    asset_var = rolling.var()
    market_var = market_returns.rolling(lookback_days, min_periods=lookback_days).var()
    covariance = rolling.cov(market_returns)
    explained_var = covariance.pow(2).div(market_var.replace(0.0, np.nan), axis=0)
    residual_var = (asset_var - explained_var).where(market_var.notna(), axis=0)
    return np.sqrt(residual_var.clip(lower=0.0))


def _xs_params(params: XSIdioVolParams) -> XSMomentumParams:
    return XSMomentumParams(
        universe=params.universe,
        bar=params.bar,
        rebalance=params.rebalance,
        lookback_days=params.lookback_days,
        quantile=params.quantile,
        vol_window_days=params.vol_window_days,
        inverse_vol=False,
        vol_target_annual=params.vol_target_annual,
        max_name_weight=params.max_name_weight,
        fee_bps=params.fee_bps,
        slippage_bps=params.slippage_bps,
    )


def run_xs_idiovol_backtest(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: XSIdioVolParams,
    market_close: pd.Series | None = None,
) -> BacktestResult:
    """Run the research-only low-idiosyncratic-volatility long-short book."""
    close = close.sort_index()
    close_daily = _daily_close(close)
    market_daily = (
        market_close.sort_index().resample("1D").last()
        if market_close is not None
        else close_daily.get(MARKET_SYMBOL)
    )
    scores = -residual_volatility(
        close_daily,
        params.lookback_days,
        market_close=market_daily,
    )
    realized_vol = (
        close_daily.pct_change(fill_method=None)
        .rolling(params.vol_window_days, min_periods=2)
        .std()
    )
    decision_target = build_target_weights(
        scores,
        membership,
        _xs_params(params),
        realized_vol,
        market_close=market_daily,
    ).reindex(columns=close_daily.columns, fill_value=0.0)
    executable_target_daily = decision_target.shift(1).fillna(0.0)
    executable_target = (
        executable_target_daily.reindex(close.index).ffill().fillna(0.0)
    )
    positions = executable_target.shift(1).fillna(0.0)

    gross_returns = (
        positions * close.pct_change(fill_method=None).fillna(0.0)
    ).sum(axis=1)
    funding_return = _funding_returns(positions, funding).sum(axis=1)
    cost = (
        compute_turnover(executable_target)
        * (params.fee_bps + params.slippage_bps)
        / 10_000
    )
    returns = gross_returns + funding_return - cost
    equity = (1.0 + returns).cumprod()
    daily_returns = (1.0 + returns).resample("1D").prod() - 1.0
    trades = pd.DataFrame()
    metrics = compute_metrics(
        equity,
        returns,
        executable_target,
        trades,
        params.bar,
    )
    metrics.update(
        {
            "validation_status": "research_backtest",
            "idealized_fill": False,
            "funding_cashflow": float(funding_return.sum()),
            "funding_settlement_count": int(
                (
                    funding.reindex(index=close.index, columns=close.columns)
                    .fillna(0.0)
                    .ne(0.0)
                )
                .any(axis=1)
                .sum()
            ),
            "long_low_idiovol_short_high_idiovol": True,
        }
    )
    return BacktestResult(
        equity,
        daily_returns,
        positions,
        executable_target_daily,
        trades,
        metrics,
    )


def scan_xs_idiovol(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: XSIdioVolParams,
    grid: dict[str, list[Any]],
    market_close: pd.Series | None = None,
    prior_family_n_trials: int = 0,
    researched_n_trials: int | None = None,
) -> pd.DataFrame:
    unsupported = set(grid) - GRID_FIELDS
    if unsupported:
        raise ValueError(f"unsupported XS idio-vol grid fields: {sorted(unsupported)}")

    keys = list(grid)
    combos = [
        dict(zip(keys, values, strict=True))
        for values in product(*(grid[key] for key in keys))
    ]
    trial_floor = int(prior_family_n_trials) + len(combos)
    if researched_n_trials is None:
        total_n_trials = trial_floor
        n_trials_provenance = "grid_size_floor"
        n_trials_is_floor = True
    else:
        total_n_trials = int(researched_n_trials)
        if total_n_trials < trial_floor:
            raise ValueError("researched_n_trials is below the family-cumulative grid floor")
        n_trials_provenance = "caller_declared"
        n_trials_is_floor = False

    rows = []
    for combo in combos:
        result = run_xs_idiovol_backtest(
            close,
            funding,
            membership,
            replace(params, **combo),
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
