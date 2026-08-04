"""H-024..H-027 deterministic Stage-2 moneyness/volatility probes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.xvenue_leadlag_probe import abs_correlation

BATCH_ID = "moneyness_vol_probe_20260728"
MIN_COMMON_DAYS = 65
DISTINCTNESS_THRESHOLD = 0.30
ROUNDTRIP_COST_BPS = 8.0
ONE_WAY_COST_BPS = ROUNDTRIP_COST_BPS / 2.0
VOL_TARGET = 0.175
VOL_WINDOW_DAYS = 28
LEVERAGE_CAP = 3.0
MAJORS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")

OPTFLOW_DATASETS = {
    "BTC-USDT-SWAP": "optflow_deribit_btc",
    "ETH-USDT-SWAP": "optflow_deribit_eth",
}
DVOL_DATASETS = {
    "BTC-USDT-SWAP": "dvol_deribit_btc_1h",
    "ETH-USDT-SWAP": "dvol_deribit_eth_1h",
}
RV30_DATASETS = {
    "BTC-USDT-SWAP": "rv30_deribit_btc_1h",
    "ETH-USDT-SWAP": "rv30_deribit_eth_1h",
}

CANDIDATE_META: dict[str, dict[str, Any]] = {
    "F-OPT-HEDGE-DEMAND": {
        "candidate_id": "B-f-opt-hedge-demand",
        "candidate_dir": "f_opt_hedge_demand",
        "hypothesis_id": "H-024",
        "n_trials": 4,
        "first_cell": {"z_cut": 1.0, "lookback_hours": 24},
    },
    "F-OPT-MONEYNESS-STRUCTURE": {
        "candidate_id": "B-f-opt-moneyness-structure",
        "candidate_dir": "f_opt_moneyness_structure",
        "hypothesis_id": "H-025",
        "n_trials": 4,
        "first_cell": {"z_cut": 1.0, "lookback_hours": 24},
    },
    "F-XVOL-RATIO": {
        "candidate_id": "B-f-xvol-ratio",
        "candidate_dir": "f_xvol_ratio",
        "hypothesis_id": "H-027",
        "n_trials": 4,
        "first_cell": {"z_cut": 1.5, "window_days": 90},
    },
    "F-VRP-TIMING": {
        "candidate_id": "B-f-vrp-timing-retry1",
        "candidate_dir": "f_vrp_timing_retry1",
        "hypothesis_id": "H-026",
        "n_trials": 8,
        "first_cell": {"z_cut": 1.0, "window_days": 90},
    },
}

# Declared ceilings for the result-blind I49 check. The executed optflow window
# is shortened to the last calendar day with 24 complete bucket rows per asset.
FORMAL_WINDOWS: dict[str, dict[str, str]] = {
    "H-024": {"start": "2024-04-01", "end_exclusive": "2026-07-29"},
    "H-025": {"start": "2024-04-01", "end_exclusive": "2026-07-29"},
    "H-027": {"start": "2021-09-20", "end_exclusive": "2026-07-29"},
    "H-026": {"start": "2021-09-20", "end_exclusive": "2026-07-29"},
}

E044 = "E-044/F-OPTFLOW-POSITIONING"
E025 = "E-025/F-PAIRS-OU"
E050 = "E-050/F-VRP-TIMING"
H014 = "F-VOL-REGIME-OPT"
H024 = "H-024/F-OPT-HEDGE-DEMAND"

REFERENCE_PATHS: dict[str, Path] = {
    E044: Path(
        "results/idea_batch_20260713_taxonomy_003/"
        "f_optflow_positioning/combo_daily_returns.csv"
    ),
    E025: Path(
        "results/pipeline_batch2_20260625/c1_pairs_ou/combo_daily_returns.csv"
    ),
    E050: Path("results/h013_vrp_timing_20260714/combo_daily_returns.csv"),
    H014: Path("results/h014_stage3_20260714/combo_daily_returns.csv"),
}
DISTINCTNESS_REFERENCES: dict[str, dict[str, tuple[str, ...]]] = {
    "H-024": {"gating": (E044, H014), "advisory": ()},
    "H-025": {"gating": (H024, E044, H014), "advisory": ()},
    "H-027": {"gating": (E025, H014), "advisory": ()},
    "H-026": {"gating": (H014,), "advisory": (E050,)},
}


def _utc(value: Any) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _row_mapping(row: Any) -> dict[str, Any]:
    return dict(row) if isinstance(row, Mapping) else dict(row)


def _fields(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("fields")
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, Mapping) else {}


def extract_bucket_shares(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Return complete hourly OTM-put-buy and OTM-premium shares."""

    output: list[dict[str, Any]] = []
    for raw in rows:
        row = _row_mapping(raw)
        if str(row.get("dataset_id")) not in OPTFLOW_DATASETS.values():
            continue
        if str(row.get("quality_status") or "").lower() == "suspect":
            continue
        fields = _fields(row)
        premium = _finite(fields.get("premium_volume"))
        put_buy = _finite(fields.get("otm_put_buy_amt"))
        atm = _finite(fields.get("atm_premium"))
        itm = _finite(fields.get("itm_premium"))
        otm = _finite(fields.get("otm_premium"))
        bucket_total = None if None in (atm, itm, otm) else atm + itm + otm
        if (
            premium is None
            or put_buy is None
            or bucket_total is None
            or premium <= 0.0
            or bucket_total <= 0.0
            or min(put_buy, atm, itm, otm) < 0.0
        ):
            continue
        output.append(
            {
                "dataset_id": str(row["dataset_id"]),
                "published_at": _utc(row["published_at"]),
                "premium_volume": premium,
                "otm_put_buy_amt": put_buy,
                "bucket_premium": bucket_total,
                "otm_premium": otm,
                "hedge_demand_share": put_buy / premium,
                "moneyness_share": otm / bucket_total,
            }
        )
    if not output:
        return pd.DataFrame(
            columns=[
                "dataset_id",
                "published_at",
                "premium_volume",
                "otm_put_buy_amt",
                "bucket_premium",
                "otm_premium",
                "hedge_demand_share",
                "moneyness_share",
            ]
        )
    return (
        pd.DataFrame(output)
        .sort_values(["dataset_id", "published_at"])
        .drop_duplicates(["dataset_id", "published_at"], keep="last")
        .reset_index(drop=True)
    )


