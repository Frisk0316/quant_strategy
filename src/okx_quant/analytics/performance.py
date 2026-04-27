"""
Performance metrics for strategy evaluation.
Extracted from §3.4 of Crypto_Quant_Plan_v1.md.

All functions are pure (no I/O, no state).
Crypto: annualize with sqrt(365) for daily, sqrt(365*24) for hourly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import skew, kurtosis


def sharpe(r: pd.Series | np.ndarray, rf: float = 0.0, periods: int = 365) -> float:
    """Annualized Sharpe ratio. periods=365 for daily, 365*24 for hourly."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2:
        return 0.0
    e = r - rf
    std = e.std(ddof=1)
    if std == 0:
        return 0.0
    return float(np.sqrt(periods) * e.mean() / std)


def sortino(r: pd.Series | np.ndarray, rf: float = 0.0, periods: int = 365) -> float:
    """Sortino ratio (downside deviation only)."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2:
        return 0.0
    e = r - rf
    dn = e[e < 0]
    if len(dn) == 0:
        return float("inf")
    downside_std = np.sqrt((dn ** 2).mean())
    if downside_std == 0:
        return 0.0
    return float(np.sqrt(periods) * e.mean() / downside_std)


def max_drawdown(r: pd.Series | np.ndarray) -> float:
    """Maximum drawdown (negative number). Returns 0.0 if no drawdown."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return 0.0
    eq = (1 + r).cumprod()
    eq_series = pd.Series(eq)
    dd = (eq_series - eq_series.cummax()) / eq_series.cummax()
    return float(dd.min())


def calmar(r: pd.Series | np.ndarray, periods: int = 365) -> float:
    """Calmar ratio = annualized CAGR / |max_drawdown|."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return 0.0
    eq = (1 + r).cumprod()
    years = len(r) / periods
    if years == 0:
        return 0.0
    log_cagr = np.log(float(eq[-1])) / years
    cagr = float("inf") if log_cagr > 709 else float(np.exp(log_cagr) - 1)
    mdd = abs(max_drawdown(r))
    if mdd == 0:
        return float("inf")
    return cagr / mdd


def profit_factor(r: pd.Series | np.ndarray) -> float:
    """Ratio of gross profit to gross loss."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    gross_profit = r[r > 0].sum()
    gross_loss = abs(r[r < 0].sum())
    if gross_loss == 0:
        return float("inf")
    return float(gross_profit / gross_loss)


def win_rate(r: pd.Series | np.ndarray) -> float:
    """Fraction of non-zero returns that are positive."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    non_zero = r[r != 0]
    if len(non_zero) == 0:
        return 0.0
    return float((non_zero > 0).sum() / len(non_zero))


def omega(r: pd.Series | np.ndarray, tau: float = 0.0) -> float:
    """Omega ratio: sum of gains above tau / sum of losses below tau."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    gains = (r - tau).clip(min=0).sum()
    losses = (tau - r).clip(min=0).sum()
    if losses == 0:
        return float("inf")
    return float(gains / losses)


def tail_ratio(r: pd.Series | np.ndarray) -> float:
    """95th percentile / 5th percentile of absolute returns."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return 1.0
    p5 = abs(np.percentile(r, 5))
    if p5 == 0:
        return float("inf")
    return float(abs(np.percentile(r, 95)) / p5)


def summary(r: pd.Series | np.ndarray, periods: int = 365) -> dict:
    """Compute all metrics at once. Convenient for reporting."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    return {
        "n_periods": len(r),
        "total_return": float((1 + r).prod() - 1),
        "sharpe": sharpe(r, periods=periods),
        "sortino": sortino(r, periods=periods),
        "max_drawdown": max_drawdown(r),
        "calmar": calmar(r, periods=periods),
        "profit_factor": profit_factor(r),
        "win_rate": win_rate(r),
        "omega": omega(r),
        "tail_ratio": tail_ratio(r),
        "skewness": float(skew(r)) if len(r) >= 3 else 0.0,
        "kurtosis": float(kurtosis(r, fisher=False)) if len(r) >= 4 else 3.0,
    }
