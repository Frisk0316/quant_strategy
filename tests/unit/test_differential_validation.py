import json
import math
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backtesting import differential_validation as dv
from okx_quant.api.routes_backtest import make_backtest_router


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_NAUTILUS_ENGINE_SMOKE = dv._nautilus_engine_smoke


@pytest.fixture(autouse=True)
def _stub_nautilus_engine_smoke(monkeypatch):
    monkeypatch.setattr(
        dv,
        "_nautilus_engine_smoke",
        lambda bundle, *args, **kwargs: {
            "status": "SKIP",
            "engine_execution": "not_run",
            "reason": "unit tests stub Nautilus BacktestEngine smoke",
            "scope_limit": "unit test stub; production validation uses the real helper",
        },
    )


def _authoritative_ct_val_validation(symbols):
    sources = {}
    for symbol in [str(item) for item in symbols if item]:
        if symbol.endswith("-SWAP"):
            sources[symbol] = {"value": 0.01, "source": "config_override"}
        else:
            sources[symbol] = {"value": 1.0, "source": "spot_unit"}
    return {
        "ct_val_sources": sources,
        "ct_val_all_authoritative": True,
        "ct_val_non_authoritative_symbols": [],
        "ct_val_gate_passed": True,
    }


def _write_json(path, payload, *, add_ct_val=True):
    data = dict(payload)
    if add_ct_val and path.name == "result.json":
        validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
        if "ct_val_all_authoritative" not in validation:
            validation = dict(validation)
            validation.update(_authoritative_ct_val_validation(data.get("symbols") or []))
            data["validation"] = validation
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _base_run(tmp_path, run_id="diff_run", strategy="ma_crossover"):
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": [strategy],
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1H",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
        },
    )
    _write_json(
        run_dir / "config.json",
        {
            "system": {"equity_usd": 1000.0},
            "strategies": {
                "ma_crossover": {"fast_window": 2, "slow_window": 3, "symbols": ["BTC-USDT-SWAP"]},
                "ema_crossover": {"fast_span": 2, "slow_span": 4, "symbols": ["BTC-USDT-SWAP"]},
                "macd_crossover": {
                    "fast_span": 3,
                    "slow_span": 6,
                    "signal_span": 3,
                    "symbols": ["BTC-USDT-SWAP"],
                },
            },
            "backtest": {},
        },
    )
    prices = pd.DataFrame(
        {
            "ts": [1_704_067_200_000, 1_704_070_800_000, 1_704_074_400_000],
            "datetime": [
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "2024-01-01T02:00:00Z",
            ],
            "inst_id": ["BTC-USDT-SWAP"] * 3,
            "open": [100.0, 101.0, 102.0],
            "high": [100.0, 101.0, 102.0],
            "low": [100.0, 101.0, 102.0],
            "close": [100.0, 101.0, 102.0],
            "vol": [10.0, 11.0, 12.0],
        }
    )
    prices.to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame(
        {
            "ts": [1_704_067_200_000, 1_704_070_800_000, 1_704_074_400_000],
            "datetime": [
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "2024-01-01T02:00:00Z",
            ],
            "equity": [1000.0, 1010.0, 1000.0],
        }
    ).to_csv(run_dir / "equity_curve.csv", index=False)
    pd.DataFrame(
        {
            "ts": [1_704_070_800_000],
            "datetime": ["2024-01-01T01:00:00Z"],
            "strategy": [strategy],
            "inst_id": ["BTC-USDT-SWAP"],
            "side": ["buy"],
            "fair_value": [101.0],
        }
    ).to_csv(run_dir / "signals.csv", index=False)
    pd.DataFrame(
        {
            "ts": [1_704_070_800_000],
            "datetime": ["2024-01-01T01:00:00Z"],
            "strategy": [strategy],
            "inst_id": ["BTC-USDT-SWAP"],
            "side": ["buy"],
            "fill_px": [101.0],
            "fill_sz": [1.0],
            "net_realized_pnl": [0.0],
        }
    ).to_csv(run_dir / "trades.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    return run_dir


def _daily_winner_run(tmp_path, run_id="daily_winner_reference"):
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    dates = pd.date_range("2024-01-01T00:00:00Z", periods=4, freq="D")
    closes = {
        "BTC-USDT-SWAP": [110.0, 101.0, 100.0, 100.0],
        "ETH-USDT-SWAP": [105.0, 120.0, 103.0, 100.0],
        "SOL-USDT-SWAP": [101.0, 100.0, 130.0, 100.0],
    }
    price_rows = []
    for symbol in symbols:
        for ts, close in zip(dates, closes[symbol]):
            price_rows.append({
                "ts": int(ts.timestamp() * 1000),
                "datetime": ts.isoformat().replace("+00:00", "Z"),
                "inst_id": symbol,
                "open": 100.0,
                "high": max(100.0, close),
                "low": min(100.0, close),
                "close": close,
                "vol": 10.0,
            })
    pd.DataFrame(price_rows).to_csv(run_dir / "price_series.csv", index=False)
    round_trips = [
        {
            "inst_id": "BTC-USDT-SWAP",
            "entry_ts": "2024-01-02T00:00:00Z",
            "exit_ts": "2024-01-03T00:00:00Z",
            "entry_price": 100.0,
            "exit_price": 101.0,
            "cost_rate": 0.0,
        },
        {
            "inst_id": "ETH-USDT-SWAP",
            "entry_ts": "2024-01-03T00:00:00Z",
            "exit_ts": "2024-01-04T00:00:00Z",
            "entry_price": 100.0,
            "exit_price": 103.0,
            "cost_rate": 0.0,
        },
        {
            "inst_id": "SOL-USDT-SWAP",
            "entry_ts": "2024-01-04T00:00:00Z",
            "exit_ts": "2024-01-05T00:00:00Z",
            "entry_price": 100.0,
            "exit_price": 100.0,
            "cost_rate": 0.0,
        },
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
            "equity": [
                {"datetime": "2024-01-01T00:00:00Z", "equity": 1000.0},
                {"datetime": "2024-01-02T00:00:00Z", "equity": 1010.0},
                {"datetime": "2024-01-03T00:00:00Z", "equity": 1040.3},
                {"datetime": "2024-01-04T00:00:00Z", "equity": 1040.3},
            ],
            "round_trips": round_trips,
        },
    )
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    return run_dir


def _ohlcv_rotation_run(tmp_path, run_id="ohlcv_rotation_reference"):
    from backtesting.ohlcv_rotation_backtest import run_ohlcv_rotation_backtest
    from okx_quant.strategies.ohlcv_rotation import OHLCVRotationParams

    run_dir = tmp_path / run_id
    run_dir.mkdir()
    idx = pd.date_range("2024-01-01T00:00:00Z", periods=240, freq="min")
    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    btc_close = [100.0 + i * 0.005 for i in range(len(idx))]
    eth_close = [100.0 + i * 0.001 for i in range(len(idx))]
    dfs = {}
    for symbol, closes in {"BTC-USDT-SWAP": btc_close, "ETH-USDT-SWAP": eth_close}.items():
        df = pd.DataFrame(
            {
                "open": closes,
                "high": closes,
                "low": [value * 0.998 for value in closes],
                "close": closes,
                "vol": [100.0 + i % 7 for i in range(len(idx))],
            },
            index=idx.tz_convert(None),
        )
        dfs[symbol] = df

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
    assert not result.target_weights.empty

    price_rows = []
    for symbol, df in dfs.items():
        for ts, row in df.iterrows():
            utc = pd.Timestamp(ts, tz="UTC")
            price_rows.append({
                "ts": int(utc.timestamp() * 1000),
                "datetime": utc.isoformat().replace("+00:00", "Z"),
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
        "ts": [pd.Timestamp(ts, tz="UTC").isoformat().replace("+00:00", "Z") for ts in result.equity_curve.index],
        "datetime": [pd.Timestamp(ts, tz="UTC").isoformat().replace("+00:00", "Z") for ts in result.equity_curve.index],
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
            "parameters": {
                "strategies": {
                    "ohlcv_rotation": {
                        "benchmark_inst_id": "BTC-USDT-SWAP",
                        "bar": "1m",
                        "rebalance_minutes": 30,
                        "top_k": 1,
                        "rank_exit_buffer": 2,
                        "lookback_fast_minutes": 5,
                        "lookback_slow_minutes": 20,
                        "volume_z_window_minutes": 5,
                        "realized_vol_window_minutes": 5,
                        "breakout_window_minutes": 5,
                        "ema_window_minutes": 5,
                        "benchmark_ema_window_minutes": 20,
                        "atr_window_minutes": 5,
                        "min_volume_z": 0.0,
                        "max_position_weight": 1.0,
                        "fee_bps": 0.0,
                        "slippage_bps": 0.0,
                    }
                },
                "backtest": {"fill_all_signals": False},
            },
        },
    )
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    return run_dir


