"""Vectorized XS momentum research backtest."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
from typing import Any

import pandas as pd

from backtesting.data_loader import load_candles, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from okx_quant.strategies.xs_momentum import (
    XSMomentumParams,
    target_weights as build_target_weights,
    vol_normalized_momentum,
)


def _daily_close(close: pd.DataFrame) -> pd.DataFrame:
    return close.sort_index().resample("1D").last().dropna(how="all")


def _funding_returns(positions: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    rates = funding.reindex(index=positions.index, columns=positions.columns).fillna(0.0)
    return -(positions * rates)


def _limit_membership(membership: pd.DataFrame, top_n: int | None) -> pd.DataFrame:
    if not top_n:
        return membership
    out = membership.copy()
    eligible = out[out["eligible"]].sort_values(["date", "adv_usd"], ascending=[True, False])
    out["eligible"] = False
    keep = eligible[eligible.groupby("date").cumcount() < int(top_n)]
    out.loc[keep.index, "eligible"] = True
    return out


def run_xs_momentum_backtest(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: XSMomentumParams,
    market_close: pd.Series | None = None,
) -> BacktestResult:
    del high, low, vol
    close = close.sort_index()
    close_daily = _daily_close(close)
    scores = vol_normalized_momentum(
        close_daily,
        lookback=params.lookback_days,
        skip=params.skip_days,
        vol_window=params.vol_window_days,
    )
    realized_vol = close_daily.pct_change().rolling(params.vol_window_days, min_periods=2).std()
    market_daily = market_close.resample("1D").last() if market_close is not None else None
    target_daily = build_target_weights(scores, membership, params, realized_vol, market_close=market_daily)
    # Daily closes are timestamped at midnight; shift before intraday expansion.
    target = target_daily.shift(1).reindex(close.index).ffill().fillna(0.0)
    positions = target.shift(1).fillna(0.0)

    bar_returns = close.pct_change().fillna(0.0)
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
        }
    )
    return BacktestResult(equity, daily_returns, positions, target_daily, trades, metrics)


def scan_xs_momentum(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: XSMomentumParams,
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
    rows = []
    param_fields = set(XSMomentumParams.__dataclass_fields__)
    for combo in combos:
        run_params = replace(params, **{k: v for k, v in combo.items() if k in param_fields})
        result = run_xs_momentum_backtest(
            close,
            high,
            low,
            vol,
            funding,
            _limit_membership(membership, combo.get("top_n")),
            run_params,
            market_close=market_close,
        )
        rows.append({
            **combo,
            "n_trials": total_n_trials,
            "n_trials_provenance": n_trials_provenance,
            "n_trials_is_floor": n_trials_is_floor,
            **result.metrics,
        })
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    out.attrs["n_trials_provenance"] = n_trials_provenance
    out.attrs["n_trials_is_floor"] = n_trials_is_floor
    return out


def load_xs_momentum_inputs(
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
    candles = {
        symbol: load_candles(
            symbol,
            bar=bar,
            data_dir=data_dir,
            start=start,
            end=end,
            backend=backend,  # type: ignore[arg-type]
            dsn=dsn,
            exchange=exchange,
        )
        for symbol in symbols
    }
    funding = {}
    for symbol in symbols:
        rates = load_funding(symbol, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn)["rate"]
        funding[symbol] = rates[~rates.index.duplicated(keep="last")]
    close = pd.DataFrame({symbol: df["close"] for symbol, df in candles.items()})
    high = pd.DataFrame({symbol: df["high"] for symbol, df in candles.items()})
    low = pd.DataFrame({symbol: df["low"] for symbol, df in candles.items()})
    vol = pd.DataFrame({symbol: df["vol"] for symbol, df in candles.items()})
    return close, high, low, vol, pd.DataFrame(funding)
