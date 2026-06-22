from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from okx_quant.api import routes_backtest as routes


def test_backtest_market_symbol_loads_are_guarded_by_run_id_not_selection_cleanup():
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "frontend" / "view-backtest.js").read_text(encoding="utf-8")
    fetch_pos = text.index("window.API.fetchBacktestPriceSeries")
    effect_start = text.rfind("useEffect(() => {", 0, fetch_pos)
    effect_end = text.index('}, [runId, result, selectedChartSymbols.join("|")]);', fetch_pos)

    assert effect_start >= 0, "market-symbol loading effect not found"
    body = text[effect_start:effect_end]
    assert "useRef" in text
    assert "runIdRef.current !== runId" in body
    assert "return () => { cancelled = true; }" not in body


def test_equity_and_drawdown_charts_use_fluid_width_wrapper():
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "frontend" / "view-backtest.js").read_text(encoding="utf-8")

    assert text.count('<div class="chart-wrap fluid"><${LineChart}') >= 2


def test_backtest_run_list_uses_large_timeout_for_db_backed_results():
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "frontend" / "data.js").read_text(encoding="utf-8")

    assert 'fetchBacktestRuns:        ()        => _memoGetLarge("backtest-runs", "/api/backtest/runs")' in text
    assert 'fetchRuns:                ()        => _memoGetLarge("backtest-runs", "/api/backtest/runs")' in text


def test_frontend_exposes_summary_first_backtest_loading():
    repo_root = Path(__file__).resolve().parents[2]
    data_text = (repo_root / "frontend" / "data.js").read_text(encoding="utf-8")
    view_text = (repo_root / "frontend" / "view-backtest.js").read_text(encoding="utf-8")

    assert 'fetchBacktestSummary:     (id)      => _get("/api/backtest/" + id + "/summary")' in data_text
    assert "window.API.fetchBacktestSummary" in view_text
    assert "window.API.fetchBacktestSummary(runId)" in view_text
    assert "window.API.fetchBacktest(runId)" in view_text


def test_data_coverage_uses_short_inflight_cache():
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "frontend" / "data.js").read_text(encoding="utf-8")

    assert 'fetchDataCoverage:        ()        => _memoGet("data-coverage", "/api/data/coverage")' in text


def test_validation_lab_engine_cards_show_contract_limits_artifacts_and_triggers():
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "frontend" / "view-validation.js").read_text(encoding="utf-8")

    assert "Contract limit:" in text
    assert "Artifacts:" in text
    assert "Trigger:" in text
    assert "required artifacts present:" in text
    assert "Python package vectorbt is installed" in text
    assert "advisory export plus optional signal replay execution" in text
    assert "Engine execution matrix" in text
    assert "External validation conclusion" in text
    assert "Next required actions" in text
    assert "Replay coverage" in text
    assert "Missing artifacts" in text
    assert "contract=${activeContract}" in text


def test_validation_lab_can_run_saved_backtest_records_directly():
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "frontend" / "view-validation.js").read_text(encoding="utf-8")

    assert 'fixture_role: "saved_backtest_run"' in text
    assert 'validation_scope: "run"' in text
    assert "window.API.triggerDifferentialValidation(selectedFixtureRunId, { engines })" in text
    assert "window.API.fetchDifferentialValidation(runId, validationId)" in text
    assert "window.API.fetchDifferentialValidationArtifact(runId, validationId, file)" in text


