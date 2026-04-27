"""
Strategy abstract base class.
All strategies implement on_market() and on_fill().
RiskGuard controls size_multiplier; strategies cannot bypass it.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from okx_quant.core.events import Event, SignalPayload
from okx_quant.data.okx_book import OkxBook


class Strategy(ABC):
    def __init__(self, name: str, params: dict) -> None:
        self.name = name
        self.params = params
        self.is_active: bool = True
        # Controlled by RiskGuard: 1.0 = normal, 0.5 = soft-stop, 0.0 = halted
        self.size_multiplier: float = 1.0

    @abstractmethod
    async def on_market(
        self,
        event: Event,
        book: Optional[OkxBook] = None,
    ) -> Optional[SignalPayload]:
        """
        Called on every market event for subscribed instruments.
        Returns SignalPayload if a signal is generated, None otherwise.
        """
        ...

    @abstractmethod
    async def on_fill(self, event: Event) -> None:
        """Called when a fill is confirmed for this strategy."""
        ...

    def halt(self) -> None:
        self.size_multiplier = 0.0
        self.is_active = False

    def soft_stop(self) -> None:
        self.size_multiplier = 0.5

    def resume(self) -> None:
        self.size_multiplier = 1.0
        self.is_active = True

    def get_param(self, key: str, default=None):
        return self.params.get(key, default)
