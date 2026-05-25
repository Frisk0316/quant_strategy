"""
Vectorised backtest runner for the OHLCV Rotation strategy.

Entry point: run_ohlcv_rotation_backtest(dfs, params) -> BacktestResult

Timeline convention (no look-ahead):
  signal[t]  computed from closed candle at t
  position   = target_weights.shift(1)  (execute next bar)
  pnl[t]     = position[t] * bar_return[t]
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from okx_quant.strategies.ohlcv_rotation import (
    OHLCVRotationParams,
    apply_exit_rules,
    build_feature_panel,
    compute_benchmark_regime,
    compute_cross_sectional_scores,
    generate_target_weights,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    equity_curve: pd.Series
    daily_returns: pd.Series
    positions: pd.DataFrame
    target_weights: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_wide_panels(
    dfs: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Combine per-instrument DataFrames into wide (timestamp × inst_id) panels."""
    close = pd.DataFrame({inst: df["close"] for inst, df in dfs.items()})
    high = pd.DataFrame({inst: df["high"] for inst, df in dfs.items()})
    low = pd.DataFrame({inst: df["low"] for inst, df in dfs.items()})
    vol = pd.DataFrame({inst: df["vol"] for inst, df in dfs.items()})
    open_ = pd.DataFrame({inst: df["open"] for inst, df in dfs.items()})
    common = close.index
    return (
        close.loc[common],
        high.loc[common],
        low.loc[common],
        vol.loc[common],
        open_.loc[common],
    )


def compute_turnover(target_weights: pd.DataFrame) -> pd.Series:
    """Sum of absolute weight changes per bar."""
    return target_weights.diff().abs().sum(axis=1).fillna(0.0)


def compute_cost(target_weights: pd.DataFrame, params: OHLCVRotationParams) -> pd.Series:
    turnover = compute_turnover(target_weights)
    return turnover * (params.fee_bps + params.slippage_bps) / 10_000


def _rebalance_timestamps(index: pd.DatetimeIndex, rebalance_minutes: int) -> pd.DatetimeIndex:
    """Return timestamps where minute % rebalance_minutes == 0."""
    mask = index.minute % rebalance_minutes == 0
    return index[mask]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

BARS_PER_YEAR = {
    "1m": 365 * 24 * 60,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
    "30m": 365 * 24 * 2,
    "1H": 365 * 24,
    "4H": 365 * 6,
    "1D": 365,
}


def _safe_mean_bool(mask: pd.Series | pd.DataFrame) -> float:
    if mask.empty:
        return 0.0
    value = mask.astype(bool).mean()
    if isinstance(value, pd.Series):
        value = value.mean()
    return float(value) if pd.notna(value) else 0.0


def _pct_true(mask: pd.Series | pd.DataFrame, denominator: pd.Series | pd.DataFrame) -> float:
    if mask.empty or denominator.empty:
        return 0.0
    aligned_mask, aligned_denominator = mask.align(denominator, join="inner", axis=None)
    denom = int(aligned_denominator.astype(bool).sum().sum())
    if denom <= 0:
        return 0.0
    numerator = int((aligned_mask.astype(bool) & aligned_denominator.astype(bool)).sum().sum())
    return float(numerator / denom)


def _bar_any_pct(mask: pd.DataFrame, denominator: pd.Series) -> float:
    if mask.empty or denominator.empty:
        return 0.0
    aligned_mask = mask.reindex(denominator.index).fillna(False)
    active = denominator.astype(bool)
    denom = int(active.sum())
    if denom <= 0:
        return 0.0
    return float((aligned_mask.any(axis=1) & active).sum() / denom)


def _annualization_inputs(returns: pd.Series, bar: str | None = None) -> tuple[float, float]:
    """Return (ann_factor_for_total_return, bars_per_year) from timestamps when possible."""
    if len(returns) > 1 and isinstance(returns.index, pd.DatetimeIndex):
        elapsed_seconds = (returns.index[-1] - returns.index[0]).total_seconds()
        elapsed_years = elapsed_seconds / (365.25 * 24 * 60 * 60)
        if elapsed_years > 0:
            return 1.0 / elapsed_years, len(returns) / elapsed_years

    bars_per_year = float(BARS_PER_YEAR.get(bar or "1m", BARS_PER_YEAR["1m"]))
    ann_factor = bars_per_year / len(returns) if len(returns) > 0 else 1.0
    return ann_factor, bars_per_year


