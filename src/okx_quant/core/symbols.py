"""Instrument symbol normalization helpers."""
from __future__ import annotations


_KNOWN_QUOTES = ("USDT", "USDC", "USD")


def normalize_swap_symbol(symbol: str) -> str:
    """Return an OKX USDT/USDC/USD swap instrument id."""
    return _normalize_symbol(symbol, suffix="SWAP")


def normalize_spot_symbol(symbol: str) -> str:
    """Return an OKX spot instrument id."""
    return _normalize_symbol(symbol, suffix=None)


def _normalize_symbol(symbol: str, suffix: str | None) -> str:
    raw = str(symbol or "").strip().upper().replace("/", "-").replace("_", "-")
    if not raw:
        return raw

    parts = [part for part in raw.split("-") if part]
    if len(parts) >= 2:
        base, quote = parts[0], parts[1]
        if suffix:
            return f"{base}-{quote}-{suffix}"
        return f"{base}-{quote}"

    for quote in _KNOWN_QUOTES:
        if raw.endswith(quote) and len(raw) > len(quote):
            base = raw[: -len(quote)]
            if suffix:
                return f"{base}-{quote}-{suffix}"
            return f"{base}-{quote}"

    return raw
