"""Run replay-based backtests through the event-driven execution stack."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "backtesting"))

from backtesting.replay import run_replay_backtest
from okx_quant.core.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", action="append", required=True,
                        choices=["obi_market_maker", "as_market_maker", "funding_carry", "pairs_trading"])
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--bar", default="1H")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "ticks"))
    args = parser.parse_args()

    cfg = load_config(require_secrets=False)
    result = run_replay_backtest(
        strategy_names=args.strategy,
        cfg=cfg,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
        bar=args.bar,
    )

    print("=" * 72)
    print("REPLAY BACKTEST SUMMARY")
    print(f"Strategies: {', '.join(args.strategy)}")
    print(f"Orders: {len(result.order_log)} | Fills: {len(result.fill_log)}")
    for key, value in result.metrics.items():
        if isinstance(value, float):
            print(f"{key:>16}: {value:.6f}")
        else:
            print(f"{key:>16}: {value}")
    print("=" * 72)


if __name__ == "__main__":
    main()
