"""H-029 funding-settlement event probe."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, result_to_dict
from backtesting.pipeline_power_screen import min_detectable_sharpe

BATCH_ID = "funding_settlement_probe_20260729"
FAMILY_ID = "F-FUNDING-SETTLEMENT-DRIFT"
SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
FORMAL_START = datetime(2020, 4, 1, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2026, 7, 2, tzinfo=timezone.utc)
Z_CUT = 1.5
HOLD_HOURS = 2
ROUNDTRIP_COST = 8 / 10_000
MIN_COMMON_DAYS = 65
REFERENCE_PATHS = {
    "funding_xs": Path("results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/family_minting_candidate.json"),
    "vol_regime": Path("results/h014_stage3_20260714/combo_daily_returns.csv"),
    "funding_carry": Path("results/pipeline_batch2_20260625/c2_funding_carry/summary.json"),
}


def _utc(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def preflight_references(paths: Mapping[str, Path] = REFERENCE_PATHS) -> dict[str, Any]:
    """I49: validate mandatory dated references before any DB access."""
    xs = json.loads(paths["funding_xs"].read_text(encoding="utf-8")).get("signal")
    if not isinstance(xs, dict) or len(xs) < MIN_COMMON_DAYS:
        raise ValueError("I49 pre-flight: funding-XS reference lacks dated signal")
    vol = pd.read_csv(paths["vol_regime"], index_col=0)
    if len(vol) < MIN_COMMON_DAYS:
        raise ValueError("I49 pre-flight: vol-regime reference lacks dated returns")
    carry_gap = True
    carry_path = paths.get("funding_carry")
    if carry_path and carry_path.exists():
        payload = json.loads(carry_path.read_text(encoding="utf-8"))
        carry_gap = not isinstance(payload.get("daily_returns"), dict)
    return {
        "status": "PASS",
        "mandatory_references": {"funding_xs": len(xs), "vol_regime": len(vol)},
        "funding_carry_dated_series_gap_i49": carry_gap,
    }


def construct_event_returns(
    funding_rows: Sequence[Mapping[str, Any]],
    bars: Mapping[tuple[str, pd.Timestamp], float],
    *,
    z_cut: float = Z_CUT,
    hold_hours: int = HOLD_HOURS,
    lookback: int = 270,
) -> pd.DataFrame:
    frame = pd.DataFrame(funding_rows)
    if frame.empty:
        return pd.DataFrame(columns=["gross", "cost", "net", "active_symbols"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["rate"] = frame["rate"].astype(float)
    frame = frame.sort_values(["inst_id", "ts"])
    grouped = frame.groupby("inst_id")["rate"]
    mean = grouped.transform(lambda values: values.shift(1).rolling(lookback, min_periods=lookback).mean())
    std = grouped.transform(lambda values: values.shift(1).rolling(lookback, min_periods=lookback).std())
    frame["z"] = (frame["rate"] - mean) / std
    frame = frame.loc[frame["z"].abs() >= z_cut].copy()
    rows: list[dict[str, Any]] = []
    for row in frame.itertuples():
        settlement = row.ts.floor("min")
        entry_at = settlement + pd.Timedelta(minutes=1)
        exit_at = entry_at + pd.Timedelta(hours=hold_hours)
        entry = bars.get((row.inst_id, entry_at))
        exit_price = bars.get((row.inst_id, exit_at))
        if entry is None or exit_price is None or not entry:
            continue
        direction = -1.0 if row.z > 0 else 1.0
        gross = direction * (float(exit_price) / float(entry) - 1.0)
        rows.append({"ts": settlement, "inst_id": row.inst_id, "z": row.z, "gross": gross, "cost": ROUNDTRIP_COST})
    events = pd.DataFrame(rows)
    if events.empty:
        return pd.DataFrame(columns=["gross", "cost", "net", "active_symbols"])
    pooled = events.groupby("ts").agg(gross=("gross", "mean"), cost=("cost", "mean"), active_symbols=("inst_id", "nunique"))
    pooled["net"] = pooled["gross"] - pooled["cost"]
    return pooled


async def _fetch_events(conn: Any) -> list[dict[str, Any]]:
    funding = await conn.fetch(
        """
        SELECT inst_id, ts, COALESCE(realized_rate, funding_rate)::double precision AS rate
        FROM funding_rates
        WHERE source='binance' AND inst_id=ANY($1::text[])
          AND ts >= $2 AND ts < $3
        ORDER BY inst_id, ts
        """,
        list(SYMBOLS),
        FORMAL_START - timedelta(days=90),
        END_EXCLUSIVE,
    )
    frame = pd.DataFrame([dict(row) for row in funding])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    grouped = frame.groupby("inst_id")["rate"]
    mean = grouped.transform(lambda values: values.shift(1).rolling(270, min_periods=270).mean())
    std = grouped.transform(lambda values: values.shift(1).rolling(270, min_periods=270).std())
    frame["z"] = (frame["rate"] - mean) / std
    frame = frame.loc[(frame["ts"] >= FORMAL_START) & frame["z"].notna()].copy()
    active = frame.loc[frame["z"].abs() >= Z_CUT]
    requested: list[tuple[str, datetime]] = []
    for row in active.itertuples():
        settlement = row.ts.floor("min")
        requested.extend(
            [
                (row.inst_id, (settlement + pd.Timedelta(minutes=1)).to_pydatetime()),
                (row.inst_id, (settlement + pd.Timedelta(minutes=121)).to_pydatetime()),
            ]
        )
    bars = await conn.fetch(
        """
        SELECT c.inst_id, c.ts, c.open::double precision AS open
        FROM unnest($1::text[], $2::timestamptz[]) AS wanted(inst_id, ts)
        JOIN canonical_candles c USING (inst_id, ts)
        WHERE c.source_primary='binance' AND c.bar='1m' AND c.quality_status!='suspect'
        """,
        [row[0] for row in requested],
        [row[1] for row in requested],
    )
    prices = {(str(row["inst_id"]), _utc(row["ts"])): float(row["open"]) for row in bars}
    return [
        {
            "inst_id": row.inst_id,
            "ts": row.ts.floor("min"),
            "rate": row.rate,
            "z": row.z,
            "entry_open": prices.get((row.inst_id, row.ts.floor("min") + pd.Timedelta(minutes=1))),
            "exit_open": prices.get((row.inst_id, row.ts.floor("min") + pd.Timedelta(minutes=121))),
        }
        for row in frame.itertuples()
    ]


def _series_from_fetched(rows: Sequence[Mapping[str, Any]]) -> tuple[pd.Series, dict[str, Any]]:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.Series(dtype=float), {"eligible_rows": 0, "priced_rows": 0}
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["active"] = frame["z"].abs() >= Z_CUT
    frame["priced"] = ~frame[["entry_open", "exit_open"]].isna().any(axis=1)
    frame["net"] = 0.0
    priced = frame.loc[frame["active"] & frame["priced"]].copy()
    direction = priced["z"].map(lambda value: -1.0 if value > 0 else 1.0)
    frame.loc[priced.index, "net"] = direction * (priced["exit_open"] / priced["entry_open"] - 1.0) - ROUNDTRIP_COST
    incomplete = set(frame.loc[frame["active"] & ~frame["priced"], "ts"])
    pooled = frame.loc[~frame["ts"].isin(incomplete)].groupby("ts")["net"].sum().div(len(SYMBOLS)).sort_index()
    eligible = int(frame["active"].sum())
    priced_count = int((frame["active"] & frame["priced"]).sum())
    return pooled, {
        "eligible_rows": eligible,
        "priced_rows": priced_count,
        "priced_coverage": priced_count / eligible if eligible else 0.0,
        "traded_eligible_settlement_timestamps": int(pooled.index.nunique()),
    }


def _sharpe(series: pd.Series) -> float:
    clean = series.dropna()
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    return float(clean.mean() / std * math.sqrt(1095)) if std > 0 else 0.0


def _references(paths: Mapping[str, Path]) -> dict[str, pd.Series]:
    xs = json.loads(paths["funding_xs"].read_text(encoding="utf-8"))["signal"]
    refs = {"funding_xs": pd.Series(xs, dtype=float)}
    vol = pd.read_csv(paths["vol_regime"], index_col=0)
    refs.update({f"vol_regime:{column}": vol[column] for column in vol})
    for key, series in refs.items():
        series.index = pd.to_datetime(series.index, utc=True)
        refs[key] = series.astype(float)
    return refs


def build_probe_result(rows: Sequence[Mapping[str, Any]], *, preflight: Mapping[str, Any]) -> FeasibilityResult:
    event_returns, coverage = _series_from_fetched(rows)
    daily = event_returns.groupby(event_returns.index.floor("D")).sum() if len(event_returns) else event_returns
    correlations: dict[str, dict[str, Any]] = {}
    for name, reference in _references(REFERENCE_PATHS).items():
        pair = pd.concat([daily.rename("candidate"), reference.rename("reference")], axis=1).dropna()
        corr = float(pair.corr().iloc[0, 1]) if len(pair) >= 2 else None
        correlations[name] = {"common_days": len(pair), "correlation": corr}
    distinct_ok = all(
        row["common_days"] >= MIN_COMMON_DAYS
        and row["correlation"] is not None
        and abs(row["correlation"]) < 0.30
        for row in correlations.values()
    )
    plausible = _sharpe(event_returns)
    n_obs = int(coverage.get("traded_eligible_settlement_timestamps", 0))
    floor = min_detectable_sharpe(
        breadth=1.5,
        n_obs=n_obs,
        n_trials=4,
        periods_per_year=1095,
    ) if n_obs else math.inf
    checks = (
        FeasibilityCheck(
            "data_availability",
            "PASS" if coverage.get("priced_coverage", 0) >= 0.95 and n_obs else "FAIL",
            f"priced event coverage={coverage.get('priced_coverage', 0):.6f}",
            {**coverage, "i49_preflight": dict(preflight), "window": [FORMAL_START.isoformat(), END_EXCLUSIVE.isoformat()]},
        ),
        FeasibilityCheck(
            "distinctness",
            "PASS" if distinct_ok else "FAIL",
            "all mandatory daily correlations have >=65 days and abs(corr)<0.30" if distinct_ok else "mandatory correlation unavailable, under-covered, or >=0.30",
            {"threshold": 0.30, "required_common_days": MIN_COMMON_DAYS, "correlations": correlations},
        ),
        FeasibilityCheck(
            "cost_after_edge",
            "PASS" if plausible > 0 else "FAIL",
            f"annualized net Sharpe={plausible:.6f}",
            {"annualized_net_sharpe": plausible, "roundtrip_cost_bps": 8, "n_obs": n_obs},
        ),
        FeasibilityCheck(
            "statistical_power",
            "PASS" if plausible >= floor else "FAIL",
            f"plausible_net_sharpe={plausible:.6f} {'>=' if plausible >= floor else '<'} min_detectable_sharpe={floor:.6f}",
            {
                "breadth": 1.5,
                "n_obs": n_obs,
                "n_trials": 4,
                "periods_per_year": 1095,
                "plausible_net_sharpe": plausible,
                "min_detectable_sharpe": floor,
            },
        ),
    )
    return FeasibilityResult(BATCH_ID, "H-029", "f_funding_settlement_drift", "H-029", FAMILY_ID, checks)


async def probe_funding_settlement(conn: Any, ctx: Mapping[str, Any]) -> FeasibilityResult:
    preflight = ctx.get("i49_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "PASS":
        raise ValueError("I49 pre-flight must pass before DB probe access")
    return build_probe_result(await _fetch_events(conn), preflight=preflight)


async def _run(dsn: str, output: Path) -> None:
    preflight = preflight_references()  # Must precede connect.
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        result = await probe_funding_settlement(conn, {"i49_preflight": preflight})
    finally:
        await conn.close()
    payload = result_to_dict(result)
    output.mkdir(parents=True, exist_ok=False)
    artifact = output / "stage2_feasibility.json"
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (output / "sha256.json").write_text(json.dumps({artifact.name: digest}, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default="postgresql://quant:changeme@localhost:5432/quant")
    parser.add_argument("--output", type=Path, default=Path("results") / BATCH_ID)
    args = parser.parse_args()
    asyncio.run(_run(args.dsn, args.output))


if __name__ == "__main__":
    main()
