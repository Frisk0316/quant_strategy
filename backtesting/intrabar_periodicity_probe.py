"""H-030 deterministic Stage-2 quarter-hour periodicity probe."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, result_to_dict
from backtesting.pipeline_power_screen import min_detectable_sharpe
from backtesting.taker_flow_probe import (
    _fetch_funding,
    _load_universe,
    _native_symbol,
    _NUMBER_RE,
    build_taker_flow_proxy,
    parse_taker_fields,
)
from backtesting.xvenue_leadlag_probe import abs_correlation, load_reference_series

BATCH_ID = "slate_stage2_20260729"
FAMILY_ID = "F-INTRABAR-PERIODICITY"
FORMAL_START = datetime(2024, 4, 1, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2026, 6, 17, tzinfo=timezone.utc)
SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
Z_CUT = 1.5
HOLD_HOURS = 4
ROUNDTRIP_COST = 8 / 10_000
BOUNDARIES_PER_DAY = 96
LOOKBACK_BOUNDARIES = 90 * BOUNDARIES_PER_DAY
VOL_WINDOW_BOUNDARIES = 28 * BOUNDARIES_PER_DAY
VOL_TARGET = 0.175
LEVERAGE_CAP = 3.0
MIN_COMMON_DAYS = 365
DISTINCTNESS_THRESHOLD = 0.30
UNIVERSE_PATH = Path("data/universe/universe_membership.parquet")
H014_REFERENCE = Path("results/h014_stage3_20260714/combo_daily_returns.csv")

# Result-blind whole-slate ranges. These are contract ranges, not measured
# coverage; I49 asks whether each declared comparison can possibly reach its
# minimum before any DB access.
SLATE_FORMAL_WINDOWS: dict[str, tuple[str, str]] = {
    "H-030": ("2024-04-01", "2026-06-17"),
    "H-031": ("2024-04-01", "2026-07-29"),
    "H-032": ("2021-09-20", "2026-07-29"),
    "H-034": ("2024-01-01", "2026-06-17"),
    "H-035": ("2024-04-01", "2026-07-29"),
    "H-037": ("2020-01-01", "2026-07-29"),
}
SLATE_REFERENCE_WINDOWS: dict[str, dict[str, tuple[str, str]]] = {
    "H-030": {
        "E-059/F-TAKER-FLOW": ("2024-04-29", "2026-06-17"),
        "F-VOL-REGIME-OPT": ("2022-05-12", "2026-02-28"),
    },
    "H-031": {
        "E-064/F-OPT-HEDGE-DEMAND": ("2024-03-31", "2026-07-21"),
        "F-VOL-REGIME-OPT": ("2022-05-12", "2026-02-28"),
        "E-050/F-VRP-TIMING": ("2024-01-01", "2026-07-11"),
    },
    "H-032": {
        "E-050/F-VRP-TIMING": ("2024-01-01", "2026-07-11"),
        "E-067/F-VRP-TIMING": ("2021-06-22", "2026-07-27"),
    },
    "H-034": {
        "E-062/F-XS-IDIOVOL": ("2024-01-01", "2026-06-17"),
    },
    "H-035": {
        "E-044/F-OPTFLOW-POSITIONING": ("2024-01-01", "2026-02-28"),
        "E-064/F-OPT-HEDGE-DEMAND": ("2024-03-31", "2026-07-21"),
    },
    "H-037": {
        "E-057/F-XVENUE-LEADLAG": ("2020-01-01", "2020-04-01"),
        "cme_gap_fill baseline": ("2024-01-01", "2026-05-20"),
    },
}
SLATE_MIN_COMMON_DAYS = {
    "H-030": 365,
    "H-031": 65,
    "H-032": 65,
    "H-034": 365,
    "H-035": 65,
    "H-037": 65,
}


def _utc(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def preflight_slate_references(
    formal_windows: Mapping[str, Sequence[str]] = SLATE_FORMAL_WINDOWS,
    reference_windows: Mapping[str, Mapping[str, Sequence[str]]] = SLATE_REFERENCE_WINDOWS,
) -> dict[str, Any]:
    """Run the whole-slate I49 structural-overlap check without touching the DB."""

    details: dict[str, Any] = {"status": "PASS", "candidates": {}}
    errors: list[str] = []
    for hypothesis_id, references in reference_windows.items():
        try:
            candidate_start, candidate_end = map(_utc, formal_windows[hypothesis_id])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{hypothesis_id}: {exc}")
            continue
        required = SLATE_MIN_COMMON_DAYS[hypothesis_id]
        rows: dict[str, Any] = {}
        for name, window in references.items():
            ref_start, ref_end = map(_utc, window)
            common = max(0, (min(candidate_end, ref_end) - max(candidate_start, ref_start)).days)
            rows[name] = {
                "candidate_window": [candidate_start.date().isoformat(), candidate_end.date().isoformat()],
                "reference_window": [ref_start.date().isoformat(), ref_end.date().isoformat()],
                "achievable_common_days": common,
                "required_common_days": required,
            }
            if common < required:
                errors.append(f"{hypothesis_id} vs {name}: {common} < {required}")
        details["candidates"][hypothesis_id] = rows
    if errors:
        raise ValueError(
            "I49 whole-slate pre-flight contract stop; no DB probe may run: "
            + "; ".join(errors)
        )
    return details


def construct_boundary_events(
    rows: Sequence[Mapping[str, Any]],
    *,
    lookback_boundaries: int = LOOKBACK_BOUNDARIES,
    vol_window_boundaries: int = VOL_WINDOW_BOUNDARIES,
    z_cut: float = Z_CUT,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Construct the frozen 1.5-z/4h event returns from boundary-minute rows."""

    parsed: list[dict[str, Any]] = []
    malformed = unpriced = formal_rows = formal_parseable = formal_unpriced = 0
    for row in rows:
        ts = _utc(row["ts"])
        if ts.minute % 15:
            continue
        in_formal = FORMAL_START <= ts < END_EXCLUSIVE
        formal_rows += int(in_formal)
        raw_payload = row.get("raw_payload")
        if isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                raw_payload = None
        taker = parse_taker_fields(raw_payload)
        volume = float(row.get("volume") or 0.0)
        if taker is None or not math.isfinite(volume) or volume <= 0.0:
            malformed += 1
            continue
        formal_parseable += int(in_formal)
        entry, exit_price = row.get("entry_open"), row.get("exit_open")
        priced = entry is not None and exit_price is not None and float(entry) > 0.0
        if not priced:
            unpriced += 1
            formal_unpriced += int(in_formal)
        imbalance = (2.0 * taker[0] - volume) / volume
        parsed.append(
            {
                "ts": ts,
                "inst_id": str(row["inst_id"]),
                "imbalance": imbalance,
                "entry_open": float(entry) if priced else np.nan,
                "exit_open": float(exit_price) if priced else np.nan,
                "forward_return": (
                    float(exit_price) / float(entry) - 1.0 if priced else np.nan
                ),
            }
        )
    if not parsed:
        return pd.DataFrame(), {
            "boundary_rows": len(rows),
            "formal_boundary_rows": formal_rows,
            "formal_parseable_rows": formal_parseable,
            "formal_unpriced_rows": formal_unpriced,
            "malformed_rows": malformed,
            "unpriced_rows": unpriced,
        }

    frame = pd.DataFrame(parsed).sort_values(["inst_id", "ts"])
    grouped = frame.groupby("inst_id")["imbalance"]
    mean = grouped.transform(
        lambda values: values.shift(1).rolling(lookback_boundaries, min_periods=lookback_boundaries).mean()
    )
    std = grouped.transform(
        lambda values: values.shift(1).rolling(lookback_boundaries, min_periods=lookback_boundaries).std()
    )
    frame["z"] = (frame["imbalance"] - mean) / std.replace(0.0, np.nan)
    event_rate = 365.0 * BOUNDARIES_PER_DAY
    forward_vol = frame.groupby("inst_id")["forward_return"].transform(
        lambda values: values.shift(1).rolling(
            vol_window_boundaries,
            min_periods=vol_window_boundaries,
        ).std()
    ) * math.sqrt(event_rate)
    frame["leverage"] = (VOL_TARGET / forward_vol).clip(0.0, LEVERAGE_CAP)
    frame = frame.loc[
        (frame["ts"] >= FORMAL_START)
        & (frame["ts"] < END_EXCLUSIVE)
        & frame["z"].abs().ge(z_cut)
        & frame[["entry_open", "exit_open", "leverage"]].notna().all(axis=1)
    ].copy()
    direction = np.sign(frame["imbalance"])
    frame["gross"] = direction * frame["forward_return"] * frame["leverage"]
    frame["cost"] = ROUNDTRIP_COST
    frame["net"] = frame["gross"] - frame["cost"]
    return frame, {
        "boundary_rows": len(rows),
        "formal_boundary_rows": formal_rows,
        "formal_parseable_rows": formal_parseable,
        "formal_unpriced_rows": formal_unpriced,
        "parseable_rows": len(parsed),
        "malformed_rows": malformed,
        "unpriced_rows": unpriced,
    }


