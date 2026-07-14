"""H-014 Stage-3 data extension per the signed-off spec (2026-07-14).

Collects, from free official sources (history.deribit.com):
  entries.csv   — per (signal day, symbol, leg): the instrument entered at
                  signal+1 (t+1), targeted from SIGNAL-day close & DVOL,
                  chain filtered by creation_timestamp <= entry day.
  marks.csv     — per (instrument, day): trade-tape daily VWAP, amount,
                  trade count, mean trade IV, from each instrument's full
                  trade history (one paginated sweep per instrument).
  delivery.csv  — official daily delivery prices for btc_usd / eth_usd.

Signal days = E-039 series days with ivp >= 75 AND z >= 0.5 (union of the
pre-registered grid; per-combo subsets are taken at backtest time).

Usage: python research/probes/h014_collect_stage3_data.py
"""

from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h014_collect_leg_marks import get, load_instruments, target_strikes  # noqa: E402

SERIES = Path("results/stage1_probe_20260713_f_vol_regime_opt")
OUT = Path("results/h014_stage3_data_20260714")
IVP_MIN, Z_MIN = 75.0, 0.5
LEGS = ("call_25d", "put_25d", "put_10d")
DAY_MS = 86_400_000


def signal_days(symbol: str) -> list[dict]:
    rows = []
    with (SERIES / f"series_{symbol.lower()}.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                if float(row["ivp"]) >= IVP_MIN and float(row["z"]) >= Z_MIN:
                    rows.append({"date": row["date"], "px": float(row["px"]),
                                 "dvol": float(row["dvol"])})
            except (KeyError, ValueError):
                continue
    return rows


def instrument_trades_daily(name: str, start_ms: int, end_ms: int) -> dict[str, dict]:
    """Full trade sweep for one instrument -> per-day VWAP/amount/count/IV."""
    buckets: dict[str, dict] = defaultdict(lambda: {"pv": 0.0, "amt": 0.0, "n": 0,
                                                    "iv_sum": 0.0, "iv_n": 0})
    cursor = start_ms
    while True:
        res = get("get_last_trades_by_instrument_and_time",
                  {"instrument_name": name, "start_timestamp": cursor,
                   "end_timestamp": end_ms, "count": 1000, "sorting": "asc",
                   "include_old": "true"})
        trades = res.get("trades", [])
        for t in trades:
            day = datetime.fromtimestamp(t["timestamp"] / 1000, tz=timezone.utc).date().isoformat()
            b = buckets[day]
            b["pv"] += t["price"] * t["amount"]
            b["amt"] += t["amount"]
            b["n"] += 1
            if t.get("iv"):
                b["iv_sum"] += t["iv"]
                b["iv_n"] += 1
        if not res.get("has_more") or not trades:
            break
        cursor = trades[-1]["timestamp"] + 1
        time.sleep(0.05)
    return {
        day: {"vwap_coin": b["pv"] / b["amt"], "amount": b["amt"], "trade_count": b["n"],
              "mean_iv": b["iv_sum"] / b["iv_n"] if b["iv_n"] else None}
        for day, b in buckets.items() if b["amt"] > 0
    }


def delivery_prices(index_name: str) -> list[dict]:
    out, offset = [], 0
    while True:
        res = get("get_delivery_prices",
                  {"index_name": index_name, "offset": offset, "count": 1000})
        recs = res.get("data", [])
        out.extend({"date": r["date"], "price": r["delivery_price"]} for r in recs)
        if len(recs) < 1000:
            break
        offset += len(recs)
        time.sleep(0.05)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    needed: dict[str, tuple[int, int]] = {}  # instrument -> (first_entry_ms, expiry_ms)

    for ccy in ("BTC", "ETH"):
        days = signal_days(ccy)
        instruments = load_instruments(ccy)
        by_expiry: dict[int, list[dict]] = defaultdict(list)
        for inst in instruments:
            by_expiry[inst["expiration_timestamp"]].append(inst)
        expiries = sorted(by_expiry)
        print(f"{ccy}: {len(days)} signal days")
        for row in days:
            signal_ms = int(datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
            entry_ms = signal_ms + DAY_MS
            entry_day = (datetime.fromisoformat(row["date"]) + timedelta(days=1)).date().isoformat()
            target_exp = entry_ms + 30 * DAY_MS
            usable = [
                e for e in expiries
                if e > entry_ms + 5 * DAY_MS
                and any(i.get("creation_timestamp", 0) <= entry_ms for i in by_expiry[e])
            ]
            if not usable:
                continue
            expiry = min(usable, key=lambda e: abs(e - target_exp))
            chain = [i for i in by_expiry[expiry] if i.get("creation_timestamp", 0) <= entry_ms]
            targets = target_strikes(row["px"], row["dvol"])
            for leg in LEGS:
                k_target, kind = targets[leg]
                cands = sorted((i for i in chain if i["option_type"] == kind),
                               key=lambda i: abs(i["strike"] - k_target))
                if not cands:
                    continue
                inst = cands[0]
                name = inst["instrument_name"]
                entries.append({
                    "signal_day": row["date"], "entry_day": entry_day, "symbol": ccy,
                    "leg": leg, "instrument": name, "strike": inst["strike"],
                    "expiry": datetime.fromtimestamp(expiry / 1000, tz=timezone.utc).date().isoformat(),
                    "expiry_ms": expiry, "target_strike": round(k_target, 2),
                })
                first, _exp = needed.get(name, (entry_ms, expiry))
                needed[name] = (min(first, entry_ms), expiry)

    with (OUT / "entries.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(entries[0].keys()))
        w.writeheader()
        w.writerows(entries)
    print(f"entries: {len(entries)} rows, {len(needed)} unique instruments to sweep")

    with (OUT / "marks.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["instrument", "date", "vwap_coin",
                                           "amount", "trade_count", "mean_iv"])
        w.writeheader()
        for i, (name, (first_ms, expiry_ms)) in enumerate(sorted(needed.items()), 1):
            daily = instrument_trades_daily(name, first_ms - DAY_MS, expiry_ms + DAY_MS)
            for day in sorted(daily):
                w.writerow({"instrument": name, "date": day, **daily[day]})
            if i % 25 == 0:
                fh.flush()
                print(f"  swept {i}/{len(needed)} instruments")
            time.sleep(0.05)

    with (OUT / "delivery.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["index", "date", "price"])
        w.writeheader()
        for idx in ("btc_usd", "eth_usd"):
            for rec in delivery_prices(idx):
                w.writerow({"index": idx, **rec})

    with (OUT / "meta.json").open("w", encoding="utf-8") as fh:
        json.dump({"retrieved_at": datetime.now(timezone.utc).isoformat(),
                   "source": "history.deribit.com (official, free)",
                   "signal_filter": {"ivp_min": IVP_MIN, "z_min": Z_MIN},
                   "targeting": "strikes from SIGNAL-day close & DVOL; entry at t+1",
                   "entries": len(entries), "instruments": len(needed)}, fh, indent=2)
    print("done")


if __name__ == "__main__":
    main()
