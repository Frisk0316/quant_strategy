"""Run a minute-bar stock backtest from CSV/parquet data.

Example:
    python scripts/run_stock_backtest.py --market US --symbol AAPL --data data/stocks/AAPL_1m.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Some local Python environments have optional pandas accelerators compiled
# against an older NumPy. The backtest does not need them, so keep CLI output
# clean by forcing pandas to use its pure-Python fallback paths.
sys.modules.setdefault("numexpr", None)
sys.modules.setdefault("bottleneck", None)

from okx_quant.stocks import (  # noqa: E402
    MinuteBarBacktester,
    MinuteBacktestConfig,
    MovingAverageCrossStrategy,
    StockMarket,
    load_minute_bars,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Minute-bar TW/US stock backtest")
    parser.add_argument("--market", choices=["TW", "US"], required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--data", required=True, help="CSV or parquet file with minute OHLCV bars")
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=60)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    args = parser.parse_args()

    market = StockMarket(args.market)
    bars = load_minute_bars(args.data, market=market, symbol=args.symbol)
    strategy = MovingAverageCrossStrategy(args.symbol, fast_window=args.fast, slow_window=args.slow)
    config = MinuteBacktestConfig(
        market=market,
        initial_cash=args.initial_cash,
        slippage_bps=args.slippage_bps,
    )
    result = MinuteBarBacktester(bars, strategy=strategy, config=config).run()

    print(f"{args.symbol} {args.market} minute backtest")
    print(f"bars={len(bars):,} fills={len(result.fills):,}")
    for key in ("total_return", "sharpe", "max_drawdown", "profit_factor", "win_rate"):
        print(f"{key}={result.metrics[key]:.6f}")


if __name__ == "__main__":
    main()
