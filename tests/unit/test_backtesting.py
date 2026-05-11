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

from backtesting.artifacts import save_backtest_artifacts
from backtesting.cpcv import CPCV
from backtesting.data_loader import compute_returns, load_funding
from backtesting.replay import (
    ReplayBacktestEngine,
    ReplayBacktestResult,
    ReplayRecorder,
    build_feed_for_strategies,
    make_replay_strategy_fn,
    run_replay_backtest,
    run_replay_validations,
)
from backtesting.replay_validation import (
    ASMMReplayParamGrid,
    evaluate_replay_asmm_cpcv,
    replay_asmm_parameter_selection_returns,
)
from backtesting.walk_forward import WalkForward
from okx_quant.core.events import MarketPayload
from okx_quant.core.config import AppConfig, OKXSecrets, RiskConfig, StrategiesConfig, SystemConfig, load_config
from okx_quant.portfolio.positions import PositionLedger


def test_strategy_config_preserves_yaml_parameters_used_by_strategies():
    cfg = StrategiesConfig(**{
        "obi_market_maker": {"mlofi_weight": 0.7},
        "as_market_maker": {
            "mlofi_depth": 7,
            "mlofi_decay": 0.4,
            "mlofi_weight": 1.2,
            "elevated_size_multiplier": 0.6,
            "toxic_size_multiplier": 0.2,
        },
        "funding_carry": {
            "max_abs_basis_z": 1.8,
            "max_crowding": 0.75,
        },
        "pairs_trading": {
            "max_half_life_hours": 36.0,
            "max_hedge_uncertainty": 5.0,
        },
    })

    assert cfg.obi_market_maker.mlofi_weight == 0.7
    assert cfg.as_market_maker.mlofi_depth == 7
    assert cfg.as_market_maker.mlofi_decay == 0.4
    assert cfg.as_market_maker.mlofi_weight == 1.2
    assert cfg.as_market_maker.elevated_size_multiplier == 0.6
    assert cfg.as_market_maker.toxic_size_multiplier == 0.2
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
    cfg = minimal_cfg.model_copy(deep=True)
    cfg.strategies = StrategiesConfig(
        pairs_trading={
            "enabled": True,
            "symbol_y": "SOL-USDT-SWAP",
            "symbol_x": "ADA-USDT-SWAP",
        }
    )

    with pytest.raises(ValueError, match="Missing ctVal for non-BTC/ETH swap"):
        ReplayBacktestEngine(cfg, strategy_names=["pairs_trading"])


def test_replay_default_specs_allow_btc_eth_swaps(minimal_cfg):
    cfg = minimal_cfg.model_copy(deep=True)
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


def test_load_config_reads_backtest_execution_defaults():
    cfg = load_config(require_secrets=False)

    assert cfg.backtest.order_latency_ms == 0
    assert cfg.backtest.cancel_latency_ms == 200
    assert cfg.backtest.queue_fill_fraction == pytest.approx(0.20)


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


def test_cpcv_dsr_differs_from_psr_when_multiple_paths_exist():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=60, freq="1h")
    df = pd.DataFrame({"ret": rng.normal(0.0002, 0.005, len(idx))}, index=idx)

    cv = CPCV(n_splits=6, k_test=2, embargo_pct=0.0, purge_size=0)
    results = cv.evaluate(df, lambda _train, test: test["ret"], periods=365 * 24, n_trials=27)

    assert results["n_paths"] > 1
    assert results["n_trials"] == 27
    assert results["dsr"] != pytest.approx(results["psr"])


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


def _stub_replay_runner(strategy_names, cfg, data_dir, start, end, bar, periods):
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    idx = pd.date_range(start_ts, end_ts - pd.Timedelta(hours=1), freq="1h", tz="UTC")
    gamma = float(cfg.strategies.as_market_maker.gamma)
    noise = np.linspace(-1e-6, 1e-6, len(idx)) if len(idx) else np.array([])
    returns = pd.Series(gamma / 10_000.0 + noise, index=(idx.view("int64") // 1_000_000))
    metrics = {
        "sharpe": gamma,
        "dsr": gamma / 10.0,
        "psr": gamma / 10.0,
        "fill_rate": 1.0,
    }
    return ReplayBacktestResult(
        returns=returns,
        equity_curve=pd.Series(dtype=float),
        metrics=metrics,
        order_log=pd.DataFrame([{"cl_ord_id": "o"}]),
        fill_log=pd.DataFrame([{"cl_ord_id": "o"}]),
        funding_log=pd.DataFrame(),
        trade_log=pd.DataFrame(),
    )


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
    )

    assert validation["walk_forward"]
    assert "oos_sharpe" in validation["walk_forward"][0]
    assert validation["cpcv"]["n_combinations"] == 3
    assert len(validation["cpcv"]["combos"]) == 3
    assert "dsr" in validation["cpcv"]


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


def test_replay_asmm_parameter_selection_uses_is_and_oos_windows():
    idx = pd.date_range("2024-01-01", periods=8, freq="1h", tz="UTC")
    df = pd.DataFrame({"close": np.linspace(100.0, 107.0, len(idx))}, index=idx)
    cfg = AppConfig(
        system=SystemConfig(mode="demo", symbols=["BTC-USDT-SWAP"], equity_usd=10_000.0),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(okx_api_key="x", okx_secret="y", okx_passphrase="z"),
    )

    result = replay_asmm_parameter_selection_returns(
        df.iloc[:4],
        df.iloc[4:],
        cfg=cfg,
        param_grid=ASMMReplayParamGrid(gamma=(0.05, 0.2), kappa=(1.5,), beta_vpin=(2.0,)),
        runner=_stub_replay_runner,
    )

    assert result["selected_params"]["gamma"] == pytest.approx(0.2)
    assert len(result["returns"]) == 4
    assert isinstance(result["returns"].index, pd.DatetimeIndex)
    assert result["oos_order_count"] == 1
    assert result["returns_source"] == "replay_asmm_parameter_selection"


def test_replay_asmm_cpcv_marks_replay_cost_model():
    idx = pd.date_range("2024-01-01", periods=12, freq="1h", tz="UTC")
    df = pd.DataFrame({"close": np.linspace(100.0, 111.0, len(idx))}, index=idx)
    cfg = AppConfig(
        system=SystemConfig(mode="demo", symbols=["BTC-USDT-SWAP"], equity_usd=10_000.0),
        strategies=StrategiesConfig(),
        risk=RiskConfig(),
        secrets=OKXSecrets.model_construct(okx_api_key="x", okx_secret="y", okx_passphrase="z"),
    )

    results = evaluate_replay_asmm_cpcv(
        df,
        cfg=cfg,
        param_grid=ASMMReplayParamGrid(gamma=(0.1,), kappa=(1.5,), beta_vpin=(2.0,)),
        n_splits=3,
        k_test=1,
        embargo_pct=0.0,
        purge_size=0,
        runner=_stub_replay_runner,
    )

    assert results["n_combinations"] == 3
    assert results["n_trials"] == 1
    assert results["cost_model_complete"] is True
    assert results["calibration_required"] is True
    assert results["returns_source"] == "replay_asmm_parameter_selection"


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
