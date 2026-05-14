"""
Tests for ohlcv_rotation strategy — Phase 1 (vectorised backtest).

All tests use synthetic DataFrames; no DB or parquet files required.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtesting"))

from okx_quant.strategies.ohlcv_rotation import (
    OHLCVRotationParams,
    apply_exit_rules,
    build_feature_panel,
    compute_benchmark_regime,
    compute_cross_sectional_scores,
    generate_target_weights,
)
from ohlcv_rotation_backtest import (
    BacktestResult,
    compute_cost,
    compute_metrics,
    compute_turnover,
    run_ohlcv_rotation_backtest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_index(n: int = 500) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="1min")


def _make_close(
    index: pd.DatetimeIndex,
    inst_ids: list[str],
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {}
    for i, inst in enumerate(inst_ids):
        returns = rng.normal(0.0001 * (i + 1), 0.001, len(index))
        price = 100.0 * np.exp(np.cumsum(returns))
        data[inst] = price
    return pd.DataFrame(data, index=index)


def _make_ohlcv(
    index: pd.DatetimeIndex,
    inst_ids: list[str],
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    close = _make_close(index, inst_ids, seed)
    dfs: dict[str, pd.DataFrame] = {}
    rng = np.random.default_rng(seed + 1)
    for inst in inst_ids:
        c = close[inst].values
        noise = 1 + rng.uniform(0.0, 0.003, len(index))
        h = c * noise
        l = c / noise
        o = c * (1 + rng.uniform(-0.001, 0.001, len(index)))
        v = rng.uniform(100, 200, len(index))
        dfs[inst] = pd.DataFrame(
            {"open": o, "high": h, "low": l, "close": c, "vol": v}, index=index
        )
    return dfs


def _minimal_params(universe: list[str]) -> OHLCVRotationParams:
    return OHLCVRotationParams(
        universe=universe,
        benchmark_inst_id=universe[0],
        rebalance_minutes=60,
        top_k=2,
        rank_exit_buffer=4,
        lookback_fast_minutes=20,
        lookback_slow_minutes=60,
        volume_z_window_minutes=20,
        realized_vol_window_minutes=60,
        breakout_window_minutes=30,
        ema_window_minutes=20,
        benchmark_ema_window_minutes=60,
        atr_window_minutes=20,
        min_volume_z=0.0,  # permissive for most tests
        fee_bps=2.0,
        slippage_bps=2.0,
    )


def _make_panels(
    index: pd.DatetimeIndex, inst_ids: list[str], seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dfs = _make_ohlcv(index, inst_ids, seed)
    close = pd.DataFrame({i: dfs[i]["close"] for i in inst_ids})
    high = pd.DataFrame({i: dfs[i]["high"] for i in inst_ids})
    low = pd.DataFrame({i: dfs[i]["low"] for i in inst_ids})
    vol = pd.DataFrame({i: dfs[i]["vol"] for i in inst_ids})
    return close, high, low, vol


# ---------------------------------------------------------------------------
# 13.1 Feature Test
# ---------------------------------------------------------------------------

class TestFeaturePanel:
    def test_features_no_inf(self) -> None:
        idx = _make_index(600)
        inst_ids = ["A", "B", "C"]
        close, high, low, vol = _make_panels(idx, inst_ids)
        params = _minimal_params(inst_ids)

        features = build_feature_panel(close, high, low, vol, params)

        expected_keys = {"return_fast", "return_slow", "volume_z", "realized_vol", "rolling_high", "ema", "atr"}
        assert expected_keys.issubset(features.keys())

        for key, df in features.items():
            if isinstance(df, pd.DataFrame):
                inf_count = np.isinf(df.values).sum()
                assert inf_count == 0, f"inf found in feature '{key}'"

    def test_feature_shapes(self) -> None:
        idx = _make_index(300)
        inst_ids = ["X", "Y"]
        close, high, low, vol = _make_panels(idx, inst_ids)
        params = _minimal_params(inst_ids)
        features = build_feature_panel(close, high, low, vol, params)

        for key, df in features.items():
            if isinstance(df, pd.DataFrame):
                assert df.shape == (len(idx), len(inst_ids)), f"wrong shape for '{key}'"
                assert list(df.columns) == inst_ids, f"wrong columns for '{key}'"

    def test_volume_z_no_inf_with_zero_std(self) -> None:
        idx = _make_index(100)
        inst_ids = ["A"]
        close, high, low, _ = _make_panels(idx, inst_ids)
        # Constant volume → std = 0
        vol = pd.DataFrame({"A": np.ones(len(idx))}, index=idx)
        params = _minimal_params(inst_ids)
        features = build_feature_panel(close, high, low, vol, params)
        assert not np.isinf(features["volume_z"].values).any()
        assert not features["volume_z"].isna().all().all()


# ---------------------------------------------------------------------------
# 13.2 No Look-ahead Test
# ---------------------------------------------------------------------------

class TestNoLookahead:
    def test_rolling_high_uses_shift1(self) -> None:
        idx = _make_index(300)
        inst_ids = ["A"]
        close, high, low, vol = _make_panels(idx, inst_ids, seed=99)
        params = _minimal_params(inst_ids)
        params.breakout_window_minutes = 30

        features = build_feature_panel(close, high, low, vol, params)
        rh = features["rolling_high"]["A"]

        # rolling_high at t must NOT include high[t]
        # Verify by construction: set high at last bar to an all-time-high
        # and confirm rolling_high there is still the previous max
        t_last = idx[-1]
        big_high = high["A"].max() * 10
        high_modified = high.copy()
        high_modified.loc[t_last, "A"] = big_high

        features2 = build_feature_panel(close, high_modified, low, vol, params)
        rh2 = features2["rolling_high"]["A"]

        # rolling_high at t_last must NOT include big_high (it uses shift(1))
        assert rh2.loc[t_last] < big_high, (
            "rolling_high[t] should NOT include high[t] — lookahead detected"
        )

    def test_rolling_high_equals_shifted_formula(self) -> None:
        idx = _make_index(200)
        inst_ids = ["B"]
        close, high, low, vol = _make_panels(idx, inst_ids)
        params = _minimal_params(inst_ids)
        w = params.breakout_window_minutes

        features = build_feature_panel(close, high, low, vol, params)
        expected = high["B"].shift(1).rolling(w, min_periods=1).max()

        pd.testing.assert_series_equal(
            features["rolling_high"]["B"].dropna(),
            expected.dropna(),
            check_names=False,
        )


# ---------------------------------------------------------------------------
# 13.3 Ranking Test
# ---------------------------------------------------------------------------

class TestRanking:
    def test_strong_beats_weak_beats_negative(self) -> None:
        n = 400
        idx = _make_index(n)

        # A: strong uptrend, B: flat, C: strong downtrend
        rng = np.random.default_rng(0)
        noise = rng.normal(0, 0.001, n)
        close_a = 100 * np.exp(np.cumsum(np.full(n, 0.002) + noise))
        close_b = 100 * np.exp(np.cumsum(np.full(n, 0.0) + noise))
        close_c = 100 * np.exp(np.cumsum(np.full(n, -0.002) + noise))

        close = pd.DataFrame({"A": close_a, "B": close_b, "C": close_c}, index=idx)
        high = close * 1.002
        low = close * 0.998
        vol = pd.DataFrame({"A": 150.0, "B": 100.0, "C": 80.0}, index=idx)

        params = _minimal_params(["A", "B", "C"])
        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)

        # Use last rebalance bar where all features are computed
        last_valid = scores.dropna(how="all").index[-1]
        row = scores.loc[last_valid].dropna()

        assert row["A"] > row["B"] > row["C"], (
            f"Expected A > B > C but got A={row['A']:.3f} B={row['B']:.3f} C={row['C']:.3f}"
        )

    def test_negative_momentum_not_selected(self) -> None:
        n = 400
        idx = _make_index(n)
        rng = np.random.default_rng(1)
        noise = rng.normal(0, 0.001, n)
        close_a = 100 * np.exp(np.cumsum(np.full(n, 0.003) + noise))
        close_c = 100 * np.exp(np.cumsum(np.full(n, -0.003) + noise))

        close = pd.DataFrame({"A": close_a, "C": close_c}, index=idx)
        high = close * 1.002
        low = close * 0.998
        vol = pd.DataFrame({"A": 150.0, "C": 80.0}, index=idx)

        params = _minimal_params(["A", "C"])
        params.top_k = 1
        params.min_volume_z = 0.0

        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)

        regime = pd.Series(True, index=idx)
        reb_ts = idx[params.lookback_slow_minutes::params.rebalance_minutes]

        weights = generate_target_weights(scores, features, regime, params, pd.DatetimeIndex(reb_ts))

        # C (downtrend) should never be selected
        if "C" in weights.columns:
            assert (weights["C"] == 0).all(), "Downtrending instrument C should never be selected"


# ---------------------------------------------------------------------------
# 13.4 Entry Rule Test
# ---------------------------------------------------------------------------

class TestEntryRules:
    def _setup(self) -> tuple[pd.DatetimeIndex, pd.DataFrame, OHLCVRotationParams]:
        n = 500
        idx = _make_index(n)
        rng = np.random.default_rng(7)
        noise = rng.normal(0, 0.001, n)
        close_a = 100 * np.exp(np.cumsum(np.full(n, 0.003) + noise))
        close = pd.DataFrame({"A": close_a}, index=idx)
        high = close * 1.002
        low = close * 0.998
        vol = pd.DataFrame({"A": 150.0}, index=idx)
        params = _minimal_params(["A"])
        params.top_k = 1
        params.min_volume_z = 0.0
        return idx, close, high, low, vol, params

    def test_regime_false_blocks_entry(self) -> None:
        idx, close, high, low, vol, params = self._setup()
        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)
        regime = pd.Series(False, index=idx)  # always bearish
        reb_ts = pd.DatetimeIndex(idx[params.lookback_slow_minutes::params.rebalance_minutes])
        weights = generate_target_weights(scores, features, regime, params, reb_ts)
        assert (weights == 0).all().all(), "Bearish regime should block all entries"

    def test_negative_return_fast_blocks_entry(self) -> None:
        n = 500
        idx = _make_index(n)
        rng = np.random.default_rng(8)
        # Downtrend for first 300 bars, then strong up
        returns = np.concatenate([
            rng.normal(-0.002, 0.001, 300),
            rng.normal(0.005, 0.001, 200),
        ])
        close_a = 100 * np.exp(np.cumsum(returns))
        close = pd.DataFrame({"A": close_a}, index=idx)
        high = close * 1.002
        low = close * 0.998
        vol = pd.DataFrame({"A": 150.0}, index=idx)
        params = _minimal_params(["A"])
        params.top_k = 1
        params.min_volume_z = 0.0
        params.lookback_fast_minutes = 20

        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)
        regime = pd.Series(True, index=idx)

        # Check only rebalance bars in the downtrend window
        reb_ts = pd.DatetimeIndex(idx[params.lookback_slow_minutes:280:params.rebalance_minutes])
        weights = generate_target_weights(scores, features, regime, params, reb_ts)
        # During downtrend, return_fast < 0 → no entries
        assert (weights == 0).all().all(), "Negative return_fast should block entries"

    def test_volume_z_threshold_is_not_a_hard_entry_filter(self) -> None:
        n = 500
        idx = _make_index(n)
        rng = np.random.default_rng(9)
        noise_a = rng.normal(0, 0.0005, n)
        noise_b = rng.normal(0, 0.0005, n)
        close_a = 100 * np.exp(np.cumsum(np.full(n, 0.004) + noise_a))
        close_b = 100 * np.exp(np.cumsum(np.full(n, 0.001) + noise_b))
        close = pd.DataFrame({"A": close_a, "B": close_b}, index=idx)
        high = close * 1.002
        low = close * 0.998
        vol = pd.DataFrame({"A": 100.0}, index=idx)  # constant → z-score = 0
        vol = pd.DataFrame({"A": 100.0, "B": 100.0}, index=idx)  # constant z-score = 0
        params = _minimal_params(["A", "B"])
        params.top_k = 1
        params.min_volume_z = 10.0

        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)
        regime = pd.Series(True, index=idx)
        reb_ts = pd.DatetimeIndex(idx[params.lookback_slow_minutes::params.rebalance_minutes])
        weights = generate_target_weights(scores, features, regime, params, reb_ts)
        assert (weights["A"] > 0).any(), (
            "volume_z threshold should not hard-block entries; volume should affect ranking via score"
        )


# ---------------------------------------------------------------------------
# 13.5 Exit Rule Test
# ---------------------------------------------------------------------------

class TestExitRules:
    def _make_held_position(
        self,
        n: int = 300,
        trend: float = 0.003,
    ) -> tuple[pd.DatetimeIndex, dict, OHLCVRotationParams]:
        idx = _make_index(n)
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 0.0005, n)
        close_a = 100 * np.exp(np.cumsum(np.full(n, trend) + noise))
        params = _minimal_params(["A"])
        params.top_k = 1
        params.min_volume_z = 0.0
        dfs = {
            "A": pd.DataFrame(
                {
                    "open": close_a,
                    "high": close_a * 1.001,
                    "low": close_a * 0.999,
                    "close": close_a,
                    "vol": 150.0,
                },
                index=idx,
            )
        }
        return idx, dfs, params

    def test_regime_exit_clears_position(self) -> None:
        idx, dfs, params = self._make_held_position()
        # Build a position, then flip regime to False
        close = pd.DataFrame({"A": dfs["A"]["close"]}, index=idx)
        high = pd.DataFrame({"A": dfs["A"]["high"]}, index=idx)
        low = pd.DataFrame({"A": dfs["A"]["low"]}, index=idx)
        vol = pd.DataFrame({"A": dfs["A"]["vol"]}, index=idx)

        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)

        # Regime: True for first half, False for second half
        regime = pd.Series(True, index=idx)
        regime.iloc[len(idx) // 2:] = False

        reb_ts = pd.DatetimeIndex(idx[params.lookback_slow_minutes::params.rebalance_minutes])
        raw_w = generate_target_weights(scores, features, regime, params, reb_ts)
        final_w = apply_exit_rules(raw_w, features, scores, regime, params)

        bearish_ts = reb_ts[reb_ts >= idx[len(idx) // 2]]
        for ts in bearish_ts:
            if ts in final_w.index:
                assert final_w.loc[ts, "A"] == 0.0, f"Position should be 0 in bearish regime at {ts}"

    def test_ema_exit(self) -> None:
        """Close falling below EMA should exit position."""
        n = 400
        idx = _make_index(n)
        # Strong uptrend for 200 bars, then sharp reversal
        trend = np.concatenate([np.full(200, 0.004), np.full(200, -0.01)])
        close_a = 100 * np.exp(np.cumsum(trend))
        close = pd.DataFrame({"A": close_a}, index=idx)
        high = close * 1.001
        low = close * 0.999
        vol = pd.DataFrame({"A": 150.0}, index=idx)
        params = _minimal_params(["A"])
        params.top_k = 1
        params.min_volume_z = 0.0
        params.ema_window_minutes = 20

        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)
        regime = pd.Series(True, index=idx)
        reb_ts = pd.DatetimeIndex(idx[params.lookback_slow_minutes::params.rebalance_minutes])
        raw_w = generate_target_weights(scores, features, regime, params, reb_ts)
        final_w = apply_exit_rules(raw_w, features, scores, regime, params)

        # After reversal, close < EMA → position must be 0 eventually
        reversal_ts = reb_ts[reb_ts >= idx[250]]
        closed = [ts for ts in reversal_ts if ts in final_w.index and final_w.loc[ts, "A"] == 0.0]
        assert len(closed) > 0, "EMA exit should have triggered after reversal"

    def test_rank_exit_buffer(self) -> None:
        """Instrument that drops in rank beyond rank_exit_buffer should exit."""
        n = 400
        idx = _make_index(n)
        # A: strong early, then weak; B: weak early, then strong
        trend_a = np.concatenate([np.full(200, 0.004), np.full(200, -0.001)])
        trend_b = np.concatenate([np.full(200, -0.001), np.full(200, 0.006)])
        close_a = 100 * np.exp(np.cumsum(trend_a))
        close_b = 80 * np.exp(np.cumsum(trend_b))
        close = pd.DataFrame({"A": close_a, "B": close_b}, index=idx)
        high = close * 1.001
        low = close * 0.999
        vol = pd.DataFrame({"A": 150.0, "B": 150.0}, index=idx)
        params = _minimal_params(["A", "B"])
        params.top_k = 1
        params.rank_exit_buffer = 1  # exit immediately if rank > 1
        params.min_volume_z = 0.0

        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)
        regime = pd.Series(True, index=idx)
        reb_ts = pd.DatetimeIndex(idx[params.lookback_slow_minutes::params.rebalance_minutes])
        raw_w = generate_target_weights(scores, features, regime, params, reb_ts)
        final_w = apply_exit_rules(raw_w, features, scores, regime, params)

        # Both A and B can't hold simultaneously with top_k=1
        for ts in final_w.index:
            n_held = (final_w.loc[ts] > 0).sum()
            assert n_held <= params.top_k, f"More than top_k={params.top_k} positions held at {ts}"


# ---------------------------------------------------------------------------
# 13.6 Cost Test
# ---------------------------------------------------------------------------

class TestCostDeducted:
    def test_cost_reduces_returns(self) -> None:
        # Use long, strongly-trending data to guarantee entry conditions are met.
        n = 3000
        idx = _make_index(n)
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 0.0005, n)
        close_btc = 100 * np.exp(np.cumsum(np.full(n, 0.003) + noise))
        close_eth = 100 * np.exp(np.cumsum(np.full(n, 0.002) + noise[::-1]))

        dfs = {
            "BTC": pd.DataFrame(
                {"open": close_btc, "high": close_btc * 1.002,
                 "low": close_btc * 0.998, "close": close_btc,
                 "vol": 150.0 + 30 * np.sin(np.arange(n) * 0.05)},
                index=idx,
            ),
            "ETH": pd.DataFrame(
                {"open": close_eth, "high": close_eth * 1.002,
                 "low": close_eth * 0.998, "close": close_eth,
                 "vol": 120.0 + 25 * np.cos(np.arange(n) * 0.05)},
                index=idx,
            ),
        }

        params = _minimal_params(["BTC", "ETH"])
        params.min_volume_z = 0.0
        params.fee_bps = 10.0
        params.slippage_bps = 10.0

        result = run_ohlcv_rotation_backtest(dfs, params)

        params_nc = _minimal_params(["BTC", "ETH"])
        params_nc.min_volume_z = 0.0
        params_nc.fee_bps = 0.0
        params_nc.slippage_bps = 0.0

        result_nc = run_ohlcv_rotation_backtest(dfs, params_nc)

        diffs = (result_nc.equity_curve - result.equity_curve).dropna()
        assert (diffs >= -1e-12).all(), "Cost cannot make equity higher than no-cost"
        n_trades = result.metrics["number_of_trades"]
        assert diffs.max() > 1e-8, (
            f"No cost difference detected — trades={n_trades}. "
            "Trending data should generate entries."
        )

    def test_cost_formula_exact(self) -> None:
        """Verify: cost = turnover * (fee_bps + slippage_bps) / 10000."""
        from ohlcv_rotation_backtest import compute_cost, compute_turnover

        idx = _make_index(200)
        target_weights = pd.DataFrame(
            {
                "A": [0.0, 0.3, 0.3, 0.0, 0.0, 0.3],
                "B": [0.0, 0.0, 0.3, 0.3, 0.0, 0.0],
            },
            index=idx[:6],
        )
        params = _minimal_params(["A", "B"])
        params.fee_bps = 3.0
        params.slippage_bps = 2.0

        expected_turnover = compute_turnover(target_weights)
        expected_cost = expected_turnover * 5.0 / 10_000

        actual_cost = compute_cost(target_weights, params)

        pd.testing.assert_series_equal(actual_cost, expected_cost, check_names=False)


class TestMetrics:
    def test_compute_metrics_annualizes_hourly_returns_from_elapsed_time(self) -> None:
        idx = pd.date_range("2024-01-01", periods=24 * 30 + 1, freq="1h")
        returns = pd.Series(np.linspace(-0.001, 0.0015, len(idx)), index=idx)
        equity_curve = (1 + returns).cumprod()
        target_weights = pd.DataFrame({"BTC": 1.0}, index=idx)
        trades = pd.DataFrame(columns=["pnl", "holding_minutes"])

        metrics = compute_metrics(equity_curve, returns, target_weights, trades, bar="1H")

        elapsed_years = (idx[-1] - idx[0]).total_seconds() / (365.25 * 24 * 60 * 60)
        expected_bars_per_year = len(returns) / elapsed_years
        expected_ann_vol = float(returns.std() * math.sqrt(expected_bars_per_year))
        old_1m_ann_vol = float(returns.std() * math.sqrt(365 * 24 * 60))

        assert metrics["annualized_volatility"] == pytest.approx(expected_ann_vol)
        assert metrics["annualized_volatility"] < old_1m_ann_vol / 2


# ---------------------------------------------------------------------------
# Integration smoke test
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_backtest_runs_end_to_end(self) -> None:
        idx = _make_index(800)
        inst_ids = ["BTC", "ETH", "SOL"]
        dfs = _make_ohlcv(idx, inst_ids)
        params = _minimal_params(inst_ids)
        params.min_volume_z = 0.0

        result = run_ohlcv_rotation_backtest(dfs, params)

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == len(idx)
        assert not result.equity_curve.isna().any(), "equity_curve must not contain NaN"
        assert not np.isinf(result.equity_curve.values).any(), "equity_curve must not contain inf"
        assert "sharpe" in result.metrics
        assert "total_return" in result.metrics

    def test_backtest_metrics_include_rebalance_aligned_entry_diagnostics(self) -> None:
        idx = _make_index(800)
        inst_ids = ["BTC", "ETH", "SOL"]
        dfs = _make_ohlcv(idx, inst_ids)
        params = _minimal_params(inst_ids)
        params.min_volume_z = 0.0

        result = run_ohlcv_rotation_backtest(dfs, params)
        metrics = result.metrics

        close = pd.DataFrame({inst: dfs[inst]["close"] for inst in inst_ids})
        high = pd.DataFrame({inst: dfs[inst]["high"] for inst in inst_ids})
        low = pd.DataFrame({inst: dfs[inst]["low"] for inst in inst_ids})
        vol = pd.DataFrame({inst: dfs[inst]["vol"] for inst in inst_ids})
        features = build_feature_panel(close, high, low, vol, params)
        features["close"] = close
        scores = compute_cross_sectional_scores(features, params)
        reb_ts = idx[idx.minute % params.rebalance_minutes == 0]
        expected_score_coverage = float(scores.reindex(reb_ts).notna().any(axis=1).mean())

        assert metrics["score_coverage_at_reb_pct"] == pytest.approx(expected_score_coverage)
        assert metrics["score_coverage_pct"] == pytest.approx(expected_score_coverage)
        for key in [
            "fast_return_filter_pass_pct",
            "slow_return_filter_pass_pct",
            "vol_filter_pass_pct",
            "breakout_filter_pass_pct",
            "all_entry_filters_pass_pct",
            "fast_return_filter_bar_pct",
            "slow_return_filter_bar_pct",
            "vol_filter_bar_pct",
            "breakout_filter_bar_pct",
            "all_entry_filters_bar_pct",
        ]:
            assert 0.0 <= metrics[key] <= 1.0
        assert "low_trade_warning" in metrics
        assert "entry_diagnostic_primary_bottleneck" in metrics

    def test_missing_benchmark_raises(self) -> None:
        idx = _make_index(200)
        dfs = _make_ohlcv(idx, ["ETH"])
        params = _minimal_params(["ETH"])
        params.benchmark_inst_id = "BTC"  # not in dfs

        with pytest.raises(ValueError, match="Benchmark instrument"):
            run_ohlcv_rotation_backtest(dfs, params)
