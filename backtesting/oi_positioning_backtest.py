"""Vectorized open-interest positioning research backtest."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from backtesting.data_loader import load_external_observations
from backtesting.funding_xs_dispersion_backtest import load_funding_xs_dispersion_inputs
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from backtesting.xs_momentum_backtest import _daily_close, _funding_returns

TRADING_DAYS_PER_YEAR = 365.0
MAX_GROSS_LEVERAGE = 2.0


@dataclass
class OIPositioningParams:
    universe: list[str] = field(default_factory=list)
    bar: str = "1D"
    lookback_days: int = 3
    z_min: float = 0.0
    oi_norm_window_days: int = 90
    vol_window_days: int = 28
    inverse_vol: bool = True
    vol_target_annual: float = 0.175
    max_name_weight: float = 0.10
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


def oi_dataset_id_for_symbol(symbol: str) -> str:
    base = str(symbol).upper().split("-")[0]
    return f"oi_binance_hist_{base.lower()}"


def _fields_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _naive_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    out = pd.DatetimeIndex(pd.to_datetime(index, utc=True, errors="coerce")).dropna()
    if out.tz is not None:
        out = out.tz_convert("UTC").tz_localize(None)
    return out


def daily_contract_open_interest(
    observations: pd.DataFrame,
    close_index: pd.Index,
    symbols: list[str],
) -> pd.DataFrame:
    """Return daily contract-count OI from fields.open_interest_contracts only."""
    days = _naive_utc_index(close_index).normalize().unique().sort_values()
    out = pd.DataFrame(index=days, columns=symbols, dtype=float)
    if observations.empty or not symbols:
        return out

    frame = observations.copy()
    frame["observed_at"] = pd.to_datetime(frame.get("observed_at"), utc=True, errors="coerce")
    frame = frame.dropna(subset=["observed_at"])
    if "quality_status" in frame.columns:
        frame = frame[frame["quality_status"].fillna("").astype(str).str.lower() != "suspect"]
    frame["contract_oi"] = frame.get("fields", pd.Series(dtype=object)).map(
        lambda value: _fields_dict(value).get("open_interest_contracts")
    )
    frame["contract_oi"] = pd.to_numeric(frame["contract_oi"], errors="coerce")
    frame = frame.dropna(subset=["contract_oi"])
    if frame.empty:
        return out

    frame["day"] = frame["observed_at"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    for symbol in symbols:
        dataset_id = oi_dataset_id_for_symbol(symbol)
        subset = frame[frame["dataset_id"] == dataset_id].sort_values("observed_at")
        if subset.empty:
            continue
        daily = subset.groupby("day", sort=True).tail(1).set_index("day")["contract_oi"].astype(float)
        out[symbol] = daily.reindex(days)
    return out


def _oi_signal(close_daily: pd.DataFrame, oi_daily: pd.DataFrame, params: OIPositioningParams) -> pd.DataFrame:
    log_oi = np.log(oi_daily.where(oi_daily > 0.0))
    oi_delta = log_oi - log_oi.shift(int(params.lookback_days))
    daily_oi_delta = log_oi.diff()
    oi_vol = daily_oi_delta.rolling(int(params.oi_norm_window_days), min_periods=2).std()
    z = oi_delta / oi_vol.replace(0.0, np.nan)
    price_move = np.log(close_daily / close_daily.shift(int(params.lookback_days)))
    direction = -np.sign(price_move)
    signal = direction.where((z <= -float(params.z_min)) & price_move.notna() & z.notna(), 0.0)
    return signal.where(oi_daily.notna())


def _eligible_symbols_by_day(membership: pd.DataFrame, symbols: list[str]) -> dict[pd.Timestamp, set[str]]:
    if membership.empty:
        return {}
    frame = membership.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"])
    frame = frame[frame["symbol"].isin(symbols)]
    frame = frame[frame["eligible"].astype(bool)]
    return {pd.Timestamp(day): set(group["symbol"].astype(str)) for day, group in frame.groupby("date")}


def _gross_vol_scale(weights: pd.Series, realized_vol: pd.Series, target_annual: float) -> float:
    aligned_vol = realized_vol.reindex(weights.index).dropna()
    active_weights = weights.reindex(aligned_vol.index).fillna(0.0)
    if active_weights.empty:
        return 1.0
    book_daily_vol = float(np.sqrt(np.square(active_weights * aligned_vol).sum()))
    if book_daily_vol <= 0.0 or not np.isfinite(book_daily_vol):
        return 1.0
    return min(MAX_GROSS_LEVERAGE, float(target_annual) / (book_daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)))


def build_oi_positioning_target_weights(
    close_daily: pd.DataFrame,
    oi_daily: pd.DataFrame,
    membership: pd.DataFrame,
    params: OIPositioningParams,
) -> pd.DataFrame:
    close_daily = close_daily.sort_index()
    oi_daily = oi_daily.reindex(index=close_daily.index, columns=close_daily.columns)
    symbols = [symbol for symbol in (params.universe or list(close_daily.columns)) if symbol in close_daily.columns]
    signal = _oi_signal(close_daily[symbols], oi_daily[symbols], params)
    realized_vol = close_daily[symbols].pct_change(fill_method=None).rolling(
        int(params.vol_window_days),
        min_periods=2,
    ).std()
    eligible_by_day = _eligible_symbols_by_day(membership, symbols)
    out = pd.DataFrame(0.0, index=close_daily.index, columns=symbols)
    current_signal = pd.Series(0.0, index=symbols, dtype=float)
    current_weights = pd.Series(0.0, index=symbols, dtype=float)

    for ts in out.index:
        day = pd.Timestamp(ts).normalize()
        eligible = [symbol for symbol in symbols if not eligible_by_day or symbol in eligible_by_day.get(day, set())]
        if not eligible:
            current_signal[:] = 0.0
            current_weights[:] = 0.0
            out.loc[ts] = current_weights
            continue

        fresh = signal.loc[ts, eligible]
        for symbol in set(symbols).difference(eligible):
            current_signal.loc[symbol] = 0.0
        if fresh.isna().all() and current_weights.abs().sum() > 0.0:
            out.loc[ts] = current_weights
            continue
        for symbol, value in fresh.items():
            if pd.notna(value):
                current_signal.loc[symbol] = float(value)

        active = [symbol for symbol in eligible if current_signal.loc[symbol] != 0.0]
        if not active:
            current_weights[:] = 0.0
            out.loc[ts] = current_weights
            continue

        vol = realized_vol.loc[ts, active].replace(0.0, np.nan)
        if params.inverse_vol:
            inv = (1.0 / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        else:
            inv = pd.Series(1.0, index=active)
        if inv.sum() <= 0.0:
            inv = pd.Series(1.0, index=active)
        raw = current_signal.loc[active] * (inv / inv.sum())
        raw = raw.clip(lower=-float(params.max_name_weight), upper=float(params.max_name_weight))
        scale = _gross_vol_scale(raw, realized_vol.loc[ts], params.vol_target_annual)
        current_weights[:] = 0.0
        current_weights.loc[active] = (raw * scale).clip(
            lower=-float(params.max_name_weight),
            upper=float(params.max_name_weight),
        )
        out.loc[ts] = current_weights
    return out


def zero_oi_integrity_report(
    oi_daily: pd.DataFrame,
    membership: pd.DataFrame,
    *,
    max_zero_ratio: float = 0.05,
) -> dict[str, Any]:
    symbols = list(oi_daily.columns)
    eligible_by_day = _eligible_symbols_by_day(membership, symbols)
    report: dict[str, Any] = {"max_zero_ratio": float(max_zero_ratio), "excluded_symbols": [], "symbols": {}}
    for symbol in symbols:
        eligible_days = [
            ts for ts in oi_daily.index
            if not eligible_by_day or symbol in eligible_by_day.get(pd.Timestamp(ts).normalize(), set())
        ]
        series = oi_daily.loc[eligible_days, symbol].dropna() if eligible_days else pd.Series(dtype=float)
        zero_days = int((series == 0.0).sum())
        ratio = float(zero_days / len(series)) if len(series) else 0.0
        excluded = ratio > float(max_zero_ratio)
        if excluded:
            report["excluded_symbols"].append(symbol)
        report["symbols"][symbol] = {
            "eligible_days": int(len(series)),
            "zero_contract_days": zero_days,
            "zero_ratio": ratio,
            "excluded": excluded,
        }
    report["excluded_symbols"] = sorted(report["excluded_symbols"])
    return report


def run_oi_positioning_backtest(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    oi: pd.DataFrame,
    membership: pd.DataFrame,
    params: OIPositioningParams,
    market_close: pd.Series | None = None,
) -> BacktestResult:
    del high, low, vol, market_close
    close = close.sort_index()
    close_daily = _daily_close(close)
    target_daily = build_oi_positioning_target_weights(close_daily, oi, membership, params)
    target = target_daily.reindex(close.index).ffill().fillna(0.0)
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
            "oi_contract_count_source": "external_observations.fields.open_interest_contracts",
            "fade_price_move_on_falling_oi": True,
        }
    )
    return BacktestResult(equity, daily_returns, positions, target_daily, trades, metrics)


def scan_oi_positioning(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    oi: pd.DataFrame,
    membership: pd.DataFrame,
    params: OIPositioningParams,
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

    fields = set(OIPositioningParams.__dataclass_fields__)
    rows = []
    for combo in combos:
        run_params = replace(params, **{key: value for key, value in combo.items() if key in fields})
        result = run_oi_positioning_backtest(close, high, low, vol, funding, oi, membership, run_params, market_close=market_close)
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


def load_oi_positioning_inputs(
    symbols: list[str],
    *,
    bar: str = "1D",
    data_dir: str = "data/ticks",
    start: str | None = None,
    end: str | None = None,
    backend: str = "postgres",
    dsn: str | None = None,
    exchange: str = "binance",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    close, high, low, vol, funding = load_funding_xs_dispersion_inputs(
        symbols,
        bar=bar,
        data_dir=data_dir,
        start=start,
        end=end,
        backend=backend,
        dsn=dsn,
        exchange=exchange,
    )
    frames = [
        load_external_observations(
            oi_dataset_id_for_symbol(symbol),
            start=start,
            end=end,
            backend="postgres" if backend == "postgres" else "parquet",
            dsn=dsn,
        )
        for symbol in symbols
    ]
    observations = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True) if frames else pd.DataFrame()
    oi = daily_contract_open_interest(observations, _daily_close(close).index, symbols)
    return close, high, low, vol, funding, oi


def json_signal(series: pd.Series) -> dict[str, float]:
    clean = series.dropna().astype(float)
    return {pd.Timestamp(ts).date().isoformat(): float(value) for ts, value in clean.items() if np.isfinite(value)}
