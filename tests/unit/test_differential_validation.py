import json
import math

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backtesting import differential_validation as dv
from okx_quant.api.routes_backtest import make_backtest_router


def _write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def test_missing_optional_engines_are_reported_as_skip(tmp_path, monkeypatch):
    run_dir = _base_run(tmp_path)

    monkeypatch.setattr(dv.importlib.util, "find_spec", lambda name: None)
    summary = dv.run_differential_validation(
        run_dir,
        engines=["vectorbt", "backtrader", "nautilus"],
        validation_id="skip_test",
    )

    assert summary["status"] == "SKIP"
    assert summary["ohlcv_source_validation"] == "deferred"
    assert summary["engines"]["vectorbt"]["status"] == "SKIP"
    assert summary["engines"]["backtrader"]["status"] == "SKIP"
    assert summary["engines"]["nautilus"]["status"] == "SKIP"
    assert summary["engines"]["vectorbt"]["reference_role"] == "skipped_dependency"
    assert summary["engines"]["backtrader"]["reference_role"] == "skipped_dependency"
    assert summary["engines"]["nautilus"]["reference_role"] == "not_applicable"
    assert summary["engines"]["vectorbt"]["comparison"]["signal_logic"]["status"] == "SKIP"
    assert summary["signal_logic_gate"]["passed"] is False
    assert summary["promotion_gate_evidence"] is False
    assert summary["mismatch_counts"]["metrics"]["actionable"] == 0
    assert (run_dir / "validation" / "skip_test" / "validation_result.json").exists()


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
    assert detail.json()["ohlcv_source_validation"] == "deferred"


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