def _pairs_trading_run(tmp_path, run_id="pairs_trading_reference"):
    run_dir = tmp_path / run_id
    run_dir.mkdir()
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
                "ts": int(ts.timestamp() * 1000),
                "datetime": ts.isoformat().replace("+00:00", "Z"),
                "inst_id": symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "vol": 10.0,
            })
    pd.DataFrame(price_rows).to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame(
        {
            "ts": [int(timestamps[0].timestamp() * 1000), int(timestamps[-1].timestamp() * 1000)],
            "datetime": [
                timestamps[0].isoformat().replace("+00:00", "Z"),
                timestamps[-1].isoformat().replace("+00:00", "Z"),
            ],
            "equity": [1000.0, 1000.0],
        }
    ).to_csv(run_dir / "equity_curve.csv", index=False)
    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "strategies": ["pairs_trading"],
            "symbols": [symbol_y, symbol_x],
            "bar": "1H",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0},
            "parameters": {
                "strategies": {"pairs_trading": params},
                "backtest": {"fill_all_signals": True},
            },
        },
    )
    _write_json(
        run_dir / "config.json",
        {
            "system": {"equity_usd": 1000.0},
            "strategies": {"pairs_trading": params},
            "backtest": {"fill_all_signals": True},
        },
    )
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "trades.csv", index=False)

    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._pairs_trading_reference_result(bundle, "vectorbt")
    assert not reference.signals.empty
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _fear_greed_run(tmp_path, run_id="fear_greed_reference"):
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    params = {
        "symbol": "BTC-USDT-SWAP",
        "dataset_id": "fear_greed_btc",
        "max_age_seconds": 172800,
        "extreme_fear_label": "Extreme Fear",
        "exit_labels": ["Greed", "Extreme Greed"],
        "extreme_fear_threshold": 25.0,
        "exit_value_threshold": 51.0,
    }
    times = pd.to_datetime(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z",
            "2024-01-03T00:00:00Z",
        ],
        utc=True,
    )
    prices = [100.0, 102.0, 104.0]
    pd.DataFrame(
        {
            "ts": [int(ts.timestamp() * 1000) for ts in times],
            "datetime": [ts.isoformat().replace("+00:00", "Z") for ts in times],
            "inst_id": ["BTC-USDT-SWAP"] * len(times),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "vol": [10.0] * len(times),
        }
    ).to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame(
        {
            "dataset_id": ["fear_greed_btc", "fear_greed_btc"],
            "observed_at": [
                "2024-01-01T00:00:00Z",
                "2024-01-03T00:00:00Z",
            ],
            "published_at": [
                "2024-01-01T00:00:00Z",
                "2024-01-03T00:00:00Z",
            ],
            "value_num": [20.0, 70.0],
            "value_text": ["Extreme Fear", "Greed"],
            "fields": [{}, {}],
            "quality_status": ["ok", "ok"],
        }
    ).to_csv(run_dir / "external_observations.csv", index=False)
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
        {
            "system": {"equity_usd": 1000.0},
            "strategies": {"fear_greed_sentiment": params},
            "backtest": {},
        },
    )
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "trades.csv", index=False)
    pd.DataFrame(
        {
            "ts": [int(times[0].timestamp() * 1000), int(times[-1].timestamp() * 1000)],
            "datetime": [
                times[0].isoformat().replace("+00:00", "Z"),
                times[-1].isoformat().replace("+00:00", "Z"),
            ],
            "equity": [1000.0, 1000.0],
        }
    ).to_csv(run_dir / "equity_curve.csv", index=False)

    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._external_feature_reference_result(bundle, "vectorbt")
    assert list(reference.signals["side"]) == ["buy", "sell"]
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _cme_gap_run(tmp_path, run_id="cme_gap_reference"):
    run_dir = tmp_path / run_id
    run_dir.mkdir()
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
    market_times = pd.to_datetime(
        [
            "2024-01-05T00:00:00Z",
            "2024-01-08T00:00:00Z",
            "2024-01-08T12:00:00Z",
        ],
        utc=True,
    )
    prices = [100.0, 100.0, 102.5]
    pd.DataFrame(
        {
            "ts": [int(ts.timestamp() * 1000) for ts in market_times],
            "datetime": [ts.isoformat().replace("+00:00", "Z") for ts in market_times],
            "inst_id": ["BTC-USDT-SWAP"] * len(market_times),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "vol": [10.0] * len(market_times),
        }
    ).to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame(
        {
            "dataset_id": ["cme_btc1_continuous", "cme_btc1_continuous"],
            "observed_at": [
                "2024-01-05T00:00:00Z",
                "2024-01-08T00:00:00Z",
            ],
            "published_at": [
                "2024-01-05T00:00:00Z",
                "2024-01-08T00:00:00Z",
            ],
            "value_num": [100.0, 98.0],
            "value_text": ["", ""],
            "fields": [
                {"open": 100.0, "close": 100.0, "is_roll_day": False},
                {"open": 98.0, "close": 99.0, "is_roll_day": False},
            ],
            "quality_status": ["ok", "ok"],
        }
    ).to_csv(run_dir / "external_observations.csv", index=False)
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
        {
            "system": {"equity_usd": 1000.0},
            "strategies": {"cme_gap_fill": params},
            "backtest": {},
        },
    )
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "trades.csv", index=False)
    pd.DataFrame(
        {
            "ts": [int(market_times[0].timestamp() * 1000), int(market_times[-1].timestamp() * 1000)],
            "datetime": [
                market_times[0].isoformat().replace("+00:00", "Z"),
                market_times[-1].isoformat().replace("+00:00", "Z"),
            ],
            "equity": [1000.0, 1000.0],
        }
    ).to_csv(run_dir / "equity_curve.csv", index=False)

    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._external_feature_reference_result(bundle, "vectorbt")
    assert list(reference.signals["side"]) == ["buy", "sell"]
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _funding_carry_run(tmp_path, run_id="funding_carry_reference"):
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    params = {
        "perp_symbol": "BTC-USDT-SWAP",
        "spot_symbol": "BTC-USDT",
        "min_apr_threshold": 0.12,
        "max_abs_basis_z": 2.5,
        "max_crowding": 0.85,
    }
    times = pd.to_datetime(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-01T08:00:00Z",
            "2024-01-01T16:00:00Z",
        ],
        utc=True,
    )
    prices = [100.0, 101.0, 102.0]
    pd.DataFrame(
        {
            "ts": [int(ts.timestamp() * 1000) for ts in times],
            "datetime": [ts.isoformat().replace("+00:00", "Z") for ts in times],
            "inst_id": ["BTC-USDT-SWAP"] * len(times),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "vol": [10.0] * len(times),
        }
    ).to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame(
        {
            "ts": [int(ts.timestamp() * 1000) for ts in times],
            "datetime": [ts.isoformat().replace("+00:00", "Z") for ts in times],
            "inst_id": ["BTC-USDT-SWAP"] * len(times),
            "funding_rate": [0.00005, 0.0002, -0.0001],
            "funding_interval_hours": [8.0, 8.0, 8.0],
            "basis_z": [0.0, 0.0, 0.0],
            "crowding": [0.2, 0.2, 0.2],
            "source": ["unit"] * len(times),
        }
    ).to_csv(run_dir / "funding_rates.csv", index=False)
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
        {
            "system": {"equity_usd": 1000.0},
            "strategies": {"funding_carry": params},
            "backtest": {},
        },
    )
    pd.DataFrame().to_csv(run_dir / "indicator_series.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame().to_csv(run_dir / "trades.csv", index=False)
    pd.DataFrame(
        {
            "ts": [int(times[0].timestamp() * 1000), int(times[-1].timestamp() * 1000)],
            "datetime": [
                times[0].isoformat().replace("+00:00", "Z"),
                times[-1].isoformat().replace("+00:00", "Z"),
            ],
            "equity": [1000.0, 1000.0],
        }
    ).to_csv(run_dir / "equity_curve.csv", index=False)

    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._funding_carry_reference_result(bundle, "vectorbt")
    assert list(reference.signals["side"]) == ["sell", "buy"]
    reference.signals.to_csv(run_dir / "signals.csv", index=False)
    reference.trades.to_csv(run_dir / "trades.csv", index=False)
    return run_dir


def _declared_strategy_ids() -> set[str]:
    frontend_text = (REPO_ROOT / "frontend" / "data.js").read_text(encoding="utf-8")
    strategies_match = re.search(r"const STRATEGIES\s*=\s*\[(?P<body>.*?)\n\s*\];", frontend_text, re.S)
    assert strategies_match, "frontend/data.js STRATEGIES array not found"
    frontend_ids = set(re.findall(r'id:\s*"([a-z0-9_]+)"', strategies_match.group("body")))

    routes_text = (REPO_ROOT / "src" / "okx_quant" / "api" / "routes_backtest.py").read_text(encoding="utf-8")
    allowed_match = re.search(r"allowed\s*=\s*\{(?P<body>.*?)\n\s*\}", routes_text, re.S)
    assert allowed_match, "routes_backtest.py allowed strategy set not found"
    api_ids = set(re.findall(r'"([a-z][a-z0-9_]+)"', allowed_match.group("body")))
    return frontend_ids | api_ids


def test_reference_validation_contract_covers_all_declared_strategies():
    declared = _declared_strategy_ids()
    missing = declared - set(dv.REFERENCE_VALIDATION_CONTRACTS)

    assert missing == set()
    for strategy in declared:
        contract = dv.REFERENCE_VALIDATION_CONTRACTS[strategy]
        statuses = {
            str(capability.get("status"))
            for capability in (contract.get("engines") or {}).values()
        }
        if contract.get("portable_validation_required") is False:
            assert statuses <= {"not_targeted"}, strategy
        else:
            assert statuses == {"implemented"}, strategy


def test_reference_validation_contract_declares_all_engine_portability_paths():
    allowed_statuses = {"implemented", "adapter_required", "not_targeted"}
    for strategy, contract in dv.REFERENCE_VALIDATION_CONTRACTS.items():
        engines = contract.get("engines") or {}
        assert set(engines) == dv.ENGINE_NAMES, strategy
        for engine, capability in engines.items():
            assert capability.get("status") in allowed_statuses, f"{strategy}:{engine}"
            assert capability.get("role") in dv.REFERENCE_ROLES, f"{strategy}:{engine}"
            assert capability.get("limitation"), f"{strategy}:{engine}"


def test_artifact_loader_reads_replay_rotation_and_daily_winner_shapes(tmp_path):
    replay = _base_run(tmp_path, "replay_run", "ma_crossover")
    rotation = _base_run(tmp_path, "rotation_run", "ohlcv_rotation")

    daily = tmp_path / "daily_run"
    daily.mkdir()
    _write_json(
        daily / "result.json",
        {
            "run_id": "daily_run",
            "strategies": ["daily_winner"],
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1D",
            "metrics": {"sharpe": 0.0, "max_drawdown": 0.0},
            "equity": [{"datetime": "2024-01-01T00:00:00Z", "equity": 1000.0}],
            "trades": [{"datetime": "2024-01-01T00:00:00Z", "side": "buy", "fill_px": 100.0}],
        },
    )

    assert dv.load_artifact_bundle(replay).primary_strategy == "ma_crossover"
    assert dv.load_artifact_bundle(rotation).primary_strategy == "ohlcv_rotation"
    loaded_daily = dv.load_artifact_bundle(daily)
    assert loaded_daily.primary_strategy == "daily_winner"
    assert len(loaded_daily.equity_curve) == 1
    assert len(loaded_daily.trades) == 1


def test_neutral_metrics_match_expected_synthetic_values():
    equity = pd.DataFrame(
        {
            "datetime": [
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "2024-01-01T02:00:00Z",
            ],
            "equity": [100.0, 110.0, 99.0],
        }
    )
    metrics = dv.neutral_metrics(equity, periods=1)

    returns = pd.Series([0.0, 0.1, -0.1])
    assert metrics["sharpe"] == pytest.approx(dv.sharpe(returns, periods=1))
    assert metrics["max_drawdown"] == pytest.approx(-0.1)
    assert metrics["total_return"] == pytest.approx(-0.01)


def test_comparator_classifies_signal_trade_pnl_and_metric_mismatches(tmp_path):
    run_dir = _base_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv.ReferenceResult(
        engine="unit",
        status="OK",
        reference_role="reference_signals_only",
        signals=pd.DataFrame(
            {
                "datetime": ["2024-01-01T02:00:00Z"],
                "inst_id": ["BTC-USDT-SWAP"],
                "side": ["sell"],
            }
        ),
        trades=pd.DataFrame(
            {
                "datetime": ["2024-01-01T01:00:00Z"],
                "side": ["buy"],
                "price": [99.0],
                "qty": [2.0],
                "pnl": [1.0],
            }
        ),
        equity_curve=pd.DataFrame(
            {
                "datetime": [
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T01:00:00Z",
                    "2024-01-01T02:00:00Z",
                ],
                "equity": [1000.0, 999.0, 998.0],
            }
        ),
    )

    result = dv.compare_reference(bundle, reference, dv.ValidationTolerances.from_initial_equity(1000.0))

    assert result["summary"]["status"] == "FAIL"
    assert result["summary"]["signal_logic"]["status"] == "FAIL"
    assert result["summary"]["signal_logic"]["actionable_mismatch_count"] > 0
    categories = {
        row["category"]
        for rows in result["mismatches"].values()
        for row in rows
    }
    assert "strategy_logic_mismatch" in categories
    assert "execution_semantics_mismatch" in categories
    assert "pnl_accounting_mismatch" in categories
    assert "metric_formula_mismatch" in categories
    assert any(row["downstream"] for row in result["mismatches"]["metrics"])
    assert result["summary"]["mismatch_counts"]["trades"]["downstream"] >= 1


def test_comparator_classifies_indicator_mismatches(tmp_path):
    run_dir = _base_run(tmp_path)
    project_indicators = pd.DataFrame(
        {
            "ts": [1_704_070_800_000, 1_704_074_400_000],
            "datetime": ["2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
            "strategy": ["ma_crossover", "ma_crossover"],
            "inst_id": ["BTC-USDT-SWAP", "BTC-USDT-SWAP"],
            "close": [101.0, 102.0],
            "fast_value": [100.5, 999.0],
            "slow_value": [float("nan"), 101.0],
            "macd": [float("nan"), float("nan")],
            "macd_signal": [float("nan"), float("nan")],
            "macd_histogram": [float("nan"), float("nan")],
            "warmup_source": ["cold", "cold"],
        }
    )
    reference_indicators = project_indicators.copy()
    reference_indicators.loc[1, "fast_value"] = 101.5
    project_indicators.to_csv(run_dir / "indicator_series.csv", index=False)
    bundle = dv.load_artifact_bundle(run_dir)

    reference = dv.ReferenceResult(
        engine="unit",
        status="OK",
        reference_role="reference_signals_only",
        indicator_series=reference_indicators,
        signals=bundle.signals,
        trades=pd.DataFrame(
            {
                "datetime": ["2024-01-01T01:00:00Z"],
                "side": ["buy"],
                "price": [101.0],
                "qty": [1.0],
                "pnl": [0.0],
            }
        ),
        equity_curve=bundle.equity_curve,
    )

    result = dv.compare_reference(bundle, reference, dv.ValidationTolerances.from_initial_equity(1000.0))

    assert result["summary"]["status"] == "PASS"
    assert result["summary"]["signal_logic"]["status"] == "PASS"
    assert result["summary"]["scopes"]["indicator_values"]["status"] == "ADVISORY_MISMATCH"
    assert result["summary"]["scopes"]["pnl_semantics"]["role"] == "advisory"
    assert result["mismatches"]["indicators"][0]["category"] == "indicator_mismatch"


def test_advisory_trade_pnl_and_metric_mismatches_do_not_fail_signal_gate(tmp_path):
    run_dir = _base_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv.ReferenceResult(
        engine="unit",
        status="OK",
        reference_role="reference_signals_only",
        signals=bundle.signals,
        trades=pd.DataFrame(
            {
                "datetime": ["2024-01-01T01:00:00Z"],
                "side": ["buy"],
                "price": [99.0],
                "qty": [2.0],
                "pnl": [1.0],
            }
        ),
        equity_curve=pd.DataFrame(
            {
                "datetime": [
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T01:00:00Z",
                    "2024-01-01T02:00:00Z",
                ],
                "equity": [1000.0, 999.0, 998.0],
            }
        ),
    )

    result = dv.compare_reference(bundle, reference, dv.ValidationTolerances.from_initial_equity(1000.0))

    assert result["summary"]["status"] == "PASS"
    assert result["summary"]["signal_logic"]["status"] == "PASS"
    assert result["summary"]["signal_logic"]["actionable_mismatch_count"] == 0
    assert result["summary"]["scopes"]["trade_execution"]["status"] == "ADVISORY_MISMATCH"
    assert result["summary"]["scopes"]["pnl_semantics"]["status"] == "ADVISORY_MISMATCH"
    assert result["summary"]["scopes"]["metrics"]["status"] == "ADVISORY_MISMATCH"


def test_external_validation_conclusion_flags_independent_signal_failure():
    conclusion = dv._external_validation_conclusion(
        validation_conclusion={"status": "FAIL", "summary": "failed"},
        source_data_validation={"status": "PASS", "ohlcv_source_validation": "db_parity_pass", "checks": {}},
        portability_gate={"passed": False, "blocked_reason": "no_reference_engine_completed"},
        engine_execution_matrix=[
            {
                "engine": "backtrader",
                "status": "OK",
                "reference_role": "reference_signals_only",
                "gate_role": "independent_reference",
                "portable_gate_eligible": False,
                "trigger_status": "completed",
                "missing_artifacts": [],
            }
        ],
    )

    assert conclusion["external_engines"]["independent_attempted"] == ["backtrader"]
    assert conclusion["external_engines"]["independent_reference"] == []
    assert "backtrader independent reference did not pass signal_logic" in conclusion["blocking_gaps"]


def test_external_validation_conclusion_flags_nautilus_partial_signal_coverage():
    conclusion = dv._external_validation_conclusion(
        validation_conclusion={"status": "ADVISORY_ONLY", "summary": "advisory"},
        source_data_validation={"status": "WARN", "ohlcv_source_validation": "artifact_pass_db_skipped", "checks": {}},
        portability_gate={"passed": False, "blocked_reason": "only_advisory_reference_replay_completed"},
        engine_execution_matrix=[
            {
                "engine": "nautilus",
                "status": "OK",
                "reference_role": "advisory",
                "gate_role": "advisory_only",
                "portable_gate_eligible": False,
                "trigger_status": "completed",
                "missing_artifacts": [],
                "signal_replay_coverage": {
                    "total_signal_rows": 3,
                    "replayable_signal_rows": 1,
                },
            }
        ],
    )

    assert "nautilus signal replay partial coverage: 1/3 signals" in conclusion["blocking_gaps"]
    assert any("all exported/reference signals" in item for item in conclusion["next_required_actions"])


def test_nautilus_replay_signals_reports_mapped_symbol_coverage(tmp_path):
    run_dir = _base_run(tmp_path, "nautilus_signal_coverage")
    signals = pd.DataFrame(
        {
            "datetime": [
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "2024-01-01T02:00:00Z",
                "2024-01-01T03:00:00Z",
            ],
            "inst_id": ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BTC-USDT-SWAP"],
            "strategy": ["unit"] * 4,
            "side": ["buy", "sell", "buy", "hold"],
        }
    )
    bundle = dv.load_artifact_bundle(run_dir)

    replay, coverage = dv._nautilus_replay_signals(
        bundle,
        instruments={"BTC-USDT-SWAP": object(), "ETH-USDT-SWAP": object()},
        signals=signals,
    )

    assert len(replay) == 2
    assert coverage["total_signal_rows"] == 4
    assert coverage["buy_sell_signal_rows"] == 3
    assert coverage["replayable_signal_rows"] == 2
    assert coverage["skipped_non_primary_symbol"] == 1
    assert coverage["skipped_unmapped_symbol"] == 1
    assert coverage["skipped_unsupported_side"] == 1
    assert coverage["mapped_symbols"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert coverage["replayed_symbols"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert coverage["skipped_symbols"] == ["SOL-USDT-SWAP"]


def test_missing_optional_engines_skip_but_nautilus_export_still_runs(tmp_path, monkeypatch):
    run_dir = _base_run(tmp_path)

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: None)
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="skip_test",
    )

    assert summary["status"] == "PASS"
    assert summary["ohlcv_source_validation"] == "artifact_pass_db_skipped"
    assert summary["source_data_validation"]["status"] == "PASS"
    assert summary["source_data_validation"]["checks"]["price_series"]["status"] == "PASS"
    assert summary["source_data_validation"]["checks"]["db_parity"]["status"] == "SKIP"
    assert summary["validation_conclusion"]["status"] == "ADVISORY_ONLY"
    external = summary["external_validation_conclusion"]
    assert external["status"] == "ADVISORY_ONLY"
    assert external["external_engines"]["advisory_only"] == ["nautilus"]
    assert "nautilus full project-strategy/matching-engine parity not implemented" in external["blocking_gaps"]
    assert any("Nautilus catalog/strategy/order/fill mapping" in item for item in external["next_required_actions"])
    assert summary["engines"]["vectorbt"]["status"] == "SKIP"
    assert summary["engines"]["backtrader"]["status"] == "SKIP"
    assert summary["engines"]["nautilus"]["status"] == "OK"
    assert summary["engines"]["vectorbt"]["reference_role"] == "skipped_dependency"
    assert summary["engines"]["backtrader"]["reference_role"] == "skipped_dependency"
    assert summary["engines"]["nautilus"]["reference_role"] == "advisory"
    assert summary["engines"]["nautilus"]["metadata"]["reference_mode"] == "nautilus_artifact_replay_export"
    assert summary["engines"]["nautilus"]["metadata"]["engine_execution"] == "not_run"
    assert summary["engines"]["vectorbt"]["comparison"]["signal_logic"]["status"] == "SKIP"
    assert summary["signal_logic_gate"]["passed"] is False
    assert summary["portable_validation_gate"]["passed"] is False
    assert summary["portable_validation_gate"]["advisory_passing_engines"] == ["nautilus"]
    assert summary["portable_validation_gate"]["blocked_reason"] == "only_advisory_reference_replay_completed"
    assert summary["signal_point_correctness"]["passed"] is False
    assert summary["signal_point_correctness"]["missing_or_failed_target_engines"] == ["vectorbt", "backtrader"]
    assert summary["promotion_gate_evidence"] is False
    matrix = {row["engine"]: row for row in summary["engine_execution_matrix"]}
    assert matrix["vectorbt"]["execution_state"] == "skipped"
    assert matrix["vectorbt"]["trigger_status"] == "missing_dependency"
    assert matrix["vectorbt"]["dependency_available"] is False
    assert matrix["vectorbt"]["gate_role"] == "not_eligible"
    assert any("strict comparison scope" in item for item in matrix["vectorbt"]["trigger_conditions"])
    assert matrix["nautilus"]["execution_state"] == "advisory_run"
    assert matrix["nautilus"]["gate_role"] == "advisory_only"
    assert matrix["nautilus"]["portable_gate_eligible"] is False
    assert any("advisory comparison only" in item for item in matrix["nautilus"]["trigger_conditions"])
    assert summary["engines"]["nautilus"]["comparison"]["metrics"]["status"] == "ADVISORY_MISMATCH"
    assert summary["mismatch_counts"]["metrics"]["actionable"] > 0
    assert (run_dir / "validation" / "skip_test" / "validation_result.json").exists()
    assert (run_dir / "validation" / "skip_test" / "reference_nautilus_export_manifest.json").exists()


def test_ct_val_provenance_missing_fails_source_validation(tmp_path):
    run_dir = _base_run(tmp_path, "missing_ct_val_provenance")
    result_path = run_dir / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload.pop("validation", None)
    _write_json(result_path, payload, add_ct_val=False)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="missing_ct_val_validation",
    )

    ct_val_check = summary["source_data_validation"]["checks"]["ct_val_provenance"]
    assert summary["status"] == "FAIL"
    assert summary["source_data_validation"]["status"] == "FAIL"
    assert summary["validation_conclusion"]["status"] == "FAIL"
    assert ct_val_check["status"] == "FAIL"
    assert "missing from result.validation" in ct_val_check["reason"]
    assert "source_data_validation" in summary
    assert "validation_conclusion" in summary
    assert "portable_validation_gate" in summary


def test_ct_val_provenance_surfaces_run_exchange():
    from backtesting.differential_validation import _validate_ct_val_provenance

    class _Bundle:
        symbols = ["BTC-USDT-SWAP"]
        result = {
            "validation": {
                "ct_val_all_authoritative": True,
                "exchange": "binance",
                "ct_val_sources": {"BTC-USDT-SWAP": {"value": 1.0, "source": "db"}},
            }
        }

    out = _validate_ct_val_provenance(_Bundle())
    assert out["status"] == "PASS"
    assert out["exchange"] == "binance"


def test_signal_point_correctness_matrix_reports_three_engine_rows():
    engine_results = {
        "vectorbt": {
            "status": "OK",
            "reference_role": "reference_signals_only",
            "comparison": {
                "status": "PASS",
                "signal_logic": {"status": "PASS", "actionable_mismatch_count": 0},
                "mismatch_counts": {"trades": {"total": 1}, "pnl": {"total": 2}, "metrics": {"total": 3}},
            },
        },
        "backtrader": {
            "status": "OK",
            "reference_role": "reference_signals_only",
            "comparison": {
                "status": "PASS",
                "signal_logic": {"status": "PASS", "actionable_mismatch_count": 0},
                "mismatch_counts": {},
            },
        },
        "nautilus": {
            "status": "OK",
            "reference_role": "advisory",
            "comparison": {
                "status": "PASS",
                "signal_logic": {"status": "ADVISORY_MISMATCH", "actionable_mismatch_count": 1},
                "mismatch_counts": {"pnl": {"total": 5}},
            },
        },
    }
    matrix = dv._signal_point_correctness_matrix(
        engine_results,
        ["vectorbt", "backtrader", "nautilus"],
        {
            "signals": [
                {
                    "engine": "nautilus",
                    "field": "datetime",
                    "sequence": 0,
                    "project_value": "2024-01-01T00:00:00Z",
                    "reference_value": "2024-01-01T01:00:00Z",
                    "status": "value_mismatch",
                }
            ],
        },
    )

    rows = {row["engine"]: row for row in matrix["rows"]}
    assert matrix["passed"] is False
    assert matrix["missing_or_failed_target_engines"] == ["nautilus"]
    assert rows["vectorbt"]["point_correctness_status"] == "PASS"
    assert rows["backtrader"]["point_correctness_status"] == "PASS"
    assert rows["nautilus"]["point_correctness_status"] == "FAIL"
    assert rows["nautilus"]["mismatch_count"] == 1
    assert rows["nautilus"]["mismatch_examples"][0]["field"] == "datetime"
    assert rows["nautilus"]["portable_gate_eligible"] is False
    assert rows["vectorbt"]["advisory_differences"]["metrics"]["total"] == 3


def test_nautilus_order_fill_parity_passes_signal_replay_orders_and_fills():
    matrix = dv._nautilus_order_fill_parity({
        "nautilus": {
            "status": "OK",
            "metadata": {
                "engine_execution": "signal_replay_run",
                "nautilus_engine_smoke": {
                    "status": "OK",
                    "engine_execution": "signal_replay_run",
                    "signals_available": 2,
                    "signals_replayed": 2,
                    "signal_replay_coverage": {
                        "total_signal_rows": 2,
                        "buy_sell_signal_rows": 2,
                        "replayable_signal_rows": 2,
                        "skipped_unmapped_symbol": 0,
                        "skipped_unsupported_side": 0,
                        "skipped_invalid_timestamp": 0,
                    },
                    "backtest_result": {
                        "strategy_order_attempts": 2,
                        "total_orders": 2,
                        "strategy_fills": 2,
                    },
                },
            },
        }
    })

    assert matrix["status"] == "PASS"
    assert matrix["passed"] is True
    assert matrix["order_attempts"] == 2
    assert matrix["orders_accepted"] == 2
    assert matrix["fills"] == 2
    assert matrix["full_project_strategy_parity_passed"] is False


def test_nautilus_order_fill_parity_fails_partial_replay_or_fill_gap():
    matrix = dv._nautilus_order_fill_parity({
        "nautilus": {
            "status": "OK",
            "metadata": {
                "engine_execution": "signal_replay_run",
                "nautilus_engine_smoke": {
                    "status": "OK",
                    "engine_execution": "signal_replay_run",
                    "signals_available": 3,
                    "signals_replayed": 2,
                    "signal_replay_coverage": {
                        "total_signal_rows": 3,
                        "buy_sell_signal_rows": 3,
                        "replayable_signal_rows": 2,
                        "skipped_unmapped_symbol": 1,
                        "skipped_unsupported_side": 0,
                        "skipped_invalid_timestamp": 0,
                        "skipped_symbols": ["SOL-USDT-SWAP"],
                    },
                    "backtest_result": {
                        "strategy_order_attempts": 2,
                        "total_orders": 2,
                        "strategy_fills": 1,
                    },
                },
            },
        }
    })

    assert matrix["status"] == "FAIL"
    assert matrix["passed"] is False
    assert "signal_replay_coverage" in matrix["failed_checks"]
    assert "fill_coverage" in matrix["failed_checks"]
    assert matrix["signal_replay_coverage"]["skipped_symbols"] == ["SOL-USDT-SWAP"]


def test_nautilus_manifest_records_engine_smoke_metadata(tmp_path, monkeypatch):
    run_dir = _base_run(tmp_path, "nautilus_smoke_metadata")
    smoke = {
        "status": "OK",
        "engine_execution": "smoke_run",
        "reason": "unit smoke",
        "ticks_submitted": 2,
        "data_types": ["QuoteTick", "TradeTick"],
        "signals_available": 3,
        "signals_replayed": 2,
        "signal_replay_coverage": {
            "total_signal_rows": 3,
            "replayable_signal_rows": 2,
            "skipped_symbols": ["SOL-USDT-SWAP"],
        },
        "scope_limit": "engine smoke only",
    }
    monkeypatch.setattr(dv, "_nautilus_engine_smoke", lambda bundle, *args, **kwargs: smoke)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="nautilus_smoke_validation",
    )

    metadata = summary["engines"]["nautilus"]["metadata"]
    assert metadata["engine_execution"] == "smoke_run"
    assert metadata["nautilus_engine_smoke"] == smoke
    assert summary["nautilus_order_fill_parity"]["status"] == "FAIL"
    matrix = {row["engine"]: row for row in summary["engine_execution_matrix"]}
    assert matrix["nautilus"]["signals_replayed"] == 2
    assert matrix["nautilus"]["signal_replay_coverage"]["skipped_symbols"] == ["SOL-USDT-SWAP"]

    manifest = json.loads(
        (run_dir / "validation" / "nautilus_smoke_validation" / "reference_nautilus_export_manifest.json")
        .read_text(encoding="utf-8")
    )
    assert manifest["engine_execution"] == "smoke_run"
    assert manifest["nautilus_engine_smoke"] == smoke
    assert "advisory Strategy" in manifest["limitations"][0]
    assert "queue priority" in manifest["limitations"][1]


