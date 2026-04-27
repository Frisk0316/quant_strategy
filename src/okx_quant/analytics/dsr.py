"""
Statistical validation: Deflated Sharpe Ratio (DSR) and
Probabilistic Sharpe Ratio (PSR).

Extracted from §3.6 and §4.4 of Crypto_Quant_Plan_v1.md.

DSR < 0.95: backtest result cannot be distinguished from luck.
PSR(0) < 0.95: live track record indistinguishable from zero.

References:
  Bailey & López de Prado (2014) - DSR
  Bailey & López de Prado (2012) - PSR
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm, skew, kurtosis


def deflated_sharpe(
    returns: np.ndarray,
    sr: float,
    sr_list: list[float],
    N: int,
) -> float:
    """
    Deflated Sharpe Ratio — corrects for non-normality and multiple trials.

    Formula from §3.6:
        DSR = Phi( (SR_hat - SR0) * sqrt(T-1) / sqrt(1 - gamma3*SR + (gamma4-1)/4 * SR^2) )

    Args:
        returns: Out-of-sample return series (1D array).
        sr: Observed Sharpe ratio of the strategy being evaluated.
        sr_list: List of all Sharpe ratios tried (including SR).
        N: Total number of trials (strategies) tested.

    Returns:
        DSR in [0, 1]. Threshold: DSR >= 0.95 to avoid overfitting.
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    T = len(r)
    if T < 4:
        return 0.0

    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))  # non-excess kurtosis
    clean_sr_list = np.asarray(sr_list, dtype=float)
    clean_sr_list = clean_sr_list[~np.isnan(clean_sr_list)]
    var_sr = float(np.var(clean_sr_list, ddof=1)) if len(clean_sr_list) >= 2 else 0.0
    euler = 0.5772156649  # Euler-Mascheroni constant

    # SR benchmark (expected max SR from N trials)
    if N <= 1 or var_sr == 0.0:
        SR0 = 0.0
    else:
        SR0 = np.sqrt(var_sr) * (
            (1 - euler) * norm.ppf(1 - 1 / N)
            + euler * norm.ppf(1 - 1 / (N * np.e))
        )

    # Variance correction for non-normality
    denom = np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    if denom <= 0:
        return 0.0

    return float(norm.cdf((sr - SR0) * np.sqrt(T - 1) / denom))


def psr(returns: np.ndarray, sr_benchmark: float = 0.0) -> float:
    """
    Probabilistic Sharpe Ratio — probability that observed SR exceeds benchmark.

    Formula from §4.4:
        PSR(SR*) = Phi( (SR_hat - SR*) * sqrt(n-1) / sqrt(1 - g3*SR + (g4-1)/4 * SR^2) )

    Args:
        returns: Return series (1D array).
        sr_benchmark: The benchmark Sharpe to test against. Default 0.0 (beat zero).

    Returns:
        PSR in [0, 1]. Threshold: PSR(0) >= 0.95 for statistical significance.
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n < 4:
        return 0.0

    sr_hat = r.mean() / r.std(ddof=1)
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))

    num = (sr_hat - sr_benchmark) * np.sqrt(n - 1)
    denom = np.sqrt(1 - g3 * sr_hat + (g4 - 1) / 4 * sr_hat ** 2)
    if denom <= 0:
        return 0.0

    return float(norm.cdf(num / denom))


def pbo(returns_matrix: np.ndarray) -> float:
    """
    Probability of Backtest Overfitting (PBO).
    Combinatorial split: IS winner vs OOS rank.

    Args:
        returns_matrix: Array of shape (n_trials, n_periods).
                        Each row is one strategy's return series.

    Returns:
        PBO in [0, 1]. PBO > 0.5 indicates the selection process is worse than random.
    """
    M, T = returns_matrix.shape
    if M < 2 or T < 4:
        return 0.5

    half = T // 2
    dominates = 0
    trials = 0

    # Simple half-split PBO (full CPCV handled in backtesting/cpcv.py)
    for split in range(10):
        rng = np.random.default_rng(split)
        idx = rng.permutation(T)
        is_idx = idx[:half]
        oos_idx = idx[half:]

        is_sharpe = [returns_matrix[m, is_idx].mean() / (returns_matrix[m, is_idx].std(ddof=1) + 1e-12)
                     for m in range(M)]
        oos_sharpe = [returns_matrix[m, oos_idx].mean() / (returns_matrix[m, oos_idx].std(ddof=1) + 1e-12)
                      for m in range(M)]

        best_is = int(np.argmax(is_sharpe))
        oos_rank = float(np.argsort(np.argsort(oos_sharpe))[best_is]) / (M - 1)
        if oos_rank < 0.5:
            dominates += 1
        trials += 1

    return dominates / trials if trials > 0 else 0.5
