"""Vectorized S7 perp-vs-spot basis mean-reversion research backtest."""
from __future__ import annotations

from dataclasses import replace
import math
from itertools import product
from typing import Any

import pandas as pd

from backtesting.data_loader import load_candles, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from okx_quant.strategies.s7_basis_meanrev import S7BasisMeanReversionParams


def _daily_close(close: pd.DataFrame) -> pd.DataFrame:
    return close.sort_index().resample("1D").last().dropna(how="all")


def _funding_returns(perp_positions: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    rates = funding.reindex(index=perp_positions.index, columns=perp_positions.columns).fillna(0.0)
    return -(perp_positions * rates)


def _basis_z(perp_daily: pd.DataFrame, spot_daily: pd.DataFrame, params: S7BasisMeanReversionParams) -> pd.DataFrame:
    rows = {}
    window = max(2, params.lookback_days + 1)
    for perp, spot in params.pairs.items():
        basis = perp_daily[perp] / spot_daily[spot] - 1.0
        mean = basis.rolling(window, min_periods=2).mean()
        std = basis.rolling(window, min_periods=2).std()
        rows[perp] = ((basis - mean) / std.replace(0.0, float("nan"))).fillna(0.0)
    return pd.DataFrame(rows)


def _basis_half_life_days(
    perp_daily: pd.DataFrame,
    spot_daily: pd.DataFrame,
    params: S7BasisMeanReversionParams,
) -> pd.DataFrame:
    rows = {}
    window = max(3, params.lookback_days + 1)
    for perp, spot in params.pairs.items():
        basis = perp_daily[perp] / spot_daily[spot] - 1.0
        lagged = basis.shift(1)
        delta = basis.diff()
        cov = lagged.rolling(window, min_periods=3).cov(delta)
        var = lagged.rolling(window, min_periods=3).var()
        beta = cov / var.replace(0.0, float("nan"))
        half_life = -math.log(2.0) / beta
        rows[perp] = half_life.where((beta < 0.0) & half_life.gt(0.0), float("inf"))
    return pd.DataFrame(rows).fillna(float("inf"))


def _target_weights(
    perp_daily: pd.DataFrame,
    spot_daily: pd.DataFrame,
    params: S7BasisMeanReversionParams,
) -> pd.DataFrame:
    z = _basis_z(perp_daily, spot_daily, params)
    half_life = _basis_half_life_days(perp_daily, spot_daily, params)
    columns = list(params.pairs) + list(params.pairs.values())
    out = pd.DataFrame(0.0, index=z.index, columns=columns)
    state = {
        perp: {"side": 0.0, "entered_at": None}
        for perp in params.pairs
    }
    for ts, row in z.iterrows():
        active_sides: dict[str, float] = {}
        for perp, z_value in row.items():
            current = state[perp]
            side = float(current["side"])
            entered_at = current["entered_at"]
            hl = float(half_life.loc[ts, perp])
            held_days = (
                (ts - entered_at).total_seconds() / 86_400
                if entered_at is not None else 0.0
            )
            if side:
                should_exit = (
                    abs(z_value) <= params.z_exit
                    or held_days >= params.max_hold_days
                    or hl > params.max_half_life_days
                )
                if should_exit:
                    current["side"] = 0.0
                    current["entered_at"] = None
                else:
                    active_sides[perp] = side
            elif abs(z_value) >= params.z_enter and hl <= params.max_half_life_days:
                current["side"] = -1.0 if z_value > 0.0 else 1.0
                current["entered_at"] = ts
                active_sides[perp] = float(current["side"])

        if not active_sides:
            continue
        pair_gross = 1.0 / len(active_sides)
        for perp, side in active_sides.items():
            spot = params.pairs[perp]
            if side < 0.0:
                out.loc[ts, perp] = -0.5 * pair_gross
                out.loc[ts, spot] = 0.5 * pair_gross
            else:
                out.loc[ts, perp] = 0.5 * pair_gross
                out.loc[ts, spot] = -0.5 * pair_gross
    return out


def run_s7_basis_meanrev_backtest(
    perp_close: pd.DataFrame,
    spot_close: pd.DataFrame,
    funding: pd.DataFrame,
    params: S7BasisMeanReversionParams,
) -> BacktestResult:
    perp_close = perp_close.sort_index()
    spot_close = spot_close.sort_index()
    close = pd.concat([perp_close, spot_close], axis=1).sort_index()
    target_daily = _target_weights(_daily_close(perp_close), _daily_close(spot_close), params)
    target = target_daily.shift(1).reindex(close.index).ffill().fillna(0.0)
    positions = target.shift(1).fillna(0.0)
    gross_returns = (positions * close.pct_change().fillna(0.0)).sum(axis=1)
    perp_positions = positions.reindex(columns=list(params.pairs)).fillna(0.0)
    funding_return = _funding_returns(perp_positions, funding).sum(axis=1)
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


def scan_s7_basis_meanrev(
    perp_close: pd.DataFrame,
    spot_close: pd.DataFrame,
    funding: pd.DataFrame,
    params: S7BasisMeanReversionParams,
    grid: dict[str, list[Any]],
    prior_family_n_trials: int = 0,
) -> pd.DataFrame:
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]
    total_n_trials = int(prior_family_n_trials) + len(combos)
    fields = set(S7BasisMeanReversionParams.__dataclass_fields__)
    rows = []
    for combo in combos:
        run_params = replace(params, **{k: v for k, v in combo.items() if k in fields})
        result = run_s7_basis_meanrev_backtest(perp_close, spot_close, funding, run_params)
        rows.append({**combo, "n_trials": total_n_trials, **result.metrics})
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    return out


def load_s7_inputs(
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
