"""
LIVE trading entry point.
REQUIRES: CPCV + DSR >= 0.95 for each strategy, 4+ weeks demo, 2+ weeks shadow.
DO NOT RUN until all validation gates are passed.
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
    if cfg.system.mode != "live":
        print(
            f"ERROR: settings.yaml mode is '{cfg.system.mode}', not 'live'.\n"
            "Change config/settings.yaml to mode: live to enable live trading.\n"
            "WARNING: Live trading uses real funds."
        )
        sys.exit(1)

    # Final confirmation
    print("=" * 60)
    print("LIVE TRADING MODE")
    print(f"Equity: ${cfg.system.equity_usd}")
    print(f"Symbols: {cfg.system.symbols}")
    print(f"Risk limits: daily_loss={cfg.risk.max_daily_loss_pct*100:.0f}%  "
          f"hard_stop={cfg.risk.hard_drawdown_pct*100:.0f}%")
    print("=" * 60)
    confirm = input("Type 'yes' to confirm live trading: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)

    asyncio.run(main(cfg))


if __name__ == "__main__":
    run()
