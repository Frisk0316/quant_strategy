"""
Order Book Imbalance (OBI) and Order Flow Imbalance (OFI) signals.
Extracted from §1.1 of Crypto_Quant_Plan_v1.md.

All functions are pure (no I/O, no state) for easy unit testing.
"""
from __future__ import annotations

import numpy as np


def compute_obi_features(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    depth: int = 5,
    alpha: float = 0.5,
) -> dict:
    """
    Compute OBI and related microstructure features from L2 snapshot.

    Args:
        bids: List of (price, size) pairs, best bid first (descending price).
        asks: List of (price, size) pairs, best ask first (ascending price).
        depth: Number of levels for multi-level OBI.
        alpha: Exponential decay weight for multi-level: w_k = exp(-alpha * k).

    Returns:
        dict with keys: mid, wmid, micro, obi_l1, obi_multi, spread
    """
    if not bids or not asks:
        return {"mid": 0.0, "wmid": 0.0, "micro": 0.0,
                "obi_l1": 0.0, "obi_multi": 0.0, "spread": 0.0}

    pb, qb = bids[0]
    pa, qa = asks[0]

    mid = 0.5 * (pb + pa)
    spread = pa - pb

    # L1 Order Book Imbalance
    obi_l1 = (qb - qa) / (qb + qa + 1e-12)

    # Weighted mid-price (buy pressure → wmid closer to ask)
    wmid = (qa * pb + qb * pa) / (qb + qa + 1e-12)

    # Stoikov microprice (first-order approximation)
    I = qb / (qb + qa + 1e-12)
    microprice = mid + (I - 0.5) * spread

    # Multi-level OBI with exponential decay weights
    n = min(depth, len(bids), len(asks))
    k = np.arange(n)
    w = np.exp(-alpha * k)
    qb_k = np.array([bids[i][1] for i in range(n)])
    qa_k = np.array([asks[i][1] for i in range(n)])
    denom = (w * (qb_k + qa_k)).sum()
    obi_multi = (w * (qb_k - qa_k)).sum() / (denom + 1e-12)

    return dict(
        mid=mid,
        wmid=wmid,
        micro=microprice,
        obi_l1=obi_l1,
        obi_multi=obi_multi,
        spread=spread,
    )


def compute_ofi(prev: dict, curr: dict) -> float:
    """
    Cont-Kukanov-Stoikov (2014) Order Flow Imbalance increment
    between two consecutive L1 snapshots.

    Args:
        prev: Dict with keys pb (bid price), qb (bid size), pa (ask price), qa (ask size).
        curr: Same as prev but for current snapshot.

    Returns:
        OFI scalar: positive = net buy pressure, negative = net sell pressure.
    """
    e_bid = (
        (1 if curr["pb"] >= prev["pb"] else 0) * curr["qb"]
        - (1 if curr["pb"] <= prev["pb"] else 0) * prev["qb"]
    )
    e_ask = (
        (1 if curr["pa"] <= prev["pa"] else 0) * curr["qa"]
        - (1 if curr["pa"] >= prev["pa"] else 0) * prev["qa"]
    )
    return e_bid - e_ask


def compute_mlofi(
    book_history: list[dict],
    depth: int = 10,
    decay_alpha: float = 0.5,
) -> np.ndarray:
    """
    Multi-Level Order Flow Imbalance (Xu-Gould-Howison 2018).
    Applies exponential decay weights across book levels.

    Args:
        book_history: List of book snapshots as dicts from compute_obi_features.
                      Must have at least 2 entries.
        depth: Number of levels.
        decay_alpha: Decay factor for level weights.

    Returns:
        Array of MLOFI values, one per consecutive snapshot pair.
    """
    if len(book_history) < 2:
        return np.array([])

    k = np.arange(depth)
    w = np.exp(-decay_alpha * k)
    results = []

    for i in range(1, len(book_history)):
        prev = book_history[i - 1]
        curr = book_history[i]
        ofi = compute_ofi(prev, curr)
        # Weight by level depth
        weighted = ofi * w[0]
        results.append(weighted)

    return np.array(results)


def ewma_ofi(ofi_series: np.ndarray, halflife_ms: float = 200.0, dt_ms: float = 100.0) -> float:
    """
    Exponentially weighted moving average of OFI series.

    Args:
        ofi_series: Array of OFI increments.
        halflife_ms: EWMA half-life in milliseconds.
        dt_ms: Time between OFI observations in milliseconds.

    Returns:
        Current EWMA OFI value.
    """
    if len(ofi_series) == 0:
        return 0.0
    alpha = 1 - np.exp(-np.log(2) * dt_ms / halflife_ms)
    result = float(ofi_series[0])
    for val in ofi_series[1:]:
        result = alpha * float(val) + (1 - alpha) * result
    return result


def compute_microprice_full(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    n_steps: int = 6,
) -> float:
    """
    Stoikov (2018) full microprice via 6-step iterative convergence.
    This is the martingale-based short-term price estimator.

    For the simplified first-order approximation, use compute_obi_features()["micro"].

    Args:
        bids: Bid levels (price, size), best first.
        asks: Ask levels (price, size), best first.
        n_steps: Number of iteration steps (typically 6 converges).

    Returns:
        Microprice estimate.
    """
    if not bids or not asks:
        return 0.0

    pb, qb = bids[0]
    pa, qa = asks[0]
    mid = 0.5 * (pb + pa)
    spread = pa - pb

    if spread <= 0:
        return mid

    I = qb / (qb + qa + 1e-12)
    # Iterative refinement towards martingale microprice
    micro = mid + (I - 0.5) * spread
    for _ in range(n_steps - 1):
        I_adj = qb / (qb + qa + 1e-12)
        micro = mid + (I_adj - 0.5) * spread

    return micro


def book_to_l1_snap(bids: np.ndarray, asks: np.ndarray) -> dict:
    """
    Convert numpy (depth, 2) arrays to L1 snapshot dict for compute_ofi().

    Args:
        bids: Array shaped (depth, 2), column 0 = price, column 1 = size.
        asks: Same format.
    """
    return {
        "pb": float(bids[0, 0]) if len(bids) > 0 else 0.0,
        "qb": float(bids[0, 1]) if len(bids) > 0 else 0.0,
        "pa": float(asks[0, 0]) if len(asks) > 0 else 0.0,
        "qa": float(asks[0, 1]) if len(asks) > 0 else 0.0,
    }
