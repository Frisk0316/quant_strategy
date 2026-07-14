"""E-052 step 1: reconstruct a 30d ATM IV proxy from the Deribit trade tape.

Pre-registered method (docs/superpowers/specs/2026-07-14-h014-e052-extension-spec.md):
per day, premium-amount-weighted mean trade IV over option trades with tenor
20-40 calendar days and strike within +/-10% of the trade's index price;
<10 qualifying trades carries the previous day (counted). Sweep window
2019-04-01 -> 2021-06-30 (overlap with DVOL from 2021-03-24 for splice calib).

Usage: python research/probes/h014_e052_iv_proxy.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h014_collect_leg_marks import get  # noqa: E402

OUT = Path("results/h014_e052_extension_20260714")
START = datetime(2019, 4, 1, tzinfo=timezone.utc)
END = datetime(2021, 7, 1, tzinfo=timezone.utc)
DAY_MS = 86_400_000
MIN_TRADES = 10
MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def parse_instrument(name: str):
    """BTC-26JUN20-9000-C -> (expiry_dt, strike, kind) or None."""
    parts = name.split("-")
    if len(parts) != 4:
        return None
    try:
        # date token like 26JUN20 or 5JUN20
        token = parts[1]
        mon = MONTHS[token[-5:-2]]
        year = 2000 + int(token[-2:])
        day = int(token[:-5])
        expiry = datetime(year, mon, day, 8, 0, tzinfo=timezone.utc)
        return expiry, float(parts[2]), parts[3]
    except (KeyError, ValueError):
        return None


TENOR_LO, TENOR_HI = 10, 60          # v2 filter (spec-amended before rerun)
MONEYNESS_MAX = 0.15
RAW_TENOR_HI, RAW_MONEYNESS_MAX = 90, 0.30  # stored superset for re-aggregation


def sweep(currency: str, raw_writer) -> tuple[dict, dict]:
    daily = defaultdict(lambda: {"wsum": 0.0, "w": 0.0, "n": 0})
    counts = defaultdict(int)
    cursor = int(START.timestamp() * 1000)
    end_ms = int(END.timestamp() * 1000)
    calls = 0
    while cursor < end_ms:
        for outer in range(6):  # survive minutes-long DNS/network outages
            try:
                res = get("get_last_trades_by_currency_and_time",
                          {"currency": currency, "kind": "option",
                           "start_timestamp": cursor, "end_timestamp": end_ms,
                           "count": 1000, "sorting": "asc", "include_old": "true"})
                break
            except Exception as err:
                if outer == 5:
                    raise
                print(f"  {currency}: network error ({err}); retry in 60s")
                time.sleep(60)
        trades = res.get("trades", [])
        calls += 1
        for t in trades:
            counts["seen"] += 1
            iv, idx = t.get("iv"), t.get("index_price")
            if not iv or not idx:
                continue
            meta = parse_instrument(t["instrument_name"])
            if not meta:
                continue
            expiry, strike, kind = meta
            ts = t["timestamp"]
            tenor_d = (expiry.timestamp() * 1000 - ts) / DAY_MS
            moneyness = abs(strike - idx) / idx
            if tenor_d <= RAW_TENOR_HI and moneyness <= RAW_MONEYNESS_MAX:
                raw_writer.writerow([t["instrument_name"], ts, t["price"],
                                     t["amount"], iv, idx, round(tenor_d, 3),
                                     round(moneyness, 5), kind])
                counts["raw_stored"] += 1
            if not (TENOR_LO <= tenor_d <= TENOR_HI):
                continue
            if moneyness > MONEYNESS_MAX:
                continue
            day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
            w = t["price"] * t["amount"]  # premium amount weight (coin)
            if w <= 0:
                continue
            b = daily[day]
            b["wsum"] += iv * w
            b["w"] += w
            b["n"] += 1
            counts["used"] += 1
        if not res.get("has_more") or not trades:
            break
        cursor = trades[-1]["timestamp"] + 1
        if calls % 200 == 0:
            print(f"  {currency}: {calls} calls, cursor "
                  f"{datetime.fromtimestamp(cursor/1000, tz=timezone.utc).date()}")
        time.sleep(0.04)
    counts["api_calls"] = calls
    return daily, counts


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    import gzip
    meta = {"generated_at": datetime.now(timezone.utc).isoformat(),
            "method": f"v2: premium-weighted mean trade IV, tenor {TENOR_LO}-{TENOR_HI}d, moneyness <= {MONEYNESS_MAX}",
            "window": [START.date().isoformat(), END.date().isoformat()],
            "min_trades": MIN_TRADES, "per_currency": {}}
    for ccy in ("BTC", "ETH"):
        raw_fh = gzip.open(OUT / f"raw_trades_{ccy.lower()}.csv.gz", "wt", newline="", encoding="utf-8")
        raw_writer = csv.writer(raw_fh)
        raw_writer.writerow(["instrument", "timestamp", "price", "amount",
                             "iv", "index_price", "tenor_d", "moneyness", "kind"])
        daily, counts = sweep(ccy, raw_writer)
        raw_fh.close()
        rows, carry = [], 0
        prev = None
        d = START.date()
        from datetime import timedelta
        while d < END.date():
            key = d.isoformat()
            b = daily.get(key)
            if b and b["n"] >= MIN_TRADES:
                val, n, src = b["wsum"] / b["w"], b["n"], "tape"
                prev = val
            elif prev is not None:
                val, n, src = prev, (b["n"] if b else 0), "carry"
                carry += 1
            else:
                d += timedelta(days=1)
                continue
            rows.append({"date": key, "iv_proxy": val, "n_trades": n, "source": src})
            d += timedelta(days=1)
        with (OUT / f"iv_proxy_{ccy.lower()}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["date", "iv_proxy", "n_trades", "source"])
            w.writeheader()
            w.writerows(rows)
        meta["per_currency"][ccy] = {**counts, "days": len(rows), "carry_days": carry}
        print(f"{ccy}: {len(rows)} days, carry {carry}, "
              f"trades used {counts['used']}/{counts['seen']}, calls {counts['api_calls']}")
    with (OUT / "iv_proxy_meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)


if __name__ == "__main__":
    main()
