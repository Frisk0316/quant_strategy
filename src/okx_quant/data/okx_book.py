"""
OKX L2 order book with checksum validation.
Extracted from §2.2 of Crypto_Quant_Plan_v1.md and extended with
accessor methods needed by signal generators.

CRITICAL: Keep original server price strings — do NOT reformat.
The checksum is computed on the original strings; any float conversion
before joining will produce wrong results. This is the most common pitfall.
"""
from __future__ import annotations

import zlib
from typing import Optional

import numpy as np
from sortedcontainers import SortedDict


class OkxBook:
    def __init__(self, inst: str) -> None:
        self.inst = inst
        self.seq: Optional[int] = None
        # bids: {float(px): original_px_str}  (descending — use negated keys)
        # asks: {float(px): original_px_str}  (ascending)
        # We store the raw size string for checksum and convert on demand.
        # Key: float price; Value: (raw_px_str, raw_sz_str)
        self.bids: SortedDict = SortedDict()   # highest bid at end
        self.asks: SortedDict = SortedDict()   # lowest ask at beginning

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply(self, side: str, levels: list) -> None:
        book = self.bids if side == "bids" else self.asks
        for entry in levels:
            px_str, sz_str = entry[0], entry[1]
            p = float(px_str)
            if float(sz_str) == 0:
                book.pop(p, None)
            else:
                book[p] = (px_str, sz_str)

    @staticmethod
    def _signed(x: int) -> int:
        """Convert unsigned CRC32 to signed int32 (OKX checksum format)."""
        return x - (1 << 32) if x >= (1 << 31) else x

    def _checksum(self) -> int:
        """
        OKX checksum: interleave top-25 bids (desc) and asks (asc),
        join as 'bidPx:bidSz:askPx:askSz:...' with ':' separator,
        CRC32 → signed int32.
        """
        bids = list(reversed(self.bids.items()))[:25]
        asks = list(self.asks.items())[:25]
        parts: list[str] = []
        for i in range(max(len(bids), len(asks))):
            if i < len(bids):
                _, (px_str, sz_str) = bids[i]
                parts += [px_str, sz_str]
            if i < len(asks):
                _, (px_str, sz_str) = asks[i]
                parts += [px_str, sz_str]
        return self._signed(zlib.crc32(":".join(parts).encode()))

    # ------------------------------------------------------------------
    # Main handler
    # ------------------------------------------------------------------

    def handle(self, msg: dict) -> None:
        """
        Process a WebSocket message (snapshot or update).
        Raises RuntimeError on sequence gap or checksum mismatch
        — caller should re-subscribe on these errors.
        """
        if msg.get("action") == "snapshot":
            self.bids.clear()
            self.asks.clear()

        d = msg["data"][0]
        self._apply("bids", d.get("bids", []))
        self._apply("asks", d.get("asks", []))

        # Sequence gap detection
        prev_seq = d.get("prevSeqId", -1)
        if prev_seq not in (-1, self.seq) and self.seq is not None:
            raise RuntimeError(f"seq gap: expected {self.seq}, got prevSeqId={prev_seq} -> resubscribe")
        self.seq = d["seqId"]

        # Checksum validation
        if "checksum" in d and int(self._checksum()) != int(d["checksum"]):
            raise RuntimeError("checksum mismatch -> resubscribe")

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def best_bid(self) -> tuple[float, float]:
        """Returns (price, size) of best bid."""
        if not self.bids:
            return (0.0, 0.0)
        px, (_, sz_str) = self.bids.peekitem(-1)
        return (px, float(sz_str))

    def best_ask(self) -> tuple[float, float]:
        """Returns (price, size) of best ask."""
        if not self.asks:
            return (float("inf"), 0.0)
        px, (_, sz_str) = self.asks.peekitem(0)
        return (px, float(sz_str))

    def mid(self) -> float:
        bid, _ = self.best_bid()
        ask, _ = self.best_ask()
        return 0.5 * (bid + ask)

    def spread(self) -> float:
        bid, _ = self.best_bid()
        ask, _ = self.best_ask()
        return ask - bid

    def levels(self, n: int = 10) -> tuple[list[tuple], list[tuple]]:
        """Returns top-n bids (desc) and asks (asc) as [(price, size), ...]."""
        bids = [(p, float(v[1])) for p, v in reversed(self.bids.items())][:n]
        asks = [(p, float(v[1])) for p, v in self.asks.items()][:n]
        return bids, asks

    def to_array(self, depth: int = 20) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns numpy arrays shaped (depth, 2) for bids and asks.
        Column 0 = price, column 1 = size.
        Used by signal generators for vectorized computation.
        """
        bids_list, asks_list = self.levels(depth)
        def _pad(lst, n):
            arr = np.array(lst, dtype=float) if lst else np.zeros((0, 2))
            if len(arr) < n:
                pad = np.zeros((n - len(arr), 2))
                arr = np.vstack([arr, pad]) if len(arr) > 0 else pad
            return arr[:n]
        return _pad(bids_list, depth), _pad(asks_list, depth)

    def is_valid(self) -> bool:
        """Returns True if book has at least one bid and one ask."""
        return bool(self.bids) and bool(self.asks)

    def __repr__(self) -> str:
        if not self.is_valid():
            return f"OkxBook({self.inst}, empty)"
        bid, bsz = self.best_bid()
        ask, asz = self.best_ask()
        return f"OkxBook({self.inst}, bid={bid}×{bsz}, ask={ask}×{asz}, spread={self.spread():.4f})"
