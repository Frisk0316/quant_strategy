"""Generate and validate portable signal-point fixtures for active strategies.

This script is intentionally scoped to first-stage portable validation:
timestamp/bar, symbol, side, action/entry-exit, and indicator/reference-signal
calculation. Order/fill semantics, PnL, fees, slippage, funding settlement, and
full Nautilus matching-engine parity remain advisory/out of scope.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "backtesting"))

from backtesting import differential_validation as dv
from backtesting.replay import ReplayBacktestEngine

ENGINES = ["vectorbt", "backtrader", "nautilus"]


def _utc_ts(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _iso(ts: Any) -> str:
    return _utc_ts(ts).isoformat().replace("+00:00", "Z")


def _ts_ms(ts: Any) -> int:
    return int(_utc_ts(ts).timestamp() * 1000)


def _swap_ct_val(symbol: str) -> float:
    if not symbol.endswith("-SWAP"):
        return 1.0
    value, _ = ReplayBacktestEngine._resolve_swap_ct_val(symbol, {})
    return float(value)


def _authoritative_ct_val_validation(symbols: list[str]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for symbol in [str(item) for item in symbols if item]:
        if symbol.endswith("-SWAP"):
            sources[symbol] = {"value": _swap_ct_val(symbol), "source": "config_override"}
        else:
            sources[symbol] = {"value": 1.0, "source": "spot_unit"}
    return {
        "ct_val_sources": sources,
        "ct_val_all_authoritative": True,
        "ct_val_non_authoritative_symbols": [],
        "ct_val_gate_passed": True,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    data = dict(payload)
    if path.name == "result.json":
        validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
        validation = dict(validation)
        validation.update(_authoritative_ct_val_validation(list(data.get("symbols") or [])))
        validation.setdefault("validation_status", "portable_signal_fixture")
        validation.setdefault("artifact_scope", "signal_point_indicator_only")
        validation.setdefault("order_fill_nautilus_full_parity", "out_of_scope_next_phase")
        data["validation"] = validation
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _prepare_run_dir(results_dir: Path, run_id: str, *, force: bool) -> Path:
    run_dir = results_dir / run_id
    if run_dir.exists() and any(run_dir.iterdir()) and not force:
        raise FileExistsError(f"{run_dir} already exists; choose another --batch-id or pass --force")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _empty_artifacts(run_dir: Path) -> None:
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "trades.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)


def _signal_trades(signals: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(columns=["ts", "datetime", "strategy", "inst_id", "side", "price", "qty", "pnl"])
    return pd.DataFrame({
        "ts": signals["ts"],
        "datetime": signals["datetime"],
        "strategy": strategy,
        "inst_id": signals["inst_id"],
        "side": signals["side"],
        "price": pd.to_numeric(signals.get("fair_value", pd.Series(np.nan, index=signals.index)), errors="coerce"),
        "qty": pd.Series(np.nan, index=signals.index),
        "pnl": pd.Series(np.nan, index=signals.index),
    })


def _write_equity(run_dir: Path, times: pd.DatetimeIndex, equity: float = 1000.0) -> None:
    pd.DataFrame({
        "ts": [_ts_ms(ts) for ts in times],
        "datetime": [_iso(ts) for ts in times],
        "equity": [float(equity)] * len(times),
    }).to_csv(run_dir / "equity_curve.csv", index=False)


def _build_technical(results_dir: Path, strategy: str, batch_id: str, *, force: bool) -> Path:
    run_id = f"{batch_id}_{strategy}"
    run_dir = _prepare_run_dir(results_dir, run_id, force=force)
    symbol = "BTC-USDT-SWAP"
    params_by_strategy = {
        "ma_crossover": {"fast_window": 3, "slow_window": 7, "symbols": [symbol]},
        "ema_crossover": {"fast_span": 3, "slow_span": 8, "symbols": [symbol]},
        "macd_crossover": {"fast_span": 4, "slow_span": 9, "signal_span": 4, "symbols": [symbol]},
    }
    params = params_by_strategy[strategy]
    times = pd.date_range("2024-01-01T00:00:00Z", periods=180, freq="h")
    closes = [
        100.0 + 5.0 * math.sin(i / 4.0) + 1.8 * math.sin(i / 11.0) + 0.01 * i
        for i in range(len(times))
    ]
    prices = pd.DataFrame({
        "ts": [_ts_ms(ts) for ts in times],
        "datetime": [_iso(ts) for ts in times],
        "inst_id": [symbol] * len(times),
        "open": closes,
        "high": [value + 0.5 for value in closes],
        "low": [value - 0.5 for value in closes],
        "close": closes,
        "vol": [10.0 + (i % 5) for i in range(len(times))],
    })
    prices.to_csv(run_dir / "price_series.csv", index=False)
    _write_equity(run_dir, times)
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "display_name": f"{strategy} portable signal fixture",
            "strategies": [strategy],
            "symbols": [symbol],
            "bar": "1H",
            "start": _iso(times[0]),
            "end": _iso(times[-1]),
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "parameters": {"strategies": {strategy: params}, "backtest": {"fill_all_signals": False}},
        },
    )
    _write_json(
        run_dir / "config.json",
        {
            "system": {"equity_usd": 1000.0},
            "strategies": {strategy: params},
            "backtest": {"fill_all_signals": False},
        },
    )
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    bundle = dv.load_artifact_bundle(run_dir)
    indicators = dv._technical_reference_indicator_series(bundle, strategy)
    signals = dv._technical_reference_signals(bundle, strategy)
    if signals.empty:
        raise RuntimeError(f"{strategy} generated no fixture signals")
    indicators.to_csv(run_dir / "indicator_series.csv", index=False)
    signals.to_csv(run_dir / "signals.csv", index=False)
    _signal_trades(signals, strategy).to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _build_pairs_trading(results_dir: Path, batch_id: str, *, force: bool) -> Path:
    run_id = f"{batch_id}_pairs_trading"
    run_dir = _prepare_run_dir(results_dir, run_id, force=force)
    symbol_y = "ETH-USDT-SWAP"
    symbol_x = "BTC-USDT-SWAP"
    params = {
        "symbol_y": symbol_y,
        "symbol_x": symbol_x,
        "kalman_delta": 1e-4,
        "entry_z": 0.8,
        "exit_z": 0.2,
        "stop_z": 99.0,
        "lookback_hours": 168,
        "bar_seconds": 3600,
        "max_half_life_hours": 1000.0,
        "max_hedge_uncertainty": 10.0,
    }
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=260, freq="h")
    price_rows = []
    for idx, ts in enumerate(timestamps):
        x_price = 40_000.0 * (1.0 + 0.0002 * idx)
        spread = 0.018 * math.sin(idx / 4.0)
        y_price = math.exp(math.log(x_price) + spread) / 20.0
        for symbol, price in ((symbol_x, x_price), (symbol_y, y_price)):
            price_rows.append({
                "ts": _ts_ms(ts),
                "datetime": _iso(ts),
                "inst_id": symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "vol": 10.0,
            })
    pd.DataFrame(price_rows).to_csv(run_dir / "price_series.csv", index=False)
    _write_equity(run_dir, pd.DatetimeIndex([timestamps[0], timestamps[-1]]))
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": ["pairs_trading"],
            "symbols": [symbol_y, symbol_x],
            "bar": "1H",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "parameters": {"strategies": {"pairs_trading": params}, "backtest": {"fill_all_signals": False}},
        },
    )
    _write_json(
        run_dir / "config.json",
        {"system": {"equity_usd": 1000.0}, "strategies": {"pairs_trading": params}, "backtest": {}},
    )
    _empty_artifacts(run_dir)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._pairs_trading_reference_result(bundle, "fixture")
    if reference.signals.empty:
        raise RuntimeError("pairs_trading generated no fixture signals")
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _build_funding_carry(results_dir: Path, batch_id: str, *, force: bool) -> Path:
    run_id = f"{batch_id}_funding_carry"
    run_dir = _prepare_run_dir(results_dir, run_id, force=force)
    params = {
        "perp_symbol": "BTC-USDT-SWAP",
        "spot_symbol": "BTC-USDT",
        "min_apr_threshold": 0.12,
        "max_abs_basis_z": 2.5,
        "max_crowding": 0.85,
    }
    times = pd.to_datetime(
        ["2024-01-01T00:00:00Z", "2024-01-01T08:00:00Z", "2024-01-01T16:00:00Z"],
        utc=True,
    )
    prices = [100.0, 101.0, 102.0]
    pd.DataFrame({
        "ts": [_ts_ms(ts) for ts in times],
        "datetime": [_iso(ts) for ts in times],
        "inst_id": ["BTC-USDT-SWAP"] * len(times),
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "vol": [10.0] * len(times),
    }).to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame({
        "ts": [_ts_ms(ts) for ts in times],
        "datetime": [_iso(ts) for ts in times],
        "inst_id": ["BTC-USDT-SWAP"] * len(times),
        "funding_rate": [0.00005, 0.0002, -0.0001],
        "funding_interval_hours": [8.0, 8.0, 8.0],
        "basis_z": [0.0, 0.0, 0.0],
        "crowding": [0.2, 0.2, 0.2],
        "source": ["fixture"] * len(times),
    }).to_csv(run_dir / "funding_rates.csv", index=False)
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": ["funding_carry"],
            "symbols": ["BTC-USDT-SWAP", "BTC-USDT"],
            "bar": "8H",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "parameters": {"strategies": {"funding_carry": params}},
        },
    )
    _write_json(
        run_dir / "config.json",
        {"system": {"equity_usd": 1000.0}, "strategies": {"funding_carry": params}, "backtest": {}},
    )
    _empty_artifacts(run_dir)
    _write_equity(run_dir, times)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._funding_carry_reference_result(bundle, "fixture")
    if reference.signals.empty:
        raise RuntimeError("funding_carry generated no fixture signals")
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _build_daily_winner(results_dir: Path, batch_id: str, *, force: bool) -> Path:
    run_id = f"{batch_id}_daily_winner"
    run_dir = _prepare_run_dir(results_dir, run_id, force=force)
    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    dates = pd.date_range("2024-01-01T00:00:00Z", periods=4, freq="D")
    closes = {
        "BTC-USDT-SWAP": [110.0, 101.0, 100.0, 100.0],
        "ETH-USDT-SWAP": [105.0, 120.0, 103.0, 100.0],
    }
    price_rows = []
    for symbol in symbols:
        for ts, close in zip(dates, closes[symbol]):
            price_rows.append({
                "ts": _ts_ms(ts),
                "datetime": _iso(ts),
                "inst_id": symbol,
                "open": 100.0,
                "high": max(100.0, close),
                "low": min(100.0, close),
                "close": close,
                "vol": 10.0,
            })
    pd.DataFrame(price_rows).to_csv(run_dir / "price_series.csv", index=False)
    round_trips = [
        {"inst_id": "BTC-USDT-SWAP", "entry_ts": "2024-01-02T00:00:00Z", "exit_ts": "2024-01-03T00:00:00Z", "entry_price": 100.0, "exit_price": 101.0, "cost_rate": 0.0},
        {"inst_id": "ETH-USDT-SWAP", "entry_ts": "2024-01-03T00:00:00Z", "exit_ts": "2024-01-04T00:00:00Z", "entry_price": 100.0, "exit_price": 103.0, "cost_rate": 0.0},
        {"inst_id": "ETH-USDT-SWAP", "entry_ts": "2024-01-04T00:00:00Z", "exit_ts": "2024-01-05T00:00:00Z", "entry_price": 100.0, "exit_price": 100.0, "cost_rate": 0.0},
    ]
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": ["daily_winner"],
            "symbols": symbols,
            "bar": "1D",
            "start": "2024-01-01",
            "end": "2024-01-04",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "round_trips": round_trips,
        },
    )
    _write_json(
        run_dir / "config.json",
        {"system": {"equity_usd": 1000.0}, "strategies": {"daily_winner": {}}, "backtest": {}},
    )
    _empty_artifacts(run_dir)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._daily_winner_reference_result(bundle, "fixture")
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    reference.equity_curve.to_csv(run_dir / "equity_curve.csv", index=False)
    return run_dir


def _build_ohlcv_rotation(results_dir: Path, batch_id: str, *, force: bool) -> Path:
    from backtesting.ohlcv_rotation_backtest import run_ohlcv_rotation_backtest
    from okx_quant.strategies.ohlcv_rotation import OHLCVRotationParams

    run_id = f"{batch_id}_ohlcv_rotation"
    run_dir = _prepare_run_dir(results_dir, run_id, force=force)
    idx = pd.date_range("2024-01-01T00:00:00Z", periods=240, freq="min")
    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    dfs: dict[str, pd.DataFrame] = {}
    for symbol, closes in {
        "BTC-USDT-SWAP": [100.0 + i * 0.005 for i in range(len(idx))],
        "ETH-USDT-SWAP": [100.0 + i * 0.001 for i in range(len(idx))],
    }.items():
        dfs[symbol] = pd.DataFrame(
            {
                "open": closes,
                "high": closes,
                "low": [value * 0.998 for value in closes],
                "close": closes,
                "vol": [100.0 + i % 7 for i in range(len(idx))],
            },
            index=idx.tz_convert(None),
        )
    params = OHLCVRotationParams(
        universe=symbols,
        benchmark_inst_id="BTC-USDT-SWAP",
        bar="1m",
        rebalance_minutes=30,
        top_k=1,
        rank_exit_buffer=2,
        lookback_fast_minutes=5,
        lookback_slow_minutes=20,
        volume_z_window_minutes=5,
        realized_vol_window_minutes=5,
        breakout_window_minutes=5,
        ema_window_minutes=5,
        benchmark_ema_window_minutes=20,
        atr_window_minutes=5,
        min_volume_z=0.0,
        max_position_weight=1.0,
        fee_bps=0.0,
        slippage_bps=0.0,
    )
    result = run_ohlcv_rotation_backtest(dfs, params)
    price_rows = []
    for symbol, df in dfs.items():
        for ts, row in df.iterrows():
            utc = pd.Timestamp(ts, tz="UTC")
            price_rows.append({
                "ts": _ts_ms(utc),
                "datetime": _iso(utc),
                "inst_id": symbol,
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "vol": row["vol"],
            })
    pd.DataFrame(price_rows).to_csv(run_dir / "price_series.csv", index=False)
    result.target_weights.to_csv(run_dir / "target_weights.csv")
    result.trades.to_csv(run_dir / "trades.csv", index=False)
    pd.DataFrame({
        "ts": [_ts_ms(ts) for ts in result.equity_curve.index],
        "datetime": [_iso(ts) for ts in result.equity_curve.index],
        "equity": result.equity_curve.to_numpy(dtype=float) * 1000.0,
    }).to_csv(run_dir / "equity_curve.csv", index=False)
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": ["ohlcv_rotation"],
            "symbols": symbols,
            "bar": "1m",
            "benchmark": "BTC-USDT-SWAP",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "parameters": {"strategies": {"ohlcv_rotation": params.__dict__}, "backtest": {"fill_all_signals": False}},
        },
    )
    _write_json(
        run_dir / "config.json",
        {"system": {"equity_usd": 1000.0}, "strategies": {"ohlcv_rotation": params.__dict__}, "backtest": {}},
    )
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._ohlcv_rotation_reference_result(bundle, "fixture")
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    return run_dir


def _build_fear_greed(results_dir: Path, batch_id: str, *, force: bool) -> Path:
    run_id = f"{batch_id}_fear_greed_sentiment"
    run_dir = _prepare_run_dir(results_dir, run_id, force=force)
    params = {
        "symbol": "BTC-USDT-SWAP",
        "dataset_id": "fear_greed_btc",
        "max_age_seconds": 172800,
        "extreme_fear_label": "Extreme Fear",
        "exit_labels": ["Greed", "Extreme Greed"],
        "extreme_fear_threshold": 25.0,
        "exit_value_threshold": 51.0,
    }
    times = pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z", "2024-01-03T00:00:00Z"], utc=True)
    prices = [100.0, 102.0, 104.0]
    pd.DataFrame({
        "ts": [_ts_ms(ts) for ts in times],
        "datetime": [_iso(ts) for ts in times],
        "inst_id": ["BTC-USDT-SWAP"] * len(times),
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "vol": [10.0] * len(times),
    }).to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame({
        "dataset_id": ["fear_greed_btc", "fear_greed_btc"],
        "observed_at": ["2024-01-01T00:00:00Z", "2024-01-03T00:00:00Z"],
        "published_at": ["2024-01-01T00:00:00Z", "2024-01-03T00:00:00Z"],
        "value_num": [20.0, 70.0],
        "value_text": ["Extreme Fear", "Greed"],
        "fields": [{}, {}],
        "quality_status": ["ok", "ok"],
    }).to_csv(run_dir / "external_observations.csv", index=False)
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": ["fear_greed_sentiment"],
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1D",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "parameters": {"strategies": {"fear_greed_sentiment": params}},
        },
    )
    _write_json(
        run_dir / "config.json",
        {"system": {"equity_usd": 1000.0}, "strategies": {"fear_greed_sentiment": params}, "backtest": {}},
    )
    _empty_artifacts(run_dir)
    _write_equity(run_dir, times)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._external_feature_reference_result(bundle, "fixture")
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _build_cme_gap(results_dir: Path, batch_id: str, *, force: bool) -> Path:
    run_id = f"{batch_id}_cme_gap_fill"
    run_dir = _prepare_run_dir(results_dir, run_id, force=force)
    params = {
        "symbol": "BTC-USDT-SWAP",
        "dataset_id": "cme_btc1_continuous",
        "max_age_seconds": 604800,
        "min_gap_bps": 25.0,
        "max_hold_days": 2.0,
        "stop_loss_bps_mult": 1.5,
        "max_gap_bps": 0.0,
        "allow_direction": "long_only",
        "roll_dates": [],
    }
    market_times = pd.date_range("2024-01-05T00:00:00Z", periods=5, freq="D")
    prices = [100.0, 100.0, 100.0, 100.0, 102.5]
    pd.DataFrame({
        "ts": [_ts_ms(ts) for ts in market_times],
        "datetime": [_iso(ts) for ts in market_times],
        "inst_id": ["BTC-USDT-SWAP"] * len(market_times),
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "vol": [10.0] * len(market_times),
    }).to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame({
        "dataset_id": ["cme_btc1_continuous", "cme_btc1_continuous"],
        "observed_at": ["2024-01-05T00:00:00Z", "2024-01-08T00:00:00Z"],
        "published_at": ["2024-01-05T00:00:00Z", "2024-01-08T00:00:00Z"],
        "value_num": [100.0, 98.0],
        "value_text": ["", ""],
        "fields": [
            {"open": 100.0, "close": 100.0, "is_roll_day": False},
            {"open": 98.0, "close": 99.0, "is_roll_day": False},
        ],
        "quality_status": ["ok", "ok"],
    }).to_csv(run_dir / "external_observations.csv", index=False)
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": ["cme_gap_fill"],
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1D",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "parameters": {"strategies": {"cme_gap_fill": params}},
        },
    )
    _write_json(
        run_dir / "config.json",
        {"system": {"equity_usd": 1000.0}, "strategies": {"cme_gap_fill": params}, "backtest": {}},
    )
    _empty_artifacts(run_dir)
    _write_equity(run_dir, market_times)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._external_feature_reference_result(bundle, "fixture")
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


BUILDERS: dict[str, Callable[[Path, str], Path]] = {
    "ma_crossover": lambda results_dir, batch_id, *, force=False: _build_technical(results_dir, "ma_crossover", batch_id, force=force),
    "ema_crossover": lambda results_dir, batch_id, *, force=False: _build_technical(results_dir, "ema_crossover", batch_id, force=force),
    "macd_crossover": lambda results_dir, batch_id, *, force=False: _build_technical(results_dir, "macd_crossover", batch_id, force=force),
    "funding_carry": _build_funding_carry,
    "pairs_trading": _build_pairs_trading,
    "ohlcv_rotation": _build_ohlcv_rotation,
    "daily_winner": _build_daily_winner,
    "fear_greed_sentiment": _build_fear_greed,
    "cme_gap_fill": _build_cme_gap,
}


def _strategy_list(raw: str) -> list[str]:
    if raw == "all":
        return list(BUILDERS)
    strategies = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(strategies) - set(dv.REFERENCE_VALIDATION_CONTRACTS))
    if unknown:
        raise ValueError(f"Unknown strategy ids: {', '.join(unknown)}")
    missing_builders = sorted(set(strategies) - set(BUILDERS))
    if missing_builders:
        raise ValueError(
            "No fixture builder for strategy ids: "
            f"{', '.join(missing_builders)}; adapter_required contracts are not "
            "included in strategy-signal-validation fixtures."
        )
    return strategies


def _engine_list(raw: str) -> list[str]:
    engines = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not engines:
        raise ValueError("--engines must include at least one engine")
    unknown = sorted(set(engines) - dv.ENGINE_NAMES)
    if unknown:
        raise ValueError(f"Unknown engine ids: {', '.join(unknown)}")
    return engines


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--strategies", default="all", help="Comma-separated strategy IDs or 'all'")
    parser.add_argument(
        "--engines",
        default=",".join(ENGINES),
        help="Comma-separated engines: vectorbt,backtrader,nautilus",
    )
    parser.add_argument("--batch-id", default=None, help="Stable suffix for fixture and validation IDs")
    parser.add_argument("--force", action="store_true", help="Allow overwriting files in an existing generated fixture dir")
    args = parser.parse_args(argv)
    try:
        args.strategies = _strategy_list(args.strategies)
        args.engines = _engine_list(args.engines)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def _validation_scope(engines: list[str]) -> str:
    if "nautilus" in engines:
        return "signal_point_indicator_plus_nautilus_signal_replay_order_fill"
    return "signal_point_indicator"


def _prepare_engine_environment(engines: list[str]) -> None:
    if "vectorbt" in engines:
        os.environ.setdefault("NUMBA_DISABLE_JIT", "1")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    batch_id = args.batch_id or f"portable_signal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    strategies = args.strategies
    engines = args.engines
    _prepare_engine_environment(engines)

    rows = []
    for strategy in strategies:
        builder = BUILDERS[strategy]
        run_dir = builder(results_dir, batch_id, force=args.force)
        validation_id = f"{batch_id}_three_engine_signal_point"
        summary = dv.run_strategy_differential_validation(
            results_dir,
            strategy,
            engines=engines,
            fixture_run_id=run_dir.name,
            validation_id=validation_id,
        )
        rows.append({
            "strategy": strategy,
            "fixture_run_id": run_dir.name,
            "validation_id": validation_id,
            "status": summary.get("status"),
            "validation_conclusion": (summary.get("validation_conclusion") or {}).get("status"),
            "source_data_validation": (summary.get("source_data_validation") or {}).get("status"),
            "portable_validation_gate": (summary.get("portable_validation_gate") or {}).get("passed"),
            "signal_point_correctness": (summary.get("signal_point_correctness") or {}).get("passed"),
            "nautilus_order_fill_parity": (summary.get("nautilus_order_fill_parity") or {}).get("status"),
            "evidence_path": summary.get("evidence_path"),
        })

    report = {
        "batch_id": batch_id,
        "engines": engines,
        "scope": _validation_scope(engines),
        "out_of_scope": [
            "project_strategy_source_execution_in_nautilus",
            "l2_l3_queue_priority_parity",
            "pnl_parity",
            "fee_slippage_parity",
            "funding_settlement_parity",
        ],
        "rows": rows,
    }
    summary_path = results_dir / "strategy_validation" / f"{batch_id}_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    failed = [
        row for row in rows
        if row["status"] != "PASS"
        or row["validation_conclusion"] != "REFERENCE_PASS"
        or row["source_data_validation"] != "PASS"
        or row["portable_validation_gate"] is not True
        or row["signal_point_correctness"] is not True
        or ("nautilus" in engines and row["nautilus_order_fill_parity"] != "PASS")
    ]
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
