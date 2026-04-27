"""
Position sizing functions.
Extracted from §4.1 of Crypto_Quant_Plan_v1.md.

All functions are pure (no I/O, no state).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def vol_target_size(
    returns: pd.Series | np.ndarray,
    equity: float,
    target_ann_vol: float = 0.20,
    lookback: int = 30,
) -> float:
    """
    Volatility-targeting position size (most effective single risk control).
    Automatically de-levers during market stress.

    Formula: notional = (target_vol / realized_vol) * equity

    Args:
        returns: Recent return series.
        equity: Current account equity in USD.
        target_ann_vol: Target annualized volatility (default 20%).
        lookback: Rolling window for realized vol (default 30 periods).

    Returns:
        Suggested position notional in USD.
    """
    r = pd.Series(np.asarray(returns, dtype=float)).dropna()
    if len(r) < 2:
        return 0.0
    realized = r.rolling(lookback, min_periods=2).std().iloc[-1] * np.sqrt(365 * 24)
    realized = max(float(realized), 1e-8)
    return equity * target_ann_vol / realized


def quarter_kelly(
    mu: float,
    sigma: float,
    equity: float,
    clip_min: float = 0.0025,
    clip_max: float = 0.02,
) -> float:
    """
    Quarter-Kelly position sizing.
    Full Kelly f* = mu / sigma^2 is the leverage; ¼-Kelly reduces variance ~75%.

    Args:
        mu: Expected return per period.
        sigma: Standard deviation of returns per period.
        equity: Current equity in USD.
        clip_min: Minimum risk fraction (0.25% of equity).
        clip_max: Maximum risk fraction (2% of equity, from plan §6 iron law).

    Returns:
        Suggested position notional in USD.
    """
    if sigma <= 0:
        return 0.0
    full_kelly = mu / (sigma ** 2)
    quarter_k = full_kelly / 4.0
    # Clamp to [clip_min, clip_max] fraction of equity
    fraction = float(np.clip(quarter_k, clip_min, clip_max))
    return equity * fraction


def fixed_fractional(
    equity: float,
    risk_pct: float = 0.01,
    stop_distance_pct: float = 0.02,
) -> float:
    """
    Fixed-fractional position sizing.
    Risk 1% of equity per trade; position size inversely proportional to stop distance.

    Args:
        equity: Current equity in USD.
        risk_pct: Fraction of equity to risk per trade (default 1%).
        stop_distance_pct: Stop-loss distance as fraction of price (default 2%).

    Returns:
        Suggested position notional in USD.
    """
    if stop_distance_pct <= 0:
        return 0.0
    risk_amount = equity * risk_pct
    return risk_amount / stop_distance_pct


def round_to_lot(size_usd: float, price: float, lot_sz: float, min_sz: float) -> str:
    """
    Convert USD notional to OKX contract size string, rounded to lot_sz.

    Args:
        size_usd: Notional in USD.
        price: Current instrument price.
        lot_sz: Minimum lot size from /api/v5/public/instruments.
        min_sz: Minimum order size from instruments.

    Returns:
        Size string for OKX order API, or "" if below minimum.
    """
    if price <= 0 or lot_sz <= 0:
        return ""
    raw_size = size_usd / price
    # Round down to nearest lot_sz
    rounded = float(int(raw_size / lot_sz)) * lot_sz
    if rounded < min_sz:
        return ""
    # Format without trailing zeros
    if lot_sz >= 1:
        return str(int(rounded))
    # Determine decimal places from lot_sz
    decimals = len(str(lot_sz).rstrip("0").split(".")[-1]) if "." in str(lot_sz) else 0
    return f"{rounded:.{decimals}f}"


def size_in_contracts(
    notional_usd: float,
    ct_val: float,
    price: float,
    lot_sz: float = 1.0,
    min_sz: float = 1.0,
) -> str:
    """
    Convert USD notional to OKX perpetual contract count.
    For BTC-USDT-SWAP: ctVal=0.01 BTC, so 1 contract ≈ 0.01 * price USD.

    Args:
        notional_usd: Target position notional in USD.
        ct_val: Contract face value (e.g., 0.01 for BTC-USDT-SWAP).
        price: Current mid-price.
        lot_sz: Minimum lot size (typically 1 for perp contracts).
        min_sz: Minimum order size.
    """
    if ct_val <= 0 or price <= 0:
        return ""
    contract_value = ct_val * price
    n_contracts = notional_usd / contract_value
    rounded = float(int(n_contracts / lot_sz)) * lot_sz
    if rounded < min_sz:
        return ""
    return str(int(rounded))
