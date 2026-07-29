"""H-037 deterministic Stage-2 regulated-venue leadership probe."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.pipeline_power_screen import min_detectable_sharpe
from backtesting.xvenue_leadlag_probe import abs_correlation

BATCH_ID = "slate_stage2_20260729"
DATASET = "cme_btc1_continuous"
FORMAL_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
FORMAL_END = datetime(2026, 7, 29, tzinfo=timezone.utc)
ROUNDTRIP_COST = 8 / 10_000
DAILY_LIMITATION = (
    "The available CME contract is daily-only, so it cannot test the paper's "
    "intraday leadership mechanism. The frozen overnight first cell is only a "
    "coarse next-daily-interval session-boundary implication."
)


def _daily(series: pd.Series) -> pd.Series:
    output = series.astype(float).copy()
    output.index = pd.to_datetime(output.index, utc=True).normalize()
    return output[~output.index.duplicated(keep="last")].sort_index()


def build_cme_session_events(
    cme_settle: pd.Series,
    btc_close: pd.Series,
    *,
    x_cut_sigma: float = 0.5,
) -> pd.DataFrame:
    """Build the daily-only overnight first-cell implication without lookahead."""

    if x_cut_sigma <= 0:
        raise ValueError("x_cut_sigma must be positive")
    cme, btc = _daily(cme_settle), _daily(btc_close)
    move = cme.pct_change(fill_method=None)
    # No window is a registered grid dimension: expanding prior-only scale is
    # the deterministic, parameter-free interpretation of x_cut in sigma units.
    scale = move.shift(1).expanding(min_periods=20).std().replace(0.0, np.nan)
    aligned = pd.concat(
        {"cme_move": move, "scale": scale, "btc_next": btc.pct_change().shift(-1)},
        axis=1,
    ).dropna()
    aligned = aligned.loc[aligned["cme_move"].abs().ge(x_cut_sigma * aligned["scale"])].copy()
    aligned["direction"] = np.sign(aligned["cme_move"])
    aligned["gross"] = aligned["direction"] * aligned["btc_next"]
    aligned["cost"] = ROUNDTRIP_COST
    aligned["net"] = aligned["gross"] - aligned["cost"]
    return aligned


def _fields(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("fields")
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, Mapping) else {}


def _settles(rows: Sequence[Mapping[str, Any]]) -> pd.Series:
    values: dict[pd.Timestamp, float] = {}
    for row in rows:
        fields = _fields(row)
        value = fields.get("settle", fields.get("close", row.get("value_num")))
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            values[pd.Timestamp(row["published_at"]).normalize()] = number
    return pd.Series(values, dtype=float).sort_index()


async def _fetch_cme(conn: Any) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT dataset_id, observed_at, published_at, value_num, fields, quality_status
        FROM external_observations
        WHERE dataset_id=$1 AND published_at >= $2 AND published_at < $3
        ORDER BY published_at
        """,
        DATASET,
        FORMAL_START,
        FORMAL_END,
    )
    return [dict(row) for row in rows]


async def _fetch_btc(conn: Any) -> pd.Series:
    rows = await conn.fetch(
        """
        SELECT date_trunc('day', ts) AS day,
               (array_agg(close ORDER BY ts DESC))[1]::double precision AS close
        FROM canonical_candles
        WHERE inst_id='BTC-USDT-SWAP' AND bar='1m' AND source_primary='binance'
          AND quality_status!='suspect' AND ts >= $1 AND ts < $2
        GROUP BY day ORDER BY day
        """,
        FORMAL_START,
        FORMAL_END,
    )
    return pd.Series(
        {pd.Timestamp(row["day"]): float(row["close"]) for row in rows},
        dtype=float,
    )


