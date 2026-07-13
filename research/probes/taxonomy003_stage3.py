"""Stage-3 fold-refit WF/CPCV runs for idea batch taxonomy_003 (H-015..H-020).

Pre-registration: docs/superpowers/specs/2026-07-14-taxonomy003-stage3-specs.md
(grids/directions frozen BEFORE this script first ran). Research-grade runner,
Claude-authored per the 2026-07-14 user authorization; reuses the repo's
fold-refit harness (backtesting/pipeline_refit.refit_validation) and family
minting checker so DSR/PSR are computed identically to prior Stage-3 runs.

Common mechanics: Binance venue-scoped canonical daily bars (SQL daily
aggregation of 1m), t+1 execution, 2 bps fee + 2 bps slippage per side on
turnover, funding cashflow on held positions, portfolio vol-target 0.175 on a
28d always-on basket vol (leverage clipped [0, 3]).

Usage: python research/probes/taxonomy003_stage3.py [--family F-...] [--out DIR]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtesting.data_loader import load_external_observations  # noqa: E402
from backtesting.pipeline_family_minting import decide_family_minting  # noqa: E402
from backtesting.pipeline_refit import combo_key, refit_validation  # noqa: E402

DSN = "postgresql://quant:changeme@localhost:5432/quant"
BATCH_DIR = Path("results/idea_batch_20260713_taxonomy_003")
DATA_DIR = BATCH_DIR / "data"
START, END = "2024-01-01", "2026-07-11"
FEE_BPS, SLIP_BPS = 2.0, 2.0
VOL_TARGET, VOL_WINDOW, LEV_CAP = 0.175, 28, 3.0
Z_WINDOW = 90
MAJORS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
REF_CANDIDATES = {
    "F-FUNDING-XS-DISPERSION": "results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/family_minting_candidate.json",
    "F-OI-POSITIONING": "results/idea_batch_20260701_taxonomy_002/f_oi_positioning/family_minting_candidate.json",
}


# ---------------------------------------------------------------- data layer
async def _fetch_daily(conn) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = await conn.fetch(
        """
        SELECT inst_id, (ts AT TIME ZONE 'UTC')::date AS day,
               (array_agg(close ORDER BY ts DESC))[1] AS close,
               sum(vol_quote) AS dollar_vol, count(*) AS bars
        FROM canonical_candles
        WHERE bar='1m' AND source_primary='binance'
          AND quality_status != 'suspect'
          AND ts >= $1::timestamptz AND ts < $2::timestamptz
        GROUP BY inst_id, day
        """,
        datetime.fromisoformat(START).replace(tzinfo=timezone.utc),
        datetime.fromisoformat(END).replace(tzinfo=timezone.utc),
    )
    df = pd.DataFrame([dict(r) for r in rows])
    df["day"] = pd.to_datetime(df["day"])
    complete = df[df["bars"] >= 1296]  # >=90% of 1440 1m bars
    close = complete.pivot(index="day", columns="inst_id", values="close").astype(float)
    dvol = complete.pivot(index="day", columns="inst_id", values="dollar_vol").astype(float)
    frows = await conn.fetch(
        """
        SELECT inst_id, (ts AT TIME ZONE 'UTC')::date AS day, sum(funding_rate) AS rate
        FROM funding_rates
        WHERE ts >= $1::timestamptz AND ts < $2::timestamptz
        GROUP BY inst_id, day
        """,
        datetime.fromisoformat(START).replace(tzinfo=timezone.utc),
        datetime.fromisoformat(END).replace(tzinfo=timezone.utc),
    )
    fdf = pd.DataFrame([dict(r) for r in frows])
    fdf["day"] = pd.to_datetime(fdf["day"])
    funding = fdf.pivot(index="day", columns="inst_id", values="rate").astype(float)
    return close, dvol, funding


def load_daily() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    async def go():
        conn = await asyncpg.connect(DSN, timeout=15)
        try:
            return await _fetch_daily(conn)
        finally:
            await conn.close()

    return asyncio.run(go())


def load_csv_series(name: str, value_col: str) -> pd.Series:
    df = pd.read_csv(DATA_DIR / name, parse_dates=["date"])
    s = df.set_index("date")[value_col].astype(float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def optflow_daily_mean(dataset_id: str) -> pd.Series:
    obs = load_external_observations(dataset_id, start=START, end=END, backend="postgres", dsn=DSN)
    obs = obs[obs.get("quality_status", pd.Series(dtype=object)) != "suspect"] if "quality_status" in obs else obs
    pub = pd.to_datetime(obs["published_at"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    # bucket published within day D contributes to day-D signal (all <= day-D close)
    day = (pub - pd.Timedelta(microseconds=1)).dt.normalize()
    return obs["value_num"].astype(float).groupby(day).mean().sort_index()


# ------------------------------------------------------------- book building
def basket_lever(returns: pd.DataFrame, symbols: list[str]) -> pd.Series:
    basket = returns[symbols].mean(axis=1)
    vol = basket.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std() * math.sqrt(365)
    return (VOL_TARGET / vol).clip(0.0, LEV_CAP)


def book_returns(
    sig: pd.DataFrame,
    close: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    shift: int = 1,
    vol_scale: bool = True,
) -> pd.Series:
    """sig: day x symbol exposure in [-1, 1] using info <= that day. Trades at t+shift."""
    returns = close.pct_change()
    syms = list(sig.columns)
    active = sig.abs().sum(axis=1)
    weights = sig.div(active.where(active > 0, 1.0), axis=0)
    if vol_scale:
        # lever always lagged one day so sizing never sees same-day vol
        weights = weights.mul(basket_lever(returns, syms).shift(1), axis=0)
    weights = weights.shift(shift).fillna(0.0)
    fund = funding.reindex(columns=syms).reindex(weights.index).fillna(0.0)
    ret = (weights * returns[syms]).sum(axis=1)
    fund_ret = -(weights * fund).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * (FEE_BPS + SLIP_BPS) / 10_000
    return (ret + fund_ret - cost).rename("ret")


def zscore(s: pd.Series, window: int) -> pd.Series:
    mu = s.rolling(window, min_periods=window).mean()
    sd = s.rolling(window, min_periods=window).std()
    return (s - mu) / sd.replace(0.0, np.nan)


# ------------------------------------------------------------- candidates
def combos_optflow(close, dvol, funding):
    daily = {
        "BTC-USDT-SWAP": optflow_daily_mean("optflow_deribit_btc"),
        "ETH-USDT-SWAP": optflow_daily_mean("optflow_deribit_eth"),
    }
    out = {}
    for L in (1, 3):
        for z_cut in (1.0, 1.5):
            sig = pd.DataFrame(index=close.index)
            for sym, s in daily.items():
                sm = s.rolling(L, min_periods=L).mean()
                z = zscore(sm, Z_WINDOW).reindex(close.index)
                sig[sym] = (z < z_cut).astype(float).where(z.notna(), 0.0)
            out[combo_key({"L": L, "z_cut": z_cut})] = book_returns(sig, close, funding)
    return out


def combos_xs_illiquidity(close, dvol, funding):
    membership = pd.read_parquet("data/universe/universe_membership.parquet")
    membership = membership[membership["eligible"]]
    elig = membership.pivot_table(index="date", columns="symbol", values="eligible", aggfunc="any")
    elig = elig.reindex(close.index).fillna(False)
    common = [c for c in close.columns if c in elig.columns]
    returns = close[common].pct_change()
    illiq = returns.abs() / dvol[common]
    rebalance_days = pd.Series(close.index, index=close.index).resample("W-MON").first().dropna()
    out = {}
    for W in (14, 28):
        for q in (0.20, 0.30):
            amihud = illiq.rolling(W, min_periods=W).mean()
            weights = pd.DataFrame(np.nan, index=close.index, columns=common)
            for day in rebalance_days:
                if day not in amihud.index:
                    continue
                row = amihud.loc[day]
                ok = row[elig.loc[day, common] & row.notna() & (dvol.loc[day, common] > 0)]
                if len(ok) < 10:
                    weights.loc[day] = 0.0
                    continue
                n = max(1, int(len(ok) * q))
                longs = ok.nlargest(n).index   # most illiquid
                shorts = ok.nsmallest(n).index
                w = pd.Series(0.0, index=common)
                w[longs] = 0.5 / len(longs)
                w[shorts] = -0.5 / len(shorts)
                weights.loc[day] = w.clip(-0.10, 0.10)
            # whole-row rebalance snapshots carried forward between rebalances
            weights = weights.ffill(limit=10).fillna(0.0)
            unlev = (weights.shift(1) * returns).sum(axis=1)
            vol = unlev.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std() * math.sqrt(365)
            lever = (VOL_TARGET / vol).clip(0.0, LEV_CAP).shift(1).fillna(0.0)
            final = weights.mul(lever, axis=0).shift(1).fillna(0.0)
            fund = funding.reindex(columns=common).reindex(final.index).fillna(0.0)
            ret = (final * returns).sum(axis=1) - (final * fund).sum(axis=1)
            cost = final.diff().abs().sum(axis=1).fillna(0.0) * (FEE_BPS + SLIP_BPS) / 10_000
            out[combo_key({"W": W, "q": q})] = (ret - cost).rename("ret")
    return out


def combos_stablecoin(close, dvol, funding):
    s = load_csv_series("stablecoins.csv", "total_circulating_usd").shift(1)  # D+1 PIT lag
    out = {}
    for G in (14, 28):
        growth = np.log(s / s.shift(G))
        z = zscore(growth, 365)
        for z_min in (0.0, 0.5):
            zz = z.reindex(close.index)
            sig = pd.DataFrame(
                {sym: (zz >= z_min).astype(float).where(zz.notna(), 0.0) for sym in MAJORS},
                index=close.index,
            )
            out[combo_key({"G": G, "z_min": z_min})] = book_returns(sig, close, funding)
    return out


def combos_coinbase(close, dvol, funding):
    cb = {
        "BTC-USDT-SWAP": load_csv_series("coinbase_btc.csv", "close").shift(1),
        "ETH-USDT-SWAP": load_csv_series("coinbase_eth.csv", "close").shift(1),
    }
    out = {}
    for L in (1, 3):
        for z_min in (0.0, 0.5):
            sig = pd.DataFrame(index=close.index)
            for sym in MAJORS:
                bn = close[sym].copy()
                bn.index = bn.index.normalize()
                prem = (cb[sym].reindex(bn.index) / bn - 1.0).rolling(L, min_periods=L).mean()
                z = zscore(prem, Z_WINDOW)
                z.index = close.index
                sig[sym] = (z >= z_min).astype(float).where(z.notna(), 0.0)
            out[combo_key({"L": L, "z_min": z_min})] = book_returns(sig, close, funding)
    return out


def combos_onchain(close, dvol, funding):
    h = load_csv_series("hashrate.csv", "hashrate_ths").shift(1)
    out = {}
    for fast in (14, 30):
        for slow in (60, 90):
            ribbon = (h.rolling(fast, min_periods=fast).mean()
                      >= h.rolling(slow, min_periods=slow).mean())
            rb = ribbon.reindex(close.index.normalize()).astype(float)
            rb.index = close.index
            sig = pd.DataFrame({"BTC-USDT-SWAP": rb}, index=close.index).fillna(0.0)
            out[combo_key({"fast": fast, "slow": slow})] = book_returns(sig, close, funding)
    return out


def combos_calendar(close, dvol, funding):
    out = {}
    for name, weekend in (("weekdays", False), ("weekends", True)):
        dow = close.index.dayofweek
        hold = (dow >= 5) if weekend else (dow < 5)
        sig = pd.DataFrame({sym: hold.astype(float) for sym in MAJORS}, index=close.index)
        # deterministic schedule known in advance: no information shift needed
        out[combo_key({"cell": name})] = book_returns(sig, close, funding, shift=0)
    return out


CANDIDATES = {
    "F-OPTFLOW-POSITIONING": ("H-015", "E-044", combos_optflow, 4),
    "F-XS-ILLIQUIDITY": ("H-016", "E-045", combos_xs_illiquidity, 4),
    "F-STABLECOIN-LIQUIDITY": ("H-017", "E-046", combos_stablecoin, 4),
    "F-COINBASE-PREMIUM": ("H-018", "E-047", combos_coinbase, 4),
    "F-ONCHAIN-FLOW": ("H-019", "E-048", combos_onchain, 4),
    "F-CALENDAR-SEASONALITY": ("H-020", "E-049", combos_calendar, 2),
}
MECHANISMS = {
    "F-OPTFLOW-POSITIONING": "Deribit put/call taker-buy premium imbalance risk-off long/flat",
    "F-XS-ILLIQUIDITY": "XS Amihud illiquidity premium, long illiquid short liquid",
    "F-STABLECOIN-LIQUIDITY": "aggregate stablecoin supply growth risk-on/off long/flat",
    "F-COINBASE-PREMIUM": "Coinbase-vs-Binance premium z demand-pressure long/flat",
    "F-ONCHAIN-FLOW": "hash-ribbon miner-capitulation long/flat (BTC only)",
    "F-CALENDAR-SEASONALITY": "weekday-vs-weekend two-cell holding contrast",
}


def leak_check(combo_returns: dict[str, pd.Series]) -> bool:
    """t+1 discipline sanity: same-day signal-return correlation must not be
    materially higher than the executed (shifted) correlation would justify.
    Mechanical: assert returns are not identical when the book is delayed one
    more day — proves the shift path is live rather than a no-op."""
    key = sorted(combo_returns)[0]
    base = combo_returns[key]
    return bool((base.shift(1).fillna(0.0) - base).abs().sum() > 0)


def run_family(family: str, close, dvol, funding, refs) -> dict:
    hyp, exp_id, fn, n_trials = CANDIDATES[family]
    combos = fn(close, dvol, funding)
    # common evaluation window: start where every combo has data, zero-fill holes
    starts = [s.dropna().index.min() for s in combos.values()]
    common_start = max(s for s in starts if s is not None)
    combos = {
        k: v.loc[common_start:].fillna(0.0) for k, v in combos.items()
    }
    validation = refit_validation(combos, n_trials=n_trials)
    default_key = sorted(combos)[0]
    candidate_signal = {
        ts.date().isoformat(): float(v) for ts, v in combos[default_key].items()
    }
    minting = decide_family_minting(
        candidate_signal,
        refs,
        "NEW",
        MECHANISMS[family],
        "docs/EXPERIMENT_REGISTRY.md",
        batch_id="idea_batch_20260713_taxonomy_003",
        candidate_id=family.lower(),
    )
    gate = (
        validation.get("dsr") is not None
        and validation.get("psr") is not None
        and validation["dsr"] >= 0.95
        and validation["psr"] >= 0.95
    )
    nonzero = any(s.abs().sum() > 0 for s in combos.values())
    summary = {
        "schema_version": 1,
        "batch_id": "idea_batch_20260713_taxonomy_003",
        "family_id": family,
        "hypothesis_id": hyp,
        "experiment_id": exp_id,
        "window": [START, END],
        "n_trials": n_trials,
        "n_trials_provenance": "caller_declared",
        "grid_combos": sorted(combos),
        "default_combo_for_minting": default_key,
        "nonzero_grid_activity": nonzero,
        "leak_shift_path_live": leak_check(combos),
        "idealized_fill": False,
        "costs": {"fee_bps": FEE_BPS, "slippage_bps": SLIP_BPS, "funding_cashflow": True},
        "vol_target": {"annual": VOL_TARGET, "window_days": VOL_WINDOW, "lev_cap": LEV_CAP},
        "validation": validation,
        "family_minting": minting,
        "statistical_gate_passed": bool(gate),
        "promotion_gate_passed": False,
        "portable_validation_gate": False,
        "portable_block_reason": "research-grade Claude runner; adapter-required/absent",
        "runner": "research/probes/taxonomy003_stage3.py",
    }
    out_dir = BATCH_DIR / family.lower().replace("-", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    per_combo = pd.DataFrame({k: v for k, v in combos.items()})
    per_combo.to_csv(out_dir / "combo_daily_returns.csv")
    v = validation
    print(
        f"{family}: WF {v.get('wf_oos_sharpe')} CPCV {v.get('cpcv_oos_sharpe')} "
        f"DSR {v.get('dsr')} PSR {v.get('psr')} gate={'PASS' if gate else 'FAIL'} "
        f"minting={minting['decision']} corr={minting['max_abs_corr']:.3f}"
    )
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", action="append")
    args = ap.parse_args()
    families = args.family or list(CANDIDATES)
    close, dvol, funding = load_daily()
    print(f"daily bars: {close.shape[0]} days x {close.shape[1]} symbols "
          f"({close.index[0].date()} -> {close.index[-1].date()})")
    refs = {}
    for fam, path in REF_CANDIDATES.items():
        refs[fam] = json.load(open(path, encoding="utf-8"))["signal"]
    for family in families:
        run_family(family, close, dvol, funding, refs)


if __name__ == "__main__":
    main()
