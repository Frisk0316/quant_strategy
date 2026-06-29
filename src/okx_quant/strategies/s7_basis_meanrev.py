"""S7 basis mean-reversion research strategy stub."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from okx_quant.core.events import Event, SignalPayload
from okx_quant.strategies.base import Strategy


@dataclass
class S7BasisMeanReversionParams:
    pairs: dict[str, str] = field(default_factory=lambda: {
        "BTC-USDT-SWAP": "BTC-USDT",
        "ETH-USDT-SWAP": "ETH-USDT",
    })
    bar: str = "1m"
    lookback_days: int = 7
    z_enter: float = 2.0
    z_exit: float = 0.5
    max_half_life_days: float = 3.0
    max_hold_days: int = 7
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


class S7BasisMeanReversionStrategy(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("s7_basis_meanrev", params)

    async def on_market(self, event: Event, book=None) -> Optional[SignalPayload]:
        return None

    async def on_fill(self, event: Event) -> None:
        pass
