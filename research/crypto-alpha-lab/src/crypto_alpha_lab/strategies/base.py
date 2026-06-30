"""Base interface for research-only alpha strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping, Sequence

StrategyStatus = Literal["draft", "candidate", "validated"]
SignalSide = Literal["long", "short", "flat"]


@dataclass(frozen=True)
class StrategyMetadata:
    """Immutable metadata for an alpha candidate."""

    strategy_id: str
    name: str
    version: str = "0.1.0"
    paper_ids: tuple[str, ...] = ()
    research_status: StrategyStatus = "draft"
    supports_live_trading: bool = False

    def __post_init__(self) -> None:
        if self.supports_live_trading:
            raise ValueError("crypto-alpha-lab strategies must remain research-only")


@dataclass(frozen=True)
class SignalInstruction:
    """Minimal signal contract that can later be adapted to a backtester."""

    timestamp: datetime
    symbol: str
    side: SignalSide
    weight: float
    confidence: float = 1.0
    reason: str = ""


class BaseStrategy(ABC):
    """Abstract base class for paper-derived research strategies."""

    metadata: StrategyMetadata

    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        self.params = dict(params or {})

    @property
    def strategy_id(self) -> str:
        return self.metadata.strategy_id

    @abstractmethod
    def validate_inputs(self, market_data: Mapping[str, Any]) -> None:
        """Validate that required research data is present."""

    @abstractmethod
    def generate_signals(self, market_data: Mapping[str, Any]) -> Sequence[SignalInstruction]:
        """Generate research signals from market data."""

    def describe(self) -> dict[str, Any]:
        """Return serializable strategy metadata for research logs."""

        return {
            "strategy_id": self.metadata.strategy_id,
            "name": self.metadata.name,
            "version": self.metadata.version,
            "paper_ids": list(self.metadata.paper_ids),
            "research_status": self.metadata.research_status,
            "supports_live_trading": self.metadata.supports_live_trading,
            "params": self.params,
        }
