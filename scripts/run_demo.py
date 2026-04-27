"""
Demo mode entry point.
Connects to OKX demo environment (x-simulated-trading: 1).
Run for >= 4 weeks before any live trading.
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
    assert cfg.system.mode == "demo", (
        f"settings.yaml mode is '{cfg.system.mode}', expected 'demo'. "
        "Change config/settings.yaml to mode: demo before running this script."
    )
    print(f"Starting DEMO mode | equity=${cfg.system.equity_usd} | symbols={cfg.system.symbols}")
    asyncio.run(main(cfg))


if __name__ == "__main__":
    run()
