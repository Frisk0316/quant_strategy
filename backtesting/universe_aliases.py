"""Consumer-time economic-asset aliases for point-in-time universes."""
from __future__ import annotations

from collections.abc import Iterable


SAME_ASSET_ALIASES = {
    "binance": {
        "SHIB-USDT-SWAP": "1000SHIB-USDT-SWAP",
    },
}


def collapse_same_asset_aliases(
    symbols: Iterable[str],
    *,
    exchange: str,
) -> tuple[str, ...]:
    """Map aliases and keep the first selected member for each economic asset."""

    aliases = SAME_ASSET_ALIASES.get(exchange.lower(), {})
    return tuple(dict.fromkeys(aliases.get(symbol, symbol) for symbol in symbols))