def _value_series(rows: Sequence[Mapping[str, Any]], dataset_id: str) -> pd.Series:
    values: dict[pd.Timestamp, float] = {}
    for raw in rows:
        row = _row_mapping(raw)
        if str(row.get("dataset_id")) != dataset_id:
            continue
        if str(row.get("quality_status") or "").lower() == "suspect":
            continue
        value = _finite(row.get("value_num"))
        if value is not None:
            values[_utc(row["published_at"])] = value
    return pd.Series(values, dtype=float).sort_index()


def extract_dvol_ratio(rows: Sequence[Mapping[str, Any]]) -> pd.Series:
    """Return aligned hourly ETH/BTC DVOL."""

    btc = _value_series(rows, DVOL_DATASETS["BTC-USDT-SWAP"])
    eth = _value_series(rows, DVOL_DATASETS["ETH-USDT-SWAP"])
    aligned = pd.concat({"btc": btc, "eth": eth}, axis=1).dropna()
    ratio = aligned["eth"] / aligned["btc"].replace(0.0, np.nan)
    return ratio.replace([np.inf, -np.inf], np.nan).dropna().rename("eth_btc_dvol_ratio")


def extract_vrp_regime_series(
    rows: Sequence[Mapping[str, Any]],
    *,
    median_window_hours: int,
) -> pd.DataFrame:
    """Return hourly DVOL-RV30 and the lag-safe rolling RV30 regime."""

    if type(median_window_hours) is not int or median_window_hours <= 0:
        raise ValueError("median_window_hours must be a positive integer")
    output = pd.DataFrame()
    for symbol, prefix in (("BTC-USDT-SWAP", "btc"), ("ETH-USDT-SWAP", "eth")):
        dvol = _value_series(rows, DVOL_DATASETS[symbol])
        rv30 = _value_series(rows, RV30_DATASETS[symbol])
        pair = pd.concat({"dvol": dvol, "rv30": rv30}, axis=1).dropna()
        output[f"{prefix}_dvol"] = pair["dvol"]
        output[f"{prefix}_rv30"] = pair["rv30"]
        output[f"{prefix}_vrp"] = pair["dvol"] - pair["rv30"]
        median = pair["rv30"].rolling(
            median_window_hours, min_periods=median_window_hours
        ).median()
        output[f"{prefix}_rv30_median"] = median
        output[f"{prefix}_calm"] = pair["rv30"] < median
    return output.sort_index()


