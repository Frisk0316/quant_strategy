"""H-013 / F-VRP-TIMING: E-038 Stage-2 feasibility probe + Stage-3 fold-refit run.

Spec (pre-registered, user-signed-off 2026-07-12; Stage-3 user-authorized
2026-07-14): docs/superpowers/specs/2026-07-12-f-vrp-timing-hypothesis.md.
Long/flat BTC/ETH perps: long when VRP z (hourly Deribit DVOL minus trailing
realized vol from 1m candles, z vs fixed 90d) >= z_min, else flat. Grid
{RV window W in [14, 28] days, z_min in [0.0, 0.5]} = 4 combos, n_trials = 4.
Window 2024-01-01 -> data end, per spec. Reuses the taxonomy003 book/validation
helpers so DSR/PSR mechanics are identical to prior Stage-3 runs.

Usage: python research/probes/h013_vrp_stage3.py
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import taxonomy003_stage3 as t3  # noqa: E402
from backtesting.data_loader import load_external_observations  # noqa: E402
from backtesting.pipeline_family_minting import decide_family_minting  # noqa: E402
from backtesting.pipeline_refit import combo_key, refit_validation  # noqa: E402

DSN = t3.DSN
OUT = Path("results/h013_vrp_timing_20260714")
WARMUP_START = "2023-09-01"  # W + 90d z warmup before the spec window
SPEC_START, SPEC_END = "2024-01-01", "2026-07-11"
MAJORS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
DVOL_DS = {"BTC-USDT-SWAP": "dvol_deribit_btc_1h", "ETH-USDT-SWAP": "dvol_deribit_eth_1h"}
GRID_W = (14, 28)
GRID_Z = (0.0, 0.5)
Z_WINDOW = 90
MIN_BARS = 1296  # 90% of 1440


async def _fetch_rv_parts(conn) -> pd.DataFrame:
    rows = await conn.fetch(
        """
        SELECT inst_id, (ts AT TIME ZONE 'UTC')::date AS day,
               sum(r) AS s1, sum(r*r) AS s2, count(*) AS n
        FROM (
          SELECT inst_id, ts,
                 ln(close / lag(close) OVER (PARTITION BY inst_id ORDER BY ts)) AS r
          FROM canonical_candles
          WHERE inst_id = ANY($1) AND bar='1m' AND source_primary='binance'
            AND quality_status != 'suspect'
            AND ts >= $2::timestamptz AND ts < $3::timestamptz
        ) x
        WHERE r IS NOT NULL
        GROUP BY inst_id, day
        """,
        MAJORS,
        datetime.fromisoformat(WARMUP_START).replace(tzinfo=timezone.utc),
        datetime.fromisoformat(SPEC_END).replace(tzinfo=timezone.utc),
    )
    df = pd.DataFrame([dict(r) for r in rows])
    df["day"] = pd.to_datetime(df["day"])
    return df


def realized_vol(parts: pd.DataFrame, symbol: str, window_days: int) -> pd.Series:
    """Annualized % std of 1m log returns over trailing W calendar days.

    Days with <90% expected 1m bars reuse the previous day's RV (spec)."""
    sub = parts[parts["inst_id"] == symbol].set_index("day").sort_index()
    idx = pd.date_range(sub.index.min(), sub.index.max(), freq="D")
    sub = sub.reindex(idx)
    s1 = sub["s1"].fillna(0.0).rolling(window_days, min_periods=window_days).sum()
    s2 = sub["s2"].fillna(0.0).rolling(window_days, min_periods=window_days).sum()
    n = sub["n"].fillna(0.0).rolling(window_days, min_periods=window_days).sum()
    var = (s2 / n) - (s1 / n) ** 2
    rv = var.clip(lower=0.0).pow(0.5) * math.sqrt(365 * 1440) * 100
    incomplete = sub["n"].fillna(0.0) < MIN_BARS
    rv[incomplete] = float("nan")
    return rv.ffill()


