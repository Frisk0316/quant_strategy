"""Fast parameter scanners for active bar-level research helpers."""
from __future__ import annotations

import pandas as pd


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
