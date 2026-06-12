"""Deprecated bar-proxy backtest entrypoint.

The legacy script centered on order-book market-making proxies that have been
removed from the active project scope. Use ``scripts/run_replay_backtest.py``
for replay backtests and ``scripts/run_differential_validation.py`` for
portable validation evidence.
"""

from __future__ import annotations


def main() -> int:
    print(
        "scripts/run_backtest.py is deprecated. "
        "Use scripts/run_replay_backtest.py for active strategies and "
        "scripts/run_differential_validation.py for validation artifacts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
