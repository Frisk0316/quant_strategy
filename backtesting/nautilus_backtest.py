"""
Nautilus Trader L2 tick-accurate backtest runner.
This provides the highest-fidelity simulation:
- Price-time priority queue simulation
- post_only order support
- Slippage via book-walk (level walking) on L2 data
- Same strategy code as live trading

Requires: pip install nautilus_trader

Usage:
    python backtesting/nautilus_backtest.py --strategy as_market_maker --days 30
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import nautilus_trader
    NAUTILUS_AVAILABLE = True
except ImportError:
    NAUTILUS_AVAILABLE = False


def run_as_mm_backtest(
    data_dir: str = "data/ticks",
    inst_id: str = "BTC-USDT-SWAP",
    start: str = "2024-01-01",
    end: str = "2024-03-01",
    gamma: float = 0.1,
    kappa: float = 1.5,
    c_alpha: float = 100.0,
) -> dict:
    """
    Run AS Market Maker backtest using Nautilus Trader.

    Returns:
        dict with performance metrics.
    """
    if not NAUTILUS_AVAILABLE:
        raise ImportError(
            "nautilus_trader required for L2 backtest.\n"
            "Install: pip install nautilus_trader\n"
            "Then run VectorBT scanner first to narrow parameters."
        )

    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.currencies import USDT
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.identifiers import Venue
    from nautilus_trader.model.objects import Money

    engine = BacktestEngine(
        config=BacktestEngineConfig(
            logging=LoggingConfig(log_level="WARNING"),
        )
    )

    # Add OKX venue
    engine.add_venue(
        venue=Venue("OKX"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USDT,
        starting_balances=[Money(10_000, USDT)],
    )

    # Note: Full Nautilus integration requires OKX adapter configuration
    # and Parquet catalog loading. This is a skeleton — refer to:
    # https://nautilustrader.io/docs/
    # and the OKX adapter docs for complete setup.

    print("Nautilus backtest skeleton — see backtesting/nautilus_backtest.py for setup guide")
    return {}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--inst", default="BTC-USDT-SWAP")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-03-01")
    args = parser.parse_args()

    result = run_as_mm_backtest(
        inst_id=args.inst,
        start=args.start,
        end=args.end,
    )
    print(result)
