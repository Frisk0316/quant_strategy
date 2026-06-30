"""Vectorized C2 funding-carry plus basis-z filter research backtest."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from backtesting.data_loader import load_candles, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover

TRADING_DAYS_PER_YEAR = 365.0


@dataclass
class C2FundingCarryParams:
    pairs: dict[str, str] = field(default_factory=lambda: {
        "BTC-USDT-SWAP": "BTC-USDT",
        "ETH-USDT-SWAP": "ETH-USDT",
    })
    bar: str = "1m"
    funding_lookback_days: int = 7
    basis_lookback_days: int = 7
    funding_enter_apr: float = 0.10
    exit_funding_apr: float = 0.0
    basis_z_max: float = 3.0
    rebalance: str = "daily"
    fee_bps: float = 2.0
    slippage_bps: float = 2.0
    basis_execution_slippage_bps: float = 0.0
    carry_cost_bps: float = 0.0
    stress_funding_apr_threshold: float = 0.0
    stress_basis_z_threshold: float = 3.0


def _daily_close(close: pd.DataFrame) -> pd.DataFrame:
    return close.sort_index().resample("1D").last().dropna(how="all")


def _funding_returns(perp_positions: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    rates = funding.reindex(index=perp_positions.index, columns=perp_positions.columns).fillna(0.0)
    return -(perp_positions * rates)


def _rebalance_mask(index: pd.DatetimeIndex, rebalance: str) -> pd.Series:
    if rebalance.lower() == "weekly":
        return pd.Series(index.weekday == 0, index=index)
    return pd.Series(True, index=index)


def _basis_z(perp_daily: pd.DataFrame, spot_daily: pd.DataFrame, params: C2FundingCarryParams) -> pd.DataFrame:
    rows = {}
    window = max(2, int(params.basis_lookback_days) + 1)
    for perp, spot in params.pairs.items():
        basis = perp_daily[perp] / spot_daily[spot] - 1.0
        mean = basis.rolling(window, min_periods=2).mean()
        std = basis.rolling(window, min_periods=2).std()
        rows[perp] = ((basis - mean) / std.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return pd.DataFrame(rows)


def _funding_apr(funding: pd.DataFrame, params: C2FundingCarryParams) -> pd.DataFrame:
    daily_mean_rate = funding.sort_index().resample("1D").mean().fillna(0.0)
    window = max(1, int(params.funding_lookback_days))
    return daily_mean_rate.rolling(window, min_periods=1).mean() * 3.0 * TRADING_DAYS_PER_YEAR


def _bars_per_day(index: pd.DatetimeIndex, bar: str) -> float:
    if len(index) > 1:
        diffs = pd.Series(index).diff().dropna()
        if not diffs.empty:
            seconds = float(diffs.median().total_seconds())
            if seconds > 0:
                return max(1.0, 86_400.0 / seconds)
    return {
        "1m": 1440.0,
        "5m": 288.0,
        "15m": 96.0,
        "30m": 48.0,
        "1H": 24.0,
        "4H": 6.0,
        "1D": 1.0,
    }.get(bar, 1440.0)


def _cost_breakdown(
    target: pd.DataFrame,
    positions: pd.DataFrame,
    params: C2FundingCarryParams,
) -> dict[str, pd.Series]:
    turnover = compute_turnover(target)
    fees = turnover * params.fee_bps / 10_000
    two_leg_slippage = turnover * params.slippage_bps / 10_000
    basis_execution_slippage = turnover * params.basis_execution_slippage_bps / 10_000
    gross = positions.abs().sum(axis=1)
    carry_cost = gross * params.carry_cost_bps / 10_000 / _bars_per_day(positions.index, params.bar)
    total = fees + two_leg_slippage + basis_execution_slippage + carry_cost
    return {
        "total": total,
        "fee": fees,
        "two_leg_rebalance_slippage": two_leg_slippage,
        "basis_execution_slippage": basis_execution_slippage,
        "carry": carry_cost,
    }


def _stress_windows(mask: pd.Series) -> list[dict[str, str]]:
    windows: list[dict[str, str]] = []
    start = None
    prev = None
    for ts, active in mask.sort_index().items():
        if bool(active) and start is None:
            start = ts
        if not bool(active) and start is not None and prev is not None:
            windows.append({"start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(prev).date())})
            start = None
        prev = ts
    if start is not None and prev is not None:
        windows.append({"start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(prev).date())})
    return windows


def _stress_evaluation(
    daily_returns: pd.Series,
    positions: pd.DataFrame,
    perp_daily: pd.DataFrame,
    spot_daily: pd.DataFrame,
    funding: pd.DataFrame,
    params: C2FundingCarryParams,
) -> dict[str, Any]:
    basis_z = _basis_z(perp_daily, spot_daily, params).reindex(daily_returns.index).fillna(0.0)
    apr = _funding_apr(funding, params).reindex(daily_returns.index).ffill().fillna(0.0)
    funding_negative = apr < params.stress_funding_apr_threshold
    basis_blowout = basis_z.abs() > params.stress_basis_z_threshold
    stress_mask = (funding_negative | basis_blowout).any(axis=1).reindex(daily_returns.index).fillna(False)

    daily_active = (
        positions.abs().sum(axis=1).resample("1D").max().reindex(daily_returns.index).fillna(0.0) > 0.0
    )
    exit_trigger = (
        (apr < params.exit_funding_apr) | (basis_z.abs() > params.basis_z_max)
    ).any(axis=1).reindex(daily_returns.index).fillna(False)
    caught_mid_flip = stress_mask & daily_active & exit_trigger

    stress_returns = daily_returns.reindex(stress_mask.index).fillna(0.0)[stress_mask]
    if stress_returns.empty:
        stress_pnl = 0.0
        stress_max_drawdown = 0.0
    else:
        stress_equity = (1.0 + stress_returns).cumprod()
        stress_pnl = float(stress_equity.iloc[-1] - 1.0)
        stress_max_drawdown = float((stress_equity / stress_equity.cummax() - 1.0).min())

    return {
        "rule": "daily stress if trailing 7-day funding APR < 0 or abs(basis z) > 3; evaluated as one group",
        "stress_day_count": int(stress_mask.sum()),
        "stress_windows": _stress_windows(stress_mask),
        "stress_pnl": stress_pnl,
        "stress_max_drawdown": stress_max_drawdown,
        "active_stress_day_count": int((stress_mask & daily_active).sum()),
        "mid_flip_active_days": int(caught_mid_flip.sum()),
        "negative_funding_day_count": int(funding_negative.any(axis=1).sum()),
        "basis_blowout_day_count": int(basis_blowout.any(axis=1).sum()),
    }


def _target_weights(
    perp_daily: pd.DataFrame,
    spot_daily: pd.DataFrame,
    funding: pd.DataFrame,
    params: C2FundingCarryParams,
) -> pd.DataFrame:
    basis_z = _basis_z(perp_daily, spot_daily, params)
    apr = _funding_apr(funding, params).reindex(basis_z.index).ffill().fillna(0.0)
    columns = list(params.pairs) + list(params.pairs.values())
    out = pd.DataFrame(0.0, index=basis_z.index, columns=columns)
    active = {perp: False for perp in params.pairs}
    for ts, row in basis_z.iterrows():
        if not bool(_rebalance_mask(pd.DatetimeIndex([ts]), params.rebalance).iloc[0]):
            prior = out.iloc[out.index.get_loc(ts) - 1] if out.index.get_loc(ts) > 0 else None
            if prior is not None:
                out.loc[ts] = prior
            continue
        active_perps = []
        for perp, z_value in row.items():
            current_apr = float(apr.loc[ts, perp])
            blowout = abs(float(z_value)) > params.basis_z_max
            if active[perp] and (current_apr < params.exit_funding_apr or blowout):
                active[perp] = False
            elif (not active[perp]) and current_apr > params.funding_enter_apr and not blowout:
                active[perp] = True
            if active[perp]:
                active_perps.append(perp)
        if active_perps:
            pair_gross = 1.0 / len(active_perps)
            for perp in active_perps:
                spot = params.pairs[perp]
                out.loc[ts, perp] = -0.5 * pair_gross
                out.loc[ts, spot] = 0.5 * pair_gross
    return out


def run_c2_funding_carry_backtest(
    perp_close: pd.DataFrame,
    spot_close: pd.DataFrame,
    funding: pd.DataFrame,
    params: C2FundingCarryParams,
) -> BacktestResult:
    perp_close = perp_close.sort_index()
    spot_close = spot_close.sort_index()
    close = pd.concat([perp_close, spot_close], axis=1).sort_index()
    perp_daily = _daily_close(perp_close)
    spot_daily = _daily_close(spot_close)
    target_daily = _target_weights(perp_daily, spot_daily, funding, params)
    target = target_daily.shift(1).reindex(close.index).ffill().fillna(0.0)
    positions = target.shift(1).fillna(0.0)
    gross_returns = (positions * close.pct_change().fillna(0.0)).sum(axis=1)
    perp_positions = positions.reindex(columns=list(params.pairs)).fillna(0.0)
    funding_return = _funding_returns(perp_positions, funding).sum(axis=1)
    costs = _cost_breakdown(target, positions, params)
    returns = gross_returns + funding_return - costs["total"]
    equity = (1.0 + returns).cumprod()
    daily_returns = (1.0 + returns).resample("1D").prod() - 1.0
    metrics = compute_metrics(equity, returns, target, pd.DataFrame(), params.bar)
    daily_vol = float(daily_returns.dropna().std()) if not daily_returns.dropna().empty else 0.0
    metrics.update({
        "validation_status": "research_backtest",
        "idealized_fill": False,
        "funding_cashflow": float(funding_return.sum()),
        "fee_cost": float(costs["fee"].sum()),
        "two_leg_rebalance_slippage_cost": float(costs["two_leg_rebalance_slippage"].sum()),
        "basis_execution_slippage_cost": float(costs["basis_execution_slippage"].sum()),
        "carry_cost": float(costs["carry"].sum()),
        "total_cost": float(costs["total"].sum()),
        "realized_daily_volatility": daily_vol,
        "realized_annualized_volatility": daily_vol * float(np.sqrt(TRADING_DAYS_PER_YEAR)),
        "realized_vol_red_flag_below_2pct": bool(daily_vol * float(np.sqrt(TRADING_DAYS_PER_YEAR)) < 0.02),
        "stress_evaluation": _stress_evaluation(daily_returns, positions, perp_daily, spot_daily, funding, params),
    })
    return BacktestResult(equity, daily_returns, positions, target_daily, pd.DataFrame(), metrics)


def scan_c2_funding_carry(
    perp_close: pd.DataFrame,
    spot_close: pd.DataFrame,
    funding: pd.DataFrame,
    params: C2FundingCarryParams,
    grid: dict[str, list[Any]],
    prior_family_n_trials: int = 0,
) -> pd.DataFrame:
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]
    total_n_trials = int(prior_family_n_trials) + len(combos)
    fields = set(C2FundingCarryParams.__dataclass_fields__)
    rows = []
    for combo in combos:
        run_params = replace(params, **{k: v for k, v in combo.items() if k in fields})
        result = run_c2_funding_carry_backtest(perp_close, spot_close, funding, run_params)
        rows.append({**combo, "n_trials": total_n_trials, **result.metrics})
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    return out


def load_c2_inputs(
    pairs: dict[str, str],
    *,
    bar: str = "1m",
    data_dir: str = "data/ticks",
    start: str | None = None,
    end: str | None = None,
    backend: str = "postgres",
    dsn: str | None = None,
    exchange: str = "binance",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    perps = {
        symbol: load_candles(symbol, bar=bar, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn, exchange=exchange)  # type: ignore[arg-type]
        for symbol in pairs
    }
    spots = {
        symbol: load_candles(symbol, bar=bar, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn, exchange=exchange)  # type: ignore[arg-type]
        for symbol in pairs.values()
    }
    funding = {
        symbol: load_funding(symbol, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn)["rate"]
        for symbol in pairs
    }
    return (
        pd.DataFrame({symbol: df["close"] for symbol, df in perps.items()}),
        pd.DataFrame({symbol: df["close"] for symbol, df in spots.items()}),
        pd.DataFrame(funding),
    )