def test_real_nautilus_engine_smoke_runs_signal_replay_when_available(tmp_path):
    pytest.importorskip("nautilus_trader")
    run_dir = _base_run(tmp_path, "real_nautilus_signal_replay")
    bundle = dv.load_artifact_bundle(run_dir)

    smoke = REAL_NAUTILUS_ENGINE_SMOKE(bundle)

    assert smoke["status"] == "OK"
    assert smoke["engine_execution"] == "signal_replay_run"
    assert smoke["signals_replayed"] == 1
    assert smoke["signal_replay_coverage"]["replayable_signal_rows"] == 1
    assert smoke["backtest_result"]["strategy_order_attempts"] >= 1
    assert smoke["backtest_result"]["total_orders"] >= 1
    assert smoke["backtest_result"]["strategy_fills"] >= 1
    parity = dv._nautilus_order_fill_parity({
        "nautilus": {"status": "OK", "metadata": {"nautilus_engine_smoke": smoke}}
    })
    assert parity["status"] == "PASS"


def test_real_nautilus_engine_smoke_replays_mapped_daily_winner_symbols(tmp_path):
    pytest.importorskip("nautilus_trader")
    run_dir = _daily_winner_run(tmp_path, "real_nautilus_daily_winner_replay")
    bundle = dv.load_artifact_bundle(run_dir)
    signals, _, _, _ = dv._daily_winner_reference_components(bundle)

    smoke = REAL_NAUTILUS_ENGINE_SMOKE(bundle, signals=signals)

    coverage = smoke["signal_replay_coverage"]
    assert smoke["status"] == "OK"
    assert smoke["engine_execution"] == "signal_replay_run"
    assert coverage["total_signal_rows"] == 6
    assert coverage["replayable_signal_rows"] == 4
    assert coverage["skipped_unmapped_symbol"] == 2
    assert coverage["replayed_symbols"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert coverage["skipped_symbols"] == ["SOL-USDT-SWAP"]
    assert smoke["signals_replayed"] == 4
    assert smoke["backtest_result"]["strategy_order_attempts"] >= 4
    assert smoke["backtest_result"]["strategy_fills"] >= 4


def test_source_data_validation_fails_invalid_ohlcv_artifact(tmp_path):
    run_dir = _base_run(tmp_path, "bad_ohlcv")
    prices = pd.read_csv(run_dir / "price_series.csv")
    prices.loc[1, "high"] = 1.0
    prices.to_csv(run_dir / "price_series.csv", index=False)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="bad_ohlcv_validation",
    )

    price_check = summary["source_data_validation"]["checks"]["price_series"]
    assert summary["status"] == "FAIL"
    assert summary["ohlcv_source_validation"] == "artifact_fail"
    assert summary["source_data_validation"]["status"] == "FAIL"
    assert price_check["status"] == "FAIL"
    assert price_check["failures"]["high_too_low"] == 1
    assert summary["validation_conclusion"]["status"] == "FAIL"