def _date_keys(series: Mapping[str, Any]) -> set[str]:
    output = set()
    for key, value in series.items():
        text = str(key)[:10]
        if len(text) == 10 and text[4:5] == "-" and text[7:8] == "-" and _finite(value) is not None:
            output.add(text)
    return output


def _series_bundle(value: Any, label: str) -> dict[str, dict[str, float]]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must contain dated return series")
    if _date_keys(value):
        return {
            "value": {
                str(day)[:10]: float(number)
                for day, number in value.items()
                if str(day)[:10] in _date_keys(value)
            }
        }
    output: dict[str, dict[str, float]] = {}
    for name, series in value.items():
        if isinstance(series, Mapping) and _date_keys(series):
            output[str(name)] = {
                str(day)[:10]: float(number)
                for day, number in series.items()
                if str(day)[:10] in _date_keys(series)
            }
    if not output:
        raise ValueError(f"{label} has no dated return series")
    return output


def _load_reference_bundle(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        raise ValueError(f"reference artifact is missing: {path}")
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            if not fields:
                raise ValueError(f"reference artifact has no CSV header: {path}")
            day_field = "day_utc" if "day_utc" in fields else "day" if "day" in fields else fields[0]
            output = {field: {} for field in fields if field != day_field}
            for row in reader:
                day = str(row.get(day_field) or "")[:10]
                for field in output:
                    value = _finite(row.get(field))
                    if day and value is not None:
                        output[field][day] = value
        return {field: values for field, values in output.items() if values}
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"reference artifact must be a JSON object: {path}")
        for field in ("daily_returns", "combo_daily_returns", "signal"):
            if field in payload:
                return _series_bundle(payload[field], f"{path}:{field}")
        raise ValueError(
            f"{path} has no dated daily_returns/combo_daily_returns/signal field"
        )
    raise ValueError(f"unsupported reference artifact: {path}")


def _window_dates(window: Mapping[str, Any], label: str) -> set[str]:
    if not isinstance(window, Mapping) or window.get("start") is None or window.get("end_exclusive") is None:
        raise ValueError(f"{label} requires start and end_exclusive")
    start, end = _utc(window["start"]), _utc(window["end_exclusive"])
    if end <= start:
        raise ValueError(f"{label} end_exclusive must follow start")
    return {
        day.date().isoformat()
        for day in pd.date_range(start.normalize(), end.normalize(), inclusive="left", freq="D")
    }


