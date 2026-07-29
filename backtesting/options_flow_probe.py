"""H-031/H-035 deterministic Stage-2 option-flow probes."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from okx_quant.data.external_clients.deribit_option_flow import parse_option_instrument
from okx_quant.data.external_clients.deribit_option_surface import moneyness_bucket

BATCH_ID = "slate_stage2_20260729"
DATASETS = ("optflow_deribit_btc", "optflow_deribit_eth")
FIRST_CELLS = {
    "H-031": {"pre_days": 2, "hold_hours": 8},
    "H-035": {"z_cut": 1.0, "lookback_hours": 24},
}
GAMMA_LIMITATION = (
    "Dealer gamma is not directly observable. The registered proxy starts from "
    "cumulative customer option flow with an unknown initial position; the stored "
    "optflow rows additionally retain only the first 20 inverse trades per hour, "
    "not the complete per-trade tape required by the frozen signal."
)


def _fields(row: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = row.get(name)
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, Mapping) else {}


def sampled_trades(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Expand retained raw samples for fixture construction and diagnostics."""

    output: list[dict[str, Any]] = []
    for row in rows:
        raw = _fields(row, "raw_payload")
        currency = "BTC" if str(row.get("dataset_id", "")).endswith("_btc") else "ETH"
        for trade in raw.get("sample") or []:
            meta = parse_option_instrument(str(trade.get("instrument_name") or ""), currency=currency)
            amount, price = trade.get("amount"), trade.get("price")
            try:
                amount, price = float(amount), float(price)
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(amount) and math.isfinite(price) and amount > 0.0 and price >= 0.0):
                continue
            option_type = str(meta["option_type"])
            bucket = moneyness_bucket(
                option_type,
                meta["strike"],
                float(trade["index_price"]) if trade.get("index_price") is not None else None,
            )
            timestamp = trade.get("timestamp")
            if timestamp is None:
                continue
            output.append(
                {
                    "ts": pd.to_datetime(int(timestamp), unit="ms", utc=True),
                    "currency": currency,
                    "instrument_name": str(trade.get("instrument_name") or ""),
                    "direction": str(trade.get("direction") or "").lower(),
                    "amount": amount,
                    "premium": amount * price,
                    "moneyness": bucket,
                }
            )
    return pd.DataFrame(output)


def build_gamma_flow_proxy(trades: pd.DataFrame) -> pd.DataFrame:
    """Build the registered cumulative customer-flow dealer-gamma approximation."""

    required = {"ts", "currency", "direction", "premium", "moneyness"}
    missing = required.difference(trades.columns)
    if missing:
        raise ValueError(f"gamma-flow trades missing columns: {sorted(missing)}")
    frame = trades.copy().sort_values(["currency", "ts"])
    frame["signed_customer_premium"] = np.where(
        frame["direction"].eq("buy"), frame["premium"], -frame["premium"]
    )
    frame["dealer_gamma_proxy"] = -frame.groupby(["currency", "moneyness"], dropna=False)[
        "signed_customer_premium"
    ].cumsum()
    return frame


def build_large_otm_trade_flow(
    trades: pd.DataFrame,
    *,
    lookback_hours: int = 24,
) -> pd.Series:
    """Return trailing signed premium from top-decile-size OTM trades."""

    required = {"ts", "direction", "amount", "premium", "moneyness"}
    missing = required.difference(trades.columns)
    if missing:
        raise ValueError(f"large-trade rows missing columns: {sorted(missing)}")
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")
    frame = trades.copy()
    cutoff = float(frame["amount"].quantile(0.90))
    frame = frame.loc[frame["moneyness"].eq("otm") & frame["amount"].ge(cutoff)].copy()
    frame["signed_premium"] = np.where(
        frame["direction"].eq("buy"), frame["premium"], -frame["premium"]
    )
    hourly = frame.set_index("ts")["signed_premium"].resample("h").sum()
    return hourly.rolling(lookback_hours, min_periods=lookback_hours).sum()


