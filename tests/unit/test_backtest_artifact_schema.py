"""Regression tests for the frozen backtest artifact schema."""

import json
from types import SimpleNamespace

import pandas as pd

from backtesting.artifacts import (
    EQUITY_COLUMNS,
    FILL_COLUMNS,
    PRICE_SERIES_COLUMNS,
    TRADE_COLUMNS,
    save_backtest_artifacts,
)


REQUIRED_RESULT_KEYS = {
    "run_id",
    "created_at",
    "strategies",
    "symbols",
    "bar",
    "start",
    "end",
    "metrics",
    "artifacts",
}

REQUIRED_METRIC_KEYS = {
    "total_return",
    "sharpe",
    "max_drawdown",
    "profit_factor",
    "order_count",
    "fill_rate",
    "bankrupt",
}

REQUIRED_FILL_COLUMNS = {
    "ts",
    "datetime",
    "inst_id",
    "side",
    "fill_px",
    "fill_sz",
    "fee",
    "state",
    "ct_val",
}

REQUIRED_TRADE_COLUMNS = {
    "ts",
    "datetime",
    "inst_id",
    "side",
    "fill_px",
    "fill_sz",
    "fee",
    "realized_pnl",
    "net_realized_pnl",
    "size_before",
    "size_after",
    "equity_after",
}

REQUIRED_EQUITY_COLUMNS = {
    "ts",
    "datetime",
    "equity",
    "drawdown",
    "return",
}

REQUIRED_PRICE_COLUMNS = {
    "ts",
    "datetime",
    "inst_id",
    "open",
    "high",
    "low",
    "close",
    "vol",
}


def test_backtest_artifact_column_constants_include_adr_required_fields():
    assert REQUIRED_FILL_COLUMNS <= set(FILL_COLUMNS)
    assert REQUIRED_TRADE_COLUMNS <= set(TRADE_COLUMNS)
    assert REQUIRED_EQUITY_COLUMNS <= set(EQUITY_COLUMNS)
    assert REQUIRED_PRICE_COLUMNS <= set(PRICE_SERIES_COLUMNS)


def test_minimal_backtest_artifact_export_preserves_required_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKTEST_ARTIFACT_MODE", "files")
    metrics = {
        "total_return": 0.01,
        "sharpe": 1.2,
        "max_drawdown": -0.03,
        "profit_factor": 1.5,
        "order_count": 1,
        "fill_rate": 1.0,
        "bankrupt": False,
    }
    result = SimpleNamespace(
        equity_curve=pd.Series(
            [10_000.0, 10_010.0],
            index=[1_704_067_200_000, 1_704_070_800_000],
        ),
        metrics=metrics,
        order_log=pd.DataFrame(),
        fill_log=pd.DataFrame([
            {
                "ts": 1_704_067_200_000,
                "strategy": "schema",
                "inst_id": "BTC-USDT-SWAP",
                "side": "buy",
                "fill_px": 40_000.0,
                "fill_sz": 0.25,
                "fee": 0.0,
                "state": "filled",
                "metadata": {"ct_val": 0.01},
            }
        ]),
        funding_log=pd.DataFrame(),
        trade_log=pd.DataFrame([
            {
                "ts": 1_704_067_200_000,
                "strategy": "schema",
                "inst_id": "BTC-USDT-SWAP",
                "side": "buy",
                "fill_px": 40_000.0,
                "fill_sz": 0.25,
                "fee": 0.0,
                "realized_pnl": 0.0,
                "net_realized_pnl": 0.0,
                "size_before": 0.0,
                "size_after": 0.25,
                "equity_after": 10_000.0,
                "metadata": {"ct_val": 0.01},
            }
        ]),
        price_log=pd.DataFrame([
            {
                "ts": 1_704_067_200_000,
                "inst_id": "BTC-USDT-SWAP",
                "open": 40_000.0,
                "high": 40_000.0,
                "low": 40_000.0,
                "close": 40_000.0,
                "vol": 100.0,
            }
        ]),
        signal_log=[],
        risk_event_log=[],
        rejected_log=[],
        cancel_log=[],
        validation={
            "liquidate_on_end": True,
            "terminal_liquidation_fill_count": 0,
            "terminal_positions_closed": True,
        },
    )
    cfg = SimpleNamespace(
        storage=SimpleNamespace(timescale_dsn=None, candle_backend="parquet"),
    )
    args = SimpleNamespace(strategy=["schema"], start="2024-01-01", end="2024-01-02", bar="1H")

    run_dir = save_backtest_artifacts(
        result=result,
        cfg=cfg,
        args=args,
        output_dir=str(tmp_path),
        run_id="schema_contract",
        strategy_names=["schema"],
        start="2024-01-01",
        end="2024-01-02",
        bar="1H",
    )

    result_payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    fills = pd.read_csv(run_dir / "fills.csv")
    trades = pd.read_csv(run_dir / "trades.csv")
    equity = pd.read_csv(run_dir / "equity_curve.csv")
    price_series = pd.read_csv(run_dir / "price_series.csv")
    markers = pd.read_csv(run_dir / "execution_markers.csv")

    assert REQUIRED_RESULT_KEYS <= set(result_payload)
    assert REQUIRED_METRIC_KEYS <= set(result_payload["metrics"])
    assert result_payload["validation"]["liquidate_on_end"] is True
    assert result_payload["validation"]["terminal_positions_closed"] is True
    assert REQUIRED_FILL_COLUMNS <= set(fills.columns)
    assert REQUIRED_TRADE_COLUMNS <= set(trades.columns)
    assert REQUIRED_EQUITY_COLUMNS <= set(equity.columns)
    assert REQUIRED_PRICE_COLUMNS <= set(price_series.columns)
    assert "day_pnl" in markers.columns
    assert result_payload["artifacts"]["price_series"] == "price_series.csv"