async def _fetch_boundary_rows(conn: Any) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT
            CASE mi.inst_id
                WHEN 'BTCUSDT' THEN 'BTC-USDT-SWAP'
                WHEN 'ETHUSDT' THEN 'ETH-USDT-SWAP'
            END AS inst_id,
            b.ts,
            b.volume::double precision AS volume,
            b.raw_payload,
            entry.open::double precision AS entry_open,
            exit_bar.open::double precision AS exit_open
        FROM market_klines b
        JOIN market_instruments mi USING (instrument_id)
        LEFT JOIN market_klines entry
          ON entry.instrument_id=b.instrument_id AND entry.bar='1m'
         AND entry.ts=b.ts + interval '1 minute'
        LEFT JOIN market_klines exit_bar
          ON exit_bar.instrument_id=b.instrument_id AND exit_bar.bar='1m'
         AND exit_bar.ts=b.ts + interval '241 minutes'
        WHERE mi.exchange='binance'
          AND mi.market_type='linear_perpetual'
          AND mi.contract_type='perpetual'
          AND mi.inst_id=ANY($1::text[])
          AND b.bar='1m'
          AND b.ts >= $2 AND b.ts < $3
          AND EXTRACT(MINUTE FROM b.ts)::int % 15 = 0
        ORDER BY mi.inst_id, b.ts
        """,
        ["BTCUSDT", "ETHUSDT"],
        FORMAL_START - timedelta(days=90),
        END_EXCLUSIVE,
    )
    return [dict(row) for row in rows]


async def _e059_reference(conn: Any) -> pd.Series:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = END_EXCLUSIVE
    universe = _load_universe(UNIVERSE_PATH, start, end)
    symbols = sorted({symbol for members in universe.values() for symbol in members})
    native_to_symbol = {_native_symbol(symbol): symbol for symbol in symbols}
    instrument_rows = await conn.fetch(
        """
        SELECT instrument_id, inst_id
        FROM market_instruments
        WHERE exchange='binance' AND market_type='linear_perpetual'
          AND contract_type='perpetual' AND inst_id=ANY($1::text[])
        ORDER BY inst_id, listing_time NULLS FIRST
        """,
        list(native_to_symbol),
    )
    instruments = {
        row["instrument_id"]: native_to_symbol[str(row["inst_id"])]
        for row in instrument_rows
        if str(row["inst_id"]) in native_to_symbol
    }
    unresolved = sorted(set(symbols) - set(instruments.values()))
    if unresolved:
        raise ValueError(f"E-059 reference symbols unresolved: {unresolved}")
    panel_rows = [
        dict(row)
        for row in await conn.fetch(
            f"""
            WITH parsed AS (
                SELECT instrument_id, ts, open, close, volume,
                       CASE
                           WHEN jsonb_typeof(raw_payload -> 'raw')='array'
                            AND jsonb_array_length(raw_payload -> 'raw') > 10
                            AND length(COALESCE(raw_payload #>> '{{raw,9}}', '')) <= 64
                            AND length(COALESCE(raw_payload #>> '{{raw,10}}', '')) <= 64
                            AND raw_payload #>> '{{raw,9}}' ~ '{_NUMBER_RE}'
                            AND raw_payload #>> '{{raw,10}}' ~ '{_NUMBER_RE}'
                           THEN (raw_payload #>> '{{raw,9}}')::double precision
                       END AS taker_buy_base,
                       CASE
                           WHEN jsonb_typeof(raw_payload -> 'raw')='array'
                            AND jsonb_array_length(raw_payload -> 'raw') > 10
                            AND length(COALESCE(raw_payload #>> '{{raw,9}}', '')) <= 64
                            AND length(COALESCE(raw_payload #>> '{{raw,10}}', '')) <= 64
                            AND raw_payload #>> '{{raw,9}}' ~ '{_NUMBER_RE}'
                            AND raw_payload #>> '{{raw,10}}' ~ '{_NUMBER_RE}'
                           THEN (raw_payload #>> '{{raw,10}}')::double precision
                       END AS taker_buy_quote
                FROM market_klines
                WHERE instrument_id=ANY($1::uuid[]) AND bar='1m'
                  AND ts >= $2 AND ts < $3
            )
            SELECT instrument_id, (ts AT TIME ZONE 'UTC')::date AS day,
                   (array_agg(open ORDER BY ts ASC))[1]::double precision AS open,
                   (array_agg(close ORDER BY ts DESC))[1]::double precision AS close,
                   SUM(volume)::double precision AS volume,
                   SUM(taker_buy_base) FILTER (
                       WHERE taker_buy_base >= 0 AND taker_buy_quote >= 0
                   )::double precision AS taker_buy_base,
                   COUNT(*)::bigint AS row_count,
                   COUNT(*) FILTER (
                       WHERE taker_buy_base >= 0 AND taker_buy_quote >= 0
                   )::bigint AS valid_count
            FROM parsed
            GROUP BY instrument_id, (ts AT TIME ZONE 'UTC')::date
            ORDER BY instrument_id, day
            """,
            list(instruments),
            start,
            end,
        )
    ]
    for row in panel_rows:
        row["symbol"] = instruments[row["instrument_id"]]
        row["parseable"] = int(row["row_count"]) == int(row["valid_count"]) == 1_440
    funding = {
        (str(row["day"])[:10], str(row["symbol"])): row
        for row in await _fetch_funding(conn, symbols, start, end)
    }
    for row in panel_rows:
        matched = funding.get((str(row["day"])[:10], str(row["symbol"])))
        row["funding_rate"] = matched.get("funding_rate") if matched else np.nan
        row["funding_count"] = matched.get("funding_count") if matched else 0
    return build_taker_flow_proxy(pd.DataFrame(panel_rows), universe)["gross_returns"]


def _sharpe(series: pd.Series, periods_per_year: float) -> float:
    clean = series.dropna().astype(float)
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    return float(clean.mean() / std * math.sqrt(periods_per_year)) if std > 0.0 else 0.0


async def probe_intrabar_periodicity(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 whole-slate pre-flight must pass before DB probe access")
    print("[H-030] loading quarter-hour boundary rows", flush=True)
    rows = list(ctx.get("boundary_rows") or await _fetch_boundary_rows(conn))
    print(f"[H-030] loaded {len(rows):,} boundary rows", flush=True)
    events, coverage = construct_boundary_events(rows)
    expected = (END_EXCLUSIVE.date() - FORMAL_START.date()).days * BOUNDARIES_PER_DAY * len(SYMBOLS)
    parseable = int(coverage.get("formal_parseable_rows", 0))
    priced = parseable - int(coverage.get("formal_unpriced_rows", 0))
    coverage_ratio = priced / expected if expected else 0.0
    n_obs = len(events)
    elapsed_years = (END_EXCLUSIVE - FORMAL_START).total_seconds() / (365.0 * 86_400.0)
    periods_per_year = n_obs / elapsed_years if n_obs else 1.0
    plausible = _sharpe(events.get("net", pd.Series(dtype=float)), periods_per_year)
    floor = (
        min_detectable_sharpe(
            breadth=1.5,
            n_obs=n_obs,
            n_trials=4,
            periods_per_year=periods_per_year,
        )
        if n_obs
        else math.inf
    )

    candidate_daily = events.groupby(events["ts"].dt.floor("D"))["net"].mean() if n_obs else pd.Series(dtype=float)
    e059 = ctx.get("e059_reference")
    if e059 is None:
        print("[H-030] rebuilding frozen E-059 dated reference", flush=True)
        e059 = await _e059_reference(conn)
        print(f"[H-030] rebuilt {len(e059):,} E-059 dated returns", flush=True)
    h014 = load_reference_series(H014_REFERENCE, "csv", "ivp_min=75.0|z_min=0.5")
    candidate_dict = {day.date().isoformat(): float(value) for day, value in candidate_daily.items()}
    references = {
        "E-059/F-TAKER-FLOW": {
            pd.Timestamp(day).date().isoformat(): float(value)
            for day, value in pd.Series(e059).dropna().items()
        },
        "F-VOL-REGIME-OPT": h014,
    }
    correlations = {}
    for name, series in references.items():
        corr, common = abs_correlation(candidate_dict, series)
        correlations[name] = {"abs_correlation": corr, "common_days": common}
    distinct_ok = all(
        row["abs_correlation"] is not None
        and row["common_days"] >= MIN_COMMON_DAYS
        and float(row["abs_correlation"]) < DISTINCTNESS_THRESHOLD
        for row in correlations.values()
    )
    mean_gross_bps = float(events["gross"].mean() * 10_000.0) if n_obs else 0.0

    checks = (
        FeasibilityCheck(
            "data_availability",
            "PASS" if coverage_ratio >= 0.95 and n_obs else "FAIL",
            f"priced quarter-hour coverage={coverage_ratio:.6f}",
            {
                **coverage,
                "expected_formal_boundary_rows": expected,
                "priced_coverage": coverage_ratio,
                "event_count": n_obs,
                "window": [FORMAL_START.isoformat(), END_EXCLUSIVE.isoformat()],
                "stage2_first_grid_cell": {"z_cut": Z_CUT, "hold_hours": HOLD_HOURS},
                "vol_target": {
                    "annual_target": VOL_TARGET,
                    "lookback_days": 28,
                    "leverage_cap": LEVERAGE_CAP,
                    "estimator": "lagged quarter-hour 4h forward-return volatility",
                },
                "i49_preflight": dict(preflight),
            },
        ),
        FeasibilityCheck(
            "distinctness",
            "PASS" if distinct_ok else "FAIL",
            "all decisive daily correlations have >=365 days and abs(corr)<0.30"
            if distinct_ok
            else "a decisive correlation is unavailable, under-covered, or >=0.30",
            {
                "threshold": DISTINCTNESS_THRESHOLD,
                "required_common_days": MIN_COMMON_DAYS,
                "correlations": correlations,
                "decisive_reference": "E-059/F-TAKER-FLOW",
            },
        ),
        FeasibilityCheck(
            "cost_after_edge",
            "PASS" if plausible > 0.0 and mean_gross_bps > 8.0 else "FAIL",
            f"mean event gross={mean_gross_bps:.6f} bps; annualized net Sharpe={plausible:.6f}",
            {
                "roundtrip_cost_bps": 8.0,
                "mean_event_gross_bps": mean_gross_bps,
                "annualized_net_sharpe": plausible,
                "n_obs": n_obs,
                "grid_trials_evaluated": 0,
            },
        ),
        FeasibilityCheck(
            "statistical_power",
            "PASS" if plausible >= floor else "FAIL",
            f"plausible_net_sharpe={plausible:.6f} {'>=' if plausible >= floor else '<'} min_detectable_sharpe={floor:.6f}",
            {
                "breadth": 1.5,
                "n_obs": n_obs,
                "n_trials": 4,
                "periods_per_year": periods_per_year,
                "plausible_net_sharpe": plausible,
                "min_detectable_sharpe": floor,
                "grid_trials_evaluated": 0,
            },
        ),
    )
    return FeasibilityResult(BATCH_ID, "H-030", "f_intrabar_periodicity", "H-030", FAMILY_ID, checks)


async def _run(dsn: str, output_root: Path) -> None:
    preflight = preflight_slate_references()
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction(readonly=True):
            await conn.execute("SET LOCAL statement_timeout = '20min'")
            result = await probe_intrabar_periodicity(conn, {"i49_preflight": preflight})
    finally:
        await conn.close()
    output = output_root / result.candidate_dir
    output.mkdir(parents=True, exist_ok=False)
    artifact = output / "stage2_feasibility.json"
    artifact.write_text(json.dumps(result_to_dict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (output / "sha256.json").write_text(json.dumps({artifact.name: digest}, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output-root", type=Path, default=Path("results") / BATCH_ID)
    args = parser.parse_args()
    asyncio.run(_run(args.dsn, args.output_root))


if __name__ == "__main__":
    main()
