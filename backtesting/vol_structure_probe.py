"""H-032/H-034 deterministic Stage-2 volatility-structure probes."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtesting.moneyness_vol_probe import (
    DVOL_DATASETS,
    RV30_DATASETS,
    _book_proxy,
    _complete_end,
    _fetch_external_rows,
    _fetch_market,
    _vrp_signals,
)
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.pipeline_power_screen import min_detectable_sharpe
from backtesting.taker_flow_probe import _load_universe
from backtesting.xs_idiovol_backtest import XSIdioVolParams, run_xs_idiovol_backtest
from backtesting.xvenue_leadlag_probe import abs_correlation, load_reference_series

BATCH_ID = "slate_stage2_20260729"
ROUNDTRIP_COST_BPS = 8.0
ONE_WAY_COST = 4 / 10_000
DISTINCTNESS_THRESHOLD = 0.30
H032_START = datetime(2021, 3, 1, tzinfo=timezone.utc)
H032_END = datetime(2026, 7, 29, tzinfo=timezone.utc)
H034_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
H034_END = datetime(2026, 6, 17, tzinfo=timezone.utc)
UNIVERSE_PATH = Path("data/universe/universe_membership.parquet")
E050_PATH = Path("results/h013_vrp_timing_20260714/combo_daily_returns.csv")


def _utc(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def _sharpe(series: pd.Series, periods_per_year: float = 365.0) -> float:
    clean = series.dropna().astype(float)
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    return float(clean.mean() / std * math.sqrt(periods_per_year)) if std > 0 else 0.0


def build_vov_signals(
    dvol: pd.DataFrame,
    *,
    window_days: int = 90,
    z_cut: float = 1.0,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build daily 08:00 long/flat signals from realized DVOL volatility."""

    if window_days <= 1 or z_cut <= 0:
        raise ValueError("invalid VoV first cell")
    frame = dvol.astype(float).sort_index()
    frame.index = pd.to_datetime(frame.index, utc=True)
    hourly = frame.pct_change(fill_method=None)
    window = window_days * 24
    vov = hourly.rolling(window, min_periods=window).std()
    prior = vov.shift(1)
    z = (vov - prior.rolling(window, min_periods=window).mean()) / prior.rolling(
        window, min_periods=window
    ).std().replace(0.0, np.nan)
    daily = z.loc[z.index.hour == 8]
    valid = daily.notna().all(axis=1)
    signals = (daily <= -z_cut).astype(float)
    return signals, valid


def positive_jump_variance(log_returns: pd.Series) -> float:
    """Return max(positive semivariance - half bipower variation, 0)."""

    clean = pd.Series(log_returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 2:
        return math.nan
    positive_semivariance = float(clean.clip(lower=0.0).pow(2).sum())
    bipower = float(math.pi / 2.0 * (clean.abs() * clean.abs().shift(1)).sum())
    return max(positive_semivariance - 0.5 * bipower, 0.0)


def build_positive_jump_book(
    positive_jump: pd.DataFrame,
    closes: pd.DataFrame,
    membership: Mapping[str, Sequence[str]],
    *,
    lookback_days: int = 7,
    quantile: float = 0.20,
) -> dict[str, pd.Series | pd.DataFrame]:
    """Build the frozen weekly low-minus-high positive-jump-variance book."""

    if lookback_days <= 0 or not 0 < quantile < 0.5:
        raise ValueError("invalid variance-decomposition first cell")
    feature = positive_jump.astype(float).rolling(
        lookback_days, min_periods=lookback_days
    ).sum()
    weights = pd.DataFrame(0.0, index=feature.index, columns=feature.columns)
    for day in feature.index:
        if day.weekday() != 0:
            continue
        members = [symbol for symbol in membership.get(day.date().isoformat(), ()) if symbol in feature]
        values = feature.loc[day, members].dropna().sort_values()
        count = max(1, int(math.floor(len(values) * quantile)))
        if len(values) < 2 * count:
            continue
        weights.loc[day, values.index[:count]] = 0.5 / count
        weights.loc[day, values.index[-count:]] = -0.5 / count
    weights = weights.replace(0.0, np.nan).ffill().fillna(0.0)
    returns = closes.astype(float).reindex(
        index=weights.index,
        columns=weights.columns,
    ).pct_change(fill_method=None)
    basket = (weights.shift(1) * returns).sum(axis=1)
    realized = basket.rolling(28, min_periods=28).std() * math.sqrt(365.0)
    leverage = (0.175 / realized).clip(0.0, 3.0).shift(1).fillna(0.0)
    executable = weights.shift(1).fillna(0.0).mul(leverage, axis=0)
    gross = (executable * returns).sum(axis=1)
    turnover = executable.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * ONE_WAY_COST
    return {"gross": gross, "net": gross - cost, "cost": cost, "weights": executable}


def membership_frame(membership: Mapping[str, Sequence[str]]) -> pd.DataFrame:
    """Return UTC-normalized membership rows compatible with UTC price panels."""

    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp(day).tz_localize("UTC"),
                "symbol": symbol,
                "eligible": True,
            }
            for day, members in membership.items()
            for symbol in members
        ]
    )


