"""One-shot diagnostic: capture one OKX books snapshot and compare our
computed checksum against the server's. Prints the discrepancy so we can
fix OkxBook._checksum against real data. No auth needed (public channel).

Usage:
    python scripts/diag_book_checksum.py            # demo (wspap)
    python scripts/diag_book_checksum.py --live      # live (ws.okx.com)
"""
from __future__ import annotations

import asyncio
import json
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import websockets  # noqa: E402

from okx_quant.data.okx_book import OkxBook  # noqa: E402

INST = "BTC-USDT-SWAP"


async def main(live: bool) -> None:
    if live:
        url = "wss://ws.okx.com:8443/ws/v5/public"
    else:
        url = "wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999"

    async with websockets.connect(url, ping_interval=None, max_size=2**23) as ws:
        await ws.send(json.dumps({"op": "subscribe",
                                  "args": [{"channel": "books", "instId": INST}]}))
        while True:
            raw = await ws.recv()
            if raw == "pong":
                continue
            msg = json.loads(raw)
            if "event" in msg:
                print("event:", msg)
                continue
            if msg.get("arg", {}).get("channel") != "books":
                continue
            if msg.get("action") != "snapshot":
                continue

            d = msg["data"][0]
            book = OkxBook(INST)
            book._apply("bids", d.get("bids", []))
            book._apply("asks", d.get("asks", []))

            ours = book._checksum()
            server = int(d["checksum"])
            print(f"levels: bids={len(d.get('bids', []))} asks={len(d.get('asks', []))}")
            print(f"top bids: {d['bids'][:3]}")
            print(f"top asks: {d['asks'][:3]}")
            print(f"server checksum : {server}")
            print(f"our checksum    : {ours}")
            print(f"MATCH: {server == ours}")

            # Show the exact crc32 input we build, vs a couple of alternatives.
            bids = list(reversed(book.bids.items()))[:25]
            asks = list(book.asks.items())[:25]
            parts = []
            for i in range(max(len(bids), len(asks))):
                if i < len(bids):
                    _, (px, sz) = bids[i]
                    parts += [px, sz]
                if i < len(asks):
                    _, (px, sz) = asks[i]
                    parts += [px, sz]
            s = ":".join(parts)
            print(f"our crc32 input (first 160): {s[:160]}")
            print(f"crc32(unsigned)={zlib.crc32(s.encode())}")
            return


if __name__ == "__main__":
    asyncio.run(main("--live" in sys.argv))
