"""H-021 cross-venue funding-spread Stage-3 research backtest."""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isclose
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtesting.cpcv import CPCV
from backtesting.pipeline_family_minting import decide_family_minting
from backtesting.pipeline_refit import refit_validation, select_combo_on, validation_frame
from backtesting.xvenue_funding_spread_probe import (
    FROZEN_GRID,
    SYMBOL_DATASETS,
    FundingProxyParams,
    _canonical_hour,
    _expected_times,
    _fields,
    _float,
    _utc,
    align_funding_events,
    event_gap_count,
)

START = "2024-01-02T00:00:00Z"
END = "2026-07-03T00:00:00Z"
DSN = "postgresql://quant:changeme@localhost:5432/quant"
RUN_DATE = "20260715"
OUTPUT_DIR = Path(f"results/h021_stage3_{RUN_DATE}")
FAMILY_ID = "F-XVENUE-FUNDING-SPREAD"
HYPOTHESIS_ID = "H-021"
EXPERIMENT_ID = "E-056"
N_TRIALS = 12
PAIR_NAV = 1.0
LEG_WEIGHT = 0.5
BASE_COST_BPS = 4.0
STRESS_COST_BPS = 7.0
DERIBIT_IDS = {
    "BTC-USDT-SWAP": "BTC-PERPETUAL",
    "ETH-USDT-SWAP": "ETH-PERPETUAL",
}
REFERENCE_PATHS = {
    "F-FUNDING-XS-DISPERSION": Path(
        "results/idea_batch_20260701_taxonomy_002/"
        "f_funding_xs_dispersion/family_minting_candidate.json"
    ),
    "F-OI-POSITIONING": Path(
        "results/idea_batch_20260701_taxonomy_002/"
        "f_oi_positioning/family_minting_candidate.json"
    ),
}


@dataclass(frozen=True)
class PairSizes:
    binance_base_qty: float
    deribit_direction: int
    deribit_usd_notional: float


@dataclass(frozen=True)
class MarketEvent:
    ts: datetime
    spread: float
    binance_rate: float
    deribit_hourly_rates: tuple[float, ...]
    binance_mark: float
    deribit_mark: float
    deribit_hourly_marks: tuple[float, ...]


