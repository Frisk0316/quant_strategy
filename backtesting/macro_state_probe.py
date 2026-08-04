"""H-033/H-036 deterministic Stage-2 macro probes."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.pipeline_power_screen import min_detectable_sharpe

BATCH_ID = "slate_stage2_20260729"
FOMC_FIXTURE = Path("tests/fixtures/fomc_decision_dates_2020_2026.csv")
FOMC_SOURCE = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FRED_DATASETS = {
    "dgs2": "dgs2",
    "vix": "vixcls",
    "dollar": "dtwexbgs",
    "gold": "goldamgbd228n",
}
ROUNDTRIP_COST = 8 / 10_000
ONE_WAY_COST = ROUNDTRIP_COST / 2
FORMAL_START = pd.Timestamp("2020-01-01", tz="UTC")
FORMAL_END = pd.Timestamp("2026-06-18", tz="UTC")


def _utc_index(series: pd.Series) -> pd.Series:
    output = series.astype(float).copy()
    output.index = pd.to_datetime(output.index, utc=True).normalize()
    return output[~output.index.duplicated(keep="last")].sort_index()


def load_fomc_dates(path: Path = FOMC_FIXTURE) -> pd.DatetimeIndex:
    frame = pd.read_csv(path)
    if list(frame.columns) != ["decision_date"]:
        raise ValueError("FOMC fixture must contain only decision_date")
    dates = pd.DatetimeIndex(pd.to_datetime(frame["decision_date"], utc=True))
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("FOMC dates must be unique and sorted")
    return dates


def build_fomc_event_returns(
    btc_close: pd.Series,
    dgs2: pd.Series,
    decision_dates: Sequence[Any],
    *,
    pre_days: int = 1,
    hold_days: int = 2,
) -> pd.DataFrame:
    """Build the frozen pre-event and yield-surprise-directed post-event legs."""

    if pre_days <= 0 or hold_days <= 0:
        raise ValueError("FOMC windows must be positive")
    btc, yields = _utc_index(btc_close), _utc_index(dgs2)
    rows: list[dict[str, Any]] = []
    for raw_date in decision_dates:
        day = pd.Timestamp(raw_date)
        day = day.tz_localize("UTC") if day.tzinfo is None else day.tz_convert("UTC")
        day = day.normalize()
        btc_pos = btc.index.searchsorted(day)
        yield_pos = yields.index.searchsorted(day)
        if (
            btc_pos >= len(btc)
            or btc.index[btc_pos] != day
            or btc_pos < pre_days
            or btc_pos + hold_days >= len(btc)
            or yield_pos >= len(yields)
            or yields.index[yield_pos] != day
            or yield_pos == 0
        ):
            continue
        pre_gross = float(btc.iloc[btc_pos] / btc.iloc[btc_pos - pre_days] - 1.0)
        surprise = float(yields.iloc[yield_pos] - yields.iloc[yield_pos - 1])
        post_direction = -float(np.sign(surprise))
        post_gross = post_direction * float(
            btc.iloc[btc_pos + hold_days] / btc.iloc[btc_pos] - 1.0
        )
        rows.extend(
            (
                {
                    "decision_date": day,
                    "leg": "pre",
                    "gross": pre_gross,
                    "cost": ROUNDTRIP_COST,
                    "net": pre_gross - ROUNDTRIP_COST,
                    "yield_surprise": surprise,
                },
                {
                    "decision_date": day,
                    "leg": "post",
                    "gross": post_gross,
                    "cost": ROUNDTRIP_COST,
                    "net": post_gross - ROUNDTRIP_COST,
                    "yield_surprise": surprise,
                },
            )
        )
    return pd.DataFrame(rows)


def build_macro_state_book(
    closes: pd.DataFrame,
    vix: pd.Series,
    dollar: pd.Series,
    *,
    window_days: int = 60,
    z_cut: float = 1.0,
) -> pd.DataFrame:
    """Build the frozen daily breadth-2 long/flat macro-state proxy."""

    if window_days <= 1 or z_cut <= 0:
        raise ValueError("invalid macro-state first cell")
    prices = closes.astype(float).copy()
    prices.index = pd.to_datetime(prices.index, utc=True).normalize()
    state = pd.concat({"vix": _utc_index(vix), "dollar": _utc_index(dollar)}, axis=1)
    prior = state.shift(1)
    mean = prior.rolling(window_days, min_periods=window_days).mean()
    std = prior.rolling(window_days, min_periods=window_days).std().replace(0.0, np.nan)
    z = (state - mean) / std
    signal = (~((z["vix"] >= z_cut) & (z["dollar"] >= z_cut))).astype(float)
    index = prices.index.intersection(signal.dropna().index).sort_values()
    returns = prices.reindex(index).pct_change().mean(axis=1)
    position = signal.reindex(index).shift(1).fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    gross = position * returns
    return pd.DataFrame(
        {
            "position": position,
            "gross": gross,
            "cost": turnover * ONE_WAY_COST,
            "net": gross - turnover * ONE_WAY_COST,
            "vix_z": z["vix"].reindex(index),
            "dollar_z": z["dollar"].reindex(index),
        }
    )


def _sharpe(series: pd.Series, periods_per_year: float) -> float:
    clean = series.dropna().astype(float)
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    return float(clean.mean() / std * math.sqrt(periods_per_year)) if std > 0 else 0.0


def _blocked(
    hypothesis_id: str,
    family_id: str,
    candidate_dir: str,
    missing: Sequence[str],
    preflight: Mapping[str, Any],
) -> FeasibilityResult:
    checks = (
        FeasibilityCheck(
            "data_availability",
            "FAIL",
            "required frozen macro datasets are unavailable",
            {
                "missing_datasets": list(missing),
                "i49_preflight": dict(preflight),
                "stage2_first_grid_cell": (
                    {"pre_days": 1, "hold_days": 2}
                    if hypothesis_id == "H-033"
                    else {"z_cut": 1.0, "window_days": 60}
                ),
                "grid_trials_evaluated": 0,
            },
        ),
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
            {"roundtrip_cost_bps": 8.0, "annualized_net_sharpe": None, "grid_trials_evaluated": 0},
        ),
        FeasibilityCheck(
            "statistical_power",
            "FAIL",
            "not evaluated because measured observations are unavailable",
            {
                "breadth": 1.5 if hypothesis_id == "H-033" else 2.0,
                "n_obs": 0,
                "n_trials": 4,
                "periods_per_year": 16.0 if hypothesis_id == "H-033" else 365.0,
                "plausible_net_sharpe": None,
                "min_detectable_sharpe": None,
                "grid_trials_evaluated": 0,
            },
        ),
    )
    return FeasibilityResult(BATCH_ID, hypothesis_id, candidate_dir, hypothesis_id, family_id, checks)


async def _external_rows(conn: Any, datasets: Sequence[str]) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT dataset_id, published_at, value_num, quality_status
        FROM external_observations
        WHERE dataset_id=ANY($1::text[])
          AND published_at >= $2 AND published_at < $3
        ORDER BY dataset_id, published_at
        """,
        list(datasets),
        FORMAL_START.to_pydatetime(),
        FORMAL_END.to_pydatetime(),
    )
    return [dict(row) for row in rows]


