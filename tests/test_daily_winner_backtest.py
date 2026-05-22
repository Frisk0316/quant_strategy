from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtesting"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backtesting.daily_winner_backtest import DailyWinnerParams, run_daily_winner_backtest
from backtesting.data_loader import _has_low_bar_coverage, load_candles
from okx_quant.api.routes_backtest import (
    RunBacktestRequest,
    _attach_daily_winner_validation,
    _build_daily_winner_result_json,
    _normalize_daily_winner_payload,
    make_backtest_router,
)


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
    assert result.metrics["sharpe"] < 100


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
    assert payload["metrics"]["fill_count"] == 4
    assert payload["metrics"]["total_fees"] == 0.0
    assert len(payload["round_trips"]) == 2
    assert len(payload["trades"]) == 4
    assert [row["side"] for row in payload["trades"][:2]] == ["buy", "sell"]
    assert payload["trades"][0]["notional"] > 0
    assert payload["trades"][0]["pnl_usd"] is None
    assert payload["trades"][1]["pnl_usd"] is not None
    assert payload["trades"][0]["datetime"].startswith("2024-01-02")
    assert payload["validation"]["validation_mode"] == "none"
    assert "walk_forward" not in payload
    assert "cpcv" not in payload


def test_daily_winner_api_payload_models_synthetic_execution_costs() -> None:
    dfs = {
        "BTC-USDT-SWAP": _daily_df([100, 100], [110, 101]),
        "ETH-USDT-SWAP": _daily_df([100, 100], [101, 100]),
    }
    backtest_result = run_daily_winner_backtest(
        dfs,
        DailyWinnerParams(universe=list(dfs), fee_bps=2.0, slippage_bps=3.0, initial_equity=1000.0),
    )
    req = RunBacktestRequest(
        strategy="daily_winner",
        universe=list(dfs),
        start="2024-01-01",
        end="2024-01-02",
        initial_equity=1000.0,
    )

    payload = _build_daily_winner_result_json(
        run_id="schema_daily_winner_costs",
        req=req,
        result=backtest_result,
        loaded_symbols=list(dfs),
        skipped_symbols=[],
    )

    buy, sell = payload["trades"]
    expected_pnl = 1000.0 * backtest_result.trades.iloc[0]["net_return"]
    assert buy["execution_phase"] == "entry"
    assert sell["execution_phase"] == "exit"
    assert buy["qty"] > 0
    assert buy["notional"] == pytest.approx(1000.0)
    assert buy["fee"] > 0
    assert sell["fee"] > 0
    assert sell["pnl_usd"] == pytest.approx(expected_pnl)
    assert payload["metrics"]["total_fees"] == pytest.approx(buy["fee"] + sell["fee"])
    assert payload["metrics"]["fill_notional_usd"] == pytest.approx(buy["notional"] + sell["notional"])
    assert payload["metrics"]["funding_cashflow"] == 0.0
    assert payload["metrics"]["funding_mode"] == "not_modeled"


def test_daily_winner_api_payload_can_embed_validation_summaries() -> None:
    dfs = {
        "BTC-USDT-SWAP": _daily_df([100] * 10, [101, 102, 101, 103, 104, 103, 105, 106, 105, 107]),
        "ETH-USDT-SWAP": _daily_df([100] * 10, [100, 101, 102, 101, 103, 102, 104, 105, 104, 106]),
    }
    backtest_result = run_daily_winner_backtest(
        dfs,
        DailyWinnerParams(universe=list(dfs), fee_bps=0.0, slippage_bps=0.0),
    )
    req = RunBacktestRequest(strategy="daily_winner", universe=list(dfs), validate="both")
    payload = _build_daily_winner_result_json(
        run_id="schema_daily_winner_validation",
        req=req,
        result=backtest_result,
        loaded_symbols=list(dfs),
        skipped_symbols=[],
    )
    _attach_daily_winner_validation(payload, backtest_result.daily_returns, req.validation)

    assert payload["walk_forward"]
    assert payload["cpcv"]["combos"]
    assert "psr" in payload["metrics"]
    assert payload["metrics"]["validation_only"] is True
    assert payload["validation"]["validation_mode"] == "both"