def test_orderbook_market_makers_are_deleted_from_portable_validation_scope():
    deleted = {"as_market_maker", "obi_market_maker"}

    assert deleted.isdisjoint(dv.REFERENCE_VALIDATION_CONTRACTS)
    assert deleted.isdisjoint(_declared_strategy_ids())


def test_db_parity_compares_artifact_to_canonical_candles(tmp_path, monkeypatch):
    from backtesting import data_loader

    run_dir = _base_run(tmp_path, "db_parity")
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    payload["validation"]["exchange"] = "binance"
    (run_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("DIFF_VALIDATION_ENABLE_DB_PARITY", "1")
    monkeypatch.setenv("DIFF_VALIDATION_DB_DSN", "postgresql://unit")
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: True)

    def fake_load_candles(
        inst_id,
        bar="1m",
        data_dir="data/ticks",
        start=None,
        end=None,
        backend="parquet",
        dsn=None,
        include_suspect=False,
        exchange=None,
    ):
        prices = pd.read_csv(run_dir / "price_series.csv")
        assert inst_id == "BTC-USDT-SWAP"
        assert bar == "1H"
        assert backend == "postgres"
        assert exchange == "binance"
        idx = pd.to_datetime(prices["datetime"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
        return pd.DataFrame(
            {
                "open": prices["open"].astype(float).to_numpy(),
                "high": prices["high"].astype(float).to_numpy(),
                "low": prices["low"].astype(float).to_numpy(),
                "close": prices["close"].astype(float).to_numpy(),
                "vol": prices["vol"].astype(float).to_numpy(),
            },
            index=idx,
        )

    monkeypatch.setattr(data_loader, "load_candles", fake_load_candles)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="db_parity_validation",
    )

    db_check = summary["source_data_validation"]["checks"]["db_parity"]
    assert summary["ohlcv_source_validation"] == "db_parity_pass"
    assert db_check["status"] == "PASS"
    assert db_check["canonical_source_primary"] == "binance"
    assert db_check["symbols"][0]["status"] == "PASS"
    assert db_check["symbols"][0]["value_mismatches"] == 0


def test_db_parity_uses_close_only_for_close_flattened_artifacts(tmp_path, monkeypatch):
    from backtesting import data_loader

    run_dir = _base_run(tmp_path, "db_parity_close_only")
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    payload["validation"]["exchange"] = "binance"
    (run_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("DIFF_VALIDATION_ENABLE_DB_PARITY", "1")
    monkeypatch.setenv("DIFF_VALIDATION_DB_DSN", "postgresql://unit")
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: True)

    def fake_load_candles(
        inst_id,
        bar="1m",
        data_dir="data/ticks",
        start=None,
        end=None,
        backend="parquet",
        dsn=None,
        include_suspect=False,
        exchange=None,
    ):
        prices = pd.read_csv(run_dir / "price_series.csv")
        idx = pd.to_datetime(prices["datetime"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
        close = prices["close"].astype(float).to_numpy()
        return pd.DataFrame(
            {
                "open": close - 1.0,
                "high": close + 2.0,
                "low": close - 3.0,
                "close": close,
                "vol": prices["vol"].astype(float).to_numpy() * 1000.0,
            },
            index=idx,
        )

    monkeypatch.setattr(data_loader, "load_candles", fake_load_candles)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="db_parity_close_only_validation",
    )

    db_check = summary["source_data_validation"]["checks"]["db_parity"]
    assert summary["ohlcv_source_validation"] == "db_parity_pass"
    assert db_check["status"] == "PASS"
    assert db_check["symbols"][0]["value_mismatches"] == 0


def test_reference_replay_uses_db_canonical_prices_when_enabled(tmp_path, monkeypatch):
    from backtesting import data_loader

    run_dir = _base_run(tmp_path, "db_reference_prices")

    monkeypatch.setenv("DIFF_VALIDATION_ENABLE_DB_PARITY", "1")
    monkeypatch.setenv("DIFF_VALIDATION_DB_DSN", "postgresql://unit")
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: True)

    def fake_load_candles(
        inst_id,
        bar="1m",
        data_dir="data/ticks",
        start=None,
        end=None,
        backend="parquet",
        dsn=None,
        include_suspect=False,
        exchange=None,
    ):
        prices = pd.read_csv(run_dir / "price_series.csv")
        db_prices = prices.copy()
        db_prices.loc[2, "close"] = 202.0
        idx = pd.to_datetime(db_prices["datetime"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
        return pd.DataFrame(
            {
                "open": db_prices["open"].astype(float).to_numpy(),
                "high": db_prices["high"].astype(float).to_numpy(),
                "low": db_prices["low"].astype(float).to_numpy(),
                "close": db_prices["close"].astype(float).to_numpy(),
                "vol": db_prices["vol"].astype(float).to_numpy(),
            },
            index=idx,
        )

    monkeypatch.setattr(data_loader, "load_candles", fake_load_candles)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="db_reference_prices_validation",
    )

    price_input = summary["engines"]["nautilus"]["metadata"]["price_input"]
    equity = pd.read_csv(run_dir / "validation" / "db_reference_prices_validation" / "reference_nautilus_equity_curve.csv")
    db_check = summary["source_data_validation"]["checks"]["db_parity"]
    assert price_input["source"] == "db_canonical_candles"
    assert db_check["status"] == "FAIL"
    assert db_check["symbols"][0]["value_mismatches"] == 1
    assert equity["equity"].iloc[-1] == pytest.approx(2000.0)


def test_funding_db_parity_compares_artifact_to_funding_rates(tmp_path, monkeypatch):
    from backtesting import data_loader

    run_dir = _base_run(tmp_path, "funding_db_parity", "funding_carry")
    funding_times = ["2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"]
    pd.DataFrame(
        {
            "ts": [1_704_070_800_000, 1_704_074_400_000],
            "datetime": funding_times,
            "inst_id": ["BTC-USDT-SWAP", "BTC-USDT-SWAP"],
            "strategy": ["funding_carry", "funding_carry"],
            "funding_rate": [0.0001, -0.0002],
            "funding_interval_hours": [8.0, 8.0],
            "mark_price": [101.0, 102.0],
            "funding_fee": [0.1, -0.2],
        }
    ).to_csv(run_dir / "funding.csv", index=False)

    monkeypatch.setenv("DIFF_VALIDATION_ENABLE_DB_PARITY", "1")
    monkeypatch.setenv("DIFF_VALIDATION_DB_DSN", "postgresql://unit")
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: True)

    def fake_load_candles(
        inst_id,
        bar="1m",
        data_dir="data/ticks",
        start=None,
        end=None,
        backend="parquet",
        dsn=None,
        include_suspect=False,
        exchange=None,
    ):
        prices = pd.read_csv(run_dir / "price_series.csv")
        idx = pd.to_datetime(prices["datetime"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
        return pd.DataFrame(
            {
                "open": prices["open"].astype(float).to_numpy(),
                "high": prices["high"].astype(float).to_numpy(),
                "low": prices["low"].astype(float).to_numpy(),
                "close": prices["close"].astype(float).to_numpy(),
                "vol": prices["vol"].astype(float).to_numpy(),
            },
            index=idx,
        )

    def fake_load_funding(
        inst_id,
        data_dir="data/ticks",
        start=None,
        end=None,
        backend="parquet",
        dsn=None,
    ):
        assert inst_id == "BTC-USDT-SWAP"
        idx = pd.to_datetime(funding_times, utc=True).tz_convert("UTC").tz_localize(None)
        return pd.DataFrame(
            {
                "rate": [0.0001, -0.0002],
                "realized_rate": [0.0001, -0.0002],
                "funding_interval_hours": [8.0, 8.0],
                "mark_price": [101.0, 102.0],
                "source": ["okx", "okx"],
                "apr": [0.1095, -0.219],
            },
            index=idx,
        )

    monkeypatch.setattr(data_loader, "load_candles", fake_load_candles)
    monkeypatch.setattr(data_loader, "load_funding", fake_load_funding)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="funding_db_parity_validation",
    )

    funding_check = summary["source_data_validation"]["checks"]["funding"]
    funding_db_check = summary["source_data_validation"]["checks"]["funding_db_parity"]
    assert funding_check["status"] == "PASS"
    assert funding_check["rows"] == 2
    assert funding_db_check["status"] == "PASS"
    assert funding_db_check["symbols"][0]["status"] == "PASS"
    assert funding_db_check["symbols"][0]["rate_mismatches"] == 0


def test_funding_cashflow_formula_validates_signed_notional(tmp_path):
    run_dir = _base_run(tmp_path, "funding_formula", "funding_carry")
    pd.DataFrame(
        {
            "ts": [1_704_070_800_000, 1_704_074_400_000],
            "datetime": ["2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
            "inst_id": ["BTC-USDT-SWAP", "BTC-USDT-SWAP"],
            "strategy": ["funding_carry", "funding_carry"],
            "funding_rate": [0.0001, -0.0002],
            "position_notional": [-100.0, -100.0],
            "funding_fee": [0.01, -0.02],
        }
    ).to_csv(run_dir / "funding.csv", index=False)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="funding_formula_validation",
    )

    formula = summary["source_data_validation"]["checks"]["funding_cashflow_formula"]
    assert formula["status"] == "PASS"
    assert formula["basis"] == "position_notional"
    assert formula["mismatch_count"] == 0


def test_funding_cashflow_formula_fails_wrong_sign(tmp_path):
    run_dir = _base_run(tmp_path, "funding_formula_bad", "funding_carry")
    pd.DataFrame(
        {
            "ts": [1_704_070_800_000],
            "datetime": ["2024-01-01T01:00:00Z"],
            "inst_id": ["BTC-USDT-SWAP"],
            "strategy": ["funding_carry"],
            "funding_rate": [0.0001],
            "position_size": [-0.25],
            "ct_val": [0.01],
            "mark_price": [40000.0],
            "funding_fee": [-0.01],
        }
    ).to_csv(run_dir / "funding.csv", index=False)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="funding_formula_bad_validation",
    )

    formula = summary["source_data_validation"]["checks"]["funding_cashflow_formula"]
    assert summary["status"] == "FAIL"
    assert formula["status"] == "FAIL"
    assert formula["basis"] == "position_size_ct_val_mark_price"
    assert formula["mismatch_count"] == 1


def test_external_observations_db_parity_compares_artifact_to_store(tmp_path, monkeypatch):
    from backtesting import data_loader

    run_dir = _base_run(tmp_path, "external_db_parity", "fear_greed_sentiment")
    observed = ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]
    pd.DataFrame(
        {
            "dataset_id": ["fear_greed_btc", "fear_greed_btc"],
            "observed_at": observed,
            "published_at": observed,
            "value_num": [22.0, 55.0],
            "value_text": ["Extreme Fear", "Neutral"],
            "quality_status": ["ok", "ok"],
        }
    ).to_csv(run_dir / "external_observations.csv", index=False)

    monkeypatch.setenv("DIFF_VALIDATION_ENABLE_DB_PARITY", "1")
    monkeypatch.setenv("DIFF_VALIDATION_DB_DSN", "postgresql://unit")
    monkeypatch.setattr(data_loader, "_dsn_reachable", lambda dsn: True)

    def fake_load_candles(
        inst_id,
        bar="1m",
        data_dir="data/ticks",
        start=None,
        end=None,
        backend="parquet",
        dsn=None,
        include_suspect=False,
        exchange=None,
    ):
        prices = pd.read_csv(run_dir / "price_series.csv")
        idx = pd.to_datetime(prices["datetime"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
        return pd.DataFrame(
            {
                "open": prices["open"].astype(float).to_numpy(),
                "high": prices["high"].astype(float).to_numpy(),
                "low": prices["low"].astype(float).to_numpy(),
                "close": prices["close"].astype(float).to_numpy(),
                "vol": prices["vol"].astype(float).to_numpy(),
            },
            index=idx,
        )

    def fake_load_external_observations(
        dataset_id,
        data_dir="data/external",
        start=None,
        end=None,
        backend="postgres",
        dsn=None,
        lookback_seconds=0,
    ):
        assert dataset_id == "fear_greed_btc"
        return pd.DataFrame(
            {
                "dataset_id": ["fear_greed_btc", "fear_greed_btc"],
                "observed_at": pd.to_datetime(observed, utc=True),
                "published_at": pd.to_datetime(observed, utc=True),
                "value_num": [22.0, 55.0],
                "value_text": ["Extreme Fear", "Neutral"],
                "quality_status": ["ok", "ok"],
            }
        )

    monkeypatch.setattr(data_loader, "load_candles", fake_load_candles)
    monkeypatch.setattr(data_loader, "load_external_observations", fake_load_external_observations)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="external_db_parity_validation",
    )

    external_check = summary["source_data_validation"]["checks"]["external_observations"]
    external_db_check = summary["source_data_validation"]["checks"]["external_observations_db_parity"]
    assert external_check["status"] == "PASS"
    assert external_check["dataset_id"] == "fear_greed_btc"
    assert external_db_check["status"] == "PASS"
    assert external_db_check["dataset_id"] == "fear_greed_btc"
    assert external_db_check["value_mismatches"] == 0
    assert external_db_check["compared_fields"] == ["value_num", "value_text"]


def test_external_observations_artifact_fails_wrong_dataset(tmp_path):
    run_dir = _base_run(tmp_path, "external_wrong_dataset", "fear_greed_sentiment")
    pd.DataFrame(
        {
            "dataset_id": ["other_dataset"],
            "observed_at": ["2024-01-01T00:00:00Z"],
            "value_num": [22.0],
        }
    ).to_csv(run_dir / "external_observations.csv", index=False)

    summary = dv.run_differential_validation(
        run_dir,
        engines=["nautilus"],
        validation_id="external_wrong_dataset_validation",
    )

    external_check = summary["source_data_validation"]["checks"]["external_observations"]
    assert summary["status"] == "FAIL"
    assert external_check["status"] == "FAIL"
    assert external_check["dataset_mismatches"] == 1


def test_advisory_adapter_result_is_not_portable_gate_pass(tmp_path, monkeypatch):
    run_dir = _base_run(tmp_path, "pairs_reference_contract", "pairs_trading")

    def fake_replay(self, bundle):
        return dv.ReferenceResult(
            engine=self.engine,
            status="OK",
            reason="fake advisory replay",
            reference_role="advisory",
            signals=dv._artifact_reference_signals(bundle),
            equity_curve=bundle.equity_curve,
            metadata={"reference_mode": "artifact_signal_replay"},
        )

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(dv.VectorBTReferenceAdapter, "_run_available", fake_replay)
    monkeypatch.setattr(dv.BacktraderReferenceAdapter, "_run_available", fake_replay)
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader"],
        validation_id="pairs_contract",
    )

    assert summary["status"] == "PASS"
    assert summary["reference_validation_contract"]["strategy"] == "pairs_trading"
    assert summary["portable_validation_gate"]["passed"] is False
    assert summary["portable_validation_gate"]["advisory_passing_engines"] == ["vectorbt", "backtrader"]
    assert summary["portable_validation_gate"]["blocked_reason"] == "only_advisory_reference_replay_completed"
    assert summary["engines"]["vectorbt"]["reference_role"] == "advisory"
    assert summary["engines"]["vectorbt"]["comparison"]["signal_logic"]["role"] == "advisory"


