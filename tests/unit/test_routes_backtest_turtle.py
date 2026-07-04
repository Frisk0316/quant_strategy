from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backtesting.turtle_backtest import TurtleParams, run_turtle_backtest
from okx_quant.api import routes_backtest as routes

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXISTING_TURTLE_RUN_DIR = PROJECT_ROOT / "results" / "ui_turtle_92f5aa71"
EXISTING_TURTLE_RUN_AVAILABLE = all(
    (EXISTING_TURTLE_RUN_DIR / name).exists()
    for name in ("result.json", "fills.csv", "trades.csv")
)


def _daily() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            ("2024-01-01", 10, 10, 9, 10),
            ("2024-01-02", 10, 10, 9, 10),
            ("2024-01-03", 10, 10, 9, 10),
            ("2024-01-04", 10, 11, 9, 10),
            ("2024-01-05", 10, 12, 9, 10),
        ],
        columns=["date", "open", "high", "low", "close"],
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def _client(results_dir) -> TestClient:
    app = FastAPI()
    app.include_router(routes.make_backtest_router(results_dir), prefix="/api/backtest")
    return TestClient(app)


def test_turtle_run_rejects_non_daily_bar(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/backtest/run",
        json={"strategy": "turtle", "symbols": ["BTC-USDT-SWAP"], "bar": "1H"},
    )

    assert response.status_code == 400
    assert "1D" in response.json()["detail"]


def test_turtle_result_writer_emits_visual_artifacts(tmp_path) -> None:
    df = _daily()
    params = TurtleParams(
        enter_term_sys1=3,
        enter_term_sys2=4,
        leave_term_sys1=2,
        leave_term_sys2=3,
        own_capital=1_000,
        invest_pct=0.5,
        min_position=0.0001,
        fee=0.0,
        atr_period=2,
    )
    result = run_turtle_backtest(df.reset_index(), params)
    req = routes.RunBacktestRequest(
        strategy="turtle",
        symbols=["BTC-USDT-SWAP"],
        bar="1D",
        initial_equity=1_000,
        strategy_params=params.__dict__,
    )

    payload = routes._build_turtle_result_json(
        run_id="turtle_unit",
        req=req,
        result=result,
        symbol="BTC-USDT-SWAP",
        data_sources=[],
    )
    routes._write_turtle_artifacts(tmp_path, "BTC-USDT-SWAP", df, result, payload)

    assert payload["artifacts"]["price_series"] == "price_series.csv"
    assert payload["artifacts"]["indicator_series"] == "indicator_series.csv"
    assert payload["artifacts"]["trades"] == "trades.csv"
    indicators = pd.read_csv(tmp_path / "indicator_series.csv")
    assert {"ATR", "last_enter_max_sys1", "last_leave_min_sys1"} <= set(indicators.columns)
    trades = pd.read_csv(tmp_path / "trades.csv")
    assert {"inst_id", "execution_phase", "fill_px", "fill_sz"} <= set(trades.columns)


def test_visual_time_values_accepts_numeric_epoch_strings() -> None:
    assert routes._visual_time_values("1611878400000") == (
        1611878400000,
        "2021-01-29T00:00:00+00:00",
    )


def test_turtle_csv_string_records_emit_execution_markers() -> None:
    markers = routes._fallback_execution_markers_from_records(
        fills=[
            {
                "ts": "1611878400000",
                "datetime": "2021-01-29T00:00:00+00:00",
                "inst_id": "BTC-USDT-SWAP",
                "side": "buy",
                "fill_px": "33300.5",
                "fill_sz": "0.01",
                "fee": "0",
                "state": "filled",
            }
        ],
        trades=[],
        result={"strategies": ["turtle"]},
    )

    assert len(markers) == 1
    assert markers[0]["ts"] == 1611878400000
    assert markers[0]["side"] == "buy"
    assert markers[0]["price"] == 33300.5


@pytest.mark.skipif(
    not EXISTING_TURTLE_RUN_AVAILABLE,
    reason="local ui_turtle_92f5aa71 artifacts are gitignored",
)
def test_existing_turtle_run_csv_artifacts_emit_execution_markers() -> None:
    run_dir = EXISTING_TURTLE_RUN_DIR
    with (run_dir / "result.json").open(encoding="utf-8") as fh:
        result = json.load(fh)
    with (run_dir / "fills.csv").open(encoding="utf-8", newline="") as fh:
        fills = list(csv.DictReader(fh))
    with (run_dir / "trades.csv").open(encoding="utf-8", newline="") as fh:
        trades = list(csv.DictReader(fh))

    markers = routes._fallback_execution_markers_from_records(
        fills=fills,
        trades=trades,
        result=result,
    )

    assert len(markers) > 0


