"""Deprecated standalone Nautilus L2 runner.

Order-book market-making strategies were removed from active scope because the
project will not maintain order-book data. The active Nautilus work now lives in
``backtesting.differential_validation`` as advisory/signal-point evidence, not as
a standalone queue-aware L2 backtest runner.

Usage:
    python scripts/run_differential_validation.py --strategy macd_crossover --engines nautilus
"""
from __future__ import annotations


def main() -> int:
    print(
        "backtesting/nautilus_backtest.py is deprecated. "
        "Use scripts/run_differential_validation.py with --engines nautilus "
        "for current portable-validation evidence."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