def _positive(value: float, name: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return out


def equal_usd_delta_sizes(pair_position: int, binance_mark: float, pair_nav: float = PAIR_NAV) -> PairSizes:
    """Size two 0.5-NAV legs at entry; +1 is long Binance/short Deribit."""

    if pair_position not in {-1, 1}:
        raise ValueError("active pair_position must be -1 or 1")
    nav = _positive(pair_nav, "pair_nav")
    mark = _positive(binance_mark, "binance_mark")
    notional = LEG_WEIGHT * nav
    return PairSizes(
        binance_base_qty=pair_position * notional / mark,
        deribit_direction=-pair_position,
        deribit_usd_notional=notional,
    )


def inverse_perp_price_pnl_coin(
    direction: int,
    usd_notional: float,
    previous_mark: float,
    current_mark: float,
) -> float:
    """ADR-0012 R9.1 exact inverse-perpetual price PnL in coin."""

    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    notional = _positive(usd_notional, "usd_notional")
    previous = _positive(previous_mark, "previous_mark")
    current = _positive(current_mark, "current_mark")
    return direction * notional * (1.0 / previous - 1.0 / current)


def deribit_funding_cashflow(
    direction: int,
    usd_notional: float,
    hourly_rates: Sequence[float],
    hourly_marks: Sequence[float],
) -> tuple[float, float]:
    """R9.3 coin funding and R9.2 same-hour USD conversion."""

    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    if len(hourly_rates) != 8 or len(hourly_marks) != 8:
        raise ValueError("each Binance window requires exactly eight Deribit hourly settlements")
    notional = _positive(usd_notional, "usd_notional")
    coin = 0.0
    usd = 0.0
    for rate, raw_mark in zip(hourly_rates, hourly_marks):
        mark = _positive(raw_mark, "hourly_mark")
        cash_coin = -direction * float(rate) * notional / mark
        coin += cash_coin
        usd += cash_coin * mark
    return coin, usd


def pair_event_pnl(
    *,
    pair_position: int,
    sizes: PairSizes,
    binance_previous: float,
    binance_current: float,
    deribit_previous: float,
    deribit_current: float,
    binance_funding_rate: float,
    deribit_hourly_rates: Sequence[float],
    deribit_hourly_marks: Sequence[float],
    turnover: float,
    cost_bps: float,
    pair_nav: float = PAIR_NAV,
) -> dict[str, float]:
    """Account one held 8h interval in pair-NAV USD."""

    if pair_position not in {-1, 1}:
        raise ValueError("pair_position must be -1 or 1")
    nav = _positive(pair_nav, "pair_nav")
    binance_price_pnl_usd = sizes.binance_base_qty * (
        _positive(binance_current, "binance_current")
        - _positive(binance_previous, "binance_previous")
    )
    deribit_price_pnl_coin = inverse_perp_price_pnl_coin(
        sizes.deribit_direction,
        sizes.deribit_usd_notional,
        deribit_previous,
        deribit_current,
    )
    deribit_price_pnl_usd = deribit_price_pnl_coin * _positive(
        deribit_current, "deribit_current"
    )
    binance_funding_usd = (
        -pair_position * LEG_WEIGHT * nav * float(binance_funding_rate)
    )
    deribit_funding_coin, deribit_funding_usd = deribit_funding_cashflow(
        sizes.deribit_direction,
        sizes.deribit_usd_notional,
        deribit_hourly_rates,
        deribit_hourly_marks,
    )
    gross_pnl_usd = (
        binance_price_pnl_usd
        + deribit_price_pnl_usd
        + binance_funding_usd
        + deribit_funding_usd
    )
    turnover_cost_usd = nav * float(turnover) * float(cost_bps) / 10_000.0
    return {
        "binance_price_pnl_usd": binance_price_pnl_usd,
        "deribit_price_pnl_coin": deribit_price_pnl_coin,
        "deribit_price_pnl_usd": deribit_price_pnl_usd,
        "binance_funding_usd": binance_funding_usd,
        "deribit_funding_coin": deribit_funding_coin,
        "deribit_funding_usd": deribit_funding_usd,
        "gross_pnl_usd": gross_pnl_usd,
        "turnover": float(turnover),
        "turnover_cost_usd": turnover_cost_usd,
        "net_pnl_usd": gross_pnl_usd - turnover_cost_usd,
    }


def target_positions(events: Sequence[MarketEvent], params: FundingProxyParams) -> list[int]:
    """Frozen forecast/entry/exit rule with the decision shifted to t+1."""

    state = 0
    history: list[float] = []
    targets: list[int] = []
    threshold = float(params.entry_bps) / 10_000.0
    for event in events:
        history.append(float(event.spread))
        forecast = (
            sum(history[-params.lookback_events :]) / params.lookback_events
            if len(history) >= params.lookback_events
            else None
        )
        if forecast is not None:
            sign = 1 if forecast > 0.0 else -1 if forecast < 0.0 else 0
            if state == 0 and abs(forecast) >= threshold:
                state = sign
            elif state != 0 and sign != state:
                state = sign if abs(forecast) >= threshold else 0
        targets.append(state)
    return [0, *targets[:-1]] if targets else []


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


async def _fetch_inputs(dsn: str, start: datetime, end: datetime) -> tuple[list[Any], ...]:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        binance_rows = await conn.fetch(
            """
            SELECT inst_id, ts AS observed_at,
                   COALESCE(realized_rate, funding_rate) AS rate
            FROM funding_rates
            WHERE source = 'binance'
              AND inst_id = ANY($1::text[])
              AND ts >= $2::timestamptz - interval '1 second'
              AND ts <  $3::timestamptz + interval '1 second'
            ORDER BY inst_id, ts
            """,
            list(SYMBOL_DATASETS),
            start,
            end,
        )
        deribit_rows = await conn.fetch(
            """
            SELECT dataset_id, observed_at, published_at, value_num AS rate,
                   quality_status, fields, fields->>'unit' AS unit
            FROM external_observations
            WHERE dataset_id = ANY($1::text[])
              AND observed_at >= $2::timestamptz - interval '7 hours'
              AND observed_at <  $3::timestamptz
            ORDER BY dataset_id, observed_at
            """,
            list(SYMBOL_DATASETS.values()),
            start,
            end,
        )
        event_marks = await conn.fetch(
            """
            WITH marks AS (
                SELECT inst_id, source_primary,
                       date_trunc('day', ts)
                       + floor(extract(hour FROM ts) / 8)::int * interval '8 hours'
                       + interval '8 hours' AS event_ts,
                       ts, close
                FROM canonical_candles
                WHERE bar = '1m'
                  AND quality_status != 'suspect'
                  AND ((source_primary = 'binance' AND inst_id = ANY($1::text[]))
                    OR (source_primary = 'deribit' AND inst_id = ANY($2::text[])))
                  AND ts >= $3::timestamptz - interval '8 hours'
                  AND ts <  $4::timestamptz - interval '8 hours'
            )
            SELECT DISTINCT ON (inst_id, source_primary, event_ts)
                   inst_id, source_primary, event_ts AS ts, close
            FROM marks
            WHERE event_ts >= $3::timestamptz AND event_ts < $4::timestamptz
            ORDER BY inst_id, source_primary, event_ts, ts DESC
            """,
            list(SYMBOL_DATASETS),
            list(DERIBIT_IDS.values()),
            start,
            end,
        )
        hourly_marks = await conn.fetch(
            """
            WITH marks AS (
                SELECT inst_id, date_trunc('hour', ts) + interval '1 hour' AS hour_ts,
                       ts, close
                FROM canonical_candles
                WHERE bar = '1m'
                  AND quality_status != 'suspect'
                  AND source_primary = 'deribit'
                  AND inst_id = ANY($1::text[])
                  AND ts >= $2::timestamptz - interval '8 hours'
                  AND ts <  $3::timestamptz - interval '8 hours'
            )
            SELECT DISTINCT ON (inst_id, hour_ts) inst_id, hour_ts AS ts, close
            FROM marks
            ORDER BY inst_id, hour_ts, ts DESC
            """,
            list(DERIBIT_IDS.values()),
            start,
            end,
        )
    finally:
        await conn.close()
    return list(binance_rows), list(deribit_rows), list(event_marks), list(hourly_marks)


def _market_events(dsn: str, start: datetime, end: datetime) -> dict[str, list[MarketEvent]]:
    binance_rows, deribit_rows, event_mark_rows, hourly_mark_rows = _run_sync(
        _fetch_inputs(dsn, start, end)
    )
    aligned, coverage = align_funding_events(
        binance_rows, deribit_rows, start=start, end=end
    )
    expected = _expected_times(start, end)
    for symbol, rows in aligned.items():
        if len(rows) != len(expected) or event_gap_count(rows) or coverage[symbol]["invalid_deribit_rows_seen"]:
            raise RuntimeError(
                f"{symbol} missing/invalid 8h funding events; fail closed without compression"
            )

    rates: dict[tuple[str, datetime], float] = {}
    for row in deribit_rows:
        dataset = str(row.get("dataset_id") or "")
        raw_ts = _utc(row["observed_at"])
        ts = _canonical_hour(raw_ts)
        rate = _float(row.get("rate"))
        fields = _fields(row)
        published = _utc(row.get("published_at") or raw_ts)
        if (
            dataset in SYMBOL_DATASETS.values()
            and ts is not None
            and rate is not None
            and str(row.get("quality_status") or "") != "suspect"
            and str(row.get("unit") or fields.get("unit") or "") == "rate_1h_decimal"
            and published <= raw_ts
        ):
            rates[(dataset, ts)] = float(rate)

    event_marks = {
        (str(row["source_primary"]), str(row["inst_id"]), _utc(row["ts"])): _positive(
            row["close"], "event_mark"
        )
        for row in event_mark_rows
    }
    hourly_marks = {
        (str(row["inst_id"]), _utc(row["ts"])): _positive(row["close"], "hourly_mark")
        for row in hourly_mark_rows
    }
    output: dict[str, list[MarketEvent]] = {}
    for symbol, aligned_rows in aligned.items():
        dataset = SYMBOL_DATASETS[symbol]
        deribit_id = DERIBIT_IDS[symbol]
        events: list[MarketEvent] = []
        for row in aligned_rows:
            hours = tuple(row.ts - timedelta(hours=offset) for offset in range(7, -1, -1))
            try:
                hourly_rates = tuple(rates[(dataset, hour)] for hour in hours)
                deribit_hourly_marks = tuple(hourly_marks[(deribit_id, hour)] for hour in hours)
                binance_mark = event_marks[("binance", symbol, row.ts)]
                deribit_mark = event_marks[("deribit", deribit_id, row.ts)]
            except KeyError as exc:
                raise RuntimeError(
                    f"{symbol} missing venue-scoped price/funding mark {exc}; fail closed"
                ) from exc
            if not isclose(sum(hourly_rates), row.deribit_rate, rel_tol=0.0, abs_tol=1e-15):
                raise RuntimeError(f"{symbol} Deribit hourly funding sum drifted from aligned event")
            events.append(
                MarketEvent(
                    ts=row.ts,
                    spread=row.spread,
                    binance_rate=row.binance_rate,
                    deribit_hourly_rates=hourly_rates,
                    binance_mark=binance_mark,
                    deribit_mark=deribit_mark,
                    deribit_hourly_marks=deribit_hourly_marks,
                )
            )
        output[symbol] = events
    return output


def _pair_path(events: Sequence[MarketEvent], params: FundingProxyParams) -> pd.DataFrame:
    positions = target_positions(events, params)
    rows: list[dict[str, float]] = []
    current = 0
    sizes: PairSizes | None = None
    for index, event in enumerate(events):
        if index == 0:
            rows.append({"gross": 0.0, "turnover": 0.0})
            continue
        previous = events[index - 1]
        desired = positions[index]
        turnover = float(abs(desired - current))
        if desired != current:
            current = desired
            sizes = (
                equal_usd_delta_sizes(current, previous.binance_mark)
                if current
                else None
            )
        if current and sizes is not None:
            accounted = pair_event_pnl(
                pair_position=current,
                sizes=sizes,
                binance_previous=previous.binance_mark,
                binance_current=event.binance_mark,
                deribit_previous=previous.deribit_mark,
                deribit_current=event.deribit_mark,
                binance_funding_rate=event.binance_rate,
                deribit_hourly_rates=event.deribit_hourly_rates,
                deribit_hourly_marks=event.deribit_hourly_marks,
                turnover=0.0,
                cost_bps=0.0,
            )
            gross = accounted["gross_pnl_usd"]
        else:
            gross = 0.0
        if index == len(events) - 1:
            turnover += abs(current)
            current = 0
            sizes = None
        rows.append({"gross": gross, "turnover": turnover})
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex([event.ts for event in events]))
    frame["base"] = frame["gross"] - frame["turnover"] * BASE_COST_BPS / 10_000.0
    frame["stress"] = frame["gross"] - frame["turnover"] * STRESS_COST_BPS / 10_000.0
    return frame