def test_price_and_indicator_panels_expose_vertical_zoom_sliders():
    repo_root = Path(__file__).resolve().parents[2]
    view_text = (repo_root / "frontend" / "view-backtest.js").read_text(encoding="utf-8")
    style_text = (repo_root / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "onYZoomChange" in view_text
    assert 'aria-label="Vertical Y-axis scale"' in view_text
    assert 'aria-label="Vertical MACD Y-axis scale"' in view_text
    assert "inline=${true}" in view_text
    assert ".chart-y-slider" in style_text
    assert ".chart-y-scale-controls" in style_text


def test_risk_tab_loads_signals_for_signal_to_fill_gap():
    repo_root = Path(__file__).resolve().parents[2]
    data_text = (repo_root / "frontend" / "data.js").read_text(encoding="utf-8")
    view_text = (repo_root / "frontend" / "view-backtest.js").read_text(encoding="utf-8")

    assert 'fetchBacktestSignals:     (id)      => _getLarge("/api/backtest/" + id + "/signals")' in data_text
    assert "window.API.fetchBacktestSignals" in view_text
    assert "Signals / fills" in view_text
    assert "Unfilled signal gap" in view_text


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


def test_price_series_fallback_cache_returns_copies():
    key = ("run-cache-test", "*")
    routes._price_series_fallback_cache.clear()
    routes._set_price_series_cache(key, [{"inst_id": "BTC-USDT-SWAP", "close": 100.0}])

    rows = routes._get_price_series_cache(key)
    assert rows == [{"inst_id": "BTC-USDT-SWAP", "close": 100.0}]
    rows[0]["close"] = 999.0

    assert routes._get_price_series_cache(key) == [{"inst_id": "BTC-USDT-SWAP", "close": 100.0}]
    routes._price_series_fallback_cache.clear()


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


def test_trade_fallback_uses_daily_winner_execution_rows_directly():
    markers = routes._fallback_execution_markers_from_records(
        result={"strategies": ["daily_winner"]},
        trades=[
            {
                "inst_id": "BTC-USDT-SWAP",
                "datetime": "2024-01-01T00:00:00Z",
                "execution_phase": "entry",
                "side": "buy",
                "price": 42000.0,
                "qty": 0.1,
                "notional_usd": 4200.0,
            },
            {
                "inst_id": "BTC-USDT-SWAP",
                "datetime": "2024-01-02T00:00:00Z",
                "execution_phase": "exit",
                "side": "sell",
                "price": 43000.0,
                "qty": 0.1,
                "notional_usd": 4300.0,
                "pnl_usd": 100.0,
            },
        ],
    )

    assert [row["side"] for row in markers] == ["buy", "sell"]
    assert [row["marker_text"].split()[0] for row in markers] == ["ENTRY", "EXIT"]
    assert markers[0]["notional_usd"] == 4200.0
    assert markers[1]["net_realized_pnl"] == 100.0


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


def test_price_series_fallback_prefers_known_daily_winner_loaded_backend(monkeypatch):
    calls: list[tuple[str, str | None]] = []

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
        calls.append((backend, exchange))
        if backend != "postgres":
            return pd.DataFrame()
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

    monkeypatch.setattr(routes, "_resolve_candle_backend", lambda: ("postgres", "postgresql://example/db"))
    monkeypatch.setattr("backtesting.data_loader.load_candles", fake_load_candles)

    rows = routes._fallback_price_series_from_result(
        {
            "strategies": ["daily_winner"],
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1D",
            "start": "2024-01-01",
            "end": "2024-01-03",
            "data_source": {"primary_exchange": "binance"},
            "validation": {
                "daily_winner_data_sources": [
                    {
                        "inst_id": "BTC-USDT-SWAP",
                        "attempts": [
                            {"backend": "market", "exchange": "binance", "rows": 0},
                            {"backend": "postgres", "exchange": None, "rows": 2},
                        ],
                    }
                ]
            },
        }
    )

    assert len(rows) == 2
    assert calls == [("postgres", None)]


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


def test_price_series_route_uses_artifact_rows_before_whole_payload(tmp_path, monkeypatch):
    calls = []

    async def fake_read_artifact_rows(*, dsn, run_id, artifact_type, symbol=None, limit=0, offset=0, n=0):
        calls.append(
            {
                "dsn": dsn,
                "run_id": run_id,
                "artifact_type": artifact_type,
                "symbol": symbol,
                "limit": limit,
                "offset": offset,
                "n": n,
            }
        )
        return [
            {
                "ts": 1704067200000,
                "datetime": "2024-01-01T00:00:00+00:00",
                "inst_id": "BTC-USDT-SWAP",
                "close": 42000.0,
            }
        ]

    monkeypatch.setenv("DATABASE_URL", "postgresql://unit/db")
    monkeypatch.setattr(routes, "read_artifact_rows", fake_read_artifact_rows, raising=False)

    app = FastAPI()
    app.include_router(routes.make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.get("/api/backtest/run_db/price-series?symbol=BTC-USDT-SWAP&n=1200")

    assert response.status_code == 200
    assert response.json() == [
        {
            "ts": 1704067200000,
            "datetime": "2024-01-01T00:00:00+00:00",
            "inst_id": "BTC-USDT-SWAP",
            "close": 42000.0,
        }
    ]
    assert calls == [
        {
            "dsn": "postgresql://unit/db",
            "run_id": "run_db",
            "artifact_type": "price_series",
            "symbol": "BTC-USDT-SWAP",
            "limit": 0,
            "offset": 0,
            "n": 1200,
        }
    ]


def test_fills_route_uses_artifact_rows_with_limit_and_offset(tmp_path, monkeypatch):
    calls = []

    async def fake_read_artifact_rows(*, dsn, run_id, artifact_type, symbol=None, limit=0, offset=0, n=0):
        calls.append((artifact_type, symbol, limit, offset, n))
        return [{"id": "fill-6"}, {"id": "fill-7"}]

    monkeypatch.setenv("DATABASE_URL", "postgresql://unit/db")
    monkeypatch.setattr(routes, "read_artifact_rows", fake_read_artifact_rows, raising=False)

    app = FastAPI()
    app.include_router(routes.make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.get("/api/backtest/run_db/fills?limit=2&offset=5")

    assert response.status_code == 200
    assert response.json() == [{"id": "fill-6"}, {"id": "fill-7"}]
    assert calls == [("fills", None, 2, 5, 0)]


def test_differential_validation_csv_artifact_uses_artifact_rows(tmp_path, monkeypatch):
    calls = []

    async def fake_read_artifact_rows(*, dsn, run_id, artifact_type, symbol=None, limit=0, offset=0, n=0):
        calls.append((run_id, artifact_type, symbol, limit, offset, n))
        return [{"row": 1}]

    monkeypatch.setenv("DATABASE_URL", "postgresql://unit/db")
    monkeypatch.setattr(routes, "read_artifact_rows", fake_read_artifact_rows, raising=False)

    app = FastAPI()
    app.include_router(routes.make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.get("/api/backtest/run_db/differential-validation/val1/artifact/mismatches_signals.csv")

    assert response.status_code == 200
    assert response.json() == [{"row": 1}]
    assert calls == [("run_db", "validation/val1/mismatches_signals.csv", None, 0, 0, 0)]


def test_summary_endpoint_returns_lightweight_run_payload(tmp_path):
    run_dir = tmp_path / "summary_run"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(
        """
        {
          "run_id": "summary_run",
          "display_name": "Summary Run",
          "created_at": "2026-06-22T00:00:00+00:00",
          "strategies": ["ema_crossover"],
          "symbols": ["BTC-USDT-SWAP"],
          "bar": "1H",
          "start": "2024-01-01",
          "end": "2024-02-01",
          "metrics": {"total_return": 0.01},
          "parameters": {"strategies": {"ema_crossover": {"fast_span": 8}}},
          "artifacts": {"price_series": "price_series.csv"},
          "validation": {"ct_val_all_authoritative": true},
          "price_series": [{"close": 42000.0}],
          "trades": [{"pnl": 1.0}]
        }
        """,
        encoding="utf-8",
    )

    app = FastAPI()
    app.include_router(routes.make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.get("/api/backtest/summary_run/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "summary_run"
    assert payload["metrics"] == {"total_return": 0.01}
    assert payload["artifacts"] == {"price_series": "price_series.csv"}
    assert "price_series" not in payload
    assert "trades" not in payload


def test_execution_markers_endpoint_filters_by_symbol(tmp_path):
    run_dir = tmp_path / "run_markers"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(
        """
        {
          "run_id": "run_markers",
          "strategies": ["daily_winner"],
          "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
          "bar": "1m",
          "start": "2024-01-01",
          "end": "2024-01-02",
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
                "side": "buy",
                "price": 42000.0,
            },
            {
                "ts": 1704067200000,
                "datetime": "2024-01-01T00:00:00+00:00",
                "inst_id": "ETH-USDT-SWAP",
                "side": "buy",
                "price": 2300.0,
            },
        ]
    ).to_csv(run_dir / "execution_markers.csv", index=False)

    app = FastAPI()
    app.include_router(routes.make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.get("/api/backtest/run_markers/execution-markers?symbol=BTC-USDT-SWAP")

    assert response.status_code == 200
    assert [row["inst_id"] for row in response.json()] == ["BTC-USDT-SWAP"]


def test_get_run_backfills_parameters_from_config_for_legacy_results(tmp_path):
    run_dir = tmp_path / "legacy_params"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(
        """
        {
          "run_id": "legacy_params",
          "strategies": ["ema_crossover"],
          "symbols": ["BTC-USDT-SWAP"],
          "bar": "1H",
          "start": "2024-01-01",
          "end": "2024-01-02",
          "metrics": {}
        }
        """,
        encoding="utf-8",
    )
    (run_dir / "config.json").write_text(
        """
        {
          "strategies": {
            "ema_crossover": {
              "symbols": ["BTC-USDT-SWAP"],
              "fast_span": 8,
              "slow_span": 21,
              "indicator_db_warmup": false,
              "td_mode": "cross"
            }
          },
          "risk": {
            "max_order_notional_usd": 2500.0,
            "max_pos_pct_equity": 0.75,
            "max_leverage": 3.0
          },
          "backtest": {
            "order_latency_ms": 0,
            "cancel_latency_ms": 200,
            "queue_fill_fraction": 0.2,
            "liquidate_on_end": true
          },
          "cli_args": {
            "strategy_params": {"fast_span": 8, "slow_span": 21},
            "risk_overrides": {"max_order_notional_usd": 2500.0}
          }
        }
        """,
        encoding="utf-8",
    )

    app = FastAPI()
    app.include_router(routes.make_backtest_router(tmp_path), prefix="/api/backtest")
    client = TestClient(app)

    response = client.get("/api/backtest/legacy_params")

    assert response.status_code == 200
    params = response.json()["parameters"]
    assert params["strategies"]["ema_crossover"]["fast_span"] == 8
    assert params["risk"]["max_order_notional_usd"] == 2500.0
    assert params["backtest"]["queue_fill_fraction"] == 0.2
    assert params["overrides"]["strategy_params"]["slow_span"] == 21
