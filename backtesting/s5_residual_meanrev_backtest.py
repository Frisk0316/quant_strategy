"""Vectorized S5 residual mean-reversion research backtest."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
from typing import Any

import pandas as pd

from backtesting.data_loader import load_candles, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from okx_quant.strategies.s5_residual_meanrev import S5ResidualMeanReversionParams


def _daily_close(close: pd.DataFrame) -> pd.DataFrame:
    return close.sort_index().resample("1D").last().dropna(how="all")


def _funding_returns(positions: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    rates = funding.reindex(index=positions.index, columns=positions.columns).fillna(0.0)
    return -(positions * rates)


def _factor_columns(columns: list[str], factors: str) -> list[str]:
    wanted = ["BTC-USDT-SWAP"]
    if str(factors).upper() == "BTC+ETH":
        wanted.append("ETH-USDT-SWAP")
    return [col for col in wanted if col in columns]


def _limit_membership(membership: pd.DataFrame, top_n: int | None) -> pd.DataFrame:
    if not top_n:
        return membership
    out = membership.copy()
    eligible = out[out["eligible"]].sort_values(["date", "adv_usd"], ascending=[True, False])
    out["eligible"] = False
    keep = eligible[eligible.groupby("date").cumcount() < int(top_n)]
    out.loc[keep.index, "eligible"] = True
    return out


def _residual_z(close_daily: pd.DataFrame, params: S5ResidualMeanReversionParams) -> pd.DataFrame:
    returns = close_daily.pct_change()
    factors = _factor_columns(list(close_daily.columns), params.factors)
    factor_return = returns[factors].mean(axis=1) if factors else pd.Series(0.0, index=returns.index)
    tradable = [col for col in close_daily.columns if col not in {"BTC-USDT-SWAP", "ETH-USDT-SWAP"}]
    residual = returns[tradable].subtract(factor_return, axis=0)
    score = residual.rolling(params.lookback_days, min_periods=1).sum()
    denom = residual.rolling(max(2, params.lookback_days + 1), min_periods=2).std()
    return (score / denom.replace(0.0, float("nan"))).fillna(0.0)


def _target_weights(
    close_daily: pd.DataFrame,
    membership: pd.DataFrame,
    params: S5ResidualMeanReversionParams,
) -> pd.DataFrame:
    scores = _residual_z(close_daily, params)
    member = _limit_membership(membership, params.top_n).copy()
    member["date"] = pd.to_datetime(member["date"]).dt.normalize()
    out = pd.DataFrame(0.0, index=scores.index, columns=close_daily.columns)
    current = pd.Series(0.0, index=close_daily.columns)
    for ts in scores.index:
        if params.rebalance.lower() == "weekly" and ts.weekday() != 0:
            out.loc[ts] = current
            continue
        eligible = member[(member["date"] == ts.normalize()) & (member["eligible"])]
        allowed = [symbol for symbol in eligible["symbol"] if symbol in scores.columns]
        row = scores.loc[ts, allowed].dropna()
        previous = current.reindex(row.index).fillna(0.0)
        shorts = row[(row >= params.z_enter) | ((previous < 0.0) & (row > params.z_exit))].index
        longs = row[(row <= -params.z_enter) | ((previous > 0.0) & (row < -params.z_exit))].index
        current = pd.Series(0.0, index=close_daily.columns)
        if len(shorts) and len(longs):
            current.loc[shorts] = -0.5 / len(shorts)
            current.loc[longs] = 0.5 / len(longs)
            current = current.clip(lower=-params.max_name_weight, upper=params.max_name_weight)
        out.loc[ts] = current
    return out


def run_s5_residual_meanrev_backtest(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: S5ResidualMeanReversionParams,
) -> BacktestResult:
    close = close.sort_index()
    target_daily = _target_weights(_daily_close(close), membership, params)
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


def scan_s5_residual_meanrev(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: S5ResidualMeanReversionParams,
    grid: dict[str, list[Any]],
    prior_family_n_trials: int = 0,
) -> pd.DataFrame:
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]
    total_n_trials = int(prior_family_n_trials) + len(combos)
    fields = set(S5ResidualMeanReversionParams.__dataclass_fields__)
    rows = []
    for combo in combos:
        run_params = replace(params, **{k: v for k, v in combo.items() if k in fields})
        result = run_s5_residual_meanrev_backtest(close, funding, _limit_membership(membership, combo.get("top_n")), run_params)
        rows.append({**combo, "n_trials": total_n_trials, **result.metrics})
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    return out


def load_s5_inputs(
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