def _cell_name(params: FundingProxyParams) -> str:
    return f"L{params.lookback_events}_H{params.entry_bps:g}"


def _grid_returns(
    by_symbol: Mapping[str, Sequence[MarketEvent]],
) -> tuple[dict[str, pd.Series], dict[str, pd.Series], pd.DataFrame, dict[str, Any]]:
    base: dict[str, pd.Series] = {}
    stress: dict[str, pd.Series] = {}
    csv_columns: dict[str, pd.Series] = {}
    cell_table: dict[str, Any] = {}
    for params in FROZEN_GRID:
        cell = _cell_name(params)
        paths = {symbol: _pair_path(events, params) for symbol, events in by_symbol.items()}
        base_events = pd.concat({symbol: frame["base"] for symbol, frame in paths.items()}, axis=1)
        stress_events = pd.concat({symbol: frame["stress"] for symbol, frame in paths.items()}, axis=1)
        if base_events.isna().any().any() or stress_events.isna().any().any():
            raise RuntimeError(f"{cell} event alignment contains gaps; fail closed")
        base[cell] = base_events.mean(axis=1).resample("1D").sum()
        stress[cell] = stress_events.mean(axis=1).resample("1D").sum()
        csv_columns[f"{cell}__base"] = base[cell]
        csv_columns[f"{cell}__stress"] = stress[cell]
        cell_table[cell] = {
            "params": {
                "lookback_events": params.lookback_events,
                "entry_bps": params.entry_bps,
            },
            "base_aggregate_pnl": float(base[cell].sum()),
            "stress_aggregate_pnl": float(stress[cell].sum()),
            "by_symbol": {
                symbol: {
                    "base_pnl": float(frame["base"].sum()),
                    "stress_pnl": float(frame["stress"].sum()),
                    "gross_pnl": float(frame["gross"].sum()),
                    "turnover": float(frame["turnover"].sum()),
                }
                for symbol, frame in paths.items()
            },
        }
    return base, stress, pd.DataFrame(csv_columns), cell_table


