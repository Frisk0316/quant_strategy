from __future__ import annotations

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from okx_quant.api import routes_backtest as routes


def test_downsample_price_records_preserves_each_symbol():
    records = [
        {"ts": i, "datetime": f"2024-01-{i + 1:02d}", "inst_id": symbol, "close": float(i)}
        for symbol in ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        for i in range(10)
    ]

    sampled = routes._downsample_records_by_symbol(records, 3)

    assert {row["inst_id"] for row in sampled} == {"BTC-USDT-SWAP", "ETH-USDT-SWAP"}
    assert len([row for row in sampled if row["inst_id"] == "BTC-USDT-SWAP"]) >= 2
    assert len([row for row in sampled if row["inst_id"] == "ETH-USDT-SWAP"]) >= 2


def test_trade_fallback_builds_entry_and_exit_markers():
    markers = routes._fallback_execution_markers_from_records(
        result={"strategies": ["daily_winner"]},
        trades=[
            {
                "inst_id": "BTC-USDT-SWAP",
                "entry_ts": "2024-01-01T00:00:00Z",
                "exit_ts": "2024-01-02T00:00:00Z",
                "entry_price": 42000.0,
                "exit_price": 43000.0,
                "net_return": 0.023,
            }
        ],
    )

    assert [row["side"] for row in markers] == ["buy", "sell"]
    assert [row["marker_text"].split()[0] for row in markers] == ["ENTRY", "EXIT"]
    assert all(row["inst_id"] == "BTC-USDT-SWAP" for row in markers)
    assert all(isinstance(row["ts"], int) for row in markers)


def test_fill_fallback_takes_precedence_over_trade_markers():
    markers = routes._fallback_execution_markers_from_records(
        result={"strategies": ["ma_crossover"]},
        fills=[
            {
                "inst_id": "ETH-USDT-SWAP",
                "ts": 1704067200000,
                "state": "filled",
                "side": "sell",
                "fill_px": 2300.0,
                "fill_sz": 0.25,
            }
        ],
        trades=[
            {
                "inst_id": "BTC-USDT-SWAP",
                "entry_ts": "2024-01-01T00:00:00Z",
                "entry_price": 42000.0,
            }
        ],
    )

    assert len(markers) == 1
    assert markers[0]["inst_id"] == "ETH-USDT-SWAP"
    assert markers[0]["side"] == "sell"


def test_price_series_fallback_loads_all_result_symbols(monkeypatch):
    calls: list[tuple[str, str, str | None, str | None]] = []

    def fake_load_candles(
        *,
        inst_id,
        bar,
        data_dir,
        start,
        end,
        backend,
        dsn,
        exchange,
    ):
        calls.append((inst_id, bar, start, end))
        index = pd.to_datetime(["2024-01-01", "2024-01-02"])
        return pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "vol": [10.0, 11.0],
            },
            index=index,
        )

    monkeypatch.setattr(routes, "_resolve_candle_backend", lambda: ("parquet", None))
    monkeypatch.setattr("backtesting.data_loader.load_candles", fake_load_candles)

    rows = routes._fallback_price_series_from_result(
        {
            "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            "bar": "1D",
            "start": "2024-01-01",
            "end": "2024-01-03",
            "data_source": {"primary_exchange": "binance"},
        }
    )

    assert {row["inst_id"] for row in rows} == {"BTC-USDT-SWAP", "ETH-USDT-SWAP"}
    assert len(rows) == 4
    assert calls == [
        ("BTC-USDT-SWAP", "1D", "2024-01-01", "2024-01-03"),
        ("ETH-USDT-SWAP", "1D", "2024-01-01", "2024-01-03"),
    ]
    assert all({"ts", "datetime", "open", "high", "low", "close", "vol"} <= set(row) for row in rows)


def test_price_series_route_backfills_symbols_missing_from_existing_artifact(tmp_path, monkeypatch):
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(
        """
        {
          "run_id": "run1",
          "strategies": ["daily_winner"],
          "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
          "bar": "1D",
          "start": "2024-01-01",
          "end": "2024-01-03",
          "metrics": {}
        }
        """,
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "ts": 1704067200000,
                "datetime": "2024-01-01T00:00:00+00:00",
                "inst_id": "BTC-USDT-SWAP",
                "open": 42000.0,
                "high": 43000.0,
                "low": 41000.0,
                "close": 42500.0,
                "vol": 10.0,
            }
        ]
    ).to_csv(run_dir / "price_series.csv", index=False)

    def fake_fallback(result, *, symbol=None, fills=None, trades=None):
        assert symbol is None
        return [
            {
                "ts": 1704067200000,
                "datetime": "2024-01-01T00:00:00+00:00",
                "inst_id": "ETH-USDT-SWAP",
                "open": 2300.0,
                "high": 2350.0,
                "low": 2250.0,
                "close": 2325.0,
                "vol": 20.0,
            }
        ]

    monkeypatch.setattr(routes, "_fallback_price_series_from_result", fake_fallback)

    app = FastAPI()
    app.include_router(routes.make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.get("/api/backtest/run1/price-series")

    assert response.status_code == 200
    assert {row["inst_id"] for row in response.json()} == {"BTC-USDT-SWAP", "ETH-USDT-SWAP"}
