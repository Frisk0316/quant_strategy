"""
Standalone clock sync utility.
OKX returns error 50102 if timestamp drift > 30 seconds.
Run this at startup and via cron every ~5 minutes.

Usage:
    python scripts/sync_time.py            # one-shot sync and exit
    python scripts/sync_time.py --daemon   # continuous daemon mode
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.core.logging import setup_logging
from okx_quant.data.rest_client import OKXRestClient


def sync_once(client: OKXRestClient) -> float:
    offset_ms = client.sync_clock()
    print(f"Clock offset: {offset_ms:.1f} ms (|{abs(offset_ms):.1f}| ms drift)")
    if abs(offset_ms) > 25_000:
        print("WARNING: clock drift exceeds 25s — OKX may reject requests (50102)")
    return offset_ms


async def daemon_loop(client: OKXRestClient, interval_secs: int) -> None:
    print(f"Clock sync daemon started (interval: {interval_secs}s)")
    while True:
        try:
            sync_once(client)
        except Exception as e:
            print(f"Clock sync failed: {e}")
        await asyncio.sleep(interval_secs)


def main() -> None:
    parser = argparse.ArgumentParser(description="OKX clock sync")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=300, help="Sync interval in seconds")
    args = parser.parse_args()

    try:
        cfg = load_config()
        setup_logging(cfg.system.log_level, cfg.system.json_logs)
        client = OKXRestClient(
            api_key=cfg.secrets.okx_api_key,
            secret=cfg.secrets.okx_secret,
            passphrase=cfg.secrets.okx_passphrase,
            base_url=cfg.okx.base_url,
            demo=cfg.is_demo(),
        )
    except Exception as e:
        print(f"Failed to load config or create client: {e}")
        sys.exit(1)

    try:
        if args.daemon:
            asyncio.run(daemon_loop(client, args.interval))
        else:
            offset = sync_once(client)
            sys.exit(0 if abs(offset) < 30_000 else 1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
