"""H-014 data collection: real traded premiums for the Stage-3 entry legs.

Free path (no vendor purchase): Deribit official history API trade tape.
Scope-smart: only days in the UNION of the pre-registered grid's RICH regimes
(ivp >= 75 AND z >= 0.5, the loosest combo) from the immutable E-039 series,
plus each such day's ~30d expiry legs (25d call / 25d put / 10d put / ATM
call+put). For each (day, leg): nearest listed strike, day-VWAP traded price
in coin, trade count, mean trade IV. Missing-liquidity days recorded, never
fabricated.

Usage: python research/probes/h014_collect_leg_marks.py
"""

from __future__ import annotations

import csv
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIST = "https://history.deribit.com/api/v2/public"
SERIES = Path("results/stage1_probe_20260713_f_vol_regime_opt")
OUT = Path("results/h014_leg_marks_20260714")
UA = {"User-Agent": "quant-strategy-h014-collect/1"}
IVP_MIN, Z_MIN = 75.0, 0.5  # loosest pre-registered combo -> union of RICH days
TENOR_D = 30
D1_25 = 0.6744897501960817
D1_10 = 1.2815515655446004


def get(path: str, params: dict, retries: int = 5):
    url = f"{HIST}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read())["result"]
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.0 * (attempt + 1))


def rich_days(symbol: str) -> list[dict]:
    rows = []
    with (SERIES / f"series_{symbol.lower()}.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                if float(row["ivp"]) >= IVP_MIN and float(row["z"]) >= Z_MIN:
                    rows.append({"date": row["date"], "px": float(row["px"]), "dvol": float(row["dvol"])})
            except (KeyError, ValueError):
                continue
    return rows


def load_instruments(currency: str) -> list[dict]:
    res = get("get_instruments", {"currency": currency, "kind": "option",
                                  "expired": "true", "include_old": "true"})
    live = get("get_instruments", {"currency": currency, "kind": "option"})
    seen, out = set(), []
    for inst in (res or []) + (live or []):
        name = inst["instrument_name"]
        if name not in seen:
            seen.add(name)
            out.append(inst)
    return out


def target_strikes(px: float, dvol: float) -> dict[str, tuple[float, str]]:
    sig = dvol / 100.0
    t = TENOR_D / 365.0
    vh, st = sig * sig * t / 2.0, sig * math.sqrt(t)
    return {
        "call_25d": (px * math.exp(vh + D1_25 * st), "call"),
        "put_25d": (px * math.exp(vh - D1_25 * st), "put"),
        "put_10d": (px * math.exp(vh - D1_10 * st), "put"),
        "atm_call": (px, "call"),
        "atm_put": (px, "put"),
    }


def day_vwap(instrument: str, day: str) -> dict | None:
    start = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)
    end = start + 86_400_000
    trades, cursor = [], start
    while True:
        res = get("get_last_trades_by_instrument_and_time",
                  {"instrument_name": instrument, "start_timestamp": cursor,
                   "end_timestamp": end, "count": 1000, "sorting": "asc",
                   "include_old": "true"})
        batch = res.get("trades", [])
        trades.extend(batch)
        if not res.get("has_more") or not batch:
            break
        cursor = batch[-1]["timestamp"] + 1
    if not trades:
        return None
    amt = sum(t["amount"] for t in trades)
    vwap = sum(t["price"] * t["amount"] for t in trades) / amt
    ivs = [t["iv"] for t in trades if t.get("iv")]
    return {"vwap_coin": vwap, "trade_count": len(trades), "amount": amt,
            "mean_iv": sum(ivs) / len(ivs) if ivs else None}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fields = ["date", "symbol", "leg", "instrument", "strike", "expiry",
              "target_strike", "vwap_coin", "trade_count", "amount", "mean_iv", "status"]
    written = 0
    with (OUT / "leg_marks.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for ccy in ("BTC", "ETH"):
            days = rich_days(ccy)
            instruments = load_instruments(ccy)
            by_expiry: dict[int, list[dict]] = {}
            for inst in instruments:
                by_expiry.setdefault(inst["expiration_timestamp"], []).append(inst)
            expiries = sorted(by_expiry)
            print(f"{ccy}: {len(days)} RICH-union days, {len(instruments)} instruments")
            for row in days:
                day_ms = int(datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
                target_exp = day_ms + TENOR_D * 86_400_000
                # only expiries whose chain EXISTED on day D (creation <= D);
                # otherwise D+30 lands on daily/weekly instruments created later
                usable = [
                    e for e in expiries
                    if e > day_ms + 5 * 86_400_000
                    and any(i.get("creation_timestamp", 0) <= day_ms for i in by_expiry[e])
                ]
                if not usable:
                    continue
                expiry = min(usable, key=lambda e: abs(e - target_exp))
                chain = [
                    i for i in by_expiry[expiry]
                    if i.get("creation_timestamp", 0) <= day_ms
                ]
                exp_str = datetime.fromtimestamp(expiry / 1000, tz=timezone.utc).date().isoformat()
                for leg, (k_target, kind) in target_strikes(row["px"], row["dvol"]).items():
                    cands = sorted(
                        (i for i in chain if i["option_type"] == kind),
                        key=lambda i: abs(i["strike"] - k_target),
                    )[:2]  # nearest strike, then first fallback
                    rec = {"date": row["date"], "symbol": ccy, "leg": leg,
                           "target_strike": round(k_target, 2), "expiry": exp_str,
                           "instrument": "", "strike": "", "vwap_coin": "",
                           "trade_count": "", "amount": "", "mean_iv": "",
                           "status": "no_trades"}
                    for inst in cands:
                        marks = day_vwap(inst["instrument_name"], row["date"])
                        time.sleep(0.05)
                        if marks:
                            rec.update({"instrument": inst["instrument_name"],
                                        "strike": inst["strike"], "status": "ok",
                                        **marks})
                            break
                        rec.update({"instrument": inst["instrument_name"],
                                    "strike": inst["strike"]})
                    writer.writerow(rec)
                    written += 1
                    if written % 100 == 0:
                        fh.flush()
                        print(f"  {written} leg rows...")
    meta = {"retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source": "history.deribit.com trade tape (official, free)",
            "scope": f"union RICH days (ivp>={IVP_MIN}, z>={Z_MIN}) from immutable E-039 series",
            "rows": written}
    with (OUT / "meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"done: {written} leg rows -> {OUT}/leg_marks.csv")


if __name__ == "__main__":
    main()
