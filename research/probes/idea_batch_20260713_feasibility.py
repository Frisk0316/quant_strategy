"""Data-availability feasibility probes for idea batch 2026-07-13 (taxonomy_003).

Availability/coverage ONLY — no signal quality, no return correlations, no
parameter search (0 trials, no K). Candidates probed:
  C-1 F-OPTFLOW-POSITIONING  : DB optflow_deribit_{btc,eth} hourly coverage
  C-2 F-ONCHAIN-FLOW         : blockchain.info charts API reachability/span
  C-3 F-STABLECOIN-LIQUIDITY : DefiLlama stablecoincharts API span/granularity
  C-4 F-XS-ILLIQUIDITY       : canonical_candles vol_quote breadth on sample days
  C-5 F-COINBASE-PREMIUM     : Coinbase Exchange daily candles reachability/span

Usage: python research/probes/idea_batch_20260713_feasibility.py
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

DSN = "postgresql://quant:changeme@localhost:5432/quant"
OUT = Path("results/idea_batch_20260713_taxonomy_003")
UA = {"User-Agent": "quant-strategy-idea-probe/1"}


def fetch_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


async def probe_optflow(conn) -> dict:
    out = {}
    for ds in ("optflow_deribit_btc", "optflow_deribit_eth"):
        rows = await conn.fetch(
            """
            select observed_at, published_at, value_num
            from external_observations
            where dataset_id = $1
              and coalesce(quality_status,'') <> 'suspect'
            order by observed_at
            """,
            ds,
        )
        n = len(rows)
        lo, hi = rows[0]["observed_at"], rows[-1]["observed_at"]
        expected = int((hi - lo).total_seconds() // 3600) + 1
        gaps = []
        prev = None
        bucket_end_ok = 0
        for r in rows:
            if prev is not None:
                dh = (r["observed_at"] - prev).total_seconds() / 3600
                if dh > 1:
                    gaps.append(dh)
            prev = r["observed_at"]
            if (r["published_at"] - r["observed_at"]).total_seconds() == 3600:
                bucket_end_ok += 1
        # daily-sampled zero-delta check on value_num (frozen-feed guard)
        daily = {}
        for r in rows:
            daily[r["observed_at"].date()] = r["value_num"]
        vals = list(daily.values())
        zero_delta = sum(1 for a, b in zip(vals, vals[1:]) if a == b)
        out[ds] = {
            "rows": n,
            "first": lo.isoformat(),
            "last": hi.isoformat(),
            "coverage": n / expected,
            "gap_count_gt1h": len(gaps),
            "max_gap_hours": max(gaps) if gaps else 0.0,
            "published_at_bucket_end_ratio": bucket_end_ok / n,
            "daily_zero_delta_ratio": zero_delta / max(1, len(vals) - 1),
        }
    return out


async def probe_amihud_breadth(conn) -> dict:
    days = ("2024-03-15", "2025-03-14", "2026-06-16")
    out = {"sample_days": {}}
    for day in days:
        rows = await conn.fetch(
            """
            select inst_id, count(*) bars, sum(vol_quote) dollar_vol
            from canonical_candles
            where source_primary='binance' and bar='1m'
              and ts >= $1::timestamptz and ts < $1::timestamptz + interval '1 day'
            group by inst_id
            """,
            datetime.fromisoformat(day).replace(tzinfo=timezone.utc),
        )
        complete = [r for r in rows if r["bars"] >= 1296 and r["dollar_vol"]]  # >=90% of 1440
        out["sample_days"][day] = {
            "symbols_any": len(rows),
            "symbols_complete_with_dollar_vol": len(complete),
        }
    return out


def probe_defillama() -> dict:
    data = fetch_json("https://stablecoins.llama.fi/stablecoincharts/all")
    first = datetime.fromtimestamp(int(data[0]["date"]), tz=timezone.utc)
    last = datetime.fromtimestamp(int(data[-1]["date"]), tz=timezone.utc)
    steps = [int(b["date"]) - int(a["date"]) for a, b in zip(data[-30:], data[-29:])]
    return {
        "points": len(data),
        "first": first.date().isoformat(),
        "last": last.date().isoformat(),
        "daily_granularity": all(s == 86400 for s in steps),
        "fields_sample": sorted(data[-1].keys()),
    }


def probe_coinbase() -> dict:
    url = (
        "https://api.exchange.coinbase.com/products/BTC-USD/candles"
        "?granularity=86400&start=2021-01-01T00:00:00Z&end=2021-10-01T00:00:00Z"
    )
    candles = fetch_json(url)
    return {
        "rows_2021_sample": len(candles),
        "note": "public, 300 candles/request, paginated backfill required",
    }


def probe_blockchain_info() -> dict:
    data = fetch_json(
        "https://api.blockchain.info/charts/hash-rate?timespan=5years&format=json&sampled=false"
    )
    vals = data.get("values", [])
    return {
        "points_5y": len(vals),
        "first": datetime.fromtimestamp(vals[0]["x"], tz=timezone.utc).date().isoformat()
        if vals
        else None,
        "last": datetime.fromtimestamp(vals[-1]["x"], tz=timezone.utc).date().isoformat()
        if vals
        else None,
    }


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "data-availability only; 0 trials, no K, no signal metrics",
        "probes": {},
    }
    conn = await asyncpg.connect(DSN, timeout=10)
    try:
        result["probes"]["c1_optflow"] = await probe_optflow(conn)
        result["probes"]["c4_amihud_breadth"] = await probe_amihud_breadth(conn)
    finally:
        await conn.close()
    for key, fn in (
        ("c3_defillama_stablecoins", probe_defillama),
        ("c5_coinbase_candles", probe_coinbase),
        ("c2_blockchain_info_hashrate", probe_blockchain_info),
    ):
        try:
            result["probes"][key] = fn()
        except Exception as err:  # record reachability failures honestly
            result["probes"][key] = {"error": f"{type(err).__name__}: {err}"}
    with (OUT / "feasibility.json").open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(json.dumps(result["probes"], indent=2)[:3500])
    print(f"written: {OUT / 'feasibility.json'}")


if __name__ == "__main__":
    asyncio.run(main())
