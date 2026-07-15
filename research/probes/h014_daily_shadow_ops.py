"""H-014 daily shadow ops helper: wait for 08:00 UTC, top up data, run cycle.

Manual-cadence helper for the ADR-0011 shadow layer while no scheduled task is
approved. Waits (if needed) until 08:05 UTC today, forward-ingests hourly DVOL
and Binance 1m candles so the prior-day signal is exactly fresh, then runs one
shadow cycle and prints the summary. Safe to run any time after ~00:00 UTC;
exits nonzero on any failure (fail closed, no retries beyond the ingest CLIs').

Usage: python research/probes/h014_daily_shadow_ops.py [--no-wait]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    gate = datetime.combine(now.date(), dt_time(8, 5), tzinfo=timezone.utc)
    if not args.no_wait and now < gate:
        wait_s = (gate - now).total_seconds()
        print(f"waiting {wait_s/3600:.2f}h until {gate.isoformat()} (shadow 08:00 UTC gate)",
              flush=True)
        time.sleep(wait_s)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=26)).strftime("%Y-%m-%dT%H:00:00")
    end = now.strftime("%Y-%m-%dT%H:%M:00")
    run([PY, "scripts/market_data/ingest_external.py",
         "--dataset", "dvol_deribit_btc_1h", "--dataset", "dvol_deribit_eth_1h",
         "--start", start, "--end", end])
    run([PY, "scripts/market_data/ingest.py", "--exchange", "binance",
         "--dataset", "klines_1m", "--symbols", "BTCUSDT,ETHUSDT",
         "--start", start + "Z", "--end", end + "Z"])
    run([PY, "scripts/run_h014_shadow.py"])
    run([PY, "scripts/run_h014_shadow.py", "--report"])


if __name__ == "__main__":
    main()
