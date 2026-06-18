from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backtesting.replay import run_replay_backtest


def _write_ma_crossover_fixture(tmp_path: Path) -> Path:
    data_dir = tmp_path / "ticks"
    inst_dir = data_dir / "BTC_USDT_SWAP"
    inst_dir.mkdir(parents=True)
    prices = [10_000, 9_000, 8_000, 20_000, 19_000, 50_000, 49_000, 48_000, 47_000]
    ts = pd.date_range("2024-01-01", periods=len(prices), freq="1h", tz="UTC")
    pd.DataFrame(
        {
            "ts": ts,
            "open": prices,
            "high": [price * 1.01 for price in prices],
            "low": [price * 0.99 for price in prices],
            "close": prices,
            "vol": [100_000] * len(prices),
        }
    ).to_parquet(inst_dir / "candles_1H.parquet", index=False)
    return data_dir


def _cfg_for_exchange(base_cfg, exchange: str):
    cfg = base_cfg.model_copy(deep=True)
    cfg.storage = cfg.storage.model_copy(update={"primary_exchange": exchange, "candle_backend": "parquet"})
    cfg.system.symbols = ["BTC-USDT-SWAP"]
    cfg.system.spot_symbols = []
    cfg.strategies.ma_crossover.symbols = ["BTC-USDT-SWAP"]
    cfg.strategies.ma_crossover.fast_window = 2
    cfg.strategies.ma_crossover.slow_window = 3
    cfg.risk.max_order_notional_usd = 10_000.0
    cfg.risk.max_pos_pct_equity = 1.0
    cfg.backtest.order_latency_ms = 0
    cfg.backtest.cancel_latency_ms = 0
    cfg.backtest.queue_fill_fraction = 1.0
    return cfg


def _spec(ct_val: float, lot_size: float) -> dict:
    return {
        "BTC-USDT-SWAP": {
            "ctVal": ct_val,
            "minSz": lot_size,
            "lotSz": lot_size,
            "tickSz": 0.1,
            "tdMode": "cross",
        }
    }


def test_swap_ct_val_cancels_under_notional_sizing(minimal_cfg, tmp_path):
    data_dir = _write_ma_crossover_fixture(tmp_path)
    okx = run_replay_backtest(
        strategy_names=["ma_crossover"],
        cfg=_cfg_for_exchange(minimal_cfg, "okx"),
        data_dir=str(data_dir),
        bar="1H",
        instrument_specs=_spec(ct_val=0.01, lot_size=0.01),
    )
    binance = run_replay_backtest(
        strategy_names=["ma_crossover"],
        cfg=_cfg_for_exchange(minimal_cfg, "binance"),
        data_dir=str(data_dir),
        bar="1H",
        instrument_specs=_spec(ct_val=1.0, lot_size=0.001),
    )

    assert len(okx.fill_log) == len(binance.fill_log) >= 2
    assert okx.metrics["total_return"] == pytest.approx(binance.metrics["total_return"], abs=1e-6)
    assert okx.metrics["sharpe"] == pytest.approx(binance.metrics["sharpe"], abs=1e-6)
    assert okx.validation["exchange"] == "okx"
    assert binance.validation["exchange"] == "binance"