def _validation_with_retained_paths(combo_returns: dict[str, pd.Series]) -> dict[str, Any]:
    validation = refit_validation(
        combo_returns,
        n_trials=N_TRIALS,
        is_days=365,
        oos_days=90,
        cpcv_n_splits=6,
        cpcv_k_test=2,
        embargo_pct=0.02,
        purge_size=1,
    )
    frame = validation_frame(combo_returns)

    def fold_returns(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        selected = select_combo_on(train.index, combo_returns)
        return combo_returns[selected].reindex(test.index).fillna(0.0)

    retained = CPCV(n_splits=6, k_test=2, embargo_pct=0.02, purge_size=1).evaluate(
        frame,
        fold_returns,
        periods=365,
        n_trials=N_TRIALS,
        n_trials_provenance="caller_declared",
    )
    for official, replayed in (
        (validation["cpcv_oos_sharpe"], retained["overall_oos_sharpe"]),
        (validation["dsr"], retained["dsr"]),
        (validation["psr"], retained["psr"]),
    ):
        if official is None or not isclose(float(official), float(replayed), rel_tol=0.0, abs_tol=1e-12):
            raise RuntimeError("retained CPCV path replay does not match refit_validation")
    keys = (
        "path_returns",
        "path_return_periods",
        "path_return_lengths",
        "combined_returns",
        "combined_return_periods",
        "combined_return_length",
        "n_trials",
        "n_trials_provenance",
        "n_trials_is_floor",
    )
    validation["cpcv"].update({key: retained[key] for key in keys})
    return validation


def _reference_signals() -> dict[str, Mapping[str, float]]:
    references: dict[str, Mapping[str, float]] = {}
    for family_id, path in REFERENCE_PATHS.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        signal = payload.get("signal") if isinstance(payload, Mapping) else None
        if not isinstance(signal, Mapping) or not signal:
            raise RuntimeError(f"required family-minting reference missing/empty: {path}")
        references[family_id] = signal
    return references


def _json_signal(series: pd.Series) -> dict[str, float]:
    return {
        pd.Timestamp(ts).date().isoformat(): float(value)
        for ts, value in series.items()
        if np.isfinite(value)
    }


def _output_dir(ctx: Mapping[str, Any]) -> Path:
    return Path(ctx.get("output_dir", OUTPUT_DIR))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_xvenue_funding_spread_checkpoint(ctx: Mapping[str, Any] | None = None) -> dict[str, Any]:
    ctx = ctx or {}
    output_dir = _output_dir(ctx)
    if (output_dir / "summary.json").exists():
        raise RuntimeError(f"refusing H-021 Stage-3 retry over existing {output_dir / 'summary.json'}")
    dsn = str(ctx.get("dsn", DSN))
    start = _utc(ctx.get("start", START))
    end = _utc(ctx.get("end", END))
    by_symbol = _market_events(dsn, start, end)
    base, stress, combo_daily, cell_table = _grid_returns(by_symbol)
    validation = _validation_with_retained_paths(base)

    default_cell = _cell_name(FROZEN_GRID[0])
    minting = decide_family_minting(
        _json_signal(base[default_cell]),
        _reference_signals(),
        "NEW",
        "same-symbol Binance/Deribit funding divergence with basis convergence",
        Path("docs/EXPERIMENT_REGISTRY.md"),
        batch_id=f"h021_stage3_{RUN_DATE}",
        candidate_id="f-xvenue-funding-spread",
    )
    selected_cells = sorted(
        set(validation["wf_selected_param_counts"])
        | set(validation["cpcv_selected_param_counts"])
    )
    for cell, row in cell_table.items():
        row["fold_selected"] = cell in selected_cells
        row["stress_net_positive"] = row["stress_aggregate_pnl"] > 0.0
    robustness_passed = bool(selected_cells) and all(
        cell_table[cell]["stress_net_positive"] for cell in selected_cells
    )
    statistical_passed = bool(
        validation["dsr"] is not None
        and validation["psr"] is not None
        and validation["dsr"] >= 0.95
        and validation["psr"] >= 0.95
    )
    expected_events = len(_expected_times(start, end))
    summary = {
        "batch_id": f"h021_stage3_{RUN_DATE}",
        "candidate_id": "f-xvenue-funding-spread",
        "hypothesis_id": HYPOTHESIS_ID,
        "experiment_id": EXPERIMENT_ID,
        "family_id": FAMILY_ID,
        "grid_size_this_run": len(FROZEN_GRID),
        "family_cumulative_n_trials": N_TRIALS,
        "n_trials": N_TRIALS,
        "n_trials_provenance": "caller_declared",
        "n_trials_is_floor": False,
        "validation_mode": validation["validation_mode"],
        "wf_oos_sharpe": validation["wf_oos_sharpe"],
        "cpcv_oos_sharpe": validation["cpcv_oos_sharpe"],
        "dsr": validation["dsr"],
        "psr": validation["psr"],
        "wf_selected_param_counts": validation["wf_selected_param_counts"],
        "cpcv_selected_param_counts": validation["cpcv_selected_param_counts"],
        "cpcv": validation["cpcv"],
        "path_returns_retained": bool(validation["cpcv"].get("path_returns")),
        "family_minting": minting,
        "default_cell_for_minting": default_cell,
        "stress_recost": {
            "base_cost_bps": BASE_COST_BPS,
            "stress_cost_bps": STRESS_COST_BPS,
            "fold_selected_cells": selected_cells,
            "requirement": "every fold-selected cell has positive aggregate stress PnL",
            "passed": robustness_passed,
            "cells": cell_table,
        },
        "statistical_gate_passed": statistical_passed,
        "robustness_requirement_passed": robustness_passed,
        "stage3_gate_passed": statistical_passed and robustness_passed,
        "leak_test_passed": True,
        "leak_test_reference": (
            "target_positions shifts each event-t decision to event t+1; complete 8h timeline "
            "asserted before evaluation"
        ),
        "idealized_fill": False,
        "portable_validation_gate": False,
        "portable_validation_block_reason": "cross-venue inverse-perpetual reference adapter absent",
        "promotion_gate_passed": False,
        "accounting": {
            "rule": "ADR-0012 / DOMAIN_RULES R9",
            "binance": "linear fixed base quantity sized to 0.5 pair NAV at entry",
            "deribit": "exact inverse 1/P coin PnL converted at each same-event venue mark",
            "funding": "Binance R3.1 plus eight Deribit R9.3 hourly settlements",
            "pair_unit": "USD",
            "pair_nav": PAIR_NAV,
            "synthetic_usd_property": (
                "short inverse perpetual plus coin collateral is synthetic USD; adequate coin "
                "collateral and no liquidation are assumed only for this unlevered gross-1 pair"
            ),
        },
        "ct_val_all_authoritative": True,
        "ct_val_sources": {
            **{
                f"binance:{symbol}": {
                    "exchange": "binance",
                    "source": "exchange_base_unit",
                    "authoritative": True,
                }
                for symbol in SYMBOL_DATASETS
            },
            **{
                f"deribit:{deribit_id}": {
                    "exchange": "deribit",
                    "source": "ADR-0012_inverse_usd_face",
                    "authoritative": True,
                }
                for deribit_id in DERIBIT_IDS.values()
            },
        },
        "ct_val_not_applicable_reason": (
            "standalone USD-notional pair accounting uses Binance base units and Deribit inverse USD face"
        ),
        "data_source": {
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "event_count_per_symbol": expected_events,
            "venues": {
                "binance": {
                    "symbols": list(SYMBOL_DATASETS),
                    "source_primary": "binance",
                    "bar": "1m collapsed to last pre-settlement close",
                },
                "deribit": {
                    "symbols": list(DERIBIT_IDS.values()),
                    "source_primary": "deribit",
                    "bar": "1m collapsed to last pre-settlement close",
                    "index_substitution": False,
                },
            },
            "missing_event_policy": "fail_closed_never_compress",
            "daily_aggregation": "sum complete 8h event PnL by UTC day",
            "portfolio_aggregation": "equal mean of BTC and ETH pair-NAV returns",
        },
        "status": "checkpoint_review_required",
        "notes": [
            "First Stage-3 validation for this family; K remains 0/2.",
            "Stress is a re-cost of identical positions, not an additional trial grid.",
            "Research-only checkpoint evidence; no strategy/risk/execution/gate surface changed.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    combo_daily.index.name = "day_utc"
    combo_daily.to_csv(output_dir / "combo_daily_returns.csv")
    _write_json(output_dir / "family_minting.json", minting)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DSN)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    summary = run_xvenue_funding_spread_checkpoint(
        {"dsn": args.dsn, "output_dir": args.output_dir}
    )
    _write_json(args.output_dir / "summary.json", summary)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "wf_oos_sharpe",
                    "cpcv_oos_sharpe",
                    "dsr",
                    "psr",
                    "statistical_gate_passed",
                    "robustness_requirement_passed",
                    "promotion_gate_passed",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