@pytest.mark.skipif(
    not EXISTING_TURTLE_RUN_AVAILABLE,
    reason="local ui_turtle_92f5aa71 artifacts are gitignored",
)
def test_existing_turtle_run_symbol_filtered_execution_marker_endpoint() -> None:
    client = _client(PROJECT_ROOT / "results")

    response = client.get(
        "/api/backtest/ui_turtle_92f5aa71/execution-markers",
        params={"symbol": "BTC-USDT-SWAP", "limit": 1000},
    )

    assert response.status_code == 200
    markers = response.json()
    assert len(markers) > 0
    assert {marker["inst_id"] for marker in markers} == {"BTC-USDT-SWAP"}


def test_turtle_result_records_ignored_risk_and_execution_controls() -> None:
    df = _daily()
    params = TurtleParams(
        enter_term_sys1=3,
        enter_term_sys2=4,
        leave_term_sys1=2,
        leave_term_sys2=3,
        own_capital=1_000,
        invest_pct=0.5,
        min_position=0.0001,
        fee=0.0,
        atr_period=2,
    )
    result = run_turtle_backtest(df.reset_index(), params)
    req = routes.RunBacktestRequest(
        strategy="turtle",
        symbols=["BTC-USDT-SWAP"],
        bar="1D",
        strategy_params=params.__dict__,
        risk_overrides={"max_order_notional_usd": 999},
        fill_all_signals=True,
        execution_profile="dual_output",
    )

    payload = routes._build_turtle_result_json(
        run_id="turtle_unit",
        req=req,
        result=result,
        symbol="BTC-USDT-SWAP",
        data_sources=[],
    )

    assert payload["parameters"]["risk"] == {}
    assert payload["parameters"]["overrides"]["risk_overrides"] == {}
    assert payload["parameters"]["backtest"]["execution_profile"] == "strategy_fill"
    assert payload["parameters"]["backtest"]["fill_all_signals"] is False
    assert payload["validation"]["controls_ignored"] == [
        "risk_overrides",
        "execution_profile",
        "fill_all_signals",
    ]


def test_turtle_sweep_endpoint_queues_turtle_job(tmp_path, monkeypatch) -> None:
    routes._sweep_jobs.clear()

    def fake_turtle_sweep_job(job_id, req, sweep_id, results_dir):
        routes._sweep_jobs[job_id].update(
            {
                "status": "done",
                "progress": 100,
                "message": "fake turtle sweep complete",
                "sweep_id": sweep_id,
                "artifacts": {"summary": "summary.json"},
                "completed_count": 2,
            }
        )

    monkeypatch.setattr(routes, "_run_turtle_sweep_job", fake_turtle_sweep_job)
    client = _client(tmp_path)

    response = client.post(
        "/api/backtest/sweep",
        json={
            "strategy": "turtle",
            "symbols": ["BTC-USDT-SWAP"],
            "bar": "1D",
            "parameter_grid": {
                "enter_term_sys1": "5~7",
                "enter_term_sys2": 8,
                "leave_term_sys1": 5,
                "leave_term_sys2": 6,
            },
            "run_finalists": False,
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/backtest/sweep/status/{job_id}")
    assert status.json()["status"] == "done"
    assert status.json()["completed_count"] == 2


def test_turtle_sweep_result_and_artifact_endpoints(tmp_path) -> None:
    sweep_dir = tmp_path / "turtle_sweeps" / "sweep_unit"
    sweep_dir.mkdir(parents=True)
    (sweep_dir / "summary.json").write_text(
        json.dumps({"sweep_id": "sweep_unit", "strategy": "turtle"}),
        encoding="utf-8",
    )
    pd.DataFrame([{"rank": 1, "final_equity": 1010.0}]).to_csv(sweep_dir / "rows.csv", index=False)

    client = _client(tmp_path)

    result = client.get("/api/backtest/sweep/result/sweep_unit")
    rows = client.get("/api/backtest/sweep/artifact/sweep_unit/rows")

    assert result.status_code == 200
    assert result.json()["strategy"] == "turtle"
    assert rows.status_code == 200
    assert rows.json() == [{"rank": 1, "final_equity": 1010.0}]