def test_daily_winner_payload_normalizer_repairs_legacy_inline_result() -> None:
    payload = {
        "run_id": "legacy_daily",
        "strategies": ["daily_winner"],
        "metrics": {"number_of_trades": 1, "sharpe": 793.0},
        "equity": [
            {"ts": "2024-01-01T00:00:00.000", "equity": 5000.0, "drawdown": 0.0},
            {"ts": "2024-01-02T00:00:00.000", "equity": 5050.0, "drawdown": 0.0},
        ],
        "returns": [{"ts": "2024-01-02T00:00:00.000", "return": 0.01}],
        "trades": [
            {
                "inst_id": "BTC-USDT-SWAP",
                "entry_ts": "2024-01-02T00:00:00.000",
                "exit_ts": "2024-01-03T00:00:00.000",
                "entry_price": 100.0,
                "exit_price": 101.0,
                "cost_rate": 0.001,
                "net_return": 0.009,
            }
        ],
    }

    repaired = _normalize_daily_winner_payload(payload)

    assert repaired["equity"][0]["datetime"] == "2024-01-01"
    assert repaired["equity"][1]["return"] == pytest.approx(0.01)
    assert repaired["metrics"]["fill_count"] == 2
    assert repaired["metrics"]["total_fees"] > 0.0
    assert repaired["metrics"]["fill_notional_usd"] > 0.0
    assert repaired["validation"]["validation_mode"] == "none"
    assert "walk_forward" not in repaired
    assert "cpcv" not in repaired
    assert len(repaired["round_trips"]) == 1
    assert len(repaired["trades"]) == 2
    assert [row["side"] for row in repaired["trades"]] == ["buy", "sell"]
    assert repaired["trades"][0]["datetime"] == "2024-01-02T00:00:00.000"
    assert repaired["trades"][1]["pnl_usd"] == pytest.approx(45.0)


def test_daily_winner_validation_routes_do_not_generate_when_none(tmp_path) -> None:
    run_dir = tmp_path / "run_none"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(
        """
        {
          "run_id": "run_none",
          "strategies": ["daily_winner"],
          "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
          "bar": "1D",
          "start": "2024-01-01",
          "end": "2024-01-03",
          "metrics": {"number_of_trades": 1},
          "equity": [
            {"ts": "2024-01-01T00:00:00.000", "equity": 5000.0},
            {"ts": "2024-01-02T00:00:00.000", "equity": 5050.0}
          ],
          "returns": [{"ts": "2024-01-02T00:00:00.000", "return": 0.01}],
          "trades": [
            {
              "inst_id": "BTC-USDT-SWAP",
              "entry_ts": "2024-01-02T00:00:00.000",
              "exit_ts": "2024-01-03T00:00:00.000",
              "entry_price": 100.0,
              "exit_price": 101.0,
              "net_return": 0.01
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    assert client.get("/api/backtest/run_none/walk-forward").json() == []
    assert client.get("/api/backtest/run_none/cpcv").json() is None


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


def test_load_candles_derives_intraday_from_1m_parquet(tmp_path) -> None:
    inst_dir = tmp_path / "BTC_USDT_SWAP"
    inst_dir.mkdir()
    idx = pd.date_range("2024-01-01", periods=30, freq="1min")
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

    loaded = load_candles("BTC-USDT-SWAP", bar="15m", data_dir=str(tmp_path))

    assert len(loaded) == 2
    assert loaded.iloc[0]["open"] == 100.0
    assert loaded.iloc[0]["high"] == 115.0
    assert loaded.iloc[0]["low"] == 99.0
    assert loaded.iloc[0]["close"] == 114.5
    assert loaded.iloc[0]["vol"] == 15.0


def test_load_candles_market_derives_1d_from_1m(monkeypatch) -> None:
    from okx_quant.data.candle_store import CandleStore

    idx = pd.date_range("2024-01-01", periods=2 * 24 * 60, freq="1min", tz="UTC")
    one_minute = pd.DataFrame(
        {
            "open": np.arange(len(idx), dtype=float) + 100.0,
            "high": np.arange(len(idx), dtype=float) + 101.0,
            "low": np.arange(len(idx), dtype=float) + 99.0,
            "close": np.arange(len(idx), dtype=float) + 100.5,
            "vol": np.ones(len(idx)),
        },
        index=idx,
    )

    class FakeStore:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_market_klines(self, *, bar, **_kwargs):
            if bar == "1D":
                return pd.DataFrame(columns=["open", "high", "low", "close", "vol"])
            return one_minute.copy()

    async def fake_from_dsn(*_args, **_kwargs):
        return FakeStore()

    monkeypatch.setattr(CandleStore, "from_dsn", fake_from_dsn)

    loaded = load_candles(
        "BTC-USDT-SWAP",
        bar="1D",
        backend="market",
        dsn="postgresql://unused",
        exchange="binance",
    )

    assert len(loaded) == 2
    assert loaded.iloc[0]["open"] == 100.0
    assert loaded.iloc[0]["close"] == 1539.5
    assert loaded.iloc[0]["vol"] == 1440.0


def test_partial_derived_bar_coverage_is_low() -> None:
    start = pd.Timestamp("2024-01-01", tz="UTC").to_pydatetime()
    end = pd.Timestamp("2024-01-02", tz="UTC").to_pydatetime()
    partial = pd.DataFrame(
        {"close": np.ones(4)},
        index=pd.date_range("2024-01-01", periods=4, freq="1h"),
    )
    full = pd.DataFrame(
        {"close": np.ones(24)},
        index=pd.date_range("2024-01-01", periods=24, freq="1h"),
    )

    assert _has_low_bar_coverage(partial, start, end, "1H")
    assert not _has_low_bar_coverage(full, start, end, "1H")