def test_pairs_trading_reference_recomputes_kalman_ou_signal_gate(tmp_path, monkeypatch):
    run_dir = _pairs_trading_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._pairs_trading_reference_result(bundle, "vectorbt")

    assert reference.reference_role == "reference_signals_only"
    assert reference.metadata["reference_mode"] == "pairs_trading_kalman_ou_signal_recompute"
    assert set(reference.signals["side"]).issubset({"buy", "sell"})
    assert not reference.signals.empty
    pd.testing.assert_frame_equal(
        dv._normalize_signals(bundle.signals),
        dv._normalize_signals(reference.signals),
    )

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: object())
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="pairs_reference_contract",
    )

    assert summary["status"] == "PASS"
    assert summary["validation_conclusion"]["status"] == "REFERENCE_PASS"
    assert summary["portable_validation_gate"]["passed"] is True
    assert summary["portable_validation_gate"]["independent_passing_engines"] == ["vectorbt", "backtrader"]
    assert summary["signal_logic_gate"]["passed"] is True
    assert summary["engines"]["vectorbt"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["vectorbt"]["metadata"]["reference_mode"] == "pairs_trading_kalman_ou_signal_recompute"
    assert summary["engines"]["nautilus"]["reference_role"] == "advisory"


def test_fear_greed_reference_recomputes_external_feature_signal_gate(tmp_path, monkeypatch):
    run_dir = _fear_greed_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._external_feature_reference_result(bundle, "vectorbt")

    assert reference.reference_role == "reference_signals_only"
    assert reference.metadata["reference_mode"] == "fear_greed_sentiment_external_feature_signal_recompute"
    pd.testing.assert_frame_equal(
        dv._normalize_signals(bundle.signals),
        dv._normalize_signals(reference.signals),
    )

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: object())
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="fear_greed_reference_contract",
    )

    assert summary["status"] == "PASS"
    assert summary["validation_conclusion"]["status"] == "REFERENCE_PASS"
    assert summary["portable_validation_gate"]["passed"] is True
    assert summary["portable_validation_gate"]["independent_passing_engines"] == ["vectorbt", "backtrader"]
    assert summary["engines"]["vectorbt"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["backtrader"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["nautilus"]["reference_role"] == "advisory"


def test_cme_gap_reference_recomputes_external_feature_signal_gate(tmp_path, monkeypatch):
    run_dir = _cme_gap_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._external_feature_reference_result(bundle, "vectorbt")

    assert reference.reference_role == "reference_signals_only"
    assert reference.metadata["reference_mode"] == "cme_gap_fill_external_feature_signal_recompute"
    pd.testing.assert_frame_equal(
        dv._normalize_signals(bundle.signals),
        dv._normalize_signals(reference.signals),
    )

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: object())
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="cme_gap_reference_contract",
    )

    assert summary["status"] == "PASS"
    assert summary["validation_conclusion"]["status"] == "REFERENCE_PASS"
    assert summary["portable_validation_gate"]["passed"] is True
    assert summary["portable_validation_gate"]["independent_passing_engines"] == ["vectorbt", "backtrader"]
    assert summary["engines"]["vectorbt"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["backtrader"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["nautilus"]["reference_role"] == "advisory"


def test_funding_carry_reference_recomputes_rate_signal_gate(tmp_path, monkeypatch):
    run_dir = _funding_carry_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._funding_carry_reference_result(bundle, "vectorbt")

    assert reference.reference_role == "reference_signals_only"
    assert reference.metadata["reference_mode"] == "funding_carry_rate_signal_recompute"
    pd.testing.assert_frame_equal(
        dv._normalize_signals(bundle.signals),
        dv._normalize_signals(reference.signals),
    )

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: object())
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="funding_reference_contract",
    )

    assert summary["status"] == "PASS"
    assert summary["validation_conclusion"]["status"] == "REFERENCE_PASS"
    assert summary["portable_validation_gate"]["passed"] is True
    assert summary["portable_validation_gate"]["independent_passing_engines"] == ["vectorbt", "backtrader"]
    assert summary["signal_logic_gate"]["passed"] is True
    assert summary["engines"]["vectorbt"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["backtrader"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["nautilus"]["reference_role"] == "advisory"
    funding_check = summary["source_data_validation"]["checks"]["funding"]
    assert funding_check["status"] == "PASS"
    assert funding_check["artifact_role"] == "funding_rates"


def test_daily_winner_reference_recomputes_prior_day_winner_signal_gate(tmp_path, monkeypatch):
    run_dir = _daily_winner_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._daily_winner_reference_result(bundle, "vectorbt")

    assert reference.reference_role == "reference_signals_only"
    assert list(reference.signals[reference.signals["side"] == "buy"]["inst_id"]) == [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
        "SOL-USDT-SWAP",
    ]
    pd.testing.assert_frame_equal(
        dv._normalize_signals(bundle.signals),
        dv._normalize_signals(reference.signals),
    )

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: object())
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="daily_reference_contract",
    )

    assert summary["status"] == "PASS"
    assert summary["validation_conclusion"]["status"] == "REFERENCE_PASS"
    assert summary["portable_validation_gate"]["passed"] is True
    assert summary["portable_validation_gate"]["independent_passing_engines"] == ["vectorbt", "backtrader"]
    assert summary["signal_logic_gate"]["passed"] is True
    assert summary["engines"]["vectorbt"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["vectorbt"]["metadata"]["reference_mode"] == "daily_winner_prior_day_recompute"
    assert summary["engines"]["nautilus"]["reference_role"] == "advisory"


def test_ohlcv_rotation_reference_recomputes_target_weight_signal_gate(tmp_path, monkeypatch):
    run_dir = _ohlcv_rotation_run(tmp_path)
    bundle = dv.load_artifact_bundle(run_dir)
    reference = dv._ohlcv_rotation_reference_result(bundle, "vectorbt")

    assert reference.reference_role == "reference_signals_only"
    assert not reference.signals.empty
    pd.testing.assert_frame_equal(
        dv._normalize_signals(bundle.signals),
        dv._normalize_signals(reference.signals),
    )

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: object())
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="rotation_reference_contract",
    )

    assert summary["status"] == "PASS"
    assert summary["validation_conclusion"]["status"] == "REFERENCE_PASS"
    assert summary["portable_validation_gate"]["passed"] is True
    assert summary["portable_validation_gate"]["independent_passing_engines"] == ["vectorbt", "backtrader"]
    assert summary["signal_logic_gate"]["passed"] is True
    assert summary["engines"]["vectorbt"]["reference_role"] == "reference_signals_only"
    assert summary["engines"]["vectorbt"]["metadata"]["reference_mode"] == "ohlcv_rotation_target_weight_recompute"
    assert summary["engines"]["nautilus"]["reference_role"] == "advisory"


