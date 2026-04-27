"""Unit tests for VPIN signal functions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

from okx_quant.signals.vpin import (
    classify_bvc,
    vpin_regime,
    vpin_position_multiplier,
    vpin_spread_multiplier,
    vpin_toxicity_controls,
    compute_vpin,
    estimate_bucket_size,
)


def test_classify_bvc_neutral():
    """When price change is zero, buy and sell should be equal."""
    v_buy, v_sell = classify_bvc(price_diff=0.0, sigma=1.0, volume=100.0)
    assert abs(v_buy - 50.0) < 0.1
    assert abs(v_sell - 50.0) < 0.1


def test_classify_bvc_strong_buy():
    """Large positive price change → most volume classified as buy."""
    v_buy, v_sell = classify_bvc(price_diff=5.0, sigma=1.0, volume=100.0)
    assert v_buy > 95.0
    assert v_sell < 5.0


def test_classify_bvc_strong_sell():
    """Large negative price change → most volume classified as sell."""
    v_buy, v_sell = classify_bvc(price_diff=-5.0, sigma=1.0, volume=100.0)
    assert v_buy < 5.0
    assert v_sell > 95.0


def test_classify_bvc_volume_conserved():
    """Buy + sell should equal total volume."""
    v_buy, v_sell = classify_bvc(price_diff=1.0, sigma=0.5, volume=77.3)
    assert abs(v_buy + v_sell - 77.3) < 1e-9


def test_vpin_regime_normal():
    assert vpin_regime(0.10) == "normal"
    assert vpin_regime(0.24) == "normal"


def test_vpin_regime_elevated():
    assert vpin_regime(0.30) == "elevated"
    assert vpin_regime(0.69) == "elevated"


def test_vpin_regime_toxic():
    assert vpin_regime(0.75) == "toxic"
    assert vpin_regime(1.0) == "toxic"


def test_spread_multiplier_below_threshold():
    """VPIN below 0.4 should give multiplier exactly 1.0."""
    assert vpin_spread_multiplier(0.3, beta=2.0) == 1.0


def test_spread_multiplier_above_threshold():
    """VPIN above 0.4 should give multiplier > 1.0."""
    mult = vpin_spread_multiplier(0.7, beta=2.0)
    expected = 1.0 + 2.0 * (0.7 - 0.4)
    assert abs(mult - expected) < 1e-9


def test_vpin_position_multiplier_directionless_throttle():
    """VPIN should throttle size without creating direction."""
    assert vpin_position_multiplier(0.10) == 1.0
    assert vpin_position_multiplier(0.50) == 0.5
    assert vpin_position_multiplier(0.90) == 0.25


def test_vpin_toxicity_controls_are_serializable():
    controls = vpin_toxicity_controls(0.90, beta=2.0)
    assert controls["regime"] == "toxic"
    assert controls["spread_multiplier"] > 1.0
    assert controls["size_multiplier"] == 0.25


def test_estimate_bucket_size():
    """Bucket size should equal daily_volume / divisor."""
    assert estimate_bucket_size(75_000, divisor=75) == 1_000.0


def test_compute_vpin_returns_dataframe():
    """compute_vpin should return a non-empty DataFrame."""
    np.random.seed(42)
    n = 1000
    prices = 100 + np.cumsum(np.random.randn(n) * 0.1)
    trades = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="1s"),
        "price": prices,
        "size": np.random.uniform(0.1, 5.0, n),
    })
    result = compute_vpin(trades, V_bucket=100.0, n_window=10)
    assert isinstance(result, pd.DataFrame)
    assert "VPIN" in result.columns
    assert "CDF" in result.columns
    assert len(result) > 0
