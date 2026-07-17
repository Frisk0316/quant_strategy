import math
from statistics import NormalDist

import pytest

from backtesting.pipeline_power_screen import min_detectable_sharpe


def test_min_detectable_sharpe_matches_closed_form_normal_inversion():
    n_obs = 900
    breadth = 1
    n_trials = 4
    a_n = n_obs * breadth - 1
    z = NormalDist().inv_cdf(0.95)
    gamma = 0.5772156649
    c_n = (
        (1.0 - gamma) * NormalDist().inv_cdf(1.0 - 1.0 / n_trials)
        + gamma * NormalDist().inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    )
    psr_floor = z / math.sqrt(a_n - z * z / 2.0)
    dsr_floor = (
        math.sqrt(a_n) * c_n
        + z * math.sqrt(a_n + (c_n * c_n - z * z) / 2.0)
    ) / (a_n - z * z / 2.0)
    expected = math.sqrt(365.0) * max(psr_floor, dsr_floor)

    actual = min_detectable_sharpe(
        breadth=breadth,
        n_obs=n_obs,
        n_trials=n_trials,
    )

    assert actual == pytest.approx(expected, abs=1e-3)
    assert actual == pytest.approx(1.7206, abs=1e-3)
