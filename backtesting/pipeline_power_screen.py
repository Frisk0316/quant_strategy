"""Cheap ex-ante PSR/DSR power screen for Stage 2."""
from __future__ import annotations

import math
from statistics import NormalDist


_EULER_GAMMA = 0.5772156649


def _expected_max_z(n_trials: int) -> float:
    if n_trials <= 1:
        return 0.0
    normal = NormalDist()
    return (
        (1.0 - _EULER_GAMMA) * normal.inv_cdf(1.0 - 1.0 / n_trials)
        + _EULER_GAMMA * normal.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    )


def _required_per_observation_sharpe(
    *,
    effective_n: float,
    benchmark: float,
    probability: float,
    skew: float,
    kurtosis: float,
) -> float:
    """Invert the PSR equation for a fixed benchmark and return its smallest root."""
    z = NormalDist().inv_cdf(probability)
    a_n = effective_n - 1.0
    variance_quadratic = (kurtosis - 1.0) / 4.0
    a = a_n - z * z * variance_quadratic
    b = -2.0 * a_n * benchmark + z * z * skew
    c = a_n * benchmark * benchmark - z * z

    if abs(a) < 1e-15:
        roots = (-c / b,) if abs(b) >= 1e-15 else ()
    else:
        discriminant = b * b - 4.0 * a * c
        roots = () if discriminant < 0.0 else (
            (-b - math.sqrt(discriminant)) / (2.0 * a),
            (-b + math.sqrt(discriminant)) / (2.0 * a),
        )

    valid = []
    for sharpe in roots:
        variance = 1.0 - skew * sharpe + variance_quadratic * sharpe * sharpe
        if sharpe >= benchmark and variance > 0.0:
            statistic = (sharpe - benchmark) * math.sqrt(a_n / variance)
            if statistic >= z - 1e-12:
                valid.append(sharpe)
    if not valid:
        raise ValueError("PSR/DSR threshold has no finite Sharpe solution")
    return min(valid)


def min_detectable_sharpe(
    *,
    breadth: float,
    n_obs: int,
    n_trials: int,
    psr_probability: float = 0.95,
    dsr_probability: float = 0.95,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    periods_per_year: float = 365.0,
) -> float:
    """Return the minimum annualized Sharpe clearing both PSR and DSR.

    ``breadth`` multiplies the OOS observation count as the ex-ante estimate of
    independent bets. Normal moments are used unless sample estimates are
    supplied. DSR's across-trial dispersion is approximated by the null Sharpe
    standard error because Stage 2 intentionally has no backtest ``sr_list``.
    """
    values = (breadth, psr_probability, dsr_probability, skew, kurtosis, periods_per_year)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("power-screen inputs must be finite")
    if breadth <= 0.0:
        raise ValueError("breadth must be > 0")
    if type(n_obs) is not int or n_obs <= 0:
        raise ValueError("n_obs must be a positive integer")
    if type(n_trials) is not int or n_trials <= 0:
        raise ValueError("n_trials must be a positive integer")
    if not 0.5 < psr_probability < 1.0 or not 0.5 < dsr_probability < 1.0:
        raise ValueError("PSR/DSR probabilities must be between 0.5 and 1")
    if periods_per_year <= 0.0:
        raise ValueError("periods_per_year must be > 0")

    effective_n = float(n_obs) * float(breadth)
    if effective_n < 4.0:
        raise ValueError("effective observations must be at least 4")
    a_n = effective_n - 1.0
    dsr_benchmark = _expected_max_z(n_trials) / math.sqrt(a_n)
    psr_floor = _required_per_observation_sharpe(
        effective_n=effective_n,
        benchmark=0.0,
        probability=psr_probability,
        skew=skew,
        kurtosis=kurtosis,
    )
    dsr_floor = _required_per_observation_sharpe(
        effective_n=effective_n,
        benchmark=dsr_benchmark,
        probability=dsr_probability,
        skew=skew,
        kurtosis=kurtosis,
    )
    return max(psr_floor, dsr_floor) * math.sqrt(periods_per_year)
