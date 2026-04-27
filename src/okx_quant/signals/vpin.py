"""
VPIN (Volume-synchronized Probability of Informed Trading) computation.
Extracted from §1.2 of Crypto_Quant_Plan_v1.md.

CRITICAL: VPIN is a DIRECTIONLESS signal — it measures toxic flow intensity.
Use it to WIDEN SPREADS, not to determine trade direction.
Direction must come from OBI/CVD signals.

Reference: Easley-López de Prado-O'Hara (2012)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def compute_vpin(
    trades: pd.DataFrame,
    V_bucket: float,
    n_window: int = 50,
    bar_seconds: int = 1,
) -> pd.DataFrame:
    """
    Compute VPIN using Bulk Volume Classification (BVC).

    Args:
        trades: DataFrame with columns ['ts' (datetime or str), 'price', 'size'].
        V_bucket: Volume per bucket. Recommended: daily_volume / 75.
        n_window: Rolling window of buckets for VPIN calculation.
        bar_seconds: Time bar interval in seconds for BVC aggregation.

    Returns:
        DataFrame indexed by bucket with columns: vB, vS, imb, VPIN, CDF.
    """
    df = trades.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    bars = (
        df.set_index("ts")
        .resample(f"{bar_seconds}s")
        .agg(close=("price", "last"), volume=("size", "sum"))
        .dropna()
    )
    bars["dp"] = bars["close"].diff()
    sigma = bars["dp"].rolling(1000, min_periods=50).std()

    # Bulk Volume Classification: P(buy) = Phi(dp / sigma)
    safe_sigma = sigma.clip(lower=1e-10)
    bars["vB"] = bars["volume"] * norm.cdf(bars["dp"] / safe_sigma)
    bars["vS"] = bars["volume"] - bars["vB"]

    # Assign to buckets based on cumulative volume
    bars["bucket"] = (bars["volume"].cumsum() // V_bucket).astype(int)
    bkt = bars.groupby("bucket").agg(vB=("vB", "sum"), vS=("vS", "sum"))
    bkt["imb"] = (bkt["vB"] - bkt["vS"]).abs()
    bkt["VPIN"] = bkt["imb"].rolling(n_window).sum() / (n_window * V_bucket)
    bkt["CDF"] = bkt["VPIN"].rank(pct=True)

    return bkt


def classify_bvc(
    price_diff: float,
    sigma: float,
    volume: float,
) -> tuple[float, float]:
    """
    Classify a single bar's volume into buy and sell using BVC.

    Returns:
        (v_buy, v_sell)
    """
    if sigma <= 0:
        return volume * 0.5, volume * 0.5
    p_buy = float(norm.cdf(price_diff / sigma))
    v_buy = volume * p_buy
    v_sell = volume - v_buy
    return v_buy, v_sell


def vpin_regime(vpin_cdf: float) -> str:
    """
    Classify current VPIN level into a regime.

    Thresholds from §1.2:
        < 0.25: normal (healthy liquidity)
        0.25–0.70: elevated (caution)
        > 0.70: toxic (widen spread significantly or step back)

    Args:
        vpin_cdf: VPIN CDF percentile rank in [0, 1].

    Returns:
        'normal' | 'elevated' | 'toxic'
    """
    if vpin_cdf > 0.70:
        return "toxic"
    elif vpin_cdf > 0.25:
        return "elevated"
    return "normal"


def estimate_bucket_size(daily_volume: float, divisor: int = 75) -> float:
    """
    Recommended VPIN bucket size: daily_volume / divisor.
    Typical divisor 50–100 (≈ 15–30 minutes of volume per bucket for BTC).

    Args:
        daily_volume: Estimated average daily traded volume.
        divisor: Bucket divisor (default 75, range 50–100).
    """
    return daily_volume / divisor


def vpin_spread_multiplier(vpin_cdf: float, beta: float = 2.0) -> float:
    """
    Compute spread multiplier for Avellaneda-Stoikov based on VPIN.
    Formula from §1.3: spread *= (1 + beta * max(vpin - 0.4, 0))

    Args:
        vpin_cdf: Current VPIN CDF value.
        beta: Sensitivity parameter (default 2.0 from plan).

    Returns:
        Spread multiplier >= 1.0.
    """
    return 1.0 + beta * max(vpin_cdf - 0.4, 0.0)