def _blocked(preflight: Mapping[str, Any], row_count: int) -> FeasibilityResult:
    checks = (
        FeasibilityCheck(
            "data_availability",
            "FAIL",
            "official CME BTC settlement series is not provisioned",
            {
                "dataset_id": DATASET,
                "official_rows": row_count,
                "research_proxy_rejected": "cme_btc_yfinance is not official promotion evidence",
                "daily_resolution_limitation": DAILY_LIMITATION,
                "stage2_first_grid_cell": {"x_cut_sigma": 0.5, "session": "overnight"},
                "i49_preflight": dict(preflight),
                "grid_trials_evaluated": 0,
            },
        ),
        FeasibilityCheck(
            "distinctness",
            "FAIL",
            "not evaluated because the official frozen signal cannot be constructed",
            {"contract_stop_after": "data_availability", "max_abs_correlation": None},
        ),
        FeasibilityCheck(
            "cost_after_edge",
            "FAIL",
            "not evaluated because the official frozen event series cannot be constructed",
            {"roundtrip_cost_bps": 8.0, "annualized_net_sharpe": None, "grid_trials_evaluated": 0},
        ),
        FeasibilityCheck(
            "statistical_power",
            "FAIL",
            "not evaluated because measured daily events are unavailable",
            {"breadth": 1.0, "n_obs": 0, "n_trials": 4, "periods_per_year": 252.0, "plausible_net_sharpe": None, "min_detectable_sharpe": None, "grid_trials_evaluated": 0},
        ),
    )
    return FeasibilityResult(BATCH_ID, "H-037", "f_cme_leadership", "H-037", "F-CME-LEADERSHIP", checks)


async def probe_cme_leadership(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 whole-slate pre-flight must pass before DB probe access")
    rows = list(ctx.get("external_rows") or await _fetch_cme(conn))
    cme = _settles(rows)
    if cme.empty:
        return _blocked(preflight, len(rows))
    btc = ctx.get("btc_close")
    if btc is None:
        btc = await _fetch_btc(conn)
    events = build_cme_session_events(cme, pd.Series(btc))
    n_obs = len(events)
    years = (FORMAL_END - FORMAL_START).days / 365.0
    periods = n_obs / years if n_obs else 1.0
    net = events["net"] if n_obs else pd.Series(dtype=float)
    std = float(net.std(ddof=1)) if n_obs > 1 else 0.0
    sharpe = float(net.mean() / std * math.sqrt(periods)) if std > 0 else 0.0
    floor = min_detectable_sharpe(breadth=1.0, n_obs=n_obs, n_trials=4, periods_per_year=periods) if n_obs else math.inf
    e057 = ctx.get("e057_reference")
    baseline = ctx.get("cme_gap_fill_reference")
    correlations: dict[str, Any] = {}
    for name, reference in (("E-057/F-XVENUE-LEADLAG", e057), ("cme_gap_fill baseline", baseline)):
        if not isinstance(reference, Mapping):
            correlations[name] = {"abs_correlation": None, "common_days": 0}
            continue
        corr, common = abs_correlation(
            {day.date().isoformat(): float(value) for day, value in net.items()},
            reference,
        )
        correlations[name] = {"abs_correlation": corr, "common_days": common}
    distinct_ok = all(
        row["abs_correlation"] is not None
        and row["common_days"] >= 65
        and row["abs_correlation"] < 0.30
        for row in correlations.values()
    )
    coverage = len(cme) / max(1, pd.date_range(cme.index.min(), cme.index.max(), freq="B").size)
    checks = (
        FeasibilityCheck("data_availability", "PASS" if coverage >= 0.95 and n_obs else "FAIL", f"official CME business-day coverage={coverage:.6f}", {"coverage": coverage, "event_count": n_obs, "dataset_id": DATASET, "daily_resolution_limitation": DAILY_LIMITATION, "stage2_first_grid_cell": {"x_cut_sigma": 0.5, "session": "overnight"}, "i49_preflight": dict(preflight)}),
        FeasibilityCheck("distinctness", "PASS" if distinct_ok else "FAIL", "both mandatory correlations are below 0.30 with >=65 common days" if distinct_ok else "a mandatory CME correlation is unavailable, under-covered, or >=0.30", {"threshold": 0.30, "required_common_days": 65, "correlations": correlations}),
        FeasibilityCheck("cost_after_edge", "PASS" if sharpe > 0 else "FAIL", f"annualized net Sharpe={sharpe:.6f}", {"roundtrip_cost_bps": 8.0, "annualized_net_sharpe": sharpe, "grid_trials_evaluated": 0}),
        FeasibilityCheck("statistical_power", "PASS" if sharpe >= floor else "FAIL", f"plausible_net_sharpe={sharpe:.6f} {'>=' if sharpe >= floor else '<'} min_detectable_sharpe={floor:.6f}", {"breadth": 1.0, "n_obs": n_obs, "n_trials": 4, "periods_per_year": periods, "plausible_net_sharpe": sharpe, "min_detectable_sharpe": floor, "grid_trials_evaluated": 0}),
    )
    return FeasibilityResult(BATCH_ID, "H-037", "f_cme_leadership", "H-037", "F-CME-LEADERSHIP", checks)
