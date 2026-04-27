"""
Market regime detection for strategy gating.
Not in the live order path — runs on a slower cadence (minutes/hours).

Reference: §4.3 of Crypto_Quant_Plan_v1.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class HMMModel:
    model: object  # hmmlearn.GaussianHMM
    state_labels: dict[int, str]  # {0: 'bear', 1: 'chop', 2: 'bull'}
    n_states: int = 3


def fit_hmm_regime(
    returns: pd.Series,
    n_states: int = 3,
    n_iter: int = 200,
    random_state: int = 42,
) -> HMMModel:
    """
    Fit a 3-state Hidden Markov Model for regime detection.
    Features: daily return + 20-day rolling range (vol proxy).

    States are labelled by mean return: lowest = 'bear', highest = 'bull'.

    Args:
        returns: Daily or hourly return series.
        n_states: Number of hidden states (default 3).
        n_iter: EM iterations.
    """
    try:
        from hmmlearn import hmm as hmmlearn
    except ImportError:
        raise ImportError("hmmlearn required: pip install hmmlearn")

    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]

    # Feature matrix: [return, rolling range as vol proxy]
    window = min(20, len(r) // 4)
    rolling_range = pd.Series(r).rolling(window, min_periods=1).max() \
                  - pd.Series(r).rolling(window, min_periods=1).min()
    X = np.column_stack([r, rolling_range.values])

    model = hmmlearn.GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=n_iter,
        random_state=random_state,
    )
    model.fit(X)

    # Label states by mean return (ascending: bear → chop → bull)
    state_means = model.means_[:, 0]
    sorted_states = np.argsort(state_means)
    labels = {int(sorted_states[0]): "bear", int(sorted_states[1]): "chop",
              int(sorted_states[2]): "bull"} if n_states == 3 else {}

    return HMMModel(model=model, state_labels=labels, n_states=n_states)


def current_regime(model: HMMModel, recent_returns: pd.Series) -> str:
    """
    Predict the current regime using the fitted HMM.

    Args:
        model: Fitted HMMModel.
        recent_returns: Recent return series (at least 20 observations).

    Returns:
        Regime label: 'bear' | 'chop' | 'bull'
    """
    r = np.asarray(recent_returns, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2:
        return "chop"

    window = min(20, len(r))
    rolling_range = pd.Series(r).rolling(window, min_periods=1).max() \
                  - pd.Series(r).rolling(window, min_periods=1).min()
    X = np.column_stack([r, rolling_range.values])

    states = model.model.predict(X)
    current_state = int(states[-1])
    return model.state_labels.get(current_state, "chop")


def garch_vol_regime(
    returns: pd.Series,
    threshold_multiplier: float = 1.5,
    lookback: int = 126,
) -> bool:
    """
    Detect high-volatility regime using GARCH(1,1).
    Falls back to rolling std if arch package not available.

    Returns:
        True if in high-vol regime (conditional vol > threshold_multiplier × 6m median).
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]

    try:
        from arch import arch_model
        model = arch_model(r * 100, vol="GARCH", p=1, q=1, dist="normal")
        res = model.fit(disp="off", last_obs=len(r))
        cond_vol = float(res.conditional_volatility[-1]) / 100
    except (ImportError, Exception):
        # Fallback: use rolling std
        rolling = pd.Series(r).rolling(20, min_periods=10).std()
        cond_vol = float(rolling.iloc[-1]) if not rolling.empty else 0.0

    # Compare to 6-month median
    recent = r[-lookback:] if len(r) >= lookback else r
    median_vol = float(np.std(recent))
    return cond_vol > threshold_multiplier * median_vol


def cusum_changepoint(
    series: np.ndarray,
    threshold: Optional[float] = None,
) -> list[int]:
    """
    CUSUM-based change point detection.
    Returns indices where a structural break is detected.

    Args:
        series: 1D array of values (e.g., returns, spread).
        threshold: CUSUM threshold. Defaults to 5 * std(series).
    """
    s = np.asarray(series, dtype=float)
    mu = np.mean(s)
    if threshold is None:
        threshold = 5.0 * np.std(s)

    cusum_pos = np.zeros(len(s))
    cusum_neg = np.zeros(len(s))
    changepoints = []

    for i in range(1, len(s)):
        cusum_pos[i] = max(0, cusum_pos[i - 1] + (s[i] - mu))
        cusum_neg[i] = min(0, cusum_neg[i - 1] + (s[i] - mu))
        if cusum_pos[i] > threshold or abs(cusum_neg[i]) > threshold:
            changepoints.append(i)
            cusum_pos[i] = 0
            cusum_neg[i] = 0

    return changepoints


def correlation_breakdown(
    strategy_returns: pd.DataFrame,
    window: int = 20,
    threshold: float = 0.6,
) -> bool:
    """
    Detect when strategy correlation spikes, indicating correlated risk.
    From §4.3: if avg pairwise correlation exceeds threshold, reduce gross.

    Args:
        strategy_returns: DataFrame where each column is one strategy's returns.
        window: Rolling window for correlation calculation.
        threshold: Average correlation threshold (default 0.6 from plan).

    Returns:
        True if correlation breakdown detected.
    """
    if strategy_returns.shape[1] < 2:
        return False
    rolling_corr = strategy_returns.rolling(window, min_periods=window // 2).corr()
    if rolling_corr.empty:
        return False
    last_corr = rolling_corr.iloc[-strategy_returns.shape[1]:]
    avg_corr = (last_corr.values.sum() - strategy_returns.shape[1]) / (
        strategy_returns.shape[1] ** 2 - strategy_returns.shape[1]
    )
    return float(avg_corr) > threshold


def composite_risk_multiplier(
    *,
    vpin_cdf: Optional[float] = None,
    spread_percentile: Optional[float] = None,
    drawdown_pct: float = 0.0,
    high_vol: bool = False,
    soft_drawdown_pct: float = 0.10,
    hard_drawdown_pct: float = 0.15,
) -> float:
    """
    Shared risk multiplier for strategy throttling.

    This is a lightweight implementation of the research-layer volatility
    regime filter: it does not create alpha, it only scales risk when multiple
    stress indicators are active.
    """
    multiplier = 1.0

    if vpin_cdf is not None:
        if vpin_cdf > 0.70:
            multiplier *= 0.25
        elif vpin_cdf > 0.25:
            multiplier *= 0.5

    if spread_percentile is not None:
        if spread_percentile > 0.95:
            multiplier *= 0.25
        elif spread_percentile > 0.80:
            multiplier *= 0.5

    if high_vol:
        multiplier *= 0.5

    if drawdown_pct >= hard_drawdown_pct:
        return 0.0
    if drawdown_pct >= soft_drawdown_pct:
        multiplier *= 0.5

    return float(np.clip(multiplier, 0.0, 1.0))