async def _fetch_rows(conn: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in await conn.fetch(
            """
            SELECT dataset_id,
                   COUNT(*)::bigint AS hourly_rows,
                   SUM(
                       CASE WHEN jsonb_typeof(raw_payload -> 'sample')='array'
                            THEN jsonb_array_length(raw_payload -> 'sample') ELSE 0 END
                   )::bigint AS retained_sample_trades,
                   ARRAY_REMOVE(
                       ARRAY_AGG(DISTINCT raw_payload ->> 'sample_rule'),
                       NULL
                   ) AS raw_sample_rules
            FROM external_observations
            WHERE dataset_id=ANY($1::text[])
              AND published_at >= $2
            GROUP BY dataset_id
            ORDER BY dataset_id
            """,
            list(DATASETS),
            datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
    ]


def _blocked_result(
    hypothesis_id: str,
    family_id: str,
    candidate_dir: str,
    *,
    rows: Sequence[Mapping[str, Any]],
    preflight: Mapping[str, Any],
) -> FeasibilityResult:
    aggregated = bool(rows and "hourly_rows" in rows[0])
    samples = pd.DataFrame() if aggregated else sampled_trades(rows)
    hourly_rows = (
        sum(int(row.get("hourly_rows") or 0) for row in rows)
        if aggregated
        else len(rows)
    )
    retained_sample_trades = (
        sum(int(row.get("retained_sample_trades") or 0) for row in rows)
        if aggregated
        else len(samples)
    )
    sample_rules = sorted({
        str(rule)
        for row in rows
        for rule in (
            row.get("raw_sample_rules") or []
            if aggregated
            else [_fields(row, "raw_payload").get("sample_rule")]
        )
        if rule
    })
    limitation = GAMMA_LIMITATION if hypothesis_id == "H-031" else (
        "The frozen H-035 mechanism conditions on the top decile of every trade's "
        "size, but optflow rows persist hourly aggregates plus only a first-20 raw "
        "sample. A sample-derived decile is not the registered per-trade signal."
    )
    data = FeasibilityCheck(
        "data_availability",
        "FAIL",
        "complete per-trade Deribit option tape is not retained in optflow rows",
        {
            "hourly_rows": hourly_rows,
            "retained_sample_trades": retained_sample_trades,
            "raw_sample_rules": sample_rules,
            "limitation": limitation,
            "stage2_first_grid_cell": FIRST_CELLS[hypothesis_id],
            "i49_preflight": dict(preflight),
            "grid_trials_evaluated": 0,
        },
    )
    downstream = (
        FeasibilityCheck(
            "distinctness",
            "FAIL",
            "not evaluated because the frozen candidate return series cannot be constructed",
            {"contract_stop_after": "data_availability", "max_abs_correlation": None},
        ),
        FeasibilityCheck(
            "cost_after_edge",
            "FAIL",
            "not evaluated because the frozen candidate event series cannot be constructed",
            {"roundtrip_cost_bps": 8.0, "annualized_net_sharpe": None, "grid_trials_evaluated": 0},
        ),
        FeasibilityCheck(
            "statistical_power",
            "FAIL",
            "not evaluated because measured event observations are unavailable",
            {
                "breadth": 1.0 if hypothesis_id == "H-031" else 1.5,
                "n_obs": 0,
                "n_trials": 4,
                "periods_per_year": 52.0 if hypothesis_id == "H-031" else 365.0,
                "plausible_net_sharpe": None,
                "min_detectable_sharpe": None,
                "grid_trials_evaluated": 0,
            },
        ),
    )
    return FeasibilityResult(
        BATCH_ID,
        hypothesis_id,
        candidate_dir,
        hypothesis_id,
        family_id,
        (data, *downstream),
    )


async def _probe(
    conn: Any,
    ctx: Mapping[str, Any],
    *,
    hypothesis_id: str,
    family_id: str,
    candidate_dir: str,
) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 whole-slate pre-flight must pass before DB probe access")
    rows = list(ctx.get("external_rows") or await _fetch_rows(conn))
    return _blocked_result(
        hypothesis_id,
        family_id,
        candidate_dir,
        rows=rows,
        preflight=preflight,
    )


async def probe_opt_expiry_gamma(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    return await _probe(
        conn,
        ctx,
        hypothesis_id="H-031",
        family_id="F-OPT-EXPIRY-GAMMA",
        candidate_dir="f_opt_expiry_gamma",
    )


async def probe_opt_large_trade_info(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    return await _probe(
        conn,
        ctx,
        hypothesis_id="H-035",
        family_id="F-OPT-LARGE-TRADE-INFO",
        candidate_dir="f_opt_large_trade_info",
    )