def test_backtrader_macd_reference_uses_project_compatible_ema_path(tmp_path):
    bt = pytest.importorskip("backtrader")
    run_dir = _base_run(tmp_path, "backtrader_macd_reference", "macd_crossover")
    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=160, freq="h")
    closes = [100.0 + 8.0 * math.sin(i / 4.0) + 0.03 * i for i in range(len(timestamps))]
    prices = pd.DataFrame(
        {
            "ts": [int(ts.timestamp() * 1000) for ts in timestamps],
            "datetime": [ts.isoformat().replace("+00:00", "Z") for ts in timestamps],
            "inst_id": ["BTC-USDT-SWAP"] * len(timestamps),
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "vol": [10.0] * len(timestamps),
        }
    )
    prices.to_csv(run_dir / "price_series.csv", index=False)
    pd.DataFrame(columns=["datetime", "strategy", "inst_id", "side", "size_after"]).to_csv(
        run_dir / "trades.csv",
        index=False,
    )
    bundle = dv.load_artifact_bundle(run_dir)

    expected = dv._technical_reference_signals(bundle, "macd_crossover")
    signals, _, equity = dv._run_backtrader_technical_reference(bt, bundle, "macd_crossover")

    assert set(expected["side"]) == {"buy", "sell"}
    assert len(equity) == len(prices)
    pd.testing.assert_frame_equal(
        dv._normalize_signals(signals),
        dv._normalize_signals(expected),
    )


