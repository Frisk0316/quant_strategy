"""Fee and tax models for stock markets.

Rates are intentionally configurable because broker discounts and regulatory
fees change over time. Defaults are conservative placeholders for simulation.
"""
from __future__ import annotations

from dataclasses import dataclass

from okx_quant.stocks.models import OrderSide, StockMarket


@dataclass(frozen=True)
class StockFeeModel:
    commission_rate: float = 0.0
    min_commission: float = 0.0
    sell_tax_rate: float = 0.0
    sell_fee_rate: float = 0.0
    sell_fee_cap: float | None = None

    def estimate(self, side: OrderSide, price: float, quantity: float) -> tuple[float, float]:
        notional = abs(price * quantity)
        commission = notional * self.commission_rate
        if commission > 0 and self.min_commission > 0:
            commission = max(commission, self.min_commission)

        tax = notional * self.sell_tax_rate if side == OrderSide.SELL else 0.0
        if side == OrderSide.SELL and self.sell_fee_rate:
            extra = notional * self.sell_fee_rate
            if self.sell_fee_cap is not None:
                extra = min(extra, self.sell_fee_cap)
            commission += extra

        return float(commission), float(tax)


DEFAULT_FEE_MODELS: dict[StockMarket, StockFeeModel] = {
    StockMarket.TW: StockFeeModel(
        commission_rate=0.001425,
        min_commission=20.0,
        sell_tax_rate=0.003,
    ),
    StockMarket.US: StockFeeModel(
        commission_rate=0.0,
        min_commission=0.0,
        sell_tax_rate=0.0,
        sell_fee_rate=0.0,
    ),
}