def dvol_daily(symbol: str) -> pd.Series:
    """Last hourly DVOL close with published_at <= day 23:59 UTC (F26 as-of)."""
    obs = load_external_observations(
        DVOL_DS[symbol], start=WARMUP_START, end=SPEC_END, backend="postgres", dsn=DSN
    )
    if "quality_status" in obs:
        obs = obs[obs["quality_status"] != "suspect"]
    pub = pd.to_datetime(obs["published_at"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    frame = pd.DataFrame({"pub": pub, "v": obs["value_num"].astype(float)}).sort_values("pub")
    # hourly buckets publish at exact hours; a row published 00:00 of day X+1
    # (the 23-24h bucket of X) normalizes to X+1 and is only usable there —
    # so "last value with published_at <= day close" == groupby(normalized day).last()
    return frame.groupby(frame["pub"].dt.normalize())["v"].last()


def feasibility(dvols: dict[str, pd.Series], parts: pd.DataFrame) -> dict:
    out = {}
    for sym in MAJORS:
        s = dvols[sym].loc[SPEC_START:]
        deltas = s.diff().dropna()
        zero_ratio = float((deltas == 0).mean())
        cover = parts[(parts["inst_id"] == sym) & (parts["day"] >= SPEC_START)]
        out[sym] = {
            "dvol_days": int(s.size),
            "dvol_first": s.index.min().date().isoformat(),
            "dvol_last": s.index.max().date().isoformat(),
            "dvol_zero_delta_ratio": zero_ratio,
            "zero_delta_flag_gt_5pct": bool(zero_ratio > 0.05),
            "candle_days": int(cover.shape[0]),
            "candle_complete_days": int((cover["n"] >= MIN_BARS).sum()),
        }
    out["status"] = (
        "FAIL_frozen_feed"
        if any(out[s]["zero_delta_flag_gt_5pct"] for s in MAJORS)
        else "PASS"
    )
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    async def go():
        conn = await asyncpg.connect(DSN, timeout=15)
        try:
            return await _fetch_rv_parts(conn)
        finally:
            await conn.close()

    parts = asyncio.run(go())
    dvols = {sym: dvol_daily(sym) for sym in MAJORS}

    feas = feasibility(dvols, parts)
    with (OUT / "stage2_feasibility.json").open("w", encoding="utf-8") as fh:
        json.dump({"experiment_id": "E-038", "hypothesis_id": "H-013",
                   "family_id": "F-VRP-TIMING", "spec_window": [SPEC_START, SPEC_END],
                   "probe": feas,
                   "generated_at": datetime.now(timezone.utc).isoformat()}, fh, indent=2)
    print("E-038 feasibility:", feas["status"])
    if feas["status"] != "PASS":
        raise SystemExit(2)

    # prices/funding for the majors (reuse taxonomy003 loader, widened window)
    t3.START, t3.END = WARMUP_START, SPEC_END
    close, _dvolq, funding = t3.load_daily()
    close = close[MAJORS]

    combos: dict[str, pd.Series] = {}
    for w in GRID_W:
        rvs = {sym: realized_vol(parts, sym, w) for sym in MAJORS}
        for z_min in GRID_Z:
            sig = pd.DataFrame(index=close.index)
            for sym in MAJORS:
                dv = dvols[sym].reindex(close.index)
                rv = rvs[sym].reindex(close.index)
                vrp = dv - rv
                z = t3.zscore(vrp, Z_WINDOW)
                raw = (z >= z_min).astype(float).where(z.notna())
                # a day with no observation carries the previous day's position (1 day max)
                sig[sym] = raw.ffill(limit=1).fillna(0.0)
            ret = t3.book_returns(sig, close, funding).loc[SPEC_START:]
            combos[combo_key({"W": w, "z_min": z_min})] = ret

    starts = [s.dropna().index.min() for s in combos.values()]
    common_start = max(starts)
    combos = {k: v.loc[common_start:].fillna(0.0) for k, v in combos.items()}

    validation = refit_validation(combos, n_trials=4)
    default_key = sorted(combos)[0]
    candidate_signal = {ts.date().isoformat(): float(v) for ts, v in combos[default_key].items()}
    refs = {
        fam: json.load(open(path, encoding="utf-8"))["signal"]
        for fam, path in t3.REF_CANDIDATES.items()
    }
    minting = decide_family_minting(
        candidate_signal, refs, "NEW",
        "VRP timing: long perps when implied-minus-realized vol spread z is high",
        "docs/EXPERIMENT_REGISTRY.md",
        batch_id="h013_vrp_timing_20260714", candidate_id="f-vrp-timing",
    )
    gate = (
        validation.get("dsr") is not None and validation.get("psr") is not None
        and validation["dsr"] >= 0.95 and validation["psr"] >= 0.95
    )
    summary = {
        "schema_version": 1,
        "experiment_id": "E-050",
        "hypothesis_id": "H-013",
        "family_id": "F-VRP-TIMING",
        "window": [str(common_start.date()), str(close.index.max().date())],
        "n_trials": 4,
        "n_trials_provenance": "caller_declared",
        "grid_combos": sorted(combos),
        "default_combo_for_minting": default_key,
        "nonzero_grid_activity": bool(any(s.abs().sum() > 0 for s in combos.values())),
        "leak_shift_path_live": t3.leak_check(combos),
        "idealized_fill": False,
        "costs": {"fee_bps": t3.FEE_BPS, "slippage_bps": t3.SLIP_BPS, "funding_cashflow": True},
        "vol_target": {"annual": t3.VOL_TARGET, "window_days": t3.VOL_WINDOW, "lev_cap": t3.LEV_CAP},
        "validation": validation,
        "family_minting": minting,
        "statistical_gate_passed": bool(gate),
        "promotion_gate_passed": False,
        "portable_validation_gate": False,
        "portable_block_reason": "research-grade Claude runner; adapter-required/absent",
        "runner": "research/probes/h013_vrp_stage3.py",
    }
    with (OUT / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    pd.DataFrame(combos).to_csv(OUT / "combo_daily_returns.csv")
    v = validation
    print(
        f"H-013: WF {v.get('wf_oos_sharpe')} CPCV {v.get('cpcv_oos_sharpe')} "
        f"DSR {v.get('dsr')} PSR {v.get('psr')} gate={'PASS' if gate else 'FAIL'} "
        f"minting={minting['decision']} corr={minting['max_abs_corr']:.3f}"
    )


if __name__ == "__main__":
    main()