def compute_metrics(
    equity_curve: pd.Series,
    portfolio_returns: pd.Series,
    target_weights: pd.DataFrame,
    trades: pd.DataFrame,
    bar: str | None = None,
) -> dict:
    total_return = float(equity_curve.iloc[-1] - 1) if not equity_curve.empty else 0.0

    ann_factor, bars_per_year = _annualization_inputs(portfolio_returns, bar)
    annualized_return = (1 + total_return) ** ann_factor - 1

    ann_vol = float(portfolio_returns.std() * math.sqrt(bars_per_year))
    sharpe = (annualized_return / ann_vol) if ann_vol > 0 else 0.0

    drawdown = (equity_curve / equity_curve.cummax() - 1)
    max_drawdown = float(drawdown.min())

    calmar = (annualized_return / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    avg_turnover = float(compute_turnover(target_weights).mean())

    # trades-based metrics
    if not trades.empty and "pnl" in trades.columns:
        n_trades = int(len(trades))
        avg_hold = float(trades.get("holding_minutes", pd.Series(dtype=float)).mean())
        wins = trades["pnl"][trades["pnl"] > 0]
        losses = trades["pnl"][trades["pnl"] <= 0]
        win_rate = float(len(wins) / n_trades) if n_trades > 0 else 0.0
        profit_factor = (
            float(wins.sum() / abs(losses.sum())) if not losses.empty and losses.sum() != 0 else np.inf
        )
    else:
        n_trades = 0
        avg_hold = 0.0
        win_rate = 0.0
        profit_factor = 0.0

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "number_of_trades": n_trades,
        "average_holding_minutes": avg_hold,
        "average_turnover": avg_turnover,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
    }


# ---------------------------------------------------------------------------
# Trade extraction
# ---------------------------------------------------------------------------

