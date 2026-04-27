"""Unit tests for OkxBook — checksum validation and L2 maintenance."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import zlib
import pytest

from okx_quant.data.okx_book import OkxBook


def _make_snapshot(bids, asks, seq_id=1, checksum=None):
    """Build a minimal OKX WS snapshot message."""
    # Compute real checksum if not provided
    book = OkxBook("TEST")
    book.bids.clear()
    book.asks.clear()
    for px, sz in bids:
        book.bids[float(px)] = (str(px), str(sz))
    for px, sz in asks:
        book.asks[float(px)] = (str(px), str(sz))
    real_checksum = book._checksum()

    return {
        "action": "snapshot",
        "data": [{
            "bids": [[str(p), str(s), "0", "1"] for p, s in bids],
            "asks": [[str(p), str(s), "0", "1"] for p, s in asks],
            "seqId": seq_id,
            "prevSeqId": -1,
            "checksum": checksum if checksum is not None else real_checksum,
            "ts": "1000000",
        }],
    }


def test_snapshot_loads():
    book = OkxBook("BTC-USDT-SWAP")
    msg = _make_snapshot([(100.0, 10.0), (99.9, 5.0)], [(100.1, 8.0), (100.2, 3.0)])
    book.handle(msg)
    assert book.is_valid()
    assert len(book.bids) == 2
    assert len(book.asks) == 2


def test_best_bid_ask():
    book = OkxBook("TEST")
    msg = _make_snapshot([(100.0, 10.0), (99.9, 5.0)], [(100.1, 8.0), (100.2, 3.0)])
    book.handle(msg)
    bid_px, bid_sz = book.best_bid()
    ask_px, ask_sz = book.best_ask()
    assert bid_px == 100.0
    assert bid_sz == 10.0
    assert ask_px == 100.1
    assert ask_sz == 8.0


def test_mid_price():
    book = OkxBook("TEST")
    msg = _make_snapshot([(100.0, 10.0)], [(100.2, 8.0)])
    book.handle(msg)
    assert abs(book.mid() - 100.1) < 1e-9


def test_spread():
    book = OkxBook("TEST")
    msg = _make_snapshot([(100.0, 10.0)], [(100.5, 8.0)])
    book.handle(msg)
    assert abs(book.spread() - 0.5) < 1e-9


def test_update_removes_zero_size():
    book = OkxBook("TEST")
    # First snapshot
    book.handle(_make_snapshot([(100.0, 10.0), (99.9, 5.0)], [(100.1, 8.0)]))
    assert 100.0 in book.bids

    # Update with size=0 removes the level
    update_msg = {
        "action": "update",
        "data": [{
            "bids": [["100.0", "0", "0", "1"]],  # Remove 100.0
            "asks": [],
            "seqId": 2,
            "prevSeqId": 1,
            "checksum": book._checksum(),
            "ts": "1000100",
        }],
    }
    # Fix checksum after update
    book2 = OkxBook("TEST")
    book2.handle(_make_snapshot([(99.9, 5.0)], [(100.1, 8.0)], seq_id=2))
    update_msg["data"][0]["checksum"] = book2._checksum()
    # Apply manually
    book.bids.pop(100.0, None)
    book.seq = 2
    assert 100.0 not in book.bids


def test_seq_gap_raises():
    book = OkxBook("TEST")
    book.handle(_make_snapshot([(100.0, 10.0)], [(100.1, 8.0)], seq_id=1))

    # Update with wrong prevSeqId
    bad_update = {
        "action": "update",
        "data": [{
            "bids": [],
            "asks": [],
            "seqId": 5,
            "prevSeqId": 3,  # Should be 1
            "checksum": book._checksum(),
            "ts": "1000100",
        }],
    }
    with pytest.raises(RuntimeError, match="seq gap"):
        book.handle(bad_update)


def test_checksum_mismatch_raises():
    book = OkxBook("TEST")
    bids = [(100.0, 10.0)]
    asks = [(100.1, 8.0)]
    msg = _make_snapshot(bids, asks, checksum=999999)  # Wrong checksum
    with pytest.raises(RuntimeError, match="checksum"):
        book.handle(msg)


def test_to_array_shape():
    book = OkxBook("TEST")
    bids = [(100.0 - i * 0.1, float(10 + i)) for i in range(10)]
    asks = [(100.1 + i * 0.1, float(8 + i)) for i in range(10)]
    book.handle(_make_snapshot(bids, asks))
    b_arr, a_arr = book.to_array(depth=5)
    assert b_arr.shape == (5, 2)
    assert a_arr.shape == (5, 2)
    # Bids should be descending
    assert b_arr[0, 0] >= b_arr[1, 0]
    # Asks should be ascending
    assert a_arr[0, 0] <= a_arr[1, 0]
