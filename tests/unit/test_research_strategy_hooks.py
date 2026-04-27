"""Tests for research-derived strategy gates and throttles."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np

from okx_quant.signals.regime import composite_risk_multiplier
from okx_quant.strategies.funding_carry import evaluate_funding_carry_entry
from okx_quant.strategies.pairs_trading import PairsTradingStrategy


def test_composite_risk_multiplier_combines_stress_inputs():
    normal = composite_risk_multiplier(vpin_cdf=0.10, spread_percentile=0.50)
    stressed = composite_risk_multiplier(
        vpin_cdf=0.90,
        spread_percentile=0.99,
        high_vol=True,
    )

    assert normal == 1.0
    assert 0.0 < stressed < normal


def test_composite_risk_multiplier_hard_drawdown_zeroes_risk():
    assert composite_risk_multiplier(drawdown_pct=0.16) == 0.0


def test_funding_carry_entry_gate_blocks_bad_basis():
    allowed, reason = evaluate_funding_carry_entry(
        apr=0.25,
        min_apr=0.12,
        basis_z=3.0,
        max_abs_basis_z=2.5,
    )

    assert not allowed
    assert reason == "basis_too_extreme"


def test_funding_carry_entry_gate_allows_clean_high_apr():
    allowed, reason = evaluate_funding_carry_entry(
        apr=0.25,
        min_apr=0.12,
        basis_z=1.0,
        crowding=0.20,
    )

    assert allowed
    assert reason == "allowed"


def test_pairs_quality_gate_blocks_slow_half_life():
    strategy = PairsTradingStrategy({"max_half_life": 48.0})
    strategy._ou_params = {"theta": 0.01, "mu": 0.0, "sigma": 0.01, "half_life": 72.0}

    ok, reason = strategy._quality_gate_passed()

    assert not ok
    assert reason == "half_life_too_slow"


def test_pairs_quality_gate_allows_stable_spread():
    strategy = PairsTradingStrategy({"max_half_life": 48.0})
    strategy._ou_params = {"theta": 0.10, "mu": 0.0, "sigma": 0.01, "half_life": 12.0}
    strategy._P = 1.0

    ok, reason = strategy._quality_gate_passed()

    assert ok
    assert reason == "passed"
