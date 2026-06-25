"""S5 residual mean-reversion research strategy stub."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from okx_quant.core.events import Event, SignalPayload
from okx_quant.strategies.base import Strategy


@dataclass
class S5ResidualMeanReversionParams:
    universe: list[str] = field(default_factory=list)
    bar: str = "1m"
    rebalance: str = "weekly"
    lookback_days: int = 3
    z_enter: float = 2.0
    z_exit: float = 0.5
    factors: str = "BTC"
    top_n: int = 20
    vol_window_days: int = 28
    inverse_vol: bool = True
    vol_target_annual: float = 0.175
    max_name_weight: float = 0.10
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


class S5ResidualMeanReversionStrategy(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("s5_residual_meanrev", params)

    async def on_market(self, event: Event, book=None) -> Optional[SignalPayload]:
        return None

    async def on_fill(self, event: Event) -> None:
        pass