def test_macd_reference_indicator_series_keeps_ema_and_macd_columns_distinct(tmp_path):
    run_dir = _base_run(tmp_path, "macd_indicator_schema", "macd_crossover")
    bundle = dv.load_artifact_bundle(run_dir)

    indicators = dv._technical_reference_indicator_series(bundle, "macd_crossover")

    assert indicators["fast_value"].iloc[0] == pytest.approx(100.0)
    assert indicators["slow_value"].iloc[0] == pytest.approx(100.0)
    assert indicators["macd"].iloc[0] == pytest.approx(0.0)
    assert indicators["macd_signal"].iloc[0] == pytest.approx(0.0)


def test_strategy_fixture_listing_includes_materializable_sweep_finalists(tmp_path):
    _base_run(tmp_path, "good_macd_fixture", "macd_crossover")

    stale_dir = tmp_path / "stale_macd_fixture"
    stale_dir.mkdir()
    _write_json(
        stale_dir / "result.json",
        {
            "run_id": "stale_macd_fixture",
            "strategies": ["macd_crossover"],
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1D",
        },
    )

    sweep_dir = tmp_path / "parameter_sweeps"
    sweep_dir.mkdir()
    _write_json(
        sweep_dir / "ui_sweep_macd_crossover_missing.json",
        {
            "sweep_id": "ui_sweep_macd_crossover_missing",
            "strategy": "macd_crossover",
            "symbols": ["BTC-USDT-SWAP"],
            "finalist_results": [
                {
                    "status": "ok",
                    "run_id": "ui_sweep_macd_crossover_missing_rank_001",
                    "artifact_dir": str(tmp_path / "ui_sweep_macd_crossover_missing_rank_001"),
                    "params": {"fast_span": 12, "slow_span": 24, "signal_span": 9},
                }
            ],
        },
    )

    fixtures = dv.list_strategy_validation_fixtures(tmp_path, "macd_crossover")

    by_id = {row["run_id"]: row for row in fixtures}
    assert "good_macd_fixture" in by_id
    assert "stale_macd_fixture" not in by_id
    missing = by_id["ui_sweep_macd_crossover_missing_rank_001"]
    assert missing["fixture_role"] == "parameter_sweep_finalist"
    assert missing["validation_ready"] is False
    assert missing["materialize_ready"] is True
    assert missing["missing_artifacts"] == ["result.json", "price_series.csv", "signals.csv"]