def _stop(
    hypothesis_id: str,
    family_id: str,
    candidate_dir: str,
    data_check: FeasibilityCheck,
    *,
    breadth: float,
    periods_per_year: float = 365.0,
) -> FeasibilityResult:
    checks = (
        data_check,
        FeasibilityCheck(
            "distinctness",
            "FAIL",
            "not evaluated because the frozen return series cannot be constructed",
            {"contract_stop_after": "data_availability", "max_abs_correlation": None},
        ),
        FeasibilityCheck(
            "cost_after_edge",
            "FAIL",
            "not evaluated because the frozen return series cannot be constructed",
            {"roundtrip_cost_bps": ROUNDTRIP_COST_BPS, "annualized_net_sharpe": None, "grid_trials_evaluated": 0},
        ),
        FeasibilityCheck(
            "statistical_power",
            "FAIL",
            "not evaluated because measured observations are unavailable",
            {"breadth": breadth, "n_obs": 0, "n_trials": 4, "periods_per_year": periods_per_year, "plausible_net_sharpe": None, "min_detectable_sharpe": None, "grid_trials_evaluated": 0},
        ),
    )
    return FeasibilityResult(BATCH_ID, hypothesis_id, candidate_dir, hypothesis_id, family_id, checks)


def _series_dict(series: pd.Series) -> dict[str, float]:
    return {
        _utc(day).date().isoformat(): float(value)
        for day, value in series.dropna().items()
        if math.isfinite(float(value))
    }


def _correlations(candidate: pd.Series, references: Mapping[str, pd.Series | Mapping[str, float]]) -> dict[str, Any]:
    left = _series_dict(candidate)
    output = {}
    for name, values in references.items():
        right = _series_dict(values) if isinstance(values, pd.Series) else dict(values)
        corr, common = abs_correlation(left, right)
        output[name] = {"abs_correlation": corr, "common_days": common}
    return output


