"""Unit tests for OBI/OFI signal functions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pytest

from okx_quant.signals.obi_ofi import (
    compute_obi_features,
    compute_ofi,
    ewma_ofi,
    book_to_l1_snap,
)


BIDS = [(100.0, 10.0), (99.9, 20.0), (99.8, 15.0), (99.7, 5.0), (99.6, 8.0)]
ASKS = [(100.1, 12.0), (100.2, 18.0), (100.3, 22.0), (100.4, 9.0), (100.5, 11.0)]


def test_obi_l1_balanced():
    """When bids and asks have equal top-of-book size, OBI should be near 0."""
    bids = [(100.0, 10.0)]
    asks = [(100.1, 10.0)]
    f = compute_obi_features(bids, asks, depth=1)
    assert abs(f["obi_l1"]) < 1e-9


def test_obi_l1_bid_heavy():
    """When bids > asks, OBI should be positive."""
    bids = [(100.0, 20.0)]
    asks = [(100.1, 5.0)]
    f = compute_obi_features(bids, asks, depth=1)
    assert f["obi_l1"] > 0


def test_obi_l1_ask_heavy():
    """When asks > bids, OBI should be negative."""
    bids = [(100.0, 5.0)]
    asks = [(100.1, 20.0)]
    f = compute_obi_features(bids, asks, depth=1)
    assert f["obi_l1"] < 0


def test_mid_price():
    """Mid-price should be the average of best bid and ask."""
    bids = [(100.0, 10.0)]
    asks = [(100.2, 10.0)]
    f = compute_obi_features(bids, asks, depth=1)
    assert abs(f["mid"] - 100.1) < 1e-9


def test_spread():
    """Spread should equal ask - bid."""
    bids = [(100.0, 10.0)]
    asks = [(100.5, 10.0)]
    f = compute_obi_features(bids, asks, depth=1)
    assert abs(f["spread"] - 0.5) < 1e-9


def test_obi_multi_range():
    """Multi-level OBI should be in [-1, 1]."""
    f = compute_obi_features(BIDS, ASKS, depth=5)
    assert -1.0 <= f["obi_multi"] <= 1.0


def test_microprice_between_bid_ask():
    """Microprice should be between best bid and best ask."""
    f = compute_obi_features(BIDS, ASKS, depth=5)
    assert BIDS[0][0] <= f["micro"] <= ASKS[0][0]


def test_ofi_no_change():
    """OFI should be 0 when nothing changes."""
    snap = {"pb": 100.0, "qb": 10.0, "pa": 100.1, "qa": 10.0}
    assert compute_ofi(snap, snap) == 0.0


def test_ofi_bid_increase():
    """OFI should be positive when bid quantity increases at same price."""
    prev = {"pb": 100.0, "qb": 10.0, "pa": 100.1, "qa": 10.0}
    curr = {"pb": 100.0, "qb": 20.0, "pa": 100.1, "qa": 10.0}
    ofi = compute_ofi(prev, curr)
    assert ofi > 0


def test_ofi_ask_increase():
    """OFI should be negative when ask quantity increases at same price."""
    prev = {"pb": 100.0, "qb": 10.0, "pa": 100.1, "qa": 10.0}
    curr = {"pb": 100.0, "qb": 10.0, "pa": 100.1, "qa": 20.0}
    ofi = compute_ofi(prev, curr)
    assert ofi < 0


def test_ewma_ofi_convergence():
    """EWMA OFI should converge toward recent values."""
    series = np.zeros(50)
    series[-10:] = 1.0
    ewma_val = ewma_ofi(series, halflife_ms=200.0)
    assert ewma_val > 0  # Should be pulled positive by recent 1s


def test_empty_book():
    """Empty book should return zeros without crashing."""
    f = compute_obi_features([], [], depth=5)
    assert f["obi_l1"] == 0.0
    assert f["mid"] == 0.0


def test_book_to_l1_snap():
    """book_to_l1_snap should correctly extract L1 from numpy arrays."""
    bids = np.array([[100.0, 10.0], [99.9, 5.0]])
    asks = np.array([[100.1, 8.0], [100.2, 12.0]])
    snap = book_to_l1_snap(bids, asks)
    assert snap["pb"] == 100.0
    assert snap["qb"] == 10.0
    assert snap["pa"] == 100.1
    assert snap["qa"] == 8.0
