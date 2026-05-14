from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtesting"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backtesting.daily_winner_backtest import DailyWinnerParams, run_daily_winner_backtest
from backtesting.data_loader import load_candles
from okx_quant.api.routes_backtest import RunBacktestRequest, _build_daily_winner_result_json


def _daily_df(opens: list[float], closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(opens), freq="1D")
    high = np.maximum(opens, closes)
    low = np.minimum(opens, closes)
    return pd.DataFrame(
        {
            "open": opens,
            "high": high,
            "low": low,
            "close": closes,
            "vol": np.full(len(opens), 100.0),
        },
        index=idx,
    )


def test_daily_winner_uses_yesterday_winner_for_today_trade() -> None:
    dfs = {
        "BTC-USDT-SWAP": _daily_df([100, 100, 100, 100], [110, 101, 100, 100]),
        "ETH-USDT-SWAP": _daily_df([100, 100, 100, 100], [105, 120, 103, 100]),
        "SOL-USDT-SWAP": _daily_df([100, 100, 100, 100], [101, 100, 130, 100]),
    }
    params = DailyWinnerParams(
        universe=list(dfs),
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    result = run_daily_winner_backtest(dfs, params)

    assert list(result.trades["inst_id"]) == [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
        "SOL-USDT-SWAP",
    ]
    assert result.metrics["number_of_trades"] == 3
    assert result.metrics["expected_trade_days"] == 3
    assert result.metrics["skipped_trade_days"] == 0
    assert result.metrics["daily_trade_coverage_pct"] == 1.0


def test_daily_winner_does_not_use_today_return_to_pick_winner() -> None:
    dfs = {
        "BTC-USDT-SWAP": _daily_df([100, 100], [110, 100]),
        "ETH-USDT-SWAP": _daily_df([100, 100], [101, 150]),
    }
    params = DailyWinnerParams(universe=list(dfs), fee_bps=0.0, slippage_bps=0.0)

    result = run_daily_winner_backtest(dfs, params)

    assert result.trades.iloc[0]["inst_id"] == "BTC-USDT-SWAP"
    assert result.trades.iloc[0]["gross_return"] == 0.0


def test_daily_winner_applies_round_trip_cost() -> None:
    dfs = {
        "BTC-USDT-SWAP": _daily_df([100, 100], [110, 101]),
        "ETH-USDT-SWAP": _daily_df([100, 100], [101, 100]),
    }
    params = DailyWinnerParams(universe=list(dfs), fee_bps=2.0, slippage_bps=3.0)

    result = run_daily_winner_backtest(dfs, params)

    trade = result.trades.iloc[0]
    assert trade["gross_return"] == pytest.approx(0.01)
    assert trade["cost_rate"] == pytest.approx(0.001)
    assert trade["net_return"] == pytest.approx(0.009)


def test_daily_winner_api_payload_preserves_frontend_schema() -> None:
    dfs = {
        "BTC-USDT-SWAP": _daily_df([100, 100, 100], [110, 101, 100]),
        "ETH-USDT-SWAP": _daily_df([100, 100, 100], [101, 105, 106]),
    }
    backtest_result = run_daily_winner_backtest(
        dfs,
        DailyWinnerParams(universe=list(dfs), fee_bps=0.0, slippage_bps=0.0),
    )
    backtest_result.metrics.pop("profit_factor")
    req = RunBacktestRequest(
        strategy="daily_winner",
        universe=list(dfs),
        start="2024-01-01",
        end="2024-01-03",
    )

    payload = _build_daily_winner_result_json(
        run_id="schema_daily_winner",
        req=req,
        result=backtest_result,
        loaded_symbols=list(dfs),
        skipped_symbols=[],
    )

    assert {"run_id", "created_at", "strategies", "symbols", "bar", "metrics", "artifacts"} <= set(payload)
    assert {"datetime", "return", "equity", "drawdown"} <= set(payload["equity"][0])
    assert payload["equity"][0]["return"] == 0.0
    assert "profit_factor" in payload["metrics"]
    assert payload["metrics"]["profit_factor"] == 0.0


def test_load_candles_derives_1d_from_1m_parquet(tmp_path) -> None:
    inst_dir = tmp_path / "BTC_USDT_SWAP"
    inst_dir.mkdir()
    idx = pd.date_range("2024-01-01", periods=2 * 24 * 60, freq="1min")
    candles = pd.DataFrame(
        {
            "ts": idx,
            "open": np.arange(len(idx), dtype=float) + 100.0,
            "high": np.arange(len(idx), dtype=float) + 101.0,
            "low": np.arange(len(idx), dtype=float) + 99.0,
            "close": np.arange(len(idx), dtype=float) + 100.5,
            "vol": np.ones(len(idx)),
        }
    )
    pq.write_table(pa.Table.from_pandas(candles, preserve_index=False), inst_dir / "candles_1m.parquet")

    loaded = load_candles("BTC-USDT-SWAP", bar="1D", data_dir=str(tmp_path))

    assert len(loaded) == 2
    assert loaded.iloc[0]["open"] == 100.0
    assert loaded.iloc[0]["high"] == 1540.0
    assert loaded.iloc[0]["low"] == 99.0
    assert loaded.iloc[0]["close"] == 1539.5
    assert loaded.iloc[0]["vol"] == 1440.0
