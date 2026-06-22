"""Regression tests for the frozen backtest artifact schema."""

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from backtesting.artifacts import (
    BOOK_SNAPSHOT_COLUMNS,
    EQUITY_COLUMNS,
    EXTERNAL_OBSERVATION_COLUMNS,
    FILL_COLUMNS,
    FUNDING_RATE_COLUMNS,
    PRICE_SERIES_COLUMNS,
    TRADE_TICK_COLUMNS,
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
    "parameters",
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

REQUIRED_FUNDING_RATE_COLUMNS = {
    "ts",
    "datetime",
    "inst_id",
    "funding_rate",
    "funding_interval_hours",
}

REQUIRED_EXTERNAL_OBSERVATION_COLUMNS = {
    "ts",
    "datetime",
    "dataset_id",
    "observed_at",
    "published_at",
    "value_num",
    "value_text",
    "fields",
    "quality_status",
}

REQUIRED_BOOK_SNAPSHOT_COLUMNS = {
    "ts",
    "datetime",
    "inst_id",
    "side",
    "level",
    "px",
    "sz",
    "seq_id",
    "channel",
    "source",
}

REQUIRED_TRADE_TICK_COLUMNS = {
    "ts",
    "datetime",
    "inst_id",
    "trade_id",
    "price",
    "size",
    "side",
    "source",
}


def test_backtest_artifact_column_constants_include_adr_required_fields():
    assert REQUIRED_FILL_COLUMNS <= set(FILL_COLUMNS)
    assert REQUIRED_TRADE_COLUMNS <= set(TRADE_COLUMNS)
    assert REQUIRED_EQUITY_COLUMNS <= set(EQUITY_COLUMNS)
    assert REQUIRED_PRICE_COLUMNS <= set(PRICE_SERIES_COLUMNS)
    assert REQUIRED_FUNDING_RATE_COLUMNS <= set(FUNDING_RATE_COLUMNS)
    assert REQUIRED_EXTERNAL_OBSERVATION_COLUMNS <= set(EXTERNAL_OBSERVATION_COLUMNS)
    assert REQUIRED_BOOK_SNAPSHOT_COLUMNS <= set(BOOK_SNAPSHOT_COLUMNS)
    assert REQUIRED_TRADE_TICK_COLUMNS <= set(TRADE_TICK_COLUMNS)


def test_backtest_artifact_rows_migration_declares_fast_read_index_contract():
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "sql" / "migrations" / "0012_backtest_artifact_rows.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS backtest_artifact_rows" in text
    assert "PRIMARY KEY (run_id, artifact_type, ordinal)" in text
    assert "REFERENCES backtest_runs(run_id) ON DELETE CASCADE" in text
    assert "(run_id, artifact_type, inst_id, ordinal)" in text
    assert "(run_id, artifact_type, inst_id, ts_ms)" in text
    assert "(run_id, artifact_type)" in text


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
        funding_rate_log=pd.DataFrame([
            {
                "ts": 1_704_067_200_000,
                "inst_id": "BTC-USDT-SWAP",
                "funding_rate": 0.0001,
                "funding_interval_hours": 8.0,
                "next_funding_time": 1_704_096_000_000,
            }
        ]),
        feature_event_log=pd.DataFrame([
            {
                "ts": 1_704_067_200_000,
                "dataset_id": "fear_greed_btc",
                "observed_at": "2024-01-01T00:00:00Z",
                "published_at": "2024-01-01T00:00:00Z",
                "value_num": 20.0,
                "value_text": "Extreme Fear",
                "fields": {"classification": "Extreme Fear"},
                "quality_status": "ok",
            }
        ]),
        book_snapshot_log=pd.DataFrame([
            {
                "ts": 1_704_067_200_000,
                "inst_id": "BTC-USDT-SWAP",
                "side": "bid",
                "level": 0,
                "px": 39_999.5,
                "sz": 2.0,
                "seq_id": 10,
                "channel": "books",
                "source": "market_payload",
            },
            {
                "ts": 1_704_067_200_000,
                "inst_id": "BTC-USDT-SWAP",
                "side": "ask",
                "level": 0,
                "px": 40_000.5,
                "sz": 2.5,
                "seq_id": 10,
                "channel": "books",
                "source": "market_payload",
            },
        ]),
        trade_tick_log=pd.DataFrame([
            {
                "ts": 1_704_067_199_500,
                "inst_id": "BTC-USDT-SWAP",
                "trade_id": "t-1",
                "price": 40_000.0,
                "size": 0.5,
                "side": "buy",
                "source": "market_payload",
            }
        ]),
        validation={
            "liquidate_on_end": True,
            "terminal_liquidation_fill_count": 0,
            "terminal_positions_closed": True,
        },
    )
    cfg = SimpleNamespace(
        storage=SimpleNamespace(timescale_dsn=None, candle_backend="parquet"),
        risk=SimpleNamespace(
            max_order_notional_usd=500.0,
            max_pos_pct_equity=0.30,
            max_leverage=3.0,
        ),
        backtest=SimpleNamespace(
            order_latency_ms=0,
            cancel_latency_ms=200,
            queue_fill_fraction=0.20,
            liquidate_on_end=True,
        ),
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
    funding_rates = pd.read_csv(run_dir / "funding_rates.csv")
    external_observations = pd.read_csv(run_dir / "external_observations.csv")
    book_snapshots = pd.read_csv(run_dir / "book_snapshots.csv")
    trade_ticks = pd.read_csv(run_dir / "trade_ticks.csv")

    assert REQUIRED_RESULT_KEYS <= set(result_payload)
    assert REQUIRED_METRIC_KEYS <= set(result_payload["metrics"])
    assert result_payload["parameters"]["risk"]["max_order_notional_usd"] == 500.0
    assert result_payload["parameters"]["risk"]["max_pos_pct_equity"] == 0.30
    assert result_payload["parameters"]["risk"]["max_leverage"] == 3.0
    assert result_payload["parameters"]["backtest"]["queue_fill_fraction"] == 0.20
    assert result_payload["validation"]["liquidate_on_end"] is True
    assert result_payload["validation"]["terminal_positions_closed"] is True
    assert REQUIRED_FILL_COLUMNS <= set(fills.columns)
    assert REQUIRED_TRADE_COLUMNS <= set(trades.columns)
    assert REQUIRED_EQUITY_COLUMNS <= set(equity.columns)
    assert REQUIRED_PRICE_COLUMNS <= set(price_series.columns)
    assert REQUIRED_FUNDING_RATE_COLUMNS <= set(funding_rates.columns)
    assert REQUIRED_EXTERNAL_OBSERVATION_COLUMNS <= set(external_observations.columns)
    assert REQUIRED_BOOK_SNAPSHOT_COLUMNS <= set(book_snapshots.columns)
    assert REQUIRED_TRADE_TICK_COLUMNS <= set(trade_ticks.columns)
    assert "day_pnl" in markers.columns
    assert result_payload["artifacts"]["price_series"] == "price_series.csv"
    assert result_payload["artifacts"]["funding_rates"] == "funding_rates.csv"
    assert result_payload["artifacts"]["external_observations"] == "external_observations.csv"
    assert result_payload["artifacts"]["book_snapshots"] == "book_snapshots.csv"
    assert result_payload["artifacts"]["trade_ticks"] == "trade_ticks.csv"
    assert funding_rates["funding_rate"].iloc[0] == 0.0001
    assert external_observations["dataset_id"].iloc[0] == "fear_greed_btc"
    assert set(book_snapshots["side"]) == {"bid", "ask"}
    assert trade_ticks["trade_id"].iloc[0] == "t-1"
