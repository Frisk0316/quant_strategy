"""Unit tests for Avellaneda-Stoikov quote generation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import math
import pytest

from okx_quant.strategies.as_market_maker import as_quote


def test_bid_below_ask():
    """Bid must always be below ask."""
    bid, ask = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1)
    assert bid < ask


def test_spread_positive():
    """Spread must be positive."""
    bid, ask = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1)
    assert ask - bid > 0


def test_symmetric_at_zero_inventory():
    """With zero inventory and zero alpha, quotes should be symmetric around mid."""
    bid, ask = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1, gamma=0.1, tick=0.1)
    half = (ask - bid) / 2
    reservation = (bid + ask) / 2
    assert abs(reservation - 100.0) < 0.5  # Near mid


def test_long_inventory_skews_bid_down():
    """Long inventory should push reservation price down (skew asks up, bids down)."""
    # sigma=0.1 so penalty = 30 * 0.5 * 0.01 = 0.15, clearly exceeds tick=0.01
    bid_flat, ask_flat = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1, gamma=0.5, sigma=0.1, tick=0.01)
    bid_long, ask_long = as_quote(mid=100.0, inventory=30, alpha_signal=0.0, vpin=0.1, gamma=0.5, sigma=0.1, tick=0.01)
    # Long inventory: MM wants to sell, so reservation price is lower
    assert bid_long < bid_flat


def test_short_inventory_skews_ask_up():
    """Short inventory should push quotes up."""
    bid_flat, _ = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1, gamma=0.5, sigma=0.1, tick=0.01)
    bid_short, _ = as_quote(mid=100.0, inventory=-30, alpha_signal=0.0, vpin=0.1, gamma=0.5, sigma=0.1, tick=0.01)
    assert bid_short > bid_flat


def test_positive_alpha_raises_fair_value():
    """Positive OFI alpha should raise both bid and ask."""
    bid_zero, ask_zero = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1)
    bid_pos, ask_pos = as_quote(mid=100.0, inventory=0, alpha_signal=0.001, vpin=0.1, c_alpha=100.0)
    # Fair value = mid + c_alpha * alpha = 100 + 100*0.001 = 100.1
    assert bid_pos > bid_zero
    assert ask_pos > ask_zero


def test_vpin_widens_spread():
    """Higher VPIN should widen the spread."""
    bid_low, ask_low = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1)
    bid_high, ask_high = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.9)
    spread_low = ask_low - bid_low
    spread_high = ask_high - bid_high
    assert spread_high > spread_low


def test_max_inventory_cancels_bid():
    """When inventory >= max_pos, bid should be -inf."""
    bid, ask = as_quote(mid=100.0, inventory=50, alpha_signal=0.0, vpin=0.1, max_pos=50)
    assert bid == -math.inf


def test_min_inventory_cancels_ask():
    """When inventory <= -max_pos, ask should be inf."""
    bid, ask = as_quote(mid=100.0, inventory=-50, alpha_signal=0.0, vpin=0.1, max_pos=50)
    assert ask == math.inf


def test_tick_rounding():
    """Output prices should be multiples of tick size."""
    tick = 0.5
    bid, ask = as_quote(mid=100.0, inventory=0, alpha_signal=0.0, vpin=0.1, tick=tick)
    if bid != -math.inf:
        assert abs(bid % tick) < 1e-9 or abs(bid % tick - tick) < 1e-9
    if ask != math.inf:
        assert abs(ask % tick) < 1e-9 or abs(ask % tick - tick) < 1e-9