def _series(rows: Sequence[Mapping[str, Any]], dataset_id: str) -> pd.Series:
    values = {
        pd.Timestamp(row["published_at"]).normalize(): float(row["value_num"])
        for row in rows
        if row.get("dataset_id") == dataset_id
        and row.get("value_num") is not None
        and str(row.get("quality_status") or "").lower() != "suspect"
    }
    return pd.Series(values, dtype=float).sort_index()


async def _market_closes(conn: Any, symbols: Sequence[str]) -> pd.DataFrame:
    rows = await conn.fetch(
        """
        SELECT inst_id, date_trunc('day', ts) AS day,
               (array_agg(close ORDER BY ts DESC))[1]::double precision AS close
        FROM canonical_candles
        WHERE inst_id=ANY($1::text[]) AND bar='1m' AND source_primary='binance'
          AND quality_status!='suspect' AND ts >= $2 AND ts < $3
        GROUP BY inst_id, day ORDER BY day, inst_id
        """,
        list(symbols),
        FORMAL_START.to_pydatetime(),
        FORMAL_END.to_pydatetime(),
    )
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return pd.DataFrame(columns=list(symbols))
    frame["day"] = pd.to_datetime(frame["day"], utc=True)
    return frame.pivot(index="day", columns="inst_id", values="close").astype(float)


