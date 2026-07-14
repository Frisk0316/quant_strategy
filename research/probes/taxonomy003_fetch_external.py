"""Fetch external signal data for idea batch taxonomy_003 Stage-3 runs.

Downloads (all free, no credentials):
  - DefiLlama aggregate stablecoin circulating history (daily)  -> stablecoins.csv
  - Coinbase Exchange BTC-USD / ETH-USD daily candles (paginated) -> coinbase_{btc,eth}.csv
  - blockchain.info hash-rate chart (daily, 6y)                 -> hashrate.csv

PIT labeling convention recorded ex-ante: a value stamped date D is treated as
usable no earlier than D+1 00:00 UTC in every backtest (conservative one-day
publication lag; these APIs restate current-day values intraday).

Usage: python research/probes/taxonomy003_fetch_external.py
"""

from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path("results/idea_batch_20260713_taxonomy_003/data")
UA = {"User-Agent": "quant-strategy-taxonomy003/1"}


def fetch(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def write_csv(name: str, header: list[str], rows: list[list]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def stablecoins() -> None:
    data = fetch("https://stablecoins.llama.fi/stablecoincharts/all")
    rows = []
    for p in data:
        d = datetime.fromtimestamp(int(p["date"]), tz=timezone.utc).date().isoformat()
        circ = p.get("totalCirculatingUSD") or {}
        total = sum(v for v in circ.values() if isinstance(v, (int, float)))
        rows.append([d, total])
    write_csv("stablecoins.csv", ["date", "total_circulating_usd"], rows)


def coinbase(product: str, name: str) -> None:
    start = datetime(2023, 10, 1, tzinfo=timezone.utc)  # warmup before 2024-01
    end = datetime(2026, 7, 14, tzinfo=timezone.utc)
    rows = {}
    cur = start
    while cur < end:
        chunk_end = min(cur + timedelta(days=290), end)
        qs = urllib.parse.urlencode(
            {
                "granularity": 86400,
                "start": cur.isoformat(),
                "end": chunk_end.isoformat(),
            }
        )
        candles = fetch(f"https://api.exchange.coinbase.com/products/{product}/candles?{qs}")
        for ts, _lo, _hi, _op, close, _vol in candles:
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            rows[d] = close
        cur = chunk_end
        time.sleep(0.4)
    write_csv(name, ["date", "close"], sorted(rows.items()))


def hashrate() -> None:
    data = fetch(
        "https://api.blockchain.info/charts/hash-rate?timespan=6years&format=json&sampled=false"
    )
    rows = [
        [datetime.fromtimestamp(v["x"], tz=timezone.utc).date().isoformat(), v["y"]]
        for v in data.get("values", [])
    ]
    write_csv("hashrate.csv", ["date", "hashrate_ths"], rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "pit_convention": "value stamped date D usable no earlier than D+1 00:00 UTC",
        "sources": {
            "stablecoins.csv": "https://stablecoins.llama.fi/stablecoincharts/all",
            "coinbase_btc.csv": "https://api.exchange.coinbase.com/products/BTC-USD/candles",
            "coinbase_eth.csv": "https://api.exchange.coinbase.com/products/ETH-USD/candles",
            "hashrate.csv": "https://api.blockchain.info/charts/hash-rate",
        },
    }
    stablecoins()
    coinbase("BTC-USD", "coinbase_btc.csv")
    coinbase("ETH-USD", "coinbase_eth.csv")
    hashrate()
    with (OUT / "retrieval_meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print("retrieval_meta.json written")


if __name__ == "__main__":
    main()
