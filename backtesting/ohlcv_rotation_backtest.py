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

def compute_metrics(
    equity_curve: pd.Series,
    portfolio_returns: pd.Series,
    target_weights: pd.DataFrame,
    trades: pd.DataFrame,
) -> dict:
    n_minutes = len(portfolio_returns)
    minutes_per_year = 365 * 24 * 60

    total_return = float(equity_curve.iloc[-1] - 1) if not equity_curve.empty else 0.0

    ann_factor = minutes_per_year / n_minutes if n_minutes > 0 else 1.0
    annualized_return = (1 + total_return) ** ann_factor - 1

    ann_vol = float(portfolio_returns.std() * math.sqrt(minutes_per_year))
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
    records = []
    prev = pd.Series(0.0, index=target_weights.columns)

    open_entries: dict[str, dict] = {}  # inst_id → {entry_ts, entry_price}

    all_ts = target_weights.index
    for ts in all_ts:
        curr = target_weights.loc[ts]

        for inst in target_weights.columns:
            p = prev.get(inst, 0.0)
            c = curr.get(inst, 0.0)

            # Entry
            if p == 0.0 and c > 0.0:
                ep = close_panel.loc[ts, inst] if ts in close_panel.index else np.nan
                open_entries[inst] = {"entry_ts": ts, "entry_price": ep}

            # Exit
            elif p > 0.0 and c == 0.0 and inst in open_entries:
                ep_data = open_entries.pop(inst)
                xp = close_panel.loc[ts, inst] if ts in close_panel.index else np.nan
                entry_p = ep_data["entry_price"]
                pnl = (xp - entry_p) / entry_p if (not np.isnan(xp) and not np.isnan(entry_p) and entry_p != 0) else np.nan
                hold_min = int((ts - ep_data["entry_ts"]).total_seconds() / 60)
                records.append(
                    {
                        "inst_id": inst,
                        "entry_ts": ep_data["entry_ts"],
                        "exit_ts": ts,
                        "entry_price": entry_p,
                        "exit_price": xp,
                        "pnl": pnl,
                        "holding_minutes": hold_min,
                    }
                )

        prev = curr.copy()

    # Close any still-open positions at end
    for inst, ep_data in open_entries.items():
        last_ts = all_ts[-1]
        xp = close_panel.loc[last_ts, inst] if last_ts in close_panel.index else np.nan
        entry_p = ep_data["entry_price"]
        pnl = (xp - entry_p) / entry_p if (not np.isnan(xp) and not np.isnan(entry_p) and entry_p != 0) else np.nan
        hold_min = int((last_ts - ep_data["entry_ts"]).total_seconds() / 60)
        records.append(
            {
                "inst_id": inst,
                "entry_ts": ep_data["entry_ts"],
                "exit_ts": last_ts,
                "entry_price": entry_p,
                "exit_price": xp,
                "pnl": pnl,
                "holding_minutes": hold_min,
            }
        )

    if not records:
        return pd.DataFrame(
            columns=["inst_id", "entry_ts", "exit_ts", "entry_price", "exit_price", "pnl", "holding_minutes"]
        )
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
    metrics = compute_metrics(equity_curve, portfolio_returns, target_weights_1m, trades)

    return BacktestResult(
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        positions=actual_weights,
        target_weights=target_weights_reb,
        trades=trades,
        metrics=metrics,
    )
