"""Unit tests for position sizing functions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

from okx_quant.portfolio.sizing import (
    vol_target_size,
    quarter_kelly,
    fixed_fractional,
    round_to_lot,
    size_in_contracts,
)


def test_vol_target_scales_with_volatility():
    """Higher volatility should produce smaller position size."""
    returns_low_vol = pd.Series(np.random.randn(60) * 0.001)
    returns_high_vol = pd.Series(np.random.randn(60) * 0.01)
    size_low = vol_target_size(returns_low_vol, equity=10_000.0)
    size_high = vol_target_size(returns_high_vol, equity=10_000.0)
    assert size_low > size_high


def test_vol_target_scales_with_equity():
    """Larger equity should produce proportionally larger position."""
    returns = pd.Series(np.random.randn(60) * 0.005)
    size_small = vol_target_size(returns, equity=1_000.0)
    size_large = vol_target_size(returns, equity=10_000.0)
    assert size_large > size_small
    assert abs(size_large / size_small - 10.0) < 1.0  # ~10x


def test_vol_target_empty_returns():
    """Empty returns should return 0 without crashing."""
    assert vol_target_size(pd.Series([], dtype=float), equity=10_000.0) == 0.0


def test_quarter_kelly_positive_edge():
    """Positive edge should produce positive size."""
    size = quarter_kelly(mu=0.01, sigma=0.05, equity=10_000.0)
    assert size > 0


def test_quarter_kelly_zero_sigma():
    """Zero sigma should return 0 without dividing by zero."""
    assert quarter_kelly(mu=0.01, sigma=0.0, equity=10_000.0) == 0.0


def test_quarter_kelly_clamp_min():
    """Very small Kelly bet should be clamped to clip_min * equity."""
    size = quarter_kelly(mu=0.0001, sigma=0.1, equity=10_000.0, clip_min=0.0025)
    assert size >= 0.0025 * 10_000.0


def test_quarter_kelly_clamp_max():
    """Very large Kelly bet should be clamped to clip_max * equity."""
    size = quarter_kelly(mu=1.0, sigma=0.001, equity=10_000.0, clip_max=0.02)
    assert size <= 0.02 * 10_000.0


def test_fixed_fractional_basic():
    """1% risk with 2% stop = 50% of equity as notional."""
    size = fixed_fractional(equity=10_000.0, risk_pct=0.01, stop_distance_pct=0.02)
    assert abs(size - 5_000.0) < 1e-9


def test_fixed_fractional_zero_stop():
    """Zero stop distance should return 0."""
    assert fixed_fractional(equity=10_000.0, stop_distance_pct=0.0) == 0.0


def test_round_to_lot_below_min_returns_empty():
    """When size rounds below min_sz, return empty string (order rejected)."""
    result = round_to_lot(size_usd=5_000.0, price=50_000.0, lot_sz=1.0, min_sz=1.0)
    assert result == ""  # 5000/50000 = 0.1 → rounds to 0 < min_sz=1 → ""


def test_round_to_lot_decimal():
    """Fractional lot_sz should produce decimal string."""
    result = round_to_lot(size_usd=1_000.0, price=1_000.0, lot_sz=0.1, min_sz=0.1)
    assert result == "1.0"  # 1000/1000 = 1.0 → "1.0"


def test_size_in_contracts_btc_perp():
    """$1000 notional on BTC-USDT-SWAP with ctVal=0.01 at $50k = 2 contracts."""
    result = size_in_contracts(
        notional_usd=1_000.0,
        ct_val=0.01,
        price=50_000.0,
        lot_sz=1.0,
        min_sz=1.0,
    )
    assert result == "2"  # 1000 / (0.01 * 50000) = 1000/500 = 2


def test_size_in_contracts_ct_val_one_does_not_use_swap_fallback():
    result = size_in_contracts(
        notional_usd=1_000.0,
        ct_val=1.0,
        price=100.0,
        lot_sz=1.0,
        min_sz=1.0,
    )

    assert result == "10"


@pytest.mark.parametrize("ct_val", [0.0, -0.01, 1.01])
def test_size_in_contracts_rejects_invalid_ct_val(ct_val):
    with pytest.raises(ValueError, match="ct_val"):
        size_in_contracts(
            notional_usd=1_000.0,
            ct_val=ct_val,
            price=100.0,
            lot_sz=1.0,
            min_sz=1.0,
        )
