"""Unit tests for backtesting data loaders and validation splitters."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from backtesting.cpcv import CPCV
from backtesting.data_loader import compute_returns, load_funding
from backtesting.replay import run_replay_backtest
from backtesting.walk_forward import WalkForward
from okx_quant.core.config import AppConfig, OKXSecrets, RiskConfig, StrategiesConfig, SystemConfig


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

    candles = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC"),
        "open": [100.0, 101.0, 102.0, 103.0],
        "high": [101.0, 102.0, 103.0, 104.0],
        "low": [99.0, 100.0, 101.0, 102.0],
        "close": [100.0, 101.0, 102.0, 103.0],
        "vol": [10.0, 10.0, 10.0, 10.0],
    })
    funding = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-01 02:00:00+00:00"]),
        "rate": [0.0002],
    })
    pq.write_table(pa.Table.from_pandas(candles, preserve_index=False), data_dir / "candles_1H.parquet")
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
    assert not result.returns.empty
