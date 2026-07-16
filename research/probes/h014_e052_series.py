"""E-052 step 2: spliced IV series + extended regime classification.

Splice (pre-registered): pre-2021-03-24 = tape IV proxy minus the overlap
bias; 2021-03-24+ = actual daily DVOL. Overlap window 2021-03-24..2021-06-30;
fail closed if |corr| < 0.85 on overlap days. Then rebuild px/RV/VRP/z/ivp
exactly with the E-039 code over 2019-04 -> now and write
series_ext_{btc,eth}.csv (same columns as the E-039 series).

Usage: python research/probes/h014_e052_series.py
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f_vol_regime_opt_probe as e39  # noqa: E402

OUT = Path("results/h014_e052_extension_20260714")
DVOL_START = "2021-03-24"
OVERLAP_END = "2021-06-30"
MIN_OVERLAP_CORR = 0.85


MAX_CARRY_RUN = 5
MAX_CARRY_RATIO = 0.15


def load_proxy(ccy: str) -> dict[str, float]:
    out, sources = {}, []
    with (OUT / f"iv_proxy_{ccy.lower()}.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["date"]] = float(row["iv_proxy"])
            sources.append(row["source"])
    # v2 staleness rule (spec-amended): fail closed on long/frequent carries
    runs, cur = [], 0
    for s in sources:
        cur = cur + 1 if s == "carry" else 0
        runs.append(cur)
    carry_ratio = sum(1 for s in sources if s == "carry") / max(1, len(sources))
    if max(runs, default=0) > MAX_CARRY_RUN or carry_ratio > MAX_CARRY_RATIO:
        raise SystemExit(
            f"FAIL_CLOSED staleness ({ccy}): max_run={max(runs)} "
            f"carry_ratio={carry_ratio:.3f} vs <= {MAX_CARRY_RUN}/{MAX_CARRY_RATIO}"
        )
    return out


def main() -> None:
    # widen the E-039 fetch window to the extension start
    e39.START_MS = int(datetime(2019, 4, 1, tzinfo=timezone.utc).timestamp() * 1000)
    stats = {}
    for ccy, perp in (("BTC", "BTC-PERPETUAL"), ("ETH", "ETH-PERPETUAL")):
        proxy = load_proxy(ccy)
        dvol = e39.fetch_dvol(ccy)  # daily closes, 2021-03-24+
        px = e39.fetch_px(perp)

        overlap = [d for d in sorted(proxy) if DVOL_START <= d <= OVERLAP_END and d in dvol]
        pv = [proxy[d] for d in overlap]
        dv = [dvol[d] for d in overlap]
        bias = statistics.mean(p - v for p, v in zip(pv, dv))
        corr = statistics.correlation(pv, dv)
        stats[ccy] = {"overlap_days": len(overlap), "bias": bias, "corr": corr,
                      "proxy_std": statistics.pstdev(pv), "dvol_std": statistics.pstdev(dv)}
        print(f"{ccy}: overlap {len(overlap)}d bias {bias:+.2f} corr {corr:.4f}")
        if corr < MIN_OVERLAP_CORR:
            with (OUT / "splice_stats.json").open("w", encoding="utf-8") as fh:
                json.dump({"status": "FAIL_CLOSED_low_overlap_corr", "stats": stats},
                          fh, indent=2)
            raise SystemExit(2)

        spliced = dict(dvol)
        for d, v in proxy.items():
            if d < DVOL_START:
                spliced[d] = v - bias
        rows = e39.build_series(spliced, px)
        with (OUT / f"series_ext_{ccy.lower()}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["date", "dvol", "px", "rv", "vrp",
                                               "z", "ivp", "regime"])
            w.writeheader()
            w.writerows({k: r.get(k, "") for k in w.fieldnames} for r in rows)
        n_class = sum(1 for r in rows if "regime" in r)
        first = next((r["date"] for r in rows if "regime" in r), None)
        stats[ccy].update({"classified_days": n_class, "first_classified": first})
        print(f"{ccy}: {n_class} classified days from {first}")

    with (OUT / "splice_stats.json").open("w", encoding="utf-8") as fh:
        json.dump({"status": "PASS", "min_overlap_corr": MIN_OVERLAP_CORR,
                   "stats": stats}, fh, indent=2)


if __name__ == "__main__":
    main()
