from __future__ import annotations

import argparse
import fnmatch
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _warmup_days(cfg: dict[str, Any]) -> int:
    if "warmup_days" in cfg:
        return int(cfg["warmup_days"])
    return int(ceil(float(cfg.get("warmup_bars", 0)) / 1440.0))


def _symbol_from_dir(path: Path) -> str:
    return path.name.replace("_", "-")


def _is_denied(symbol: str, deny_list: list[str]) -> bool:
    base = symbol.split("-")[0]
    return any(base == pattern or fnmatch.fnmatch(base, pattern) for pattern in deny_list)


def _daily_dollar_volume(candles: pd.DataFrame) -> pd.Series:
    frame = candles.copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        if "ts" not in frame.columns:
            raise ValueError("candles must have a DatetimeIndex or ts column")
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["ts"]).set_index("ts")
    if frame.index.tz is not None:
        frame.index = frame.index.tz_convert("UTC").tz_localize(None)
    frame = frame.sort_index()
    dollar_volume = pd.to_numeric(frame["close"], errors="coerce") * pd.to_numeric(
        frame["vol"], errors="coerce"
    )
    return dollar_volume.resample("1D").sum(min_count=1).dropna()


def build_membership(candles_by_symbol: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> pd.DataFrame:
    daily_dv = {
        symbol: _daily_dollar_volume(candles)
        for symbol, candles in candles_by_symbol.items()
        if candles is not None and not candles.empty
    }
    if not daily_dv:
        return pd.DataFrame(columns=["date", "symbol", "eligible", "adv_usd", "listing_ts"])

    start = min(series.index.min() for series in daily_dv.values())
    end = max(series.index.max() for series in daily_dv.values())
    dates = pd.date_range(start.normalize(), end.normalize(), freq="D")
    warmup = _warmup_days(cfg)
    adv_window = int(cfg.get("adv_window_days", 30))
    min_adv = float(cfg.get("min_adv_usd", 0.0))
    top_n = int(cfg.get("top_n", len(daily_dv)))
    deny_list = list(cfg.get("deny_list", []))

    rows: list[pd.DataFrame] = []
    for symbol, dollar_volume in daily_dv.items():
        dv = dollar_volume.reindex(dates)
        active = dv.notna()
        adv = dv.shift(1).rolling(adv_window, min_periods=1).median()
        history = active.shift(1, fill_value=False).rolling(warmup, min_periods=warmup).sum()
        eligible = active & (history >= warmup) & (adv >= min_adv)
        if _is_denied(symbol, deny_list):
            eligible = eligible & False
        rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "symbol": symbol,
                    "eligible": eligible.fillna(False).astype(bool).to_numpy(),
                    "adv_usd": adv.to_numpy(),
                    "listing_ts": dollar_volume.index.min(),
                }
            )
        )

    membership = pd.concat(rows, ignore_index=True)
    eligible = membership[membership["eligible"]].copy()
    membership["eligible"] = False
    if not eligible.empty:
        keep = eligible.sort_values(["date", "adv_usd"], ascending=[True, False])
        keep = keep[keep.groupby("date").cumcount() < top_n]
        membership.loc[keep.index, "eligible"] = True
    return membership.sort_values(["date", "symbol"]).reset_index(drop=True)


def _load_candles(data_dir: Path) -> dict[str, pd.DataFrame]:
    candles: dict[str, pd.DataFrame] = {}
    for path in sorted(data_dir.glob("*/candles_1m.parquet")):
        candles[_symbol_from_dir(path.parent)] = pd.read_parquet(path)
    return candles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build point-in-time universe membership.")
    parser.add_argument("--config", default="config/universe.yaml")
    parser.add_argument("--data-dir", default="data/ticks")
    parser.add_argument("--out", default="data/universe/universe_membership.parquet")
    args = parser.parse_args(argv)

    with (PROJECT_ROOT / args.config).open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    membership = build_membership(_load_candles(PROJECT_ROOT / args.data_dir), cfg)
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    membership.to_parquet(out, index=False)
    print(f"wrote {len(membership)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
