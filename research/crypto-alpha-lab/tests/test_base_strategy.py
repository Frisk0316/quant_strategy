from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import pytest

from crypto_alpha_lab.strategies import BaseStrategy, SignalInstruction, StrategyMetadata


class ToyStrategy(BaseStrategy):
    metadata = StrategyMetadata(
        strategy_id="toy_momentum",
        name="Toy Momentum",
        paper_ids=("paper-001",),
    )

    def validate_inputs(self, market_data: Mapping[str, Any]) -> None:
        if "BTC-USDT-SWAP" not in market_data:
            raise ValueError("missing BTC-USDT-SWAP")

    def generate_signals(self, market_data: Mapping[str, Any]) -> Sequence[SignalInstruction]:
        self.validate_inputs(market_data)
        return (
            SignalInstruction(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                symbol="BTC-USDT-SWAP",
                side="long",
                weight=0.25,
                confidence=0.8,
                reason="toy fixture",
            ),
        )


def test_base_strategy_contract_describes_research_strategy() -> None:
    strategy = ToyStrategy(params={"lookback": 24})
    signals = strategy.generate_signals({"BTC-USDT-SWAP": [{"close": 100.0}]})

    assert strategy.strategy_id == "toy_momentum"
    assert signals[0].side == "long"
    assert signals[0].weight == 0.25
    assert strategy.describe()["supports_live_trading"] is False


def test_strategy_metadata_rejects_live_trading_flag() -> None:
    with pytest.raises(ValueError, match="research-only"):
        StrategyMetadata(
            strategy_id="bad_live_strategy",
            name="Bad Live Strategy",
            supports_live_trading=True,
        )
