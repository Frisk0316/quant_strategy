"""E-039 Stage-1 synthetic-pricing regime probe for H-014 / F-VOL-REGIME-OPT.

Question: does the IVP(365d) x VRP-z(90d) regime classifier separate
coin-denominated synthetic option payoffs on Deribit BTC/ETH, and is the
CHEAP-bucket long straddle non-negative?

0 trials, no parameter selection: thresholds are FIXED at the grid midpoint
(RICH: ivp>=80 & z>=1.0; CHEAP: ivp<=20 & z<=0) pre-registered in
docs/superpowers/specs/2026-07-13-f-vol-regime-opt-hypothesis.md BEFORE this
probe ran.

Known ex-ante biases (affect levels, not between-bucket separation):
flat smile (leg IV = DVOL), vanilla instead of inverse pricing, daily close
instead of 08:00 UTC delivery TWAP, +/-5% premium haircut for fees+spread.

Data: Deribit public API, daily resolution, no auth. stdlib only.
Usage: python research/probes/f_vol_regime_opt_probe.py [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://www.deribit.com/api/v2/public"
START_MS = int(datetime(2021, 3, 24, tzinfo=timezone.utc).timestamp() * 1000)
END_MS = int(datetime(2026, 7, 13, tzinfo=timezone.utc).timestamp() * 1000)
DAY_MS = 86_400_000

# fixed probe parameters (grid midpoint; see spec — do not tune here)
RV_W = 28
VRP_Z_W = 90
IVP_W = 365
TENOR_D = 30
RICH_IVP, RICH_Z = 80.0, 1.0
CHEAP_IVP, CHEAP_Z = 20.0, 0.0
HAIRCUT = 0.05  # receive 95% when selling, pay 105% when buying
D1_25 = 0.6744897501960817  # Phi^-1(0.75)
D1_10 = 1.2815515655446004  # Phi^-1(0.90)


def _get(path: str, params: dict) -> dict:
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                payload = json.loads(r.read())
            return payload["result"]
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_dvol(currency: str) -> dict[str, float]:
    """date -> DVOL daily close (index points = annualized IV %)."""
    out: dict[str, float] = {}
    end = END_MS
    while True:
        res = _get(
            "get_volatility_index_data",
            {
                "currency": currency,
                "resolution": "86400",
                "start_timestamp": START_MS,
                "end_timestamp": end,
            },
        )
        rows = res.get("data", [])
        for ts, _o, _h, _l, close in rows:
            d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
            out[d] = float(close)
        cont = res.get("continuation")
        if not rows or cont is None or cont <= START_MS:
            break
        end = cont
    return out


def fetch_px(instrument: str) -> dict[str, float]:
    """date -> daily close, paginated yearly to stay under API bar caps."""
    out: dict[str, float] = {}
    start = START_MS
    while start < END_MS:
        chunk_end = min(start + 365 * DAY_MS, END_MS)
        res = _get(
            "get_tradingview_chart_data",
            {
                "instrument_name": instrument,
                "resolution": "1D",
                "start_timestamp": start,
                "end_timestamp": chunk_end,
            },
        )
        for ts, close in zip(res.get("ticks", []), res.get("close", [])):
            d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
            out[d] = float(close)
        start = chunk_end + DAY_MS
    return out


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs(s: float, k: float, sigma: float, t: float, kind: str) -> float:
    if sigma <= 0 or t <= 0:
        return max(s - k, 0.0) if kind == "c" else max(k - s, 0.0)
    st = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + 0.5 * sigma * sigma * t) / st
    d2 = d1 - st
    if kind == "c":
        return s * norm_cdf(d1) - k * norm_cdf(d2)
    return k * norm_cdf(-d2) - s * norm_cdf(-d1)


def build_series(dvol: dict[str, float], px: dict[str, float]) -> list[dict]:
    dates = sorted(set(dvol) & set(px))
    rows = [{"date": d, "dvol": dvol[d], "px": px[d]} for d in dates]
    # realized vol: trailing RV_W daily log returns, annualized %
    for i, row in enumerate(rows):
        if i >= RV_W:
            rets = [
                math.log(rows[j]["px"] / rows[j - 1]["px"])
                for j in range(i - RV_W + 1, i + 1)
            ]
            row["rv"] = statistics.pstdev(rets) * math.sqrt(365) * 100
    for row in rows:
        if "rv" in row:
            row["vrp"] = row["dvol"] - row["rv"]
    vrp_idx = [i for i, r in enumerate(rows) if "vrp" in r]
    for pos, i in enumerate(vrp_idx):
        if pos >= VRP_Z_W:
            window = [rows[j]["vrp"] for j in vrp_idx[pos - VRP_Z_W : pos + 1]]
            mu, sd = statistics.mean(window), statistics.pstdev(window)
            if sd > 0:
                rows[i]["z"] = (rows[i]["vrp"] - mu) / sd
    for i, row in enumerate(rows):
        if i >= IVP_W:
            hist = [rows[j]["dvol"] for j in range(i - IVP_W, i + 1)]
            row["ivp"] = 100.0 * sum(1 for v in hist if v < row["dvol"]) / len(hist)
    for row in rows:
        if "z" in row and "ivp" in row:
            if row["ivp"] >= RICH_IVP and row["z"] >= RICH_Z:
                row["regime"] = "RICH"
            elif row["ivp"] <= CHEAP_IVP and row["z"] <= CHEAP_Z:
                row["regime"] = "CHEAP"
            else:
                row["regime"] = "NORMAL"
    return rows


def simulate(rows: list[dict]) -> list[dict]:
    by_date = {r["date"]: i for i, r in enumerate(rows)}
    trades = []
    t = TENOR_D / 365.0
    for i, row in enumerate(rows):
        if "regime" not in row:
            continue
        # expiry = calendar day +TENOR_D, tolerate up to 2 missing days
        expiry_i = None
        d0 = datetime.fromisoformat(row["date"])
        for slack in range(3):
            key = (d0 + timedelta(days=TENOR_D + slack)).date().isoformat()
            if key in by_date:
                expiry_i = by_date[key]
                break
        if expiry_i is None:
            continue
        s, s_t = row["px"], rows[expiry_i]["px"]
        sig = row["dvol"] / 100.0
        var_half, st_ = sig * sig * t / 2.0, sig * math.sqrt(t)
        k_c = s * math.exp(var_half + D1_25 * st_)
        k_p25 = s * math.exp(var_half - D1_25 * st_)
        k_p10 = s * math.exp(var_half - D1_10 * st_)
        c = bs(s, k_c, sig, t, "c")
        p25 = bs(s, k_p25, sig, t, "p")
        p10 = bs(s, k_p10, sig, t, "p")
        c_atm = bs(s, s, sig, t, "c")
        p_atm = bs(s, s, sig, t, "p")
        sell = 1.0 - HAIRCUT
        buy = 1.0 + HAIRCUT
        covered_call = sell * c / s - max(s_t - k_c, 0.0) / s_t
        strangle_ps = (
            sell * (c + p25) / s
            - buy * p10 / s
            - (
                max(s_t - k_c, 0.0)
                + max(k_p25 - s_t, 0.0)
                - max(k_p10 - s_t, 0.0)
            )
            / s_t
        )
        long_straddle = (max(s_t - s, 0.0) + max(s - s_t, 0.0)) / s_t - buy * (
            c_atm + p_atm
        ) / s
        trades.append(
            {
                "date": row["date"],
                "regime": row["regime"],
                "ivp": round(row["ivp"], 2),
                "z": round(row["z"], 3),
                "dvol": row["dvol"],
                "covered_call": covered_call,
                "short_strangle_ps": strangle_ps,
                "long_straddle": long_straddle,
            }
        )
    return trades


def bucket_stats(trades: list[dict], leg: str) -> dict:
    out = {}
    for regime in ("RICH", "NORMAL", "CHEAP"):
        vals = sorted(t[leg] for t in trades if t["regime"] == regime)
        if not vals:
            out[regime] = {"n": 0}
            continue
        n = len(vals)
        nonov = [t[leg] for j, t in enumerate(trades) if t["regime"] == regime][::30]
        out[regime] = {
            "n": n,
            "mean": statistics.mean(vals),
            "median": statistics.median(vals),
            "p5": vals[max(0, int(0.05 * n) - 1)],
            "min": vals[0],
            "hit_rate": sum(1 for v in vals if v > 0) / n,
            "nonoverlap_n": len(nonov),
            "nonoverlap_mean": statistics.mean(nonov) if nonov else None,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/stage1_probe_20260713_f_vol_regime_opt")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {"params": {
        "rv_w": RV_W, "vrp_z_w": VRP_Z_W, "ivp_w": IVP_W, "tenor_d": TENOR_D,
        "rich": [RICH_IVP, RICH_Z], "cheap": [CHEAP_IVP, CHEAP_Z],
        "haircut": HAIRCUT, "iv_source": "DVOL flat smile", "pricing": "vanilla BS r=0",
    }, "symbols": {}}

    for ccy, perp in (("BTC", "BTC-PERPETUAL"), ("ETH", "ETH-PERPETUAL")):
        dvol = fetch_dvol(ccy)
        px = fetch_px(perp)
        rows = build_series(dvol, px)
        trades = simulate(rows)
        with open(out_dir / f"series_{ccy.lower()}.csv", "w", newline="") as f:
            w = csv.DictWriter(
                f, fieldnames=["date", "dvol", "px", "rv", "vrp", "z", "ivp", "regime"]
            )
            w.writeheader()
            w.writerows({k: r.get(k, "") for k in w.fieldnames} for r in rows)
        with open(out_dir / f"trades_{ccy.lower()}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
            w.writeheader()
            w.writerows(trades)
        sym = {
            "dvol_days": len(dvol),
            "px_days": len(px),
            "classified_days": sum(1 for r in rows if "regime" in r),
            "regime_counts": {
                k: sum(1 for r in rows if r.get("regime") == k)
                for k in ("RICH", "NORMAL", "CHEAP")
            },
        }
        for leg in ("covered_call", "short_strangle_ps", "long_straddle"):
            sym[leg] = bucket_stats(trades, leg)
        results["symbols"][ccy] = sym
        print(f"== {ccy}: {sym['classified_days']} classified days, "
              f"regimes {sym['regime_counts']}")
        for leg in ("covered_call", "short_strangle_ps", "long_straddle"):
            for reg, s in sym[leg].items():
                if s["n"]:
                    print(
                        f"  {leg:18s} {reg:6s} n={s['n']:5d} mean={s['mean']:+.4f} "
                        f"med={s['median']:+.4f} p5={s['p5']:+.4f} min={s['min']:+.4f} "
                        f"hit={s['hit_rate']:.2f} nonov_mean="
                        f"{s['nonoverlap_mean']:+.4f} (n={s['nonoverlap_n']})"
                    )

    with open(out_dir / "probe_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"written: {out_dir}/probe_results.json")


if __name__ == "__main__":
    main()
