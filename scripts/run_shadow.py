"""
Shadow mode entry point.
Runs SimBroker and OKXBroker(demo) in parallel to compare
simulated vs actual fills, slippage, and signal latency.
Run for >= 2 weeks before half-size live.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.engine import main


def run() -> None:
    cfg = load_config()
    assert cfg.system.mode in ("shadow", "demo"), (
        f"settings.yaml mode is '{cfg.system.mode}'. "
        "Set mode: shadow for shadow trading."
    )
    print(f"Starting SHADOW mode | equity=${cfg.system.equity_usd}")
    # sim_broker=True routes to SimBroker; engine also runs OKX demo in parallel
    asyncio.run(main(cfg, sim_broker=True))


if __name__ == "__main__":
    run()