async def probe_vol_of_vol(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 whole-slate pre-flight must pass before DB probe access")
    datasets = [*DVOL_DATASETS.values(), *RV30_DATASETS.values()]
    rows = list(ctx.get("external_rows") or await _fetch_external_rows(conn, datasets, start=H032_START, end=H032_END))
    complete_end = _complete_end(rows, list(DVOL_DATASETS.values()))
    dvol = pd.DataFrame(
        {
            symbol: pd.Series(
                {
                    _utc(row["published_at"]): float(row["value_num"])
                    for row in rows
                    if row.get("dataset_id") == dataset and row.get("value_num") is not None
                },
                dtype=float,
            )
            for symbol, dataset in DVOL_DATASETS.items()
        }
    ).sort_index()
    signals, valid = build_vov_signals(dvol) if not dvol.empty else (pd.DataFrame(), pd.Series(dtype=bool))
    formal_start = valid[valid].index.min() if valid.any() else None
    formal_end = complete_end
    n_expected = max(0, (formal_end.date() - formal_start.date()).days) if formal_start is not None and formal_end is not None else 0
    n_valid = int(valid.loc[(valid.index >= formal_start) & (valid.index < formal_end)].sum()) if n_expected else 0
    coverage = n_valid / n_expected if n_expected else 0.0
    data_check = FeasibilityCheck(
        "data_availability",
        "PASS" if coverage >= 0.95 and n_valid >= 65 else "FAIL",
        f"complete DVOL/VoV daily coverage={coverage:.6f}",
        {"coverage": coverage, "n_obs": n_valid, "formal_window": [formal_start.date().isoformat() if formal_start is not None else None, formal_end.date().isoformat() if formal_end is not None else None], "stage2_first_grid_cell": {"z_cut": 1.0, "window_days": 90}, "i49_preflight": dict(preflight)},
    )
    if data_check.status == "FAIL":
        return _stop("H-032", "F-VOL-OF-VOL", "f_vol_of_vol", data_check, breadth=2.0)
    close, funding, _ = await _fetch_market(conn, start=formal_start.to_pydatetime(), end=formal_end.to_pydatetime())
    candidate = _book_proxy(signals.loc[(signals.index >= formal_start) & (signals.index < formal_end)], close, funding)["net"]
    e050 = pd.read_csv(E050_PATH)
    day_field = "day_utc" if "day_utc" in e050 else "day"
    e050[day_field] = pd.to_datetime(e050[day_field], utc=True)
    e067_signals, _ = _vrp_signals(rows, window_days=90, z_cut=1.0)
    e067 = _book_proxy(e067_signals, close, funding)["net"]
    refs: dict[str, pd.Series] = {
        f"E-050/F-VRP-TIMING:{column}": e050.set_index(day_field)[column]
        for column in e050.columns
        if column != day_field
    }
    refs["E-067/H-026/F-VRP-TIMING"] = e067
    correlations = _correlations(candidate, refs)
    distinct_ok = all(
        row["abs_correlation"] is not None
        and row["common_days"] >= 65
        and row["abs_correlation"] < DISTINCTNESS_THRESHOLD
        for row in correlations.values()
    )
    n_obs = int(candidate.dropna().shape[0])
    sharpe = _sharpe(candidate)
    floor = min_detectable_sharpe(breadth=2.0, n_obs=n_obs, n_trials=4, periods_per_year=365.0)
    checks = (
        data_check,
        FeasibilityCheck("distinctness", "PASS" if distinct_ok else "FAIL", "all mandatory VoV correlations are below 0.30 with >=65 common days" if distinct_ok else "a mandatory VoV correlation is unavailable, under-covered, or >=0.30", {"threshold": DISTINCTNESS_THRESHOLD, "required_common_days": 65, "correlations": correlations}),
        FeasibilityCheck("cost_after_edge", "PASS" if sharpe > 0 else "FAIL", f"annualized net Sharpe={sharpe:.6f}", {"roundtrip_cost_bps": ROUNDTRIP_COST_BPS, "annualized_net_sharpe": sharpe, "grid_trials_evaluated": 0}),
        FeasibilityCheck("statistical_power", "PASS" if sharpe >= floor else "FAIL", f"plausible_net_sharpe={sharpe:.6f} {'>=' if sharpe >= floor else '<'} min_detectable_sharpe={floor:.6f}", {"breadth": 2.0, "n_obs": n_obs, "n_trials": 4, "periods_per_year": 365.0, "plausible_net_sharpe": sharpe, "min_detectable_sharpe": floor, "grid_trials_evaluated": 0}),
    )
    return FeasibilityResult(BATCH_ID, "H-032", "f_vol_of_vol", "H-032", "F-VOL-OF-VOL", checks)


async def _fetch_jump_daily(conn: Any, symbols: Sequence[str]) -> pd.DataFrame:
    rows = await conn.fetch(
        """
        WITH returns AS (
            SELECT inst_id, ts, close::double precision AS close,
                   LN(close / LAG(close) OVER (PARTITION BY inst_id ORDER BY ts)) AS r
            FROM canonical_candles
            WHERE inst_id=ANY($1::text[]) AND bar='1m' AND source_primary='binance'
              AND quality_status!='suspect' AND ts >= $2 AND ts < $3
        ), lagged AS (
            SELECT inst_id, ts, close, r,
                   LAG(r) OVER (PARTITION BY inst_id ORDER BY ts) AS prior_r
            FROM returns
        )
        SELECT inst_id, date_trunc('day', ts) AS day,
               GREATEST(
                   SUM(CASE WHEN r > 0 THEN r*r ELSE 0 END)
                   - 0.5 * PI()/2 * SUM(ABS(r*prior_r)),
                   0
               )::double precision AS positive_jump,
               (array_agg(close ORDER BY ts DESC))[1]::double precision AS close,
               COUNT(r)::bigint AS bars
        FROM lagged
        GROUP BY inst_id, day
        ORDER BY day, inst_id
        """,
        list(symbols),
        H034_START,
        H034_END,
    )
    return pd.DataFrame([dict(row) for row in rows])


async def _fetch_daily_funding(conn: Any, symbols: Sequence[str]) -> pd.DataFrame:
    rows = await conn.fetch(
        """
        SELECT inst_id, date_trunc('day', ts) AS day,
               SUM(COALESCE(realized_rate, funding_rate))::double precision AS rate
        FROM funding_rates
        WHERE source='binance' AND inst_id=ANY($1::text[]) AND ts >= $2 AND ts < $3
        GROUP BY inst_id, day ORDER BY day, inst_id
        """,
        list(symbols),
        H034_START,
        H034_END,
    )
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return pd.DataFrame(columns=list(symbols))
    frame["day"] = pd.to_datetime(frame["day"], utc=True)
    return frame.pivot(index="day", columns="inst_id", values="rate").astype(float)


async def probe_variance_decomp(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 whole-slate pre-flight must pass before DB probe access")
    membership = dict(ctx.get("membership") or _load_universe(UNIVERSE_PATH, H034_START, H034_END))
    symbols = sorted({symbol for values in membership.values() for symbol in values})
    daily = pd.DataFrame(ctx.get("jump_daily") or await _fetch_jump_daily(conn, symbols))
    if daily.empty:
        data_check = FeasibilityCheck("data_availability", "FAIL", "no PIT-universe 1m variance-decomposition rows", {"coverage": 0.0, "n_obs": 0, "stage2_first_grid_cell": {"lookback_days": 7, "quantile": 0.20}, "i49_preflight": dict(preflight)})
        return _stop("H-034", "F-VARIANCE-DECOMP", "f_variance_decomp", data_check, breadth=6.0)
    daily["day"] = pd.to_datetime(daily["day"], utc=True)
    daily = daily.loc[daily["bars"] >= 1_296]
    jumps = daily.pivot(index="day", columns="inst_id", values="positive_jump").astype(float)
    closes = daily.pivot(index="day", columns="inst_id", values="close").astype(float)
    available = {
        (day.date().isoformat(), symbol)
        for day, row in jumps.notna().iterrows()
        for symbol, present in row.items()
        if present
    }
    expected = {(day, symbol) for day, members in membership.items() for symbol in members}
    coverage = len(expected & available) / len(expected) if expected else 0.0
    data_check = FeasibilityCheck(
        "data_availability",
        "PASS" if coverage >= 0.95 else "FAIL",
        f"PIT member-day positive-jump coverage={coverage:.6f}",
        {"coverage": coverage, "available_member_days": len(expected & available), "expected_member_days": len(expected), "symbol_count": len(symbols), "stage2_first_grid_cell": {"lookback_days": 7, "quantile": 0.20}, "i49_preflight": dict(preflight)},
    )
    if data_check.status == "FAIL":
        return _stop("H-034", "F-VARIANCE-DECOMP", "f_variance_decomp", data_check, breadth=6.0)
    candidate = pd.Series(build_positive_jump_book(jumps, closes, membership)["net"])
    funding = await _fetch_daily_funding(conn, symbols)
    reference_membership = membership_frame(membership)
    e062 = run_xs_idiovol_backtest(
        closes,
        funding.reindex(index=closes.index, columns=closes.columns).fillna(0.0),
        reference_membership,
        XSIdioVolParams(universe=symbols, bar="1D", lookback_days=28, quantile=0.20),
        market_close=closes.get("BTC-USDT-SWAP"),
    ).daily_returns
    correlations = _correlations(candidate, {"E-062/F-XS-IDIOVOL": e062})
    row = correlations["E-062/F-XS-IDIOVOL"]
    distinct_ok = row["abs_correlation"] is not None and row["common_days"] >= 365 and row["abs_correlation"] < DISTINCTNESS_THRESHOLD
    formal = candidate.loc[(candidate.index >= _utc(H034_START)) & (candidate.index < _utc(H034_END))].dropna()
    n_obs = len(formal)
    sharpe = _sharpe(formal)
    floor = min_detectable_sharpe(breadth=6.0, n_obs=n_obs, n_trials=4, periods_per_year=365.0)
    checks = (
        data_check,
        FeasibilityCheck("distinctness", "PASS" if distinct_ok else "FAIL", "decisive E-062 correlation is below 0.30 with >=365 common days" if distinct_ok else "decisive E-062 correlation is unavailable, under-covered, or >=0.30", {"threshold": DISTINCTNESS_THRESHOLD, "required_common_days": 365, "correlations": correlations}),
        FeasibilityCheck("cost_after_edge", "PASS" if sharpe > 0 else "FAIL", f"annualized net Sharpe={sharpe:.6f}", {"roundtrip_cost_bps": ROUNDTRIP_COST_BPS, "annualized_net_sharpe": sharpe, "grid_trials_evaluated": 0}),
        FeasibilityCheck("statistical_power", "PASS" if sharpe >= floor else "FAIL", f"plausible_net_sharpe={sharpe:.6f} {'>=' if sharpe >= floor else '<'} min_detectable_sharpe={floor:.6f}", {"breadth": 6.0, "n_obs": n_obs, "n_trials": 4, "periods_per_year": 365.0, "plausible_net_sharpe": sharpe, "min_detectable_sharpe": floor, "grid_trials_evaluated": 0}),
    )
    return FeasibilityResult(BATCH_ID, "H-034", "f_variance_decomp", "H-034", "F-VARIANCE-DECOMP", checks)
