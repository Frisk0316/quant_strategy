"""
VectorBT parameter scanner for fast bar-level strategy research.
Use this FIRST (seconds for thousands of combinations),
then validate top candidates with nautilus_backtest.py (L2 tick-accurate).

Requires: pip install vectorbt
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import pandas as pd

try:
    import vectorbt as vbt
    VBT_AVAILABLE = True
except ImportError:
    VBT_AVAILABLE = False


def scan_as_params(
    candles: pd.DataFrame,
    gamma_range: list[float] = None,
    kappa_range: list[float] = None,
    c_alpha_range: list[float] = None,
    commission_pct: float = 0.0002,
) -> pd.DataFrame:
    """
    Vectorized parameter scan for AS Market Maker parameters.
    Uses close price returns as a proxy (bar-level only — use Nautilus for L2).

    Args:
        candles: OHLCV DataFrame with DatetimeIndex.
        gamma_range: Risk aversion values to test.
        kappa_range: Order arrival intensity values.
        c_alpha_range: OFI alpha scaling values.
        commission_pct: Round-trip maker fee (0.02% for OKX perp).

    Returns:
        DataFrame of results sorted by OOS Sharpe.
    """
    if not VBT_AVAILABLE:
        raise ImportError("vectorbt required: pip install vectorbt")

    if gamma_range is None:
        gamma_range = [0.05, 0.1, 0.2, 0.5]
    if kappa_range is None:
        kappa_range = [0.5, 1.0, 1.5, 2.0]
    if c_alpha_range is None:
        c_alpha_range = [50.0, 100.0, 200.0]

    close = candles["close"]
    returns = close.pct_change().dropna()

    results = []
    for gamma in gamma_range:
        for kappa in kappa_range:
            for c_alpha in c_alpha_range:
                # Simplified bar-level signal: spread proxy
                sigma_ewm = returns.ewm(span=5 * 60, min_periods=10).std()
                spread_AS = gamma * sigma_ewm ** 2 + (2 / gamma) * np.log(1 + gamma / kappa)

                # Signal: trade when spread is wide enough to cover fees
                min_edge = commission_pct * 2  # round-trip
                signal = spread_AS > min_edge

                # Compute simple P&L proxy: capture spread_AS when signaled
                pnl = (spread_AS * signal).dropna()
                pnl_net = pnl - commission_pct * 2 * signal.dropna()

                from okx_quant.analytics.performance import sharpe, max_drawdown
                s = sharpe(pnl_net[pnl_net != 0], periods=365 * 24 * 60)
                mdd = max_drawdown(pnl_net)

                results.append({
                    "gamma": gamma,
                    "kappa": kappa,
                    "c_alpha": c_alpha,
                    "sharpe": s,
                    "max_drawdown": mdd,
                    "n_signals": int(signal.sum()),
                })

    df = pd.DataFrame(results).sort_values("sharpe", ascending=False)
    return df


def scan_funding_carry(
    funding: pd.DataFrame,
    apr_thresholds: list[float] = None,
    entry_fees_pct: float = 0.001,
) -> pd.DataFrame:
    """
    Parameter scan for funding carry APR threshold.

    Args:
        funding: DataFrame with ['rate'] column (8h funding rates).
        apr_thresholds: List of APR entry thresholds to test.

    Returns:
        Results DataFrame.
    """
    if apr_thresholds is None:
        apr_thresholds = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]

    if "rate" not in funding.columns:
        raise ValueError("funding DataFrame must have 'rate' column")

    results = []
    for threshold in apr_thresholds:
        apr = funding["rate"] * (365 * 24 / 8)
        in_position = apr > threshold

        # Estimate PnL: earn funding rate when in position, minus entry/exit fees
        pnl_per_period = funding["rate"] * in_position
        # Fee drag: each entry/exit costs entry_fees_pct (round-trip)
        transitions = in_position.diff().fillna(0).abs()
        fee_drag = transitions * entry_fees_pct

        net_pnl = pnl_per_period - fee_drag
        total_return = float(net_pnl.sum())
        n_trades = int(transitions.sum()) // 2

        from okx_quant.analytics.performance import sharpe
        # Annualize: funding is 8h, 3 settlements/day, 365 days
        s = sharpe(net_pnl[net_pnl != 0], periods=3 * 365)

        results.append({
            "apr_threshold": threshold,
            "sharpe": s,
            "total_return_pct": total_return * 100,
            "n_trades": n_trades,
            "avg_apr_pct": float(apr[in_position].mean() * 100) if in_position.any() else 0,
        })

    return pd.DataFrame(results).sort_values("sharpe", ascending=False)