def preflight_distinctness_references(
    *,
    formal_windows: Mapping[str, Mapping[str, Any]] = FORMAL_WINDOWS,
    reference_series: Mapping[str, Any] | None = None,
    reference_paths: Mapping[str, Path] = REFERENCE_PATHS,
    min_common_days: int = MIN_COMMON_DAYS,
) -> dict[str, Any]:
    """Refuse the whole limited probe before DB access if any I49 input is unusable."""

    if type(min_common_days) is not int or min_common_days <= 0:
        raise ValueError("I49 pre-flight requires a positive min_common_days")
    injected = dict(reference_series or {})
    bundles: dict[str, dict[str, dict[str, float]]] = {}
    errors: list[str] = []
    for reference in {ref for spec in DISTINCTNESS_REFERENCES.values() for refs in spec.values() for ref in refs}:
        if reference == H024:
            continue
        try:
            bundles[reference] = (
                _series_bundle(injected[reference], reference)
                if reference in injected
                else _load_reference_bundle(Path(reference_paths[reference]))
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{reference}: {exc}")
    details: dict[str, Any] = {"required_common_days": min_common_days, "candidates": {}}
    for hypothesis_id, references in DISTINCTNESS_REFERENCES.items():
        try:
            candidate_dates = _window_dates(formal_windows[hypothesis_id], hypothesis_id)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{hypothesis_id}: {exc}")
            continue
        candidate_details: dict[str, Any] = {}
        for role in ("gating", "advisory"):
            for reference in references[role]:
                if reference == H024:
                    try:
                        fields = {"same_window_candidate_signal": {
                            day: 0.0 for day in _window_dates(formal_windows["H-024"], "H-024")
                        }}
                    except (KeyError, TypeError, ValueError) as exc:
                        errors.append(f"{reference}: {exc}")
                        continue
                else:
                    fields = bundles.get(reference)
                if not fields:
                    continue
                common_by_field = {
                    field: len(candidate_dates & set(series))
                    for field, series in fields.items()
                }
                candidate_details[reference] = {
                    "role": role,
                    "common_days_by_field": common_by_field,
                    "minimum_common_days": min(common_by_field.values(), default=0),
                }
                short = {
                    field: days
                    for field, days in common_by_field.items()
                    if days < min_common_days
                }
                if short:
                    errors.append(
                        f"{hypothesis_id} vs {reference}: "
                        + ", ".join(f"{field}={days}" for field, days in short.items())
                    )
        details["candidates"][hypothesis_id] = candidate_details
    if errors:
        raise ValueError(
            "I49 pre-flight contract error; no moneyness/vol probe may run: "
            + "; ".join(errors)
        )
    return details


def validate_power_declaration(family_id: str, value: Any) -> dict[str, float | int]:
    expected_trials = int(CANDIDATE_META[family_id]["n_trials"])
    if not isinstance(value, Mapping):
        raise ValueError(f"{family_id} statistical_power must be an object")
    breadth, n_trials = value.get("breadth"), value.get("n_trials")
    if isinstance(breadth, bool) or _finite(breadth) != 2.0:
        raise ValueError(f"{family_id} ex-ante breadth must equal 2")
    if type(n_trials) is not int or n_trials != expected_trials:
        raise ValueError(
            f"{family_id} family-cumulative n_trials must equal {expected_trials}"
        )
    return {"breadth": 2.0, "n_trials": expected_trials}


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std()
    return (series - mean) / std.replace(0.0, np.nan)


def _daily_at_0800(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    return series.loc[series.index.hour == 8]


def _bucket_signals(
    rows: Sequence[Mapping[str, Any]],
    *,
    field: str,
    lookback_hours: int,
    z_cut: float,
) -> tuple[pd.DataFrame, pd.Series]:
    shares = extract_bucket_shares(rows)
    signal_columns: dict[str, pd.Series] = {}
    valid_columns: dict[str, pd.Series] = {}
    for symbol, dataset_id in OPTFLOW_DATASETS.items():
        frame = shares.loc[shares["dataset_id"] == dataset_id].set_index("published_at")
        if frame.empty:
            continue
        frame = frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq="h"))
        if field == "hedge_demand_share":
            numerator, denominator = frame["otm_put_buy_amt"], frame["premium_volume"]
        else:
            numerator, denominator = frame["otm_premium"], frame["bucket_premium"]
        feature = (
            numerator.rolling(lookback_hours, min_periods=lookback_hours).sum()
            / denominator.rolling(lookback_hours, min_periods=lookback_hours).sum().replace(0.0, np.nan)
        )
        daily_z = _zscore(_daily_at_0800(feature), 90)
        signal_columns[symbol] = (daily_z < z_cut).astype(float)
        valid_columns[symbol] = daily_z.notna()
    signals = pd.DataFrame(signal_columns)
    valid = pd.DataFrame(valid_columns)
    return signals.sort_index().fillna(0.0), valid.all(axis=1) if not valid.empty else pd.Series(dtype=bool)


def _xvol_signals(
    rows: Sequence[Mapping[str, Any]],
    *,
    window_days: int,
    z_cut: float,
) -> tuple[pd.DataFrame, pd.Series]:
    ratio = extract_dvol_ratio(rows)
    z = _daily_at_0800(_zscore(ratio, window_days * 24))
    signals = pd.DataFrame(0.0, index=z.index, columns=MAJORS)
    signals.loc[z <= -z_cut, "BTC-USDT-SWAP"] = -1.0
    signals.loc[z <= -z_cut, "ETH-USDT-SWAP"] = 1.0
    signals.loc[z >= z_cut, "BTC-USDT-SWAP"] = 1.0
    signals.loc[z >= z_cut, "ETH-USDT-SWAP"] = -1.0
    return signals, z.notna()


def _vrp_signals(
    rows: Sequence[Mapping[str, Any]],
    *,
    window_days: int,
    z_cut: float,
) -> tuple[pd.DataFrame, pd.Series]:
    frame = extract_vrp_regime_series(rows, median_window_hours=window_days * 24)
    signal_columns: dict[str, pd.Series] = {}
    valid_columns: dict[str, pd.Series] = {}
    for symbol, prefix in (("BTC-USDT-SWAP", "btc"), ("ETH-USDT-SWAP", "eth")):
        z = _zscore(frame[f"{prefix}_vrp"], 90 * 24)
        active = (z >= z_cut) & frame[f"{prefix}_calm"].astype(bool)
        daily = _daily_at_0800(active.astype(float))
        signal_columns[symbol] = daily
        daily_valid = _daily_at_0800(z.notna() & frame[f"{prefix}_rv30_median"].notna())
        valid_columns[symbol] = daily_valid
    signals = pd.DataFrame(signal_columns)
    valid = pd.DataFrame(valid_columns)
    return signals.sort_index().fillna(0.0), valid.all(axis=1) if not valid.empty else pd.Series(dtype=bool)