def test_strategy_fixture_listing_uses_lightweight_metadata(tmp_path, monkeypatch):
    _base_run(tmp_path, "good_ma_fixture", "ma_crossover")

    def fail_read_csv(*args, **kwargs):
        raise AssertionError("fixture listing should not load full CSV artifacts")

    monkeypatch.setattr(dv.pd, "read_csv", fail_read_csv)

    fixtures = dv.list_strategy_validation_fixtures(tmp_path, "ma_crossover")

    assert [row["run_id"] for row in fixtures] == ["good_ma_fixture"]


def test_strategy_fixture_resolve_materializes_missing_sweep_finalist(tmp_path, monkeypatch):
    sweep_dir = tmp_path / "parameter_sweeps"
    sweep_dir.mkdir()
    run_id = "ui_sweep_macd_crossover_missing_rank_001"
    _write_json(
        sweep_dir / "ui_sweep_macd_crossover_missing.json",
        {
            "sweep_id": "ui_sweep_macd_crossover_missing",
            "strategy": "macd_crossover",
            "symbols": ["BTC-USDT-SWAP"],
            "finalist_results": [
                {
                    "status": "ok",
                    "run_id": run_id,
                    "artifact_dir": str(tmp_path / run_id),
                    "params": {"fast_span": 12, "slow_span": 24, "signal_span": 9},
                }
            ],
        },
    )

    calls = []

    def fake_materialize(results_dir, strategy, fixture_run_id):
        calls.append((results_dir, strategy, fixture_run_id))
        return _base_run(tmp_path, fixture_run_id, strategy)

    monkeypatch.setattr(dv, "_materialize_sweep_fixture", fake_materialize)

    resolved = dv._resolve_strategy_fixture(tmp_path, "macd_crossover", run_id)

    assert resolved.name == run_id
    assert calls == [(tmp_path, "macd_crossover", run_id)]


def test_strategy_validation_writes_strategy_scoped_evidence(tmp_path, monkeypatch):
    _base_run(tmp_path, "strategy_fixture", "ma_crossover")
    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: None)

    summary = dv.run_strategy_differential_validation(
        tmp_path,
        strategy="ma_crossover",
        fixture_run_id="strategy_fixture",
        engines=["vectorbt"],
        validation_id="strategy_validation",
    )

    evidence = tmp_path / "strategy_validation" / "ma_crossover" / "strategy_validation" / "validation_result.json"
    assert summary["validation_scope"] == "strategy"
    assert summary["strategy"] == "ma_crossover"
    assert summary["fixture_run_id"] == "strategy_fixture"
    assert summary["source_run_result_mutated"] is False
    assert evidence.exists()
    assert not (tmp_path / "strategy_fixture" / "validation" / "strategy_validation").exists()
    listed = dv.list_strategy_validation_results(tmp_path, "ma_crossover")
    assert listed[0]["validation_id"] == "strategy_validation"


def test_materialized_sweep_fixture_metadata_is_exposed(tmp_path, monkeypatch):
    run_dir = _base_run(tmp_path, "rebuilt_macd_fixture", "macd_crossover")
    result_path = run_dir / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["validation"] = {
        "parameter_sweep": {
            "sweep_id": "unit_sweep",
            "materialized_from_sweep_summary": True,
        }
    }
    _write_json(result_path, payload)
    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: None)

    fixture_row = dv._strategy_fixture_row(run_dir, "macd_crossover")
    summary = dv.run_strategy_differential_validation(
        tmp_path,
        strategy="macd_crossover",
        fixture_run_id="rebuilt_macd_fixture",
        engines=["vectorbt"],
        validation_id="rebuilt_fixture_scope",
    )
    listed = dv.list_strategy_validation_results(tmp_path, "macd_crossover")

    assert fixture_row["materialized_from_sweep_summary"] is True
    assert summary["materialized_from_sweep_summary"] is True
    assert listed[0]["materialized_from_sweep_summary"] is True
    assert listed[0]["admissibility"] == "advisory_only"
    assert listed[0]["signal_logic_gate"] == summary["signal_logic_gate"]


def test_backtest_api_triggers_and_reads_differential_validation(tmp_path, monkeypatch):
    _base_run(tmp_path, "api_run")
    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: None)

    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.post(
        "/api/backtest/api_run/differential-validation/run",
        json={"engines": ["vectorbt"], "validation_id": "api_validation"},
    )
    assert response.status_code == 200

    status = client.get(f"/api/backtest/differential-validation/status/{response.json()['job_id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "done"

    listing = client.get("/api/backtest/api_run/differential-validation")
    assert listing.status_code == 200
    assert listing.json()[0]["validation_id"] == "api_validation"

    detail = client.get("/api/backtest/api_run/differential-validation/api_validation")
    assert detail.status_code == 200
    assert detail.json()["ohlcv_source_validation"] == "artifact_pass_db_skipped"


def test_backtest_api_triggers_db_only_differential_validation(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_run = _base_run(source_root, "db_only_api_run")
    artifacts = {
        "result": json.loads((source_run / "result.json").read_text(encoding="utf-8")),
        "config": json.loads((source_run / "config.json").read_text(encoding="utf-8")),
    }
    for artifact_type, filename in {
        "price_series": "price_series.csv",
        "indicator_series": "indicator_series.csv",
        "signals": "signals.csv",
        "trades": "trades.csv",
        "fills": "fills.csv",
        "equity": "equity_curve.csv",
    }.items():
        try:
            artifacts[artifact_type] = pd.read_csv(source_run / filename).to_dict("records")
        except pd.errors.EmptyDataError:
            artifacts[artifact_type] = []

    class FakeConn:
        async def fetch(self, query, run_id):
            assert run_id == "db_only_api_run"
            return [
                {"artifact_type": artifact_type, "payload": payload}
                for artifact_type, payload in artifacts.items()
            ]

        async def close(self):
            return None

    async def fake_connect(dsn):
        assert dsn == "postgresql://unit/db"
        return FakeConn()

    monkeypatch.setenv("DATABASE_URL", "postgresql://unit/db")
    monkeypatch.setitem(sys.modules, "asyncpg", types.SimpleNamespace(connect=fake_connect))
    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: None)

    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path / "results"), prefix="/api/backtest")
    client = TestClient(app)

    response = client.post(
        "/api/backtest/db_only_api_run/differential-validation/run",
        json={"engines": ["vectorbt"], "validation_id": "db_only_validation"},
    )

    assert response.status_code == 200
    status = client.get(f"/api/backtest/differential-validation/status/{response.json()['job_id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "done"

    detail = client.get("/api/backtest/db_only_api_run/differential-validation/db_only_validation")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == "db_only_api_run"
    assert not (tmp_path / "results" / "db_only_api_run" / "result.json").exists()


def test_backtest_api_exposes_reference_validation_contracts(tmp_path):
    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    listing = client.get("/api/backtest/strategy-validation/contracts")
    assert listing.status_code == 200
    strategies = {row["strategy"] for row in listing.json()}
    assert "ma_crossover" in strategies
    assert "daily_winner" in strategies

    detail = client.get("/api/backtest/strategy-validation/contracts?strategy=daily_winner")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["strategy"] == "daily_winner"
    assert payload["engines"]["vectorbt"]["status"] == "implemented"
    assert payload["engines"]["vectorbt"]["role"] == "reference_signals_only"
    assert payload["engines"]["backtrader"]["status"] == "implemented"
    assert payload["engines"]["backtrader"]["role"] == "reference_signals_only"
    assert payload["engines"]["nautilus"]["status"] == "implemented"
    assert payload["engines"]["nautilus"]["role"] == "advisory"

    rotation = client.get("/api/backtest/strategy-validation/contracts?strategy=ohlcv_rotation")
    assert rotation.status_code == 200
    rotation_payload = rotation.json()
    assert rotation_payload["engines"]["vectorbt"]["role"] == "reference_signals_only"
    assert rotation_payload["engines"]["backtrader"]["role"] == "reference_signals_only"
    assert rotation_payload["engines"]["nautilus"]["role"] == "advisory"


def test_backtest_api_triggers_strategy_validation(tmp_path, monkeypatch):
    _base_run(tmp_path, "api_strategy_fixture", "ma_crossover")
    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: None)

    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.post(
        "/api/backtest/strategy-validation/run",
        json={
            "strategy": "ma_crossover",
            "fixture_run_id": "api_strategy_fixture",
            "engines": ["vectorbt"],
            "validation_id": "api_strategy_validation",
        },
    )
    assert response.status_code == 200

    status = client.get(f"/api/backtest/differential-validation/status/{response.json()['job_id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "done"
    assert status.json()["strategy"] == "ma_crossover"

    listing = client.get("/api/backtest/strategy-validation?strategy=ma_crossover")
    assert listing.status_code == 200
    assert listing.json()[0]["validation_id"] == "api_strategy_validation"

    detail = client.get("/api/backtest/strategy-validation/ma_crossover/api_strategy_validation")
    assert detail.status_code == 200
    assert detail.json()["validation_scope"] == "strategy"
