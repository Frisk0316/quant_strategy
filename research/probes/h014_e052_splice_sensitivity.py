"""E-052 splice-bias sensitivity check (persisted artifact).

The splice bias constant is estimated on the 2021-03-24..2021-06-30 overlap
and applied to pre-2021 proxy values — a construction-time lookahead. This
check quantifies its materiality: IVP is a trailing-365d rank and VRP-z is
demeaned over 90d, so a CONSTANT shift should cancel except near the seam.
We recompute the extended series under bias shifts of +/-3 IV points and
report the Jaccard overlap of the frozen-combo (ivp>=85, z>=0.5) RICH-day
sets restricted to the NEW pre-2022-05-12 segment.

Writes results/h014_e052_extension_20260714/splice_sensitivity.json.

Usage: python research/probes/h014_e052_splice_sensitivity.py
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f_vol_regime_opt_probe as e39  # noqa: E402
from h014_e052_series import DVOL_START, load_proxy  # noqa: E402

OUT = Path("results/h014_e052_extension_20260714")
SHIFTS = (-3.0, 0.0, 3.0)
IVP_MIN, Z_MIN = 85.0, 0.5          # frozen production combo
NEW_SEGMENT_END = "2022-05-12"       # E-051's window started here


def rich_days(rows) -> set[str]:
    return {
        r["date"]
        for r in rows
        if "regime" in r and r["ivp"] >= IVP_MIN and r["z"] >= Z_MIN
        and r["date"] < NEW_SEGMENT_END
    }


def main() -> None:
    e39.START_MS = int(datetime(2019, 4, 1, tzinfo=timezone.utc).timestamp() * 1000)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "combo": {"ivp_min": IVP_MIN, "z_min": Z_MIN},
              "segment": f"< {NEW_SEGMENT_END}", "shifts_iv_pts": SHIFTS,
              "per_currency": {}}
    for ccy, perp in (("BTC", "BTC-PERPETUAL"), ("ETH", "ETH-PERPETUAL")):
        proxy = load_proxy(ccy)
        dvol = e39.fetch_dvol(ccy)
        px = e39.fetch_px(perp)
        overlap = [d for d in sorted(proxy) if DVOL_START <= d <= "2021-06-30" and d in dvol]
        bias = statistics.mean(proxy[d] - dvol[d] for d in overlap)
        sets = {}
        for shift in SHIFTS:
            spliced = dict(dvol)
            for d, v in proxy.items():
                if d < DVOL_START:
                    spliced[d] = v - bias + shift
            sets[shift] = rich_days(e39.build_series(spliced, px))
        base = sets[0.0]
        entry = {"bias": bias, "base_rich_days": len(base)}
        for shift in (-3.0, 3.0):
            s = sets[shift]
            entry[f"shift_{shift:+.0f}"] = {
                "rich_days": len(s),
                "jaccard_vs_base": len(base & s) / max(1, len(base | s)),
            }
        report["per_currency"][ccy] = entry
        print(ccy, entry)
    with (OUT / "splice_sensitivity.json").open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("written:", OUT / "splice_sensitivity.json")


if __name__ == "__main__":
    main()
