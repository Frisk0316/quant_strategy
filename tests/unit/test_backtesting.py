"""Unit tests for backtesting data loaders and validation splitters."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from types import SimpleNamespace

from backtesting.artifacts import _build_indicator_series_df, build_run_id, save_backtest_artifacts
from backtesting.cpcv import CPCV
from backtesting.data_loader import compute_returns, load_funding, load_trade_ticks
from backtesting.replay import (
    HistoricalEventFeed,
    ReplayBacktestEngine,
    ReplayBacktestResult,
    ReplayRecorder,
    _apply_post_run_gates,
    _check_data_coverage_gate,
    _compute_data_coverage,
    build_feed_for_strategies,
    make_replay_strategy_fn,
    run_replay_backtest,
    run_replay_validations,
)
from backtesting.research_controls import FILL_ALL_MAX_ORDER_NOTIONAL_USD, FILL_ALL_MAX_POS_PCT_EQUITY
from backtesting.walk_forward import WalkForward
from okx_quant.core.events import MarketPayload
from okx_quant.core.config import AppConfig, OKXSecrets, RiskConfig, StrategiesConfig, SystemConfig, load_config
from okx_quant.portfolio.positions import PositionLedger


@pytest.mark.parametrize("run_id", ["", ".", "..", "../outside", "..\\outside", "C:outside"])
def test_custom_run_id_is_rejected_in_artifact_writer(run_id):
    with pytest.raises(ValueError, match="run_id"):
        build_run_id(["ma_crossover"], "2024-01-01", "2024-02-01", "1H", run_id)


def _use_okx_registry(cfg: AppConfig) -> AppConfig:
    cfg = cfg.model_copy(deep=True)
    cfg.storage = cfg.storage.model_copy(update={"primary_exchange": "okx"})
    return cfg


def test_strategy_config_preserves_yaml_parameters_used_by_strategies():
    cfg = StrategiesConfig(**{
        "funding_carry": {
            "max_abs_basis_z": 1.8,
            "max_crowding": 0.75,
        },
        "pairs_trading": {
            "max_half_life_hours": 36.0,
            "max_hedge_uncertainty": 5.0,
        },
    })

    assert cfg.funding_carry.max_abs_basis_z == 1.8
    assert cfg.funding_carry.max_crowding == 0.75
    assert cfg.pairs_trading.max_half_life_hours == 36.0
    assert cfg.pairs_trading.max_hedge_uncertainty == 5.0


def test_strategy_config_normalizes_compact_symbols():
    cfg = StrategiesConfig(**{
        "funding_carry": {
            "perp_symbol": "BTCUSDT",
            "spot_symbol": "BTCUSDT",
        },
        "pairs_trading": {
            "symbol_y": "ETHUSDT",
            "symbol_x": "BTCUSDT",
        },
    })

    assert cfg.funding_carry.perp_symbol == "BTC-USDT-SWAP"
    assert cfg.funding_carry.spot_symbol == "BTC-USDT"
    assert cfg.pairs_trading.symbol_y == "ETH-USDT-SWAP"
    assert cfg.pairs_trading.symbol_x == "BTC-USDT-SWAP"


def test_strategy_config_accepts_legacy_max_half_life_key():
    cfg = StrategiesConfig(**{
        "pairs_trading": {
            "max_half_life": 24.0,
        },
    })

    assert cfg.pairs_trading.max_half_life_hours == 24.0
    assert cfg.pairs_trading.max_half_life == 24.0


def test_replay_default_specs_reject_unknown_swap_without_metadata(minimal_cfg):
    """Symbols not in the bundled registry (config/instrument_specs.yaml) and
    not BTC/ETH still raise — preserves the safety guard against silent ct_val
    fallback for unfamiliar contracts.
    """
    cfg = _use_okx_registry(minimal_cfg)
    cfg.strategies = StrategiesConfig(
        pairs_trading={
            "enabled": True,
            "symbol_y": "FOO-USDT-SWAP",
            "symbol_x": "BAR-USDT-SWAP",
        }
    )

    with pytest.raises(ValueError, match="Missing ctVal for swap"):
        ReplayBacktestEngine(cfg, strategy_names=["pairs_trading"])


def test_replay_default_specs_allow_btc_eth_swaps(minimal_cfg):
    cfg = _use_okx_registry(minimal_cfg)
    cfg.strategies = StrategiesConfig(
        pairs_trading={
            "enabled": True,
            "symbol_y": "ETH-USDT-SWAP",
            "symbol_x": "BTC-USDT-SWAP",
        }
    )

    engine = ReplayBacktestEngine(cfg, strategy_names=["pairs_trading"])

    assert engine._instrument_specs["ETH-USDT-SWAP"]["ctVal"] == pytest.approx(0.01)
    assert engine._instrument_specs["BTC-USDT-SWAP"]["ctVal"] == pytest.approx(0.01)


def test_replay_default_specs_resolve_registry_swaps(minimal_cfg):
    """SOL/ADA are in config/instrument_specs.yaml so they should resolve
    without falling back to BTC/ETH defaults or raising.
    """
    cfg = _use_okx_registry(minimal_cfg)
    cfg.strategies = StrategiesConfig(
        pairs_trading={
            "enabled": True,
            "symbol_y": "SOL-USDT-SWAP",
            "symbol_x": "ADA-USDT-SWAP",
        }
    )

    engine = ReplayBacktestEngine(cfg, strategy_names=["pairs_trading"])

    assert engine._instrument_specs["SOL-USDT-SWAP"]["ctVal"] == pytest.approx(1.0)
    assert engine._instrument_specs["ADA-USDT-SWAP"]["ctVal"] == pytest.approx(100.0)
    # Provenance tracked per symbol. SOL/ADA come from the YAML registry, BTC/ETH would
    # come from hardcoded fallback. Either way they are non-authoritative for live gating.
    sources = engine._ct_val_sources
    assert sources["SOL-USDT-SWAP"]["source"] == "registry"
    assert sources["ADA-USDT-SWAP"]["source"] == "registry"
    # Spot pairs are always exact unit ctVal — authoritative.
    if cfg.system.spot_symbols:
        spot_sym = next(iter(cfg.system.spot_symbols))
        assert sources[spot_sym]["source"] == "spot_unit"


def test_replay_engine_records_config_override_ctval_source(minimal_cfg):
    """Caller-supplied instrument_specs should be labeled as `config_override`
    so the live-deployment gate treats them as authoritative.
    """
    cfg = _use_okx_registry(minimal_cfg)
    cfg.strategies = StrategiesConfig(
        pairs_trading={
            "enabled": True,
            "symbol_y": "FOO-USDT-SWAP",
            "symbol_x": "BAR-USDT-SWAP",
        }
    )
    override = {
        "FOO-USDT-SWAP": {"ctVal": 0.5, "minSz": 0.01, "lotSz": 0.01, "tickSz": 0.001, "tdMode": "cross"},
        "BAR-USDT-SWAP": {"ctVal": 2.0, "minSz": 0.01, "lotSz": 0.01, "tickSz": 0.001, "tdMode": "cross"},
    }
    engine = ReplayBacktestEngine(cfg, strategy_names=["pairs_trading"], instrument_specs=override)

    assert engine._ct_val_sources["FOO-USDT-SWAP"]["source"] == "config_override"
    assert engine._ct_val_sources["FOO-USDT-SWAP"]["value"] == pytest.approx(0.5)
    assert engine._ct_val_sources["BAR-USDT-SWAP"]["source"] == "config_override"
    assert engine._ct_val_sources["BAR-USDT-SWAP"]["value"] == pytest.approx(2.0)


@pytest.mark.parametrize("bad_ct_val", [float("inf"), float("nan"), 1e8, 0.0, -1.0])
def test_replay_engine_rejects_invalid_caller_ctval_before_authoritative_label(minimal_cfg, bad_ct_val):
    """R1.5/I34: an unvalidated multiplier must never be recorded under the
    authoritative `config_override` source, even if no trade consumes it."""
    cfg = _use_okx_registry(minimal_cfg)
    override = {
        "FOO-USDT-SWAP": {"ctVal": bad_ct_val, "minSz": 0.01, "lotSz": 0.01, "tickSz": 0.001, "tdMode": "cross"},
    }

    with pytest.raises(ValueError):
        ReplayBacktestEngine(cfg, strategy_names=["pairs_trading"], instrument_specs=override)


def test_load_config_reads_backtest_execution_defaults():
    cfg = load_config(require_secrets=False)

    assert cfg.backtest.order_latency_ms == 0
    assert cfg.backtest.cancel_latency_ms == 200
    assert cfg.backtest.queue_fill_fraction == pytest.approx(0.20)
    assert cfg.backtest.fill_all_signals is False


def test_walk_forward_split_has_no_boundary_overlap():
    idx = pd.date_range("2024-01-01", periods=12, freq="1D")
    df = pd.DataFrame({"value": np.arange(len(idx))}, index=idx)

    wf = WalkForward(is_days=4, oos_days=2)
    windows = list(wf.split(df))

    assert windows
    first_is, first_oos = windows[0]
    assert first_is.index[-1] < first_oos.index[0]
    assert first_is.index.intersection(first_oos.index).empty


def test_walk_forward_evaluate_reports_window_metadata():
    idx = pd.date_range("2024-01-01", periods=14, freq="1D")
    df = pd.DataFrame({"ret": np.linspace(0.001, 0.014, len(idx))}, index=idx)

    wf = WalkForward(is_days=4, oos_days=2)
    results = wf.evaluate(df, lambda _is, oos: oos["ret"], periods=365)

    assert {"is_end", "oos_end", "is_n", "oos_n"}.issubset(results.columns)
    assert (results["is_n"] > 0).all()
    assert (results["oos_n"] > 0).all()
    assert (results["is_end"] < results["oos_start"]).all()


def test_walk_forward_accepts_result_dict_with_returns():
    idx = pd.date_range("2024-01-01", periods=14, freq="1D")
    df = pd.DataFrame({"ret": np.linspace(0.001, 0.014, len(idx))}, index=idx)

    wf = WalkForward(is_days=4, oos_days=2)
    results = wf.evaluate(df, lambda _is, oos: {"returns": oos["ret"]}, periods=365)

    assert "result" in results.columns
    assert (results["oos_n"] > 0).all()


def test_cpcv_split_keeps_non_test_groups_after_each_test_block():
    idx = pd.date_range("2024-01-01", periods=12, freq="1D")
    df = pd.DataFrame({"ret": np.linspace(0.01, 0.12, len(idx))}, index=idx)

    cv = CPCV(n_splits=6, k_test=2, embargo_pct=0.0, purge_size=1)
    target_test = np.array([2, 3, 8, 9])

    matching_split = None
    for train_idx, test_idx in cv.split(df):
        if np.array_equal(test_idx, target_test):
            matching_split = (train_idx, test_idx)
            break

    assert matching_split is not None
    train_idx, _ = matching_split
    assert np.array_equal(train_idx, np.array([0, 4, 5, 6, 10, 11]))


def test_cpcv_evaluate_builds_path_level_metrics():
    idx = pd.date_range("2024-01-01", periods=8, freq="1D")
    df = pd.DataFrame({"ret": np.linspace(0.01, 0.08, len(idx))}, index=idx)

    cv = CPCV(n_splits=4, k_test=2, embargo_pct=0.0, purge_size=0)
    results = cv.evaluate(df, lambda _train, test: test["ret"], periods=365)

    assert results["n_combinations"] == 6
    assert results["n_paths"] == 3
    assert len(results["path_sharpes"]) == 3
    assert len(results["sharpe_list"]) == 6
    assert np.isfinite(results["overall_oos_sharpe"])


def test_cpcv_accepts_result_dict_with_returns():
    idx = pd.date_range("2024-01-01", periods=8, freq="1D")
    df = pd.DataFrame({"ret": np.linspace(0.01, 0.08, len(idx))}, index=idx)

    cv = CPCV(n_splits=4, k_test=2, embargo_pct=0.0, purge_size=0)
    results = cv.evaluate(df, lambda _train, test: {"returns": test["ret"]}, periods=365)

    assert results["n_combinations"] == 6
    assert results["mean_oos_sharpe"] > 0


def test_cpcv_dsr_does_not_exceed_psr_when_multiple_paths_exist():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=60, freq="1h")
    df = pd.DataFrame({"ret": rng.normal(0.0002, 0.005, len(idx))}, index=idx)

    cv = CPCV(n_splits=6, k_test=2, embargo_pct=0.0, purge_size=0)
    results = cv.evaluate(df, lambda _train, test: test["ret"], periods=365 * 24, n_trials=27)

    assert results["n_paths"] > 1
    assert results["n_trials"] == 27
    assert results["dsr"] <= results["psr"]


def test_cpcv_n_trials_changes_deflated_sharpe_penalty():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2024-01-01", periods=60, freq="1h")
    df = pd.DataFrame({"ret": rng.normal(0.0002, 0.005, len(idx))}, index=idx)

    cv = CPCV(n_splits=6, k_test=2, embargo_pct=0.0, purge_size=0)
    low_trials = cv.evaluate(df, lambda _train, test: test["ret"], periods=365 * 24, n_trials=5)
    high_trials = cv.evaluate(df, lambda _train, test: test["ret"], periods=365 * 24, n_trials=50)

    assert low_trials["n_trials"] == 5
    assert high_trials["n_trials"] == 50
    assert high_trials["dsr"] <= low_trials["dsr"]


def test_generic_replay_strategy_fn_runs_train_and_oos_windows():
    idx = pd.date_range("2024-01-01", periods=8, freq="1h", tz="UTC")
    df = pd.DataFrame({"event_count": 1}, index=idx)
    cfg = AppConfig(
        system=SystemConfig(mode="demo", symbols=["BTC-USDT-SWAP"], equity_usd=10_000.0),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(okx_api_key="x", okx_secret="y", okx_passphrase="z"),
    )
    calls = []

    def runner(strategy_names, cfg, data_dir, start, end, bar, periods):
        calls.append((start, end))
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        ridx = pd.date_range(start_ts, end_ts - pd.Timedelta(hours=1), freq="1h", tz="UTC")
        returns = pd.Series(np.full(len(ridx), 0.001), index=(ridx.view("int64") // 1_000_000))
        return ReplayBacktestResult(
            returns=returns,
            equity_curve=pd.Series(dtype=float),
            metrics={"sharpe": 1.5, "total_return": 0.01, "max_drawdown": -0.02},
            order_log=pd.DataFrame([{"cl_ord_id": "o"}]),
            fill_log=pd.DataFrame([{"cl_ord_id": "o"}]),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    strategy_fn = make_replay_strategy_fn(
        strategy_names=["pairs_trading"],
        cfg=cfg,
        include_train_metrics=True,
        runner=runner,
    )
    result = strategy_fn(df.iloc[:4], df.iloc[4:])

    assert len(calls) == 2
    assert len(result["returns"]) == 4
    assert isinstance(result["returns"].index, pd.DatetimeIndex)
    assert result["is_metrics"]["sharpe"] == pytest.approx(1.5)
    assert result["oos_order_count"] == 1
    assert result["returns_source"] == "replay_window"


def test_run_replay_validations_serializes_wf_and_cpcv(monkeypatch):
    idx = pd.date_range("2024-01-01", periods=30, freq="1D", tz="UTC")
    df = pd.DataFrame({"event_count": 1}, index=idx)
    cfg = AppConfig(
        system=SystemConfig(mode="demo", symbols=["BTC-USDT-SWAP"], equity_usd=10_000.0),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(okx_api_key="x", okx_secret="y", okx_passphrase="z"),
    )
    monkeypatch.setattr("backtesting.replay.build_replay_validation_frame", lambda **_: df)

    def runner(strategy_names, cfg, data_dir, start, end, bar, periods):
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        ridx = pd.date_range(start_ts, end_ts - pd.Timedelta(days=1), freq="1D", tz="UTC")
        returns = pd.Series(np.full(len(ridx), 0.001), index=(ridx.view("int64") // 1_000_000))
        return ReplayBacktestResult(
            returns=returns,
            equity_curve=pd.Series(dtype=float),
            metrics={"sharpe": 1.2, "total_return": 0.01, "max_drawdown": -0.01},
            order_log=pd.DataFrame(),
            fill_log=pd.DataFrame(),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    progress_updates = []
    validation = run_replay_validations(
        strategy_names=["pairs_trading"],
        cfg=cfg,
        mode="both",
        wf_is_days=10,
        wf_oos_days=5,
        cpcv_n_splits=3,
        cpcv_k_test=1,
        cpcv_embargo_pct=0.0,
        cpcv_purge_size=0,
        runner=runner,
        progress_callback=progress_updates.append,
    )

    assert validation["walk_forward"]
    assert "oos_sharpe" in validation["walk_forward"][0]
    assert validation["cpcv"]["n_combinations"] == 3
    assert len(validation["cpcv"]["combos"]) == 3
    assert "dsr" in validation["cpcv"]
    assert any(update["message"].startswith("Walk-Forward window") for update in progress_updates)
    assert any(update["message"].startswith("CPCV combination") for update in progress_updates)


def _gate_result(metrics: dict) -> ReplayBacktestResult:
    return ReplayBacktestResult(
        returns=pd.Series(dtype=float),
        equity_curve=pd.Series(dtype=float),
        metrics=metrics,
        order_log=pd.DataFrame(),
        fill_log=pd.DataFrame(),
        funding_log=pd.DataFrame(),
        trade_log=pd.DataFrame(),
        validation={},
    )


def _gate_feed() -> HistoricalEventFeed:
    ts = pd.date_range("2024-01-01 00:00:00+00:00", periods=5, freq="1min")
    market_events = pd.DataFrame({
        "ts": (ts.view("int64") // 1_000_000).astype("int64"),
        "inst_id": ["BTC-USDT-SWAP"] * len(ts),
        "bid_px_0": [100.0] * len(ts),
        "bid_sz_0": [1.0] * len(ts),
        "ask_px_0": [101.0] * len(ts),
        "ask_sz_0": [1.0] * len(ts),
    })
    return HistoricalEventFeed(market_events=market_events, funding_events=pd.DataFrame())


def test_gate2_fill_rate_warning_triggers_when_low():
    result = _gate_result({
        "fill_rate": 0.02,
        "submitted_order_count": 10,
        "funding_settlement_count": 0,
    })

    _apply_post_run_gates(
        result,
        ["ma_crossover"],
        {"coverage_pct": 1.0, "note": "no_range_specified"},
    )

    assert result.validation["gate2_fill_rate_warning"] is True
    assert result.validation["gate2_fill_rate"] == pytest.approx(0.02)


def test_gate2_fill_rate_warning_does_not_trigger_when_acceptable():
    result = _gate_result({
        "fill_rate": 0.50,
        "submitted_order_count": 10,
        "funding_settlement_count": 0,
    })

    _apply_post_run_gates(
        result,
        ["ma_crossover"],
        {"coverage_pct": 1.0, "note": "no_range_specified"},
    )

    assert result.validation["gate2_fill_rate_warning"] is False


def test_gate3_data_coverage_raises_when_below_threshold():
    feed = _gate_feed()

    coverage = _compute_data_coverage(feed, "2024-01-01", "2024-12-31", "1H")

    assert coverage["coverage_pct"] < 0.80
    with pytest.raises(ValueError, match="Gate 3: data coverage"):
        _check_data_coverage_gate(coverage)


def test_gate3_data_coverage_skips_when_range_absent():
    feed = _gate_feed()

    coverage = _compute_data_coverage(feed, None, None, "1H")

    assert coverage["coverage_pct"] == pytest.approx(1.0)
    assert coverage["note"] == "no_range_specified"
    _check_data_coverage_gate(coverage)


def test_gate4_funding_coverage_warning_triggers_for_funding_carry():
    result = _gate_result({
        "fill_rate": 0.50,
        "submitted_order_count": 5,
        "funding_settlement_count": 0,
    })

    _apply_post_run_gates(
        result,
        ["funding_carry"],
        {"coverage_pct": 1.0, "note": "no_range_specified"},
    )

    assert result.validation["gate4_funding_coverage_warning"] is True


def test_gate4_funding_coverage_warning_does_not_trigger_for_other_strategies():
    result = _gate_result({
        "fill_rate": 0.50,
        "submitted_order_count": 5,
        "funding_settlement_count": 0,
    })

    _apply_post_run_gates(
        result,
        ["ma_crossover"],
        {"coverage_pct": 1.0, "note": "no_range_specified"},
    )

    assert result.validation["gate4_funding_coverage_warning"] is False


def test_save_backtest_artifacts_writes_validation_to_result_json(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKTEST_ARTIFACT_MODE", "files")
    cfg = AppConfig(
        system=SystemConfig(mode="demo", symbols=["BTC-USDT-SWAP"], equity_usd=10_000.0),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(okx_api_key="x", okx_secret="y", okx_passphrase="z"),
    )
    result = ReplayBacktestResult(
        returns=pd.Series([0.0, 0.001], index=[1_704_067_200_000, 1_704_070_800_000]),
        equity_curve=pd.Series([10_000.0, 10_010.0], index=[1_704_067_200_000, 1_704_070_800_000]),
        metrics={"sharpe": 1.0},
        order_log=pd.DataFrame(),
        fill_log=pd.DataFrame(),
        funding_log=pd.DataFrame(),
        trade_log=pd.DataFrame(),
    )

    run_dir = save_backtest_artifacts(
        result=result,
        cfg=cfg,
        args=SimpleNamespace(strategy=["pairs_trading"], start="2024-01-01", end="2024-01-02", bar="1H"),
        output_dir=str(tmp_path),
        run_id="validation_result",
        strategy_names=["pairs_trading"],
        start="2024-01-01",
        end="2024-01-02",
        bar="1H",
        validation_results={
            "walk_forward": [{"window": 0, "oos_sharpe": 1.23}],
            "cpcv": {"dsr": 0.97, "psr": 0.95, "combos": [{"i": 0, "sharpe": 1.0}]},
            "validation_frame_rows": 2,
        },
    )

    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["walk_forward"][0]["oos_sharpe"] == pytest.approx(1.23)
    assert payload["cpcv"]["dsr"] == pytest.approx(0.97)
    assert payload["validation"]["validation_frame_rows"] == 2


def test_save_backtest_artifacts_mirrors_fill_all_signals_to_idealized_fill(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKTEST_ARTIFACT_MODE", "files")
    cfg = AppConfig(
        system=SystemConfig(mode="demo", symbols=["BTC-USDT-SWAP"], equity_usd=10_000.0),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(okx_api_key="x", okx_secret="y", okx_passphrase="z"),
    )
    result = ReplayBacktestResult(
        returns=pd.Series([0.0, 0.001], index=[1_704_067_200_000, 1_704_070_800_000]),
        equity_curve=pd.Series([10_000.0, 10_010.0], index=[1_704_067_200_000, 1_704_070_800_000]),
        metrics={"sharpe": 1.0},
        order_log=pd.DataFrame(),
        fill_log=pd.DataFrame(),
        funding_log=pd.DataFrame(),
        trade_log=pd.DataFrame(),
        validation={"fill_all_signals": True},
    )

    run_dir = save_backtest_artifacts(
        result=result,
        cfg=cfg,
        args=SimpleNamespace(strategy=["ma_crossover"], start="2024-01-01", end="2024-01-02", bar="1H"),
        output_dir=str(tmp_path),
        run_id="idealized_fill_result",
        strategy_names=["ma_crossover"],
        start="2024-01-01",
        end="2024-01-02",
        bar="1H",
    )

    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["validation"]["fill_all_signals"] is True
    assert payload["validation"]["idealized_fill"] is True


def test_indicator_series_uses_warmup_candles_before_trimming(monkeypatch):
    ts = pd.date_range("2024-01-01 00:00:00+00:00", periods=4, freq="1h")
    price_df = pd.DataFrame({
        "ts": ts,
        "datetime": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inst_id": ["BTC-USDT-SWAP"] * 4,
        "close": [100.0, 101.0, 102.0, 103.0],
    })
    warm_ts = pd.date_range("2023-12-31 21:00:00+00:00", periods=3, freq="1h")
    warm_df = pd.DataFrame({
        "ts": warm_ts,
        "inst_id": ["BTC-USDT-SWAP"] * 3,
        "close": [97.0, 98.0, 99.0],
    })

    def fake_fetch(dsn, inst_ids, bar, start_ts, lookback_bars):
        assert dsn == "postgres://unit"
        assert inst_ids == ["BTC-USDT-SWAP"]
        assert bar == "1H"
        assert lookback_bars == 3
        return {"BTC-USDT-SWAP": warm_df}

    monkeypatch.setattr("backtesting.artifacts._fetch_warmup_candles", fake_fetch)
    cfg = SimpleNamespace(strategies=StrategiesConfig(ma_crossover={
        "fast_window": 2,
        "slow_window": 4,
        "indicator_db_warmup": True,
    }))

    out = _build_indicator_series_df(price_df, cfg, ["ma_crossover"], dsn="postgres://unit", bar="1H")

    assert len(out) == 4
    assert out["ts"].tolist() == price_df["ts"].tolist()
    assert np.isfinite(out["fast_value"]).all()
    assert np.isfinite(out["slow_value"]).all()
    assert out["slow_value"].iloc[0] == pytest.approx((97.0 + 98.0 + 99.0 + 100.0) / 4)
    assert set(out["warmup_source"]) == {"db"}


def test_indicator_series_trims_leading_rows_when_warmup_missing(monkeypatch):
    ts = pd.date_range("2024-01-01 00:00:00+00:00", periods=6, freq="1h")
    price_df = pd.DataFrame({
        "ts": ts,
        "datetime": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inst_id": ["BTC-USDT-SWAP"] * 6,
        "close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
    })
    monkeypatch.setattr("backtesting.artifacts._fetch_warmup_candles", lambda *args, **kwargs: {})
    cfg = SimpleNamespace(strategies=StrategiesConfig(ma_crossover={"fast_window": 3, "slow_window": 5}))

    out = _build_indicator_series_df(price_df, cfg, ["ma_crossover"], dsn=None, bar="1H")

    assert pd.Timestamp(out["ts"].iloc[0]) == ts[2]
    assert np.isfinite(out["fast_value"].iloc[0])
    assert pd.isna(out["slow_value"].iloc[0])
    assert set(out["warmup_source"]) == {"cold"}
    both_empty = out["fast_value"].isna() & out["slow_value"].isna()
    assert not both_empty.iloc[0]


def test_indicator_series_ema_macd_default_cold_start_does_not_fetch_db(monkeypatch):
    ts = pd.date_range("2024-01-01 00:00:00+00:00", periods=8, freq="1h")
    price_df = pd.DataFrame({
        "ts": ts,
        "datetime": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inst_id": ["BTC-USDT-SWAP"] * len(ts),
        "close": [100.0, 101.0, 103.0, 102.0, 104.0, 106.0, 105.0, 107.0],
    })

    def fail_fetch(*args, **kwargs):
        raise AssertionError("DB warmup should be opt-in for indicator artifacts")

    monkeypatch.setattr("backtesting.artifacts._fetch_warmup_candles", fail_fetch)
    cfg = SimpleNamespace(strategies=StrategiesConfig(
        ema_crossover={"fast_span": 2, "slow_span": 4},
        macd_crossover={"fast_span": 2, "slow_span": 4, "signal_span": 2},
    ))

    out = _build_indicator_series_df(
        price_df,
        cfg,
        ["ema_crossover", "macd_crossover"],
        dsn="postgres://unit",
        bar="1H",
    )

    assert set(out["strategy"]) == {"ema_crossover", "macd_crossover"}
    assert set(out["warmup_source"]) == {"cold"}
    for _, group in out.groupby("strategy"):
        assert pd.Timestamp(group["ts"].iloc[0]) == ts[0]


def test_save_artifacts_records_indicator_warmup_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKTEST_ARTIFACT_MODE", "files")
    idx = pd.date_range("2024-01-01 00:00:00+00:00", periods=6, freq="1h")
    result = SimpleNamespace(
        equity_curve=pd.Series([10_000.0, 10_010.0], index=idx[:2]),
        metrics={
            "total_return": 0.001,
            "sharpe": 0.5,
            "max_drawdown": 0.0,
            "profit_factor": 1.0,
            "order_count": 0,
            "fill_rate": 0.0,
            "bankrupt": False,
        },
        order_log=pd.DataFrame(),
        fill_log=pd.DataFrame(),
        funding_log=pd.DataFrame(),
        trade_log=pd.DataFrame(),
        price_log=pd.DataFrame({
            "ts": idx,
            "inst_id": ["BTC-USDT-SWAP"] * len(idx),
            "open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0],
            "close": [100.0, 101.0, 103.0, 102.0, 104.0, 106.0],
            "vol": [1.0] * len(idx),
        }),
        signal_log=[],
        risk_event_log=[],
        rejected_log=[],
        cancel_log=[],
        validation={},
    )
    cfg = SimpleNamespace(
        storage=SimpleNamespace(timescale_dsn=None, candle_backend="parquet"),
        strategies=StrategiesConfig(ema_crossover={"fast_span": 2, "slow_span": 4}),
    )
    args = SimpleNamespace(strategy=["ema_crossover"], start="2024-01-01", end="2024-01-02", bar="1H")

    run_dir = save_backtest_artifacts(
        result=result,
        cfg=cfg,
        args=args,
        output_dir=str(tmp_path),
        run_id="indicator_sources",
        strategy_names=["ema_crossover"],
        start="2024-01-01",
        end="2024-01-02",
        bar="1H",
    )

    indicators = pd.read_csv(run_dir / "indicator_series.csv")
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))

    assert set(indicators["warmup_source"]) == {"cold"}
    assert payload["validation"]["indicator_warmup_sources"] == {
        "ema_crossover": {"BTC-USDT-SWAP": "cold"}
    }


def test_load_funding_derives_apr_when_missing(tmp_path):
    data_dir = tmp_path / "data" / "ticks" / "BTC_USDT_SWAP"
    data_dir.mkdir(parents=True)

    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=3, freq="8h"),
        "rate": [0.0001, -0.0002, 0.0003],
        "realized_rate": [0.0001, -0.0002, 0.0003],
    })
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), data_dir / "funding.parquet")

    loaded = load_funding("BTC-USDT-SWAP", data_dir=str(tmp_path / "data" / "ticks"))

    expected_apr = loaded["rate"] * (365 * 24 / 8)
    pd.testing.assert_series_equal(loaded["apr"], expected_apr, check_names=False)


def test_compute_returns_supports_simple_and_log_modes():
    candles = pd.DataFrame({"close": [100.0, 110.0, 121.0]})

    simple_returns = compute_returns(candles, method="simple")
    log_returns = compute_returns(candles, method="log")

    assert np.allclose(simple_returns.to_numpy(), np.array([0.1, 0.1]))
    assert np.allclose(log_returns.to_numpy(), np.log(np.array([1.1, 1.1])))


def test_compute_returns_rejects_unknown_method():
    candles = pd.DataFrame({"close": [100.0, 110.0]})

    with pytest.raises(ValueError, match="method must be either 'simple' or 'log'"):
        compute_returns(candles, method="weird")


def test_replay_backtest_funding_carry_runs_dual_leg(tmp_path):
    data_dir = tmp_path / "data" / "ticks" / "BTC_USDT_SWAP"
    data_dir.mkdir(parents=True)
    spot_data_dir = tmp_path / "data" / "ticks" / "BTC_USDT"
    spot_data_dir.mkdir(parents=True)

    candles = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC"),
        "open": [100.0, 101.0, 102.0, 103.0],
        "high": [101.0, 102.0, 103.0, 104.0],
        "low": [99.0, 100.0, 101.0, 102.0],
        "close": [100.0, 101.0, 102.0, 103.0],
        "vol": [10.0, 10.0, 10.0, 10.0],
    })
    spot_candles = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC"),
        "open": [100.0, 101.0, 102.0, 101.0],
        "high": [101.0, 102.0, 103.0, 102.0],
        "low": [99.0, 100.0, 101.0, 100.0],
        "close": [100.0, 101.0, 102.0, 101.0],
        "vol": [10.0, 10.0, 10.0, 10.0],
    })
    funding = pd.DataFrame({
        "ts": pd.to_datetime([
            "2024-01-01 02:00:00+00:00",
            "2024-01-01 03:00:00+00:00",
        ]),
        "rate": [0.0002, 0.0002],
    })
    pq.write_table(pa.Table.from_pandas(candles, preserve_index=False), data_dir / "candles_1H.parquet")
    pq.write_table(pa.Table.from_pandas(spot_candles, preserve_index=False), spot_data_dir / "candles_1H.parquet")
    pq.write_table(pa.Table.from_pandas(funding, preserve_index=False), data_dir / "funding.parquet")

    cfg = AppConfig(
        system=SystemConfig(
            mode="demo",
            symbols=["BTC-USDT-SWAP"],
            spot_symbols=["BTC-USDT"],
            equity_usd=10_000.0,
        ),
        strategies=StrategiesConfig(),
        risk=RiskConfig(
            max_order_notional_usd=10_000.0,
            max_pos_pct_equity=1.0,
            max_leverage=3.0,
            max_daily_loss_pct=0.2,
            soft_drawdown_pct=0.3,
            hard_drawdown_pct=0.5,
            stale_quote_pct=0.2,
        ),
        secrets=OKXSecrets.model_construct(
            okx_api_key="x",
            okx_secret="y",
            okx_passphrase="z",
            telegram_token=None,
            telegram_chat_id=None,
        ),
    )
    cfg = _use_okx_registry(cfg)

    result = run_replay_backtest(
        strategy_names=["funding_carry"],
        cfg=cfg,
        data_dir=str(tmp_path / "data" / "ticks"),
        start="2024-01-01 00:00:00+00:00",
        end="2024-01-01 04:00:00+00:00",
    )

    assert len(result.order_log) >= 2
    assert len(result.fill_log) >= 2
    assert set(result.fill_log["inst_id"]) == {"BTC-USDT-SWAP", "BTC-USDT"}
    assert len(result.funding_log) == 1
    assert result.funding_log["cashflow"].iloc[0] > 0
    assert result.metrics["funding_settlement_count"] == 1
    assert result.metrics["funding_cashflow"] > 0
    assert result.metrics["fill_rate"] > 0
    assert "psr" in result.metrics
    assert "dsr" in result.metrics
    assert result.metrics["dsr"] == pytest.approx(result.metrics["psr"])
    assert not result.returns.empty
    # ct_val provenance must end up on result.validation so the deployment gate
    # can audit where each symbol's ctVal came from. BTC comes from the YAML
    # registry (non-authoritative), spot pair is spot_unit (authoritative);
    # therefore ct_val_all_authoritative=False and gate_passed=False.
    validation = result.validation or {}
    assert "ct_val_sources" in validation
    assert validation["ct_val_sources"]["BTC-USDT-SWAP"]["source"] in {"db", "registry", "hardcoded_btc_eth"}
    assert validation["ct_val_sources"]["BTC-USDT"]["source"] == "spot_unit"
    assert "ct_val_all_authoritative" in validation
    assert "ct_val_gate_passed" in validation


def test_replay_funding_falls_back_to_avg_entry_when_mark_price_missing(monkeypatch):
    cfg = AppConfig(
        system=SystemConfig(
            mode="demo",
            symbols=["BTC-USDT-SWAP"],
            spot_symbols=["BTC-USDT"],
            equity_usd=10_000.0,
        ),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(
            okx_api_key="x",
            okx_secret="y",
            okx_passphrase="z",
            telegram_token=None,
            telegram_chat_id=None,
        ),
    )
    cfg = _use_okx_registry(cfg)
    engine = ReplayBacktestEngine(cfg, strategy_names=["funding_carry"])
    positions = PositionLedger(initial_equity=10_000.0)
    positions.on_fill(
        "BTC-USDT-SWAP",
        "sell",
        fill_px=100.0,
        fill_sz=10.0,
        fee=0.0,
        strategy="funding_carry",
    )
    positions.get_position("BTC-USDT-SWAP").last_price = 0.0
    recorder = ReplayRecorder(initial_equity=10_000.0)
    warnings = []
    monkeypatch.setattr(
        "backtesting.replay.logger.warning",
        lambda message, **kwargs: warnings.append((message, kwargs)),
    )

    engine._settle_funding(
        MarketPayload(
            inst_id="BTC-USDT-SWAP",
            ts=1_704_078_000_000,
            bids=[],
            asks=[],
            seq_id=0,
            channel="funding-rate",
            funding_rate=0.0002,
        ),
        positions,
        recorder,
    )

    assert warnings
    assert "falling back to avg_entry" in warnings[0][0]
    assert len(recorder.funding_log) == 1
    assert recorder.funding_log[0]["cashflow"] > 0


def _terminal_book(engine: ReplayBacktestEngine, inst_id: str, bid: float, ask: float):
    from okx_quant.data.okx_book import OkxBook

    book = OkxBook(inst_id)
    engine._apply_book_snapshot(
        book,
        MarketPayload(
            inst_id=inst_id,
            ts=1_704_067_200_000,
            bids=[[str(bid), "10"]],
            asks=[[str(ask), "10"]],
            seq_id=0,
            channel="books",
        ),
    )
    return book


def test_execution_metrics_exclude_terminal_liquidation_from_submitted_order_fill_count():
    recorder = ReplayRecorder(initial_equity=10_000.0)
    recorder.order_log.append({
        "ts": 1,
        "cl_ord_id": "strategy-entry",
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "px": 100.0,
        "sz": "1",
        "strategy": "unit",
        "notional_usd": 100.0,
    })
    recorder.fill_log.append({
        "ts": 2,
        "cl_ord_id": "terminal-close",
        "ord_id": "terminal-close",
        "inst_id": "BTC-USDT-SWAP",
        "side": "sell",
        "fill_px": 101.0,
        "fill_sz": 1.0,
        "fee": 0.0,
        "notional_usd": 101.0,
        "strategy": "terminal_liquidation",
        "state": "filled",
        "metadata": {"action": "terminal_liquidation"},
    })

    metrics = recorder._execution_metrics(pd.Series([0.0, 0.01], index=[1, 2]))

    assert metrics["real_fill_count"] == 1
    assert metrics["terminal_liquidation_fill_count"] == 1
    assert metrics["submitted_order_fill_count"] == 0
    assert metrics["orders_filled_count"] == 0
    assert metrics["fill_rate"] == 0.0


def test_replay_terminal_liquidation_closes_open_swap_position(minimal_cfg):
    engine = ReplayBacktestEngine(_use_okx_registry(minimal_cfg), strategy_names=["funding_carry"])
    positions = PositionLedger(initial_equity=10_000.0)
    positions.on_fill(
        "BTC-USDT-SWAP",
        "buy",
        fill_px=100.0,
        fill_sz=10.0,
        fee=0.0,
        strategy="unit",
        ts=1,
        metadata={"ct_val": 0.01},
    )
    recorder = ReplayRecorder(initial_equity=10_000.0)

    validation, metrics = engine._liquidate_terminal_positions(
        positions=positions,
        recorder=recorder,
        books={"BTC-USDT-SWAP": _terminal_book(engine, "BTC-USDT-SWAP", 109.0, 111.0)},
        ts=2,
        liquidate_on_end=True,
    )

    assert positions.get_all_positions() == {}
    assert validation["terminal_positions_before"]["BTC-USDT-SWAP"]["size"] == pytest.approx(10.0)
    assert validation["terminal_positions_after"] == {}
    assert validation["terminal_liquidation_fill_count"] == 1
    assert validation["terminal_liquidation_notional_usd"] == pytest.approx(11.0)
    assert metrics["terminal_liquidation_notional_usd"] == pytest.approx(11.0)
    assert metrics["bankrupt"] is False
    terminal_fill = recorder.fill_log[-1]
    assert terminal_fill["metadata"]["action"] == "terminal_liquidation"
    assert terminal_fill["metadata"]["terminal_price_source"] == "last_mid"
    assert terminal_fill["metadata"]["notional_usd"] == pytest.approx(11.0)
    terminal_trade = positions.get_trade_log()[-1]
    assert terminal_trade["realized_pnl"] == pytest.approx(1.0)
    assert terminal_trade["metadata"]["ct_val"] == pytest.approx(0.01)


def test_default_instrument_specs_uses_db_lot_and_min_size(minimal_cfg, monkeypatch):
    # Regression: replay used to hardcode minSz/lotSz=0.01 for every swap, which
    # is too coarse for finer venues (Binance perp lot_size=0.001) and silently
    # rounded small vol-target orders down to 0. The DB spec must win.
    cfg = _use_okx_registry(minimal_cfg)
    monkeypatch.setattr(
        ReplayBacktestEngine,
        "_load_db_instrument_specs",
        lambda self, exchange="okx": {
            "BTC-USDT-SWAP": {
                "ct_val": 0.01,
                "lot_size": 0.001,
                "min_size": 0.001,
                "tick_size": 0.5,
            },
        },
    )
    engine = ReplayBacktestEngine(cfg, strategy_names=["funding_carry"])
    spec = engine._instrument_specs["BTC-USDT-SWAP"]
    assert spec["lotSz"] == 0.001
    assert spec["minSz"] == 0.001
    assert spec["tickSz"] == 0.5
    # Symbols absent from the DB keep the hardcoded fallback granularity.
    eth = engine._instrument_specs.get("ETH-USDT-SWAP")
    if eth is not None:
        assert eth["lotSz"] == 0.01


def test_replay_terminal_liquidation_can_be_disabled(minimal_cfg):
    engine = ReplayBacktestEngine(_use_okx_registry(minimal_cfg), strategy_names=["funding_carry"])
    positions = PositionLedger(initial_equity=10_000.0)
    positions.on_fill(
        "BTC-USDT-SWAP",
        "buy",
        fill_px=100.0,
        fill_sz=10.0,
        fee=0.0,
        strategy="unit",
        ts=1,
        metadata={"ct_val": 0.01},
    )
    recorder = ReplayRecorder(initial_equity=10_000.0)

    validation, metrics = engine._liquidate_terminal_positions(
        positions=positions,
        recorder=recorder,
        books={"BTC-USDT-SWAP": _terminal_book(engine, "BTC-USDT-SWAP", 109.0, 111.0)},
        ts=2,
        liquidate_on_end=False,
    )

    assert "BTC-USDT-SWAP" in positions.get_all_positions()
    assert recorder.fill_log == []
    assert validation["liquidate_on_end"] is False
    assert validation["terminal_positions_after"]["BTC-USDT-SWAP"]["size"] == pytest.approx(10.0)
    assert validation["terminal_positions_closed"] is False
    assert metrics["terminal_open_position_count"] == 1
    assert metrics["terminal_liquidation_fill_count"] == 0
    assert metrics["bankrupt"] is False


def test_replay_terminal_liquidation_flags_missing_price(minimal_cfg):
    engine = ReplayBacktestEngine(_use_okx_registry(minimal_cfg), strategy_names=["funding_carry"])
    positions = PositionLedger(initial_equity=10_000.0)
    positions.on_fill(
        "BTC-USDT-SWAP",
        "buy",
        fill_px=100.0,
        fill_sz=10.0,
        fee=0.0,
        strategy="unit",
        ts=1,
        metadata={"ct_val": 0.01},
    )
    positions.get_position("BTC-USDT-SWAP").last_price = 0.0
    recorder = ReplayRecorder(initial_equity=10_000.0)

    validation, metrics = engine._liquidate_terminal_positions(
        positions=positions,
        recorder=recorder,
        books={},
        ts=2,
        liquidate_on_end=True,
    )

    assert recorder.fill_log == []
    assert "BTC-USDT-SWAP" in positions.get_all_positions()
    assert validation["terminal_liquidation_missing_prices"] == [
        {"inst_id": "BTC-USDT-SWAP", "reason": "missing_last_mid_and_last_price"}
    ]
    assert validation["terminal_positions_after"]["BTC-USDT-SWAP"]["size"] == pytest.approx(10.0)
    assert metrics["bankrupt"] is True


def test_replay_terminal_liquidation_closes_multiple_legs(minimal_cfg):
    engine = ReplayBacktestEngine(_use_okx_registry(minimal_cfg), strategy_names=["funding_carry"])
    positions = PositionLedger(initial_equity=10_000.0)
    positions.on_fill(
        "BTC-USDT-SWAP",
        "sell",
        fill_px=100.0,
        fill_sz=10.0,
        fee=0.0,
        strategy="funding_carry",
        ts=1,
        metadata={"ct_val": 0.01},
    )
    positions.on_fill(
        "BTC-USDT",
        "buy",
        fill_px=100.0,
        fill_sz=1.0,
        fee=0.0,
        strategy="funding_carry",
        ts=1,
        metadata={"ct_val": 1.0},
    )
    recorder = ReplayRecorder(initial_equity=10_000.0)

    validation, metrics = engine._liquidate_terminal_positions(
        positions=positions,
        recorder=recorder,
        books={
            "BTC-USDT-SWAP": _terminal_book(engine, "BTC-USDT-SWAP", 99.0, 101.0),
            "BTC-USDT": _terminal_book(engine, "BTC-USDT", 100.0, 102.0),
        },
        ts=2,
        liquidate_on_end=True,
    )

    assert positions.get_all_positions() == {}
    assert set(validation["terminal_positions_before"]) == {"BTC-USDT-SWAP", "BTC-USDT"}
    assert validation["terminal_positions_after"] == {}
    assert validation["terminal_liquidation_fill_count"] == 2
    assert validation["terminal_liquidation_notional_usd"] == pytest.approx(10.0 + 101.0)
    assert metrics["terminal_open_position_count"] == 0
    assert metrics["bankrupt"] is False


def test_run_replay_backtest_cli_passes_no_liquidate_on_end(monkeypatch, minimal_cfg):
    from scripts import run_replay_backtest as cli

    calls = {}

    def fake_run_replay_backtest(**kwargs):
        calls.update(kwargs)
        return ReplayBacktestResult(
            returns=pd.Series([0.0], index=[1]),
            equity_curve=pd.Series([10_000.0], index=[1]),
            metrics={"bankrupt": False, "fill_rate": 0.0},
            order_log=pd.DataFrame(),
            fill_log=pd.DataFrame(),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    monkeypatch.setattr(cli, "load_config", lambda require_secrets=False: minimal_cfg)
    monkeypatch.setattr(cli, "run_replay_backtest", fake_run_replay_backtest)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_replay_backtest.py", "--strategy", "ma_crossover", "--no-liquidate-on-end"],
    )

    cli.main()

    assert calls["liquidate_on_end"] is False


def test_run_replay_backtest_cli_passes_instrument_specs_json(monkeypatch, minimal_cfg):
    from scripts import run_replay_backtest as cli

    calls = {}

    def fake_run_replay_backtest(**kwargs):
        calls.update(kwargs)
        return ReplayBacktestResult(
            returns=pd.Series([0.0], index=[1]),
            equity_curve=pd.Series([10_000.0], index=[1]),
            metrics={"bankrupt": False, "fill_rate": 0.0},
            order_log=pd.DataFrame(),
            fill_log=pd.DataFrame(),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    specs = {
        "BTC-USDT-SWAP": {
            "ctVal": 0.01,
            "minSz": 0.01,
            "lotSz": 0.01,
            "tickSz": 0.1,
            "tdMode": "cross",
        }
    }
    monkeypatch.setattr(cli, "load_config", lambda require_secrets=False: minimal_cfg)
    monkeypatch.setattr(cli, "run_replay_backtest", fake_run_replay_backtest)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_replay_backtest.py",
            "--strategy",
            "ma_crossover",
            "--instrument-specs-json",
            json.dumps(specs),
        ],
    )

    cli.main()

    assert calls["instrument_specs"] == specs


def test_run_replay_backtest_cli_enables_fill_all_signals(monkeypatch, minimal_cfg):
    from scripts import run_replay_backtest as cli

    calls = {}

    def fake_run_replay_backtest(**kwargs):
        calls.update(kwargs)
        return ReplayBacktestResult(
            returns=pd.Series([0.0], index=[1]),
            equity_curve=pd.Series([10_000.0], index=[1]),
            metrics={"bankrupt": False, "fill_rate": 0.0},
            order_log=pd.DataFrame(),
            fill_log=pd.DataFrame(),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    monkeypatch.setattr(cli, "load_config", lambda require_secrets=False: minimal_cfg)
    monkeypatch.setattr(cli, "run_replay_backtest", fake_run_replay_backtest)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_replay_backtest.py", "--strategy", "ma_crossover", "--fill-all-signals"],
    )

    cli.main()

    cfg = calls["cfg"]
    assert cfg.backtest.fill_all_signals is True
    assert cfg.backtest.queue_fill_fraction == pytest.approx(1.0)
    assert cfg.risk.max_order_notional_usd >= FILL_ALL_MAX_ORDER_NOTIONAL_USD
    assert cfg.risk.max_pos_pct_equity >= FILL_ALL_MAX_POS_PCT_EQUITY


def test_run_replay_backtest_cli_strategy_fill_profile_marks_result(monkeypatch, minimal_cfg, tmp_path):
    from scripts import run_replay_backtest as cli

    calls = {}
    saved = {}

    def fake_run_replay_backtest(**kwargs):
        calls.update(kwargs)
        return ReplayBacktestResult(
            returns=pd.Series([0.0], index=[1]),
            equity_curve=pd.Series([10_000.0], index=[1]),
            metrics={"total_return": 0.0, "fill_rate": 1.0, "real_fill_count": 1},
            order_log=pd.DataFrame([{"cl_ord_id": "o1"}]),
            fill_log=pd.DataFrame([{"cl_ord_id": "o1", "fill_sz": 1.0, "state": "filled", "fee": 0.0}]),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    def fake_save_backtest_artifacts(**kwargs):
        saved["validation"] = dict(kwargs["result"].validation)
        run_dir = tmp_path / kwargs["run_id"]
        run_dir.mkdir()
        return run_dir

    monkeypatch.setattr(cli, "load_config", lambda require_secrets=False: minimal_cfg)
    monkeypatch.setattr(cli, "run_replay_backtest", fake_run_replay_backtest)
    monkeypatch.setattr(cli, "save_backtest_artifacts", fake_save_backtest_artifacts)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_replay_backtest.py",
            "--strategy",
            "ma_crossover",
            "--execution-profile",
            "strategy_fill",
            "--save-artifacts",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "unit_profile",
        ],
    )

    cli.main()

    assert calls["cfg"].backtest.fill_all_signals is True
    assert saved["validation"]["execution_profile"] == "strategy_fill"
    assert saved["validation"]["idealized_fill"] is True


def test_run_replay_backtest_cli_dual_output_saves_two_runs_and_comparison(monkeypatch, minimal_cfg, tmp_path):
    from scripts import run_replay_backtest as cli

    saved_run_ids = []

    def fake_run_replay_backtest(**kwargs):
        is_strategy_fill = bool(kwargs["cfg"].backtest.fill_all_signals)
        total_return = 0.20 if is_strategy_fill else 0.05
        fill_rate = 1.0 if is_strategy_fill else 0.25
        return ReplayBacktestResult(
            returns=pd.Series([0.0, total_return], index=[1, 2]),
            equity_curve=pd.Series([10_000.0, 10_000.0 * (1 + total_return)], index=[1, 2]),
            metrics={
                "total_return": total_return,
                "max_drawdown": -0.01,
                "fill_rate": fill_rate,
                "submitted_order_count": 4,
                "real_fill_count": 4 if is_strategy_fill else 1,
                "submitted_order_fill_count": 4 if is_strategy_fill else 1,
                "terminal_liquidation_fill_count": 0,
            },
            order_log=pd.DataFrame([{"cl_ord_id": "o1"}]),
            fill_log=pd.DataFrame([{"cl_ord_id": "o1", "fill_sz": 1.0, "state": "filled", "fee": 0.0}]),
            funding_log=pd.DataFrame(),
            trade_log=pd.DataFrame(),
        )

    def fake_save_backtest_artifacts(**kwargs):
        saved_run_ids.append(kwargs["run_id"])
        run_dir = tmp_path / kwargs["run_id"]
        run_dir.mkdir()
        return run_dir

    monkeypatch.setattr(cli, "load_config", lambda require_secrets=False: minimal_cfg)
    monkeypatch.setattr(cli, "run_replay_backtest", fake_run_replay_backtest)
    monkeypatch.setattr(cli, "save_backtest_artifacts", fake_save_backtest_artifacts)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_replay_backtest.py",
            "--strategy",
            "macd_crossover",
            "--execution-profile",
            "dual_output",
            "--save-artifacts",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "unit_dual",
        ],
    )

    cli.main()

    assert saved_run_ids == ["unit_dual_strategy_fill", "unit_dual_realistic_execution"]
    comparison = json.loads((tmp_path / "unit_dual_execution_comparison.json").read_text(encoding="utf-8"))
    assert comparison["execution_profile"] == "dual_output"
    assert comparison["strategy_fill_run_id"] == "unit_dual_strategy_fill"
    assert comparison["realistic_execution_run_id"] == "unit_dual_realistic_execution"
    assert comparison["deltas"]["strategy_minus_realistic_return"] == pytest.approx(0.15)
    assert comparison["deltas"]["strategy_minus_realistic_fill_rate"] == pytest.approx(0.75)


def test_replay_feed_builder_tolerates_empty_requested_data(tmp_path):
    cfg = AppConfig(
        system=SystemConfig(
            mode="demo",
            symbols=["BTC-USDT-SWAP"],
            spot_symbols=["BTC-USDT"],
            equity_usd=10_000.0,
        ),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(
            okx_api_key="x",
            okx_secret="y",
            okx_passphrase="z",
            telegram_token=None,
            telegram_chat_id=None,
        ),
    )

    feed = build_feed_for_strategies(
        cfg,
        strategy_names=["funding_carry"],
        data_dir=str(tmp_path / "missing_data"),
    )

    assert feed.market_events.empty
    assert feed.funding_events.empty
    assert list(feed.iter_events()) == []


def test_historical_event_feed_emits_trade_ticks_before_same_timestamp_books():
    ts = 1_704_067_200_000
    feed = HistoricalEventFeed(
        market_events=pd.DataFrame([
            {
                "ts": ts,
                "inst_id": "BTC-USDT-SWAP",
                "bid_px_0": 99.9,
                "bid_sz_0": 1.0,
                "ask_px_0": 100.1,
                "ask_sz_0": 1.0,
            }
        ]),
        funding_events=pd.DataFrame([
            {
                "ts": ts,
                "inst_id": "BTC-USDT-SWAP",
                "funding_rate": 0.0,
            }
        ]),
        feature_events=pd.DataFrame(),
        trade_events=pd.DataFrame([
            {
                "ts": ts,
                "inst_id": "BTC-USDT-SWAP",
                "trade_id": "t1",
                "price": 100.0,
                "size": 0.5,
                "side": "buy",
            }
        ]),
    )

    events = list(feed.iter_events())

    assert [event.payload.channel for event in events] == ["trades", "books", "funding-rate"]
    assert events[0].payload.trade_id == "t1"


def test_load_trade_ticks_reads_feedstore_parquet_layout(tmp_path):
    inst_dir = tmp_path / "BTC_USDT_SWAP" / "2024-01-01"
    inst_dir.mkdir(parents=True)
    trades = pd.DataFrame(
        {
            "ts": pd.to_datetime([
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:00:01Z",
            ]),
            "trade_id": ["t1", "t2"],
            "price": [100.0, 101.0],
            "size": [0.5, 0.25],
            "side": ["buy", "sell"],
        }
    )
    pq.write_table(pa.Table.from_pandas(trades), inst_dir / "trades.parquet")

    loaded = load_trade_ticks(
        "BTC-USDT-SWAP",
        data_dir=str(tmp_path),
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T00:00:02Z",
    )

    assert list(loaded["trade_id"]) == ["t1", "t2"]
    assert loaded["price"].tolist() == [100.0, 101.0]
    assert str(loaded["ts"].dt.tz) == "None"