async def probe_macro_event_drift(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 whole-slate pre-flight must pass before DB probe access")
    rows = list(ctx.get("external_rows") or await _external_rows(conn, [FRED_DATASETS["dgs2"]]))
    dgs2 = _series(rows, FRED_DATASETS["dgs2"])
    if dgs2.empty:
        return _blocked("H-033", "F-MACRO-EVENT-DRIFT", "f_macro_event_drift", ["dgs2"], preflight)
    closes = ctx.get("market_closes")
    if closes is None:
        closes = await _market_closes(conn, ["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
    market = pd.DataFrame(closes).reindex(
        columns=["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    )
    book_close = (1.0 + market.pct_change().mean(axis=1)).cumprod()
    events = build_fomc_event_returns(
        book_close,
        dgs2,
        load_fomc_dates(),
        pre_days=1,
        hold_days=2,
    )
    n_obs = len(events)
    periods = n_obs / ((FORMAL_END - FORMAL_START).days / 365.0) if n_obs else 1.0
    sharpe = _sharpe(events.get("net", pd.Series(dtype=float)), periods)
    floor = min_detectable_sharpe(breadth=1.5, n_obs=n_obs, n_trials=4, periods_per_year=periods) if n_obs else math.inf
    expected_dates = [day for day in load_fomc_dates() if FORMAL_START <= day < FORMAL_END]
    coverage = (n_obs / 2) / len(expected_dates) if expected_dates else 0.0
    checks = (
        FeasibilityCheck("data_availability", "PASS" if coverage >= 0.95 else "FAIL", f"usable FOMC-event coverage={coverage:.6f}", {"coverage": coverage, "usable_events": n_obs // 2, "scheduled_events": len(expected_dates), "fomc_fixture": str(FOMC_FIXTURE), "fomc_source": FOMC_SOURCE, "stage2_first_grid_cell": {"pre_days": 1, "hold_days": 2}, "i49_preflight": dict(preflight)}),
        FeasibilityCheck("distinctness", "PASS", "no gating return-series reference was specified for this exogenous calendar mechanism", {"max_abs_correlation": 0.0, "reference": None}),
        FeasibilityCheck("cost_after_edge", "PASS" if sharpe > 0 else "FAIL", f"annualized net Sharpe={sharpe:.6f}", {"roundtrip_cost_bps": 8.0, "annualized_net_sharpe": sharpe, "grid_trials_evaluated": 0}),
        FeasibilityCheck("statistical_power", "PASS" if sharpe >= floor else "FAIL", f"plausible_net_sharpe={sharpe:.6f} {'>=' if sharpe >= floor else '<'} min_detectable_sharpe={floor:.6f}", {"breadth": 1.5, "n_obs": n_obs, "n_trials": 4, "periods_per_year": periods, "plausible_net_sharpe": sharpe, "min_detectable_sharpe": floor, "grid_trials_evaluated": 0}),
    )
    return FeasibilityResult(BATCH_ID, "H-033", "f_macro_event_drift", "H-033", "F-MACRO-EVENT-DRIFT", checks)


async def probe_xasset_macro_lead(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 whole-slate pre-flight must pass before DB probe access")
    required = [FRED_DATASETS[name] for name in ("vix", "dollar", "gold")]
    rows = list(ctx.get("external_rows") or await _external_rows(conn, required))
    series = {dataset: _series(rows, dataset) for dataset in required}
    missing = [dataset for dataset, values in series.items() if values.empty]
    if missing:
        return _blocked("H-036", "F-XASSET-MACRO-LEAD", "f_xasset_macro_lead", missing, preflight)
    closes = ctx.get("market_closes")
    if closes is None:
        closes = await _market_closes(conn, ["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
    book = build_macro_state_book(
        pd.DataFrame(closes),
        series[FRED_DATASETS["vix"]],
        series[FRED_DATASETS["dollar"]],
    )
    valid = book.dropna(subset=["vix_z", "dollar_z", "net"])
    coverage = len(valid) / max(1, (FORMAL_END - FORMAL_START).days - 60)
    n_obs = len(valid)
    sharpe = _sharpe(valid["net"], 365.0)
    floor = min_detectable_sharpe(breadth=2.0, n_obs=n_obs, n_trials=4, periods_per_year=365.0) if n_obs else math.inf
    checks = (
        FeasibilityCheck("data_availability", "PASS" if coverage >= 0.95 else "FAIL", f"complete macro-state daily coverage={coverage:.6f}", {"coverage": coverage, "n_obs": n_obs, "required_datasets": required, "stage2_first_grid_cell": {"z_cut": 1.0, "window_days": 60}, "i49_preflight": dict(preflight)}),
        FeasibilityCheck("distinctness", "PASS", "no gating return-series reference was specified for this exogenous cross-asset mechanism", {"max_abs_correlation": 0.0, "reference": None}),
        FeasibilityCheck("cost_after_edge", "PASS" if sharpe > 0 else "FAIL", f"annualized net Sharpe={sharpe:.6f}", {"roundtrip_cost_bps": 8.0, "annualized_net_sharpe": sharpe, "grid_trials_evaluated": 0}),
        FeasibilityCheck("statistical_power", "PASS" if sharpe >= floor else "FAIL", f"plausible_net_sharpe={sharpe:.6f} {'>=' if sharpe >= floor else '<'} min_detectable_sharpe={floor:.6f}", {"breadth": 2.0, "n_obs": n_obs, "n_trials": 4, "periods_per_year": 365.0, "plausible_net_sharpe": sharpe, "min_detectable_sharpe": floor, "grid_trials_evaluated": 0}),
    )
    return FeasibilityResult(BATCH_ID, "H-036", "f_xasset_macro_lead", "H-036", "F-XASSET-MACRO-LEAD", checks)