def extract_trades_from_weights(
    target_weights: pd.DataFrame,
    close_panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Identify round-trip trades from transitions in target_weights.
    Entry: weight transitions 0 → positive
    Exit:  weight transitions positive → 0
    """
    _cols = ["inst_id", "entry_ts", "exit_ts", "entry_price", "exit_price", "pnl", "holding_minutes"]
    if target_weights.empty:
        return pd.DataFrame(columns=_cols)

    # Pre-align close prices to the rebalance index to avoid per-row .loc lookups.
    aligned = close_panel.reindex(target_weights.index, method="ffill")

    prev = pd.Series(0.0, index=target_weights.columns)
    open_entries: dict[str, tuple] = {}  # inst_id → (entry_ts, entry_price)
    records: list[dict] = []

    columns = list(target_weights.columns)
    for ts, curr in target_weights.iterrows():
        closes_at_ts = aligned.loc[ts] if ts in aligned.index else pd.Series(np.nan, index=target_weights.columns)
        for col_idx, inst in enumerate(columns):
            p, c = prev.iat[col_idx], curr.iat[col_idx]
            ep = closes_at_ts.get(inst, np.nan)

            if p == 0.0 and c > 0.0:
                open_entries[inst] = (ts, ep)
            elif p > 0.0 and c == 0.0 and inst in open_entries:
                ets, epr = open_entries.pop(inst)
                pnl = (ep - epr) / epr if (np.isfinite(ep) and np.isfinite(epr) and epr != 0) else np.nan
                records.append({
                    "inst_id": inst, "entry_ts": ets, "exit_ts": ts,
                    "entry_price": epr, "exit_price": ep, "pnl": pnl,
                    "holding_minutes": int((ts - ets).total_seconds() / 60),
                })
        prev = curr

    # Close any still-open positions at end
    if open_entries:
        last_ts = target_weights.index[-1]
        last_closes = aligned.loc[last_ts] if last_ts in aligned.index else pd.Series(np.nan, index=target_weights.columns)
        for inst, (ets, epr) in open_entries.items():
            ep = last_closes.get(inst, np.nan)
            pnl = (ep - epr) / epr if (np.isfinite(ep) and np.isfinite(epr) and epr != 0) else np.nan
            records.append({
                "inst_id": inst, "entry_ts": ets, "exit_ts": last_ts,
                "entry_price": epr, "exit_price": ep, "pnl": pnl,
                "holding_minutes": int((last_ts - ets).total_seconds() / 60),
            })

    if not records:
        return pd.DataFrame(columns=_cols)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Main backtest runner
# ---------------------------------------------------------------------------

def run_ohlcv_rotation_backtest(
    dfs: dict[str, pd.DataFrame],
    params: OHLCVRotationParams,
) -> BacktestResult:
    """
    Run vectorised backtest for OHLCVRotationParams.

    Args:
        dfs: dict mapping inst_id → DataFrame with columns [open,high,low,close,vol]
             indexed by tz-naive UTC timestamp.
        params: strategy parameters.

    Returns:
        BacktestResult dataclass.
    """
    if params.benchmark_inst_id not in dfs:
        raise ValueError(
            f"Benchmark instrument '{params.benchmark_inst_id}' not found in dfs. "
            f"Available: {list(dfs.keys())}"
        )

    close, high, low, vol, open_ = _build_wide_panels(dfs)

    benchmark_close = close[params.benchmark_inst_id]

    # --- features ---
    features = build_feature_panel(close, high, low, vol, params)
    # Add close to features dict for use inside weight generation
    features["close"] = close

    # --- scores ---
    scores = compute_cross_sectional_scores(features, params)

    # --- regime ---
    regime = compute_benchmark_regime(benchmark_close, params)

    # --- rebalance timestamps ---
    reb_ts = _rebalance_timestamps(close.index, params.rebalance_minutes)

    # --- raw target weights (entry only, no state-dependent exits) ---
    raw_weights = generate_target_weights(scores, features, regime, params, reb_ts)

    # --- apply stateful exit rules ---
    target_weights_reb = apply_exit_rules(raw_weights, features, scores, regime, params)

    # --- upsample to 1m by forward-fill ---
    target_weights_1m = (
        target_weights_reb.reindex(close.index).ffill().fillna(0.0)
    )

    # --- execute next bar: shift(1) ---
    actual_weights = target_weights_1m.shift(1).fillna(0.0)

    # --- bar returns ---
    bar_returns = close.pct_change().fillna(0.0)

    # --- gross portfolio returns ---
    gross_returns = (actual_weights * bar_returns).sum(axis=1)

    # --- costs applied on rebalance bars (where target changes) ---
    cost_1m = compute_cost(target_weights_1m, params)

    portfolio_returns = gross_returns - cost_1m
    equity_curve = (1 + portfolio_returns).cumprod()

    # --- daily returns (resample to calendar days) ---
    daily_returns = (1 + portfolio_returns).resample("1D").prod() - 1

    # --- trades ---
    trades = extract_trades_from_weights(target_weights_reb, close)

    # --- metrics ---
    metrics = compute_metrics(equity_curve, portfolio_returns, target_weights_1m, trades, params.bar)

    # Warm-up bars: bars before first non-NaN composite score
    composite_score = scores.mean(axis=1) if not scores.empty else pd.Series(dtype=float)
    first_valid = composite_score.first_valid_index()
    warmup_bars = int(close.index.get_loc(first_valid)) if first_valid is not None and first_valid in close.index else len(close)
    data_coverage_pct = float(close.notna().all(axis=1).mean())
    metrics["warmup_bars"] = warmup_bars
    metrics["data_coverage_pct"] = data_coverage_pct
    metrics["total_bars"] = len(close)

    scores_at_reb = scores.reindex(reb_ts) if len(reb_ts) else pd.DataFrame(columns=scores.columns)
    score_available_all = scores.notna().any(axis=1) if not scores.empty else pd.Series(dtype=bool)
    score_available_reb = (
        scores_at_reb.notna().any(axis=1) if not scores_at_reb.empty else pd.Series(dtype=bool)
    )
    raw_active = raw_weights.abs().sum(axis=1) > 0 if not raw_weights.empty else pd.Series(dtype=bool)
    target_active = (
        target_weights_reb.abs().sum(axis=1) > 0
        if not target_weights_reb.empty else pd.Series(dtype=bool)
    )
    position_active = (
        target_weights_1m.abs().sum(axis=1) > 0
        if not target_weights_1m.empty else pd.Series(dtype=bool)
    )
    regime_reb = regime.reindex(reb_ts).fillna(False) if len(reb_ts) else pd.Series(dtype=bool)

    valid_score = scores_at_reb.notna()
    regime_active_reb = regime_reb.reindex(scores_at_reb.index).fillna(False).astype(bool)
    opportunity = valid_score & pd.DataFrame(
        np.repeat(regime_active_reb.to_numpy()[:, None], len(scores_at_reb.columns), axis=1),
        index=scores_at_reb.index,
        columns=scores_at_reb.columns,
    )
    row_score = scores_at_reb.copy()
    ranks = row_score.rank(axis=1, ascending=False, method="min")
    top_k_pass = ranks <= params.top_k
    entry_rank_pass = valid_score if params.fill_all_signals else top_k_pass
    rf_pass = features["return_fast"].reindex(reb_ts) > 0 if len(reb_ts) else pd.DataFrame()
    rs_pass = features["return_slow"].reindex(reb_ts) > 0 if len(reb_ts) else pd.DataFrame()
    vol_threshold_pass = (
        features["volume_z"].reindex(reb_ts) > params.min_volume_z
        if len(reb_ts) else pd.DataFrame()
    )
    close_reb = features["close"].reindex(reb_ts) if len(reb_ts) else pd.DataFrame()
    rh_reb = features["rolling_high"].reindex(reb_ts) if len(reb_ts) else pd.DataFrame()
    ema_reb = features["ema"].reindex(reb_ts) if len(reb_ts) else pd.DataFrame()
    breakout_pass = (close_reb > rh_reb) & (close_reb > ema_reb)
    all_entry_filters = entry_rank_pass & rf_pass & rs_pass & breakout_pass

    opportunity_bars = regime_reb.astype(bool) & score_available_reb.reindex(regime_reb.index).fillna(False)
    active_rebalance_count = int(regime_reb.sum()) if len(regime_reb) else 0
    n_trades = int(metrics.get("number_of_trades", 0) or 0)
    expected_min_trades = int(max(5, math.ceil(active_rebalance_count * 0.01))) if active_rebalance_count >= 100 else 0
    low_trade_warning = bool(active_rebalance_count >= 100 and n_trades < expected_min_trades)

    bottleneck_candidates = {
        "regime_active_pct": _safe_mean_bool(regime_reb),
        "score_coverage_at_reb_pct": _safe_mean_bool(score_available_reb),
        "fast_return_filter_bar_pct": _bar_any_pct(rf_pass, opportunity_bars),
        "slow_return_filter_bar_pct": _bar_any_pct(rs_pass, opportunity_bars),
        "breakout_filter_bar_pct": _bar_any_pct(breakout_pass, opportunity_bars),
        "all_entry_filters_bar_pct": _bar_any_pct(all_entry_filters, opportunity_bars),
    }
    volume_threshold_bar_pct = _bar_any_pct(vol_threshold_pass, opportunity_bars)
    primary_bottleneck = min(bottleneck_candidates, key=bottleneck_candidates.get)

    metrics["rebalance_count"] = int(len(target_weights_reb))
    metrics["fill_all_signals_enabled"] = bool(params.fill_all_signals)
    metrics["entry_cap_mode"] = "all_signals" if params.fill_all_signals else "top_k"
    metrics["score_coverage_all_bars_pct"] = _safe_mean_bool(score_available_all)
    metrics["score_coverage_at_reb_pct"] = _safe_mean_bool(score_available_reb)
    metrics["score_coverage_pct"] = metrics["score_coverage_at_reb_pct"]
    metrics["score_valid_instruments_mean_at_reb"] = (
        float(valid_score.sum(axis=1).mean()) if not valid_score.empty else 0.0
    )
    metrics["score_valid_instrument_opportunity_pct"] = (
        float(valid_score.sum().sum() / valid_score.size) if valid_score.size else 0.0
    )
    metrics["regime_active_bars"] = active_rebalance_count
    metrics["regime_active_pct"] = bottleneck_candidates["regime_active_pct"]
    metrics["top_k_rank_pass_pct"] = _pct_true(top_k_pass, opportunity)
    metrics["fast_return_filter_pass_pct"] = _pct_true(rf_pass, opportunity)
    metrics["slow_return_filter_pass_pct"] = _pct_true(rs_pass, opportunity)
    metrics["volume_hard_filter_enabled"] = False
    metrics["vol_threshold_pass_pct"] = _pct_true(vol_threshold_pass, opportunity)
    metrics["vol_filter_pass_pct"] = metrics["vol_threshold_pass_pct"]
    metrics["breakout_filter_pass_pct"] = _pct_true(breakout_pass, opportunity)
    metrics["all_entry_filters_pass_pct"] = _pct_true(all_entry_filters, opportunity)
    metrics["fast_return_filter_bar_pct"] = bottleneck_candidates["fast_return_filter_bar_pct"]
    metrics["slow_return_filter_bar_pct"] = bottleneck_candidates["slow_return_filter_bar_pct"]
    metrics["vol_threshold_bar_pct"] = volume_threshold_bar_pct
    metrics["vol_filter_bar_pct"] = metrics["vol_threshold_bar_pct"]
    metrics["breakout_filter_bar_pct"] = bottleneck_candidates["breakout_filter_bar_pct"]
    metrics["all_entry_filters_bar_pct"] = bottleneck_candidates["all_entry_filters_bar_pct"]
    metrics["entry_diagnostic_primary_bottleneck"] = primary_bottleneck
    metrics["raw_entry_signal_bars"] = int(raw_active.sum()) if len(raw_active) else 0
    metrics["raw_entry_signal_pct"] = float(raw_active.mean()) if len(raw_active) else 0.0
    metrics["target_active_rebalance_bars"] = int(target_active.sum()) if len(target_active) else 0
    metrics["target_active_rebalance_pct"] = float(target_active.mean()) if len(target_active) else 0.0
    metrics["position_active_bars"] = int(position_active.sum()) if len(position_active) else 0
    metrics["position_active_pct"] = float(position_active.mean()) if len(position_active) else 0.0
    metrics["trades_per_100_active_rebalances"] = (
        float(n_trades / active_rebalance_count * 100) if active_rebalance_count else 0.0
    )
    metrics["low_trade_warning"] = low_trade_warning
    metrics["low_trade_threshold_trades"] = expected_min_trades
    if low_trade_warning:
        metrics["low_trade_warning_reason"] = (
            f"{n_trades} trades below diagnostic threshold "
            f"{expected_min_trades} across {active_rebalance_count} active rebalances"
        )
        metrics["low_trade_primary_bottleneck"] = primary_bottleneck
    if not trades.empty:
        metrics["first_trade_ts"] = str(trades["entry_ts"].min())
        metrics["last_trade_ts"] = str(trades["exit_ts"].max())
    elif metrics["regime_active_bars"] == 0:
        metrics["no_trade_reason"] = "benchmark_regime_filter_blocked_all_rebalances"
    elif metrics["score_coverage_at_reb_pct"] == 0.0:
        metrics["no_trade_reason"] = "insufficient_feature_score_coverage"
    elif metrics["raw_entry_signal_bars"] == 0:
        metrics["no_trade_reason"] = "entry_filters_blocked_all_rebalances"
    elif metrics["target_active_rebalance_bars"] == 0:
        metrics["no_trade_reason"] = "exit_rules_removed_all_raw_entries"
    else:
        metrics["no_trade_reason"] = "no_closed_round_trips_detected"

    return BacktestResult(
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        positions=actual_weights,
        target_weights=target_weights_reb,
        trades=trades,
        metrics=metrics,
    )