def _complete_end(
    rows: Sequence[Mapping[str, Any]],
    datasets: Sequence[str],
    *,
    bucket_fields: bool = False,
) -> pd.Timestamp | None:
    counts: dict[str, dict[str, int]] = {dataset: {} for dataset in datasets}
    required = {"premium_volume", "otm_put_buy_amt", "atm_premium", "itm_premium", "otm_premium"}
    for raw in rows:
        row = _row_mapping(raw)
        dataset_id = str(row.get("dataset_id"))
        if dataset_id not in counts or str(row.get("quality_status") or "").lower() == "suspect":
            continue
        if bucket_fields and not required.issubset(_fields(row)):
            continue
        if not bucket_fields and _finite(row.get("value_num")) is None:
            continue
        day = _utc(row["published_at"]).date().isoformat()
        counts[dataset_id][day] = counts[dataset_id].get(day, 0) + 1
    complete = set.intersection(
        *({day for day, count in by_day.items() if count >= 24} for by_day in counts.values())
    ) if counts else set()
    if not complete:
        return None
    return _utc(max(complete)) + pd.Timedelta(days=1)


async def _fetch_external_rows(
    conn: Any,
    datasets: Sequence[str],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT dataset_id, observed_at, published_at, value_num, fields, quality_status
        FROM external_observations
        WHERE dataset_id = ANY($1::text[])
          AND published_at >= $2 AND published_at < $3
        ORDER BY dataset_id, published_at
        """,
        list(datasets),
        start,
        end,
    )
    return [dict(row) for row in rows]


async def _fetch_market(
    conn: Any,
    *,
    start: datetime,
    end: datetime,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    rows = await conn.fetch(
        """
        SELECT
            inst_id,
            date_trunc('day', ts - interval '8 hours') + interval '8 hours' AS decision_at,
            (array_agg(close ORDER BY ts ASC))[1]::double precision AS close,
            COUNT(*)::bigint AS bars
        FROM canonical_candles
        WHERE inst_id = ANY($1::text[])
          AND bar = '1m'
          AND source_primary = 'binance'
          AND quality_status != 'suspect'
          AND ts >= $2 AND ts < $3
        GROUP BY inst_id, decision_at
        ORDER BY decision_at, inst_id
        """,
        list(MAJORS),
        start,
        end,
    )
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return pd.DataFrame(columns=MAJORS), pd.DataFrame(columns=MAJORS), {}
    frame["decision_at"] = pd.to_datetime(frame["decision_at"], utc=True)
    complete = frame.loc[frame["bars"] >= 1_296]
    close = complete.pivot(index="decision_at", columns="inst_id", values="close").astype(float)
    funding_rows = await conn.fetch(
        """
        SELECT
            inst_id,
            date_trunc('day', ts - interval '8 hours') + interval '8 hours' AS decision_at,
            SUM(COALESCE(realized_rate, funding_rate))::double precision AS rate,
            COUNT(*)::bigint AS settlements
        FROM funding_rates
        WHERE source = 'binance'
          AND inst_id = ANY($1::text[])
          AND ts >= $2 AND ts < $3
        GROUP BY inst_id, decision_at
        ORDER BY decision_at, inst_id
        """,
        list(MAJORS),
        start,
        end,
    )
    funding_frame = pd.DataFrame([dict(row) for row in funding_rows])
    if funding_frame.empty:
        funding = pd.DataFrame(0.0, index=close.index, columns=MAJORS)
        funding_counts = {}
    else:
        funding_frame["decision_at"] = pd.to_datetime(funding_frame["decision_at"], utc=True)
        funding = funding_frame.pivot(index="decision_at", columns="inst_id", values="rate").astype(float)
        funding_counts = {
            str(symbol): int(group["settlements"].sum())
            for symbol, group in funding_frame.groupby("inst_id")
        }
    return close, funding, funding_counts


def _book_proxy(
    signals: pd.DataFrame,
    close: pd.DataFrame,
    funding: pd.DataFrame,
) -> dict[str, pd.Series]:
    index = signals.index.intersection(close.index).sort_values()
    signals = signals.reindex(index=index, columns=MAJORS).fillna(0.0)
    close = close.reindex(index=index, columns=MAJORS)
    returns = close.pct_change()
    active = signals.abs().sum(axis=1)
    weights = signals.div(active.where(active > 0.0, 1.0), axis=0)
    basket_vol = (
        returns.mean(axis=1).rolling(VOL_WINDOW_DAYS, min_periods=VOL_WINDOW_DAYS).std()
        * math.sqrt(365.0)
    )
    leverage = (VOL_TARGET / basket_vol).clip(0.0, LEVERAGE_CAP).shift(1)
    weights = weights.mul(leverage, axis=0).shift(1).fillna(0.0)
    funding = funding.reindex(index=index, columns=MAJORS).fillna(0.0)
    price_return = (weights * returns).sum(axis=1)
    funding_return = -(weights * funding).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * ONE_WAY_COST_BPS / 10_000.0
    gross = price_return + funding_return
    return {
        "gross": gross,
        "net": gross - cost,
        "turnover": turnover,
        "cost": cost,
        "weights": weights,
    }


def _annualized_sharpe(series: pd.Series) -> float:
    clean = series.dropna().astype(float)
    if len(clean) < 2:
        return 0.0
    std = float(clean.std(ddof=1))
    if not math.isfinite(std) or std <= 0.0:
        return 0.0
    sharpe = float(clean.mean()) / std * math.sqrt(365.0)
    return sharpe if math.isfinite(sharpe) else 0.0


def _data_check(
    *,
    family_id: str,
    valid: pd.Series,
    formal_start: pd.Timestamp | None,
    formal_end: pd.Timestamp | None,
    close: pd.DataFrame,
    funding_counts: Mapping[str, int],
) -> FeasibilityCheck:
    n_obs = (
        max(0, (formal_end.date() - formal_start.date()).days)
        if formal_start is not None and formal_end is not None
        else 0
    )
    valid_days = int(valid.loc[(valid.index >= formal_start) & (valid.index < formal_end)].sum()) if n_obs else 0
    price_days = {
        symbol: int(close.loc[(close.index >= formal_start) & (close.index < formal_end), symbol].notna().sum())
        if n_obs and symbol in close
        else 0
        for symbol in MAJORS
    }
    coverage = min([valid_days / n_obs if n_obs else 0.0, *(
        count / n_obs if n_obs else 0.0 for count in price_days.values()
    )])
    passed = n_obs >= MIN_COMMON_DAYS and coverage >= 0.95
    return FeasibilityCheck(
        name="data_availability",
        status="PASS" if passed else "FAIL",
        reason=f"formal-window daily feature/price coverage={coverage:.6f}",
        details={
            "family_id": family_id,
            "formal_window": {
                "start": formal_start.date().isoformat() if formal_start is not None else None,
                "end_exclusive": formal_end.date().isoformat() if formal_end is not None else None,
                "n_obs": n_obs,
            },
            "valid_feature_days": valid_days,
            "price_days": price_days,
            "funding_settlements": dict(funding_counts),
            "minimum_coverage": 0.95,
            "last_complete_external_day": (
                (formal_end - pd.Timedelta(days=1)).date().isoformat()
                if formal_end is not None
                else None
            ),
        },
    )


def _reference_bundles(ctx: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    injected = dict(ctx.get("reference_series") or {})
    bundles: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    for reference, path in REFERENCE_PATHS.items():
        if reference in injected:
            bundles[reference] = _series_bundle(injected[reference], reference)
            metadata[reference] = {"injected": True}
        else:
            bundles[reference] = _load_reference_bundle(path)
            metadata[reference] = {
                "path": str(path).replace("\\", "/"),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    return bundles, metadata


def _series_dict(series: pd.Series) -> dict[str, float]:
    return {
        pd.Timestamp(day).date().isoformat(): float(value)
        for day, value in series.dropna().items()
        if _finite(value) is not None
    }


def _distinctness_check(
    *,
    hypothesis_id: str,
    candidate: pd.Series,
    bundles: Mapping[str, Any],
    metadata: Mapping[str, Any],
    h024_signal: pd.Series | None = None,
) -> FeasibilityCheck:
    candidate_values = _series_dict(candidate)
    correlations: dict[str, dict[str, float | int | None]] = {}
    references = DISTINCTNESS_REFERENCES[hypothesis_id]
    for role in ("gating", "advisory"):
        for reference in references[role]:
            fields = (
                {"same_window_candidate_signal": _series_dict(h024_signal)}
                if reference == H024 and h024_signal is not None
                else bundles.get(reference, {})
            )
            for field, series in fields.items():
                correlation, common = abs_correlation(candidate_values, series)
                correlations[f"{reference}:{field}"] = {
                    "reference": reference,
                    "role": role,
                    "abs_correlation": correlation,
                    "common_days": common,
                }
    gating = [row for row in correlations.values() if row["role"] == "gating"]
    passed = bool(gating) and all(
        row["abs_correlation"] is not None
        and int(row["common_days"]) >= MIN_COMMON_DAYS
        and float(row["abs_correlation"]) < DISTINCTNESS_THRESHOLD
        for row in gating
    )
    h024_rows = [row for row in gating if row["reference"] == H024]
    duplicate = bool(h024_rows) and any(
        row["abs_correlation"] is None
        or float(row["abs_correlation"]) >= DISTINCTNESS_THRESHOLD
        for row in h024_rows
    )
    return FeasibilityCheck(
        name="distinctness",
        status="PASS" if passed else "FAIL",
        reason=(
            "all gating correlations have at least 65 common days and abs(corr)<0.30"
            if passed
            else (
                "H-025 assigns to F-OPT-HEDGE-DEMAND and stops as a duplicate"
                if duplicate
                else "a gating correlation is unavailable, under-covered, or at least 0.30"
            )
        ),
        details={
            "threshold": DISTINCTNESS_THRESHOLD,
            "required_common_days": MIN_COMMON_DAYS,
            "correlations": correlations,
            "reference_artifacts": dict(metadata),
            "family_assignment": "F-OPT-HEDGE-DEMAND" if duplicate else None,
            "undefined_fails_closed": True,
        },
    )


def _cost_check(
    proxy: Mapping[str, pd.Series],
    *,
    n_obs: int,
    power: Mapping[str, float | int],
) -> FeasibilityCheck:
    gross = proxy["gross"].dropna().astype(float)
    net = proxy["net"].dropna().astype(float)
    cost = proxy["cost"].reindex(net.index).fillna(0.0)
    mean_gross_bps = float(gross.mean() * 10_000.0) if len(gross) else 0.0
    mean_cost_bps = float(cost.mean() * 10_000.0) if len(cost) else 0.0
    plausible = _annualized_sharpe(net)
    passed = mean_gross_bps > mean_cost_bps and plausible > 0.0
    return FeasibilityCheck(
        name="cost_after_edge",
        status="PASS" if passed else "FAIL",
        reason=(
            f"mean daily gross={mean_gross_bps:.4f} bps "
            f"{'>' if mean_gross_bps > mean_cost_bps else '<='} "
            f"mean turnover cost={mean_cost_bps:.4f} bps"
        ),
        details={
            "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
            "one_way_turnover_cost_bps": ONE_WAY_COST_BPS,
            "daily_rebalance": True,
            "mean_daily_gross_bps": mean_gross_bps,
            "mean_daily_cost_bps": mean_cost_bps,
            "annualized_net_sharpe": plausible,
            "n_obs": n_obs,
            "plausible_net_sharpe": plausible,
            "statistical_power_inputs": {
                "breadth": float(power["breadth"]),
                "n_obs": n_obs,
                "n_trials": int(power["n_trials"]),
                "plausible_net_sharpe": plausible,
            },
            "grid_trials_evaluated": 0,
        },
    )


async def _probe(conn: Any, ctx: Mapping[str, Any], family_id: str) -> FeasibilityResult:
    meta = CANDIDATE_META[family_id]
    power = validate_power_declaration(family_id, ctx.get("statistical_power"))
    # Every registered entry repeats the whole-batch pre-flight, so even H-024
    # cannot touch the DB while H-027 lacks its mandatory E-025 dated reference.
    preflight = preflight_distinctness_references(
        formal_windows=ctx.get("formal_windows", FORMAL_WINDOWS),
        reference_series=ctx.get("reference_series"),
        reference_paths=ctx.get("reference_paths", REFERENCE_PATHS),
    )
    rows = ctx.get("external_rows")
    if rows is None:
        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        if family_id in {"F-OPT-HEDGE-DEMAND", "F-OPT-MONEYNESS-STRUCTURE"}:
            datasets = tuple(OPTFLOW_DATASETS.values())
        elif family_id == "F-XVOL-RATIO":
            datasets = tuple(DVOL_DATASETS.values())
        else:
            datasets = (*DVOL_DATASETS.values(), *RV30_DATASETS.values())
        rows = await _fetch_external_rows(conn, datasets, start=start, end=end)
    rows = list(rows)

    first_cell = meta["first_cell"]
    if family_id == "F-OPT-HEDGE-DEMAND":
        signals, valid = _bucket_signals(rows, field="hedge_demand_share", **first_cell)
        formal_end = _complete_end(rows, tuple(OPTFLOW_DATASETS.values()), bucket_fields=True)
    elif family_id == "F-OPT-MONEYNESS-STRUCTURE":
        signals, valid = _bucket_signals(rows, field="moneyness_share", **first_cell)
        formal_end = _complete_end(rows, tuple(OPTFLOW_DATASETS.values()), bucket_fields=True)
    elif family_id == "F-XVOL-RATIO":
        signals, valid = _xvol_signals(rows, **first_cell)
        formal_end = _complete_end(rows, tuple(DVOL_DATASETS.values()))
    else:
        signals, valid = _vrp_signals(rows, **first_cell)
        formal_end = _complete_end(rows, (*DVOL_DATASETS.values(), *RV30_DATASETS.values()))
    valid_index = valid.index[valid.fillna(False)]
    formal_start = valid_index.min() if len(valid_index) else None

    market = ctx.get("market")
    if isinstance(market, Mapping):
        close = market["close"].copy()
        funding = market.get("funding", pd.DataFrame()).copy()
        funding_counts = dict(market.get("funding_counts", {}))
    elif formal_start is not None and formal_end is not None:
        close, funding, funding_counts = await _fetch_market(
            conn,
            start=formal_start.to_pydatetime() - timedelta(days=2),
            end=formal_end.to_pydatetime() + timedelta(days=1),
        )
    else:
        close, funding, funding_counts = pd.DataFrame(), pd.DataFrame(), {}

    data = _data_check(
        family_id=family_id,
        valid=valid,
        formal_start=formal_start,
        formal_end=formal_end,
        close=close,
        funding_counts=funding_counts,
    )
    proxy = _book_proxy(signals, close, funding) if not close.empty else {
        name: pd.Series(dtype=float) for name in ("gross", "net", "turnover", "cost", "weights")
    }
    bundles, metadata = _reference_bundles(ctx)
    h024_signal = None
    candidate_for_distinctness = proxy["net"]
    if family_id == "F-OPT-MONEYNESS-STRUCTURE":
        h024_signals, _ = _bucket_signals(
            rows,
            field="hedge_demand_share",
            lookback_hours=24,
            z_cut=1.0,
        )
        h024_signal = h024_signals.mean(axis=1)
        candidate_for_distinctness = signals.mean(axis=1)
    distinctness = _distinctness_check(
        hypothesis_id=meta["hypothesis_id"],
        candidate=candidate_for_distinctness,
        bundles=bundles,
        metadata=metadata,
        h024_signal=h024_signal,
    )
    n_obs = int((data.details["formal_window"] or {}).get("n_obs") or 0)
    cost = _cost_check(proxy, n_obs=n_obs, power=power)
    data.details["i49_preflight"] = preflight
    data.details["stage2_first_grid_cell"] = dict(first_cell)
    result_family = (
        "F-OPT-HEDGE-DEMAND"
        if distinctness.details.get("family_assignment") == "F-OPT-HEDGE-DEMAND"
        else family_id
    )
    return FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id=meta["candidate_id"],
        candidate_dir=meta["candidate_dir"],
        hypothesis_id=meta["hypothesis_id"],
        family_id=result_family,
        checks=(data, distinctness, cost),
    )


async def probe_opt_hedge_demand(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    return await _probe(conn, ctx, "F-OPT-HEDGE-DEMAND")


async def probe_opt_moneyness_structure(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    return await _probe(conn, ctx, "F-OPT-MONEYNESS-STRUCTURE")


async def probe_xvol_ratio(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    return await _probe(conn, ctx, "F-XVOL-RATIO")


async def probe_vrp_timing_retry1(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    return await _probe(conn, ctx, "F-VRP-TIMING")
