"""H-014 / F-VOL-REGIME-OPT Stage-3 backtest (E-051).

Implements the user-signed-off spec
docs/superpowers/specs/2026-07-14-f-vol-regime-opt-stage3-spec.md under
ADR-0010 accounting (DOMAIN_RULES R8, invariant I39):

RICH regime (per pre-registered combo {ivp_min in [75,85], z_min in [0.5,1.0]})
opens a 1/30-unit tranche per symbol at t+1: short ~25d call (covered),
short 25d put + long 10d put (spread). Coin-denominated overlay daily PnL;
real trade-tape entry/marks with BS-DVOL-offset fallback (counted); official
delivery settlement; published Deribit fees. Fold-refit WF/CPCV, n_trials=4.

Usage: python research/probes/h014_stage3_backtest.py
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from f_vol_regime_opt_probe import bs  # noqa: E402  (E-039 formulas, no drift)
from backtesting.pipeline_family_minting import decide_family_minting  # noqa: E402
from backtesting.pipeline_refit import combo_key, refit_validation  # noqa: E402

DATA = Path("results/h014_stage3_data_20260714")
SERIES = Path("results/stage1_probe_20260713_f_vol_regime_opt")
OUT = Path("results/h014_stage3_20260714")
REF_CANDIDATES = {
    "F-FUNDING-XS-DISPERSION": "results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/family_minting_candidate.json",
    "F-OI-POSITIONING": "results/idea_batch_20260701_taxonomy_002/f_oi_positioning/family_minting_candidate.json",
}
GRID_IVP = (75.0, 85.0)
GRID_Z = (0.5, 1.0)
TRANCHE = 1.0 / 30.0
UNIT_CAP = 1.0
FALLBACK_UNRELIABLE = 0.30
SHORT_LEGS = {"call_25d", "put_25d"}


# ------------------------- accounting primitives (R8; golden-tested via I39)
def trade_fee(premium_coin: float) -> float:
    return min(0.0003, 0.125 * premium_coin)


def settlement_fee(payoff_coin: float) -> float:
    return min(0.00015, 0.125 * payoff_coin) if payoff_coin > 0 else 0.0


def settle(kind: str, s_t: float, k: float) -> float:
    if kind == "call":
        return max(s_t - k, 0.0) / s_t
    return max(k - s_t, 0.0) / s_t


def bs_coin(s: float, k: float, sigma_pct: float, t_years: float, kind: str) -> float:
    return bs(s, k, max(sigma_pct, 1e-6) / 100.0, max(t_years, 1e-9),
              "c" if kind == "call" else "p") / s


def short_call_cycle_pnl(entry_premium: float, s_t: float, k: float) -> float:
    """Golden-case helper: full short-call cycle PnL in coin per unit."""
    payoff = settle("call", s_t, k)
    return entry_premium - trade_fee(entry_premium) - payoff - settlement_fee(payoff)


# --------------------------------------------------------------- data layer
def load_series(symbol: str) -> pd.DataFrame:
    df = pd.read_csv(SERIES / f"series_{symbol.lower()}.csv", parse_dates=["date"])
    return df.set_index("date")


def load_inputs():
    entries = pd.read_csv(DATA / "entries.csv", parse_dates=["signal_day", "entry_day", "expiry"])
    marks = pd.read_csv(DATA / "marks.csv", parse_dates=["date"])
    mark_map = {(r.instrument, r.date.date()): (r.vwap_coin, r.mean_iv)
                for r in marks.itertuples()}
    delivery = pd.read_csv(DATA / "delivery.csv", parse_dates=["date"])
    delivery.columns = ["idx_name", "date", "price"]
    deliv_map = {(r.idx_name, r.date.date()): float(r.price)
                 for r in delivery.itertuples()}
    return entries, mark_map, deliv_map


# --------------------------------------------------------------- simulation
def leg_daily_marks(inst_row, mark_map, series, counters) -> dict[date, float]:
    """Daily coin mark per leg from entry day to expiry (exclusive), with
    trade-VWAP primary and BS-DVOL-offset fallback (R8.5)."""
    out: dict[date, float] = {}
    d = inst_row.entry_day.date()
    end = inst_row.expiry.date()
    iv_offset = None
    while d < end:
        key = (inst_row.instrument, d)
        ts = pd.Timestamp(d)
        if key in mark_map:
            vwap, mean_iv = mark_map[key]
            out[d] = vwap
            counters["trade"] += 1
            if mean_iv and ts in series.index:
                iv_offset = mean_iv - float(series.loc[ts, "dvol"])
        elif ts in series.index:
            s = float(series.loc[ts, "px"])
            sigma = float(series.loc[ts, "dvol"]) + (iv_offset or 0.0)
            t_years = (end - d).days / 365.0
            kind = "call" if inst_row.leg == "call_25d" else "put"
            out[d] = bs_coin(s, inst_row.strike, sigma, t_years, kind)
            counters["fallback"] += 1
        else:
            out[d] = out.get(d - timedelta(days=1), 0.0)
            counters["carry"] += 1
        d += timedelta(days=1)
    return out


def run_combo(entries, mark_map, deliv_map, series_by_sym, ivp_min, z_min):
    daily = defaultdict(float)
    counters = {"trade": 0, "fallback": 0, "carry": 0,
                "tranches": 0, "skipped_no_entry_mark": 0, "skipped_cap": 0}
    for sym in ("BTC", "ETH"):
        series = series_by_sym[sym]
        rich = series[(series["ivp"] >= ivp_min) & (series["z"] >= z_min)]
        sym_entries = entries[entries["symbol"] == sym]
        open_until: list[date] = []  # expiry dates of open tranches
        for signal_ts in rich.index:
            group = sym_entries[sym_entries["signal_day"] == signal_ts]
            if len(group) != 3:
                continue
            e_day = group.iloc[0]["entry_day"].date()
            open_until = [x for x in open_until if x > e_day]
            if len(open_until) * TRANCHE >= UNIT_CAP:
                counters["skipped_cap"] += 1
                continue
            legs = []
            ok = True
            for row in group.itertuples():
                key = (row.instrument, e_day)
                if key not in mark_map:
                    ok = False
                    break
                legs.append(row)
            if not ok:
                counters["skipped_no_entry_mark"] += 1
                continue
            counters["tranches"] += 1
            expiry = legs[0].expiry.date()
            open_until.append(expiry)
            for row in legs:
                sign = 1.0 if row.leg in SHORT_LEGS else -1.0  # short: gains when mark falls
                path = leg_daily_marks(row, mark_map, series, counters)
                days = sorted(path)
                entry_mark = mark_map[(row.instrument, e_day)][0]
                path[e_day] = entry_mark
                daily[(sym, e_day)] += -trade_fee(entry_mark) * TRANCHE
                prev = entry_mark
                for d in days:
                    if d <= e_day:
                        continue
                    daily[(sym, d)] += sign * (prev - path[d]) * TRANCHE
                    prev = path[d]
                s_t = deliv_map.get((f"{sym.lower()}_usd", expiry))
                if s_t is None:
                    # fallback: last available daily close at/before expiry
                    px = series.loc[:pd.Timestamp(expiry), "px"]
                    s_t = float(px.iloc[-1])
                    counters["delivery_fallback"] = counters.get("delivery_fallback", 0) + 1
                kind = "call" if row.leg == "call_25d" else "put"
                payoff = settle(kind, s_t, row.strike)
                daily[(sym, expiry)] += (sign * (prev - payoff)
                                         - settlement_fee(payoff)) * TRANCHE
    if not daily:
        return pd.Series(dtype=float), counters
    df = pd.DataFrame(
        [{"sym": k[0], "date": pd.Timestamp(k[1]), "pnl": v} for k, v in daily.items()]
    )
    wide = df.pivot_table(index="date", columns="sym", values="pnl", aggfunc="sum")
    full_idx = pd.date_range(wide.index.min(), wide.index.max(), freq="D")
    wide = wide.reindex(full_idx).fillna(0.0)
    return wide.mean(axis=1), counters


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    entries, mark_map, deliv_map = load_inputs()
    series_by_sym = {s: load_series(s) for s in ("BTC", "ETH")}
    combos, combo_meta = {}, {}
    for ivp_min in GRID_IVP:
        for z_min in GRID_Z:
            ret, counters = run_combo(entries, mark_map, deliv_map,
                                      series_by_sym, ivp_min, z_min)
            key = combo_key({"ivp_min": ivp_min, "z_min": z_min})
            ret.index = pd.to_datetime(ret.index)
            combos[key] = ret
            marks_total = counters["trade"] + counters["fallback"]
            counters["fallback_ratio"] = (
                counters["fallback"] / marks_total if marks_total else None
            )
            counters["unreliable_gt30pct_fallback"] = bool(
                counters["fallback_ratio"] and counters["fallback_ratio"] > FALLBACK_UNRELIABLE
            )
            combo_meta[key] = counters
            print(key, "tranches:", counters["tranches"],
                  "fallback_ratio:", round(counters["fallback_ratio"] or 0, 4))

    starts = [s.index.min() for s in combos.values() if len(s)]
    common_start = max(starts)
    ends = [s.index.max() for s in combos.values() if len(s)]
    common_end = min(ends)
    idx = pd.date_range(common_start, common_end, freq="D")
    combos = {k: v.reindex(idx).fillna(0.0) for k, v in combos.items()}

    validation = refit_validation(combos, n_trials=4)
    default_key = sorted(combos)[0]
    candidate_signal = {ts.date().isoformat(): float(v) for ts, v in combos[default_key].items()}
    refs = {fam: json.load(open(p, encoding="utf-8"))["signal"]
            for fam, p in REF_CANDIDATES.items()}
    minting = decide_family_minting(
        candidate_signal, refs, "NEW",
        "sell covered call + put spread in RICH vol regime (coin-denominated premium harvest)",
        "docs/EXPERIMENT_REGISTRY.md",
        batch_id="h014_stage3_20260714", candidate_id="f-vol-regime-opt",
    )
    gate = (validation.get("dsr") is not None and validation.get("psr") is not None
            and validation["dsr"] >= 0.95 and validation["psr"] >= 0.95)
    summary = {
        "schema_version": 1,
        "experiment_id": "E-051",
        "hypothesis_id": "H-014",
        "family_id": "F-VOL-REGIME-OPT",
        "window": [str(common_start.date()), str(common_end.date())],
        "n_trials": 4,
        "n_trials_provenance": "caller_declared",
        "grid_combos": sorted(combos),
        "default_combo_for_minting": default_key,
        "combo_meta": combo_meta,
        "nonzero_grid_activity": bool(any(s.abs().sum() > 0 for s in combos.values())),
        "accounting": "ADR-0010 / DOMAIN_RULES R8 (coin unit, official delivery, Deribit fees, trade-VWAP marks with counted BS fallback)",
        "long_leg": "OFF per spec; naked short puts prohibited (R8.3)",
        "idealized_fill": False,
        "validation": validation,
        "family_minting": minting,
        "statistical_gate_passed": bool(gate),
        "promotion_gate_passed": False,
        "portable_validation_gate": False,
        "portable_block_reason": "research-grade Claude runner; adapter-required/absent",
        "runner": "research/probes/h014_stage3_backtest.py",
    }
    with (OUT / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    pd.DataFrame(combos).to_csv(OUT / "combo_daily_returns.csv")
    v = validation
    print(f"H-014 E-051: WF {v.get('wf_oos_sharpe')} CPCV {v.get('cpcv_oos_sharpe')} "
          f"DSR {v.get('dsr')} PSR {v.get('psr')} gate={'PASS' if gate else 'FAIL'} "
          f"minting={minting['decision']} corr={minting['max_abs_corr']:.3f}")


if __name__ == "__main__":
    main()
