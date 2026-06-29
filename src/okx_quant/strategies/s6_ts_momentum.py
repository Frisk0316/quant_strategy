"""S6 slow time-series momentum research strategy stub."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from okx_quant.core.events import Event, SignalPayload
from okx_quant.strategies.base import Strategy


@dataclass
class S6TSMomentumParams:
    symbols: list[str] = field(default_factory=lambda: ["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
    bar: str = "1m"
    rebalance: str = "weekly"
    lookback_days: int = 60
    vol_window_days: int = 28
    vol_target_annual: float = 0.15
    max_leverage: float = 2.0
    crash_filter: bool = True
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


class S6TSMomentumStrategy(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("s6_ts_momentum", params)

    async def on_market(self, event: Event, book=None) -> Optional[SignalPayload]:
        return None

    async def on_fill(self, event: Event) -> None:
        pass
