from __future__ import annotations

import argparse
import asyncio
import fnmatch
import sys
from math import ceil
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DEFAULT_MIN_BAR_COUNT = 1000


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


def daily_dollar_volume_rows_to_candles(
    rows: Sequence[Mapping[str, Any]], *, min_bar_count: int = DEFAULT_MIN_BAR_COUNT
) -> dict[str, pd.DataFrame]:
    """Convert per-(inst_id, day) DB aggregates into build_membership()'s input shape.

    Each row needs inst_id, day (date-like), dollar_volume, bar_count. Days with
    bar_count < min_bar_count are dropped (guards partial-coverage days from
    masquerading as a full active day). One synthetic bar/day is emitted with
    close=1.0 so _daily_dollar_volume()'s close*vol resample reproduces the
    aggregate exactly; build_membership() itself is not touched.
    """
    by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if int(row["bar_count"]) < min_bar_count:
            continue
        by_symbol.setdefault(str(row["inst_id"]), []).append(row)

    candles: dict[str, pd.DataFrame] = {}
    for symbol, day_rows in by_symbol.items():
        frame = pd.DataFrame(day_rows)
        candles[symbol] = pd.DataFrame(
            {
                "ts": pd.to_datetime(frame["day"], utc=True),
                "close": 1.0,
                "vol": pd.to_numeric(frame["dollar_volume"]).to_numpy(),
            }
        )
    return candles


async def fetch_daily_dollar_volume_rows(
    dsn: str,
    *,
    bar: str,
    source_primary: str,
    inst_id_pattern: str,
) -> list[dict[str, Any]]:
    import asyncpg

    conn = await asyncpg.connect(dsn=dsn, timeout=30)
    try:
        records = await conn.fetch(
            """
            SELECT inst_id,
                   date_trunc('day', ts) AS day,
                   sum(vol_quote) AS dollar_volume,
                   count(*) AS bar_count
            FROM canonical_candles
            WHERE bar = $1
              AND source_primary = $2
              AND inst_id LIKE $3
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            bar,
            source_primary,
            inst_id_pattern,
        )
    finally:
        await conn.close()
    return [dict(record) for record in records]


def load_candles_from_db(
    dsn: str,
    *,
    bar: str = "1m",
    source_primary: str = "binance",
    inst_id_pattern: str = "%-USDT-SWAP",
    min_bar_count: int = DEFAULT_MIN_BAR_COUNT,
    fetch_rows: Callable[..., Awaitable[list[dict[str, Any]]]] | None = None,
) -> dict[str, pd.DataFrame]:
    fetcher = fetch_rows or fetch_daily_dollar_volume_rows
    rows = asyncio.run(
        fetcher(dsn, bar=bar, source_primary=source_primary, inst_id_pattern=inst_id_pattern)
    )
    return daily_dollar_volume_rows_to_candles(rows, min_bar_count=min_bar_count)


def _eligible_per_day_stats(membership: pd.DataFrame) -> dict[str, float]:
    if membership.empty:
        return {"min": 0, "median": 0.0, "max": 0}
    eligible = membership[membership["eligible"]]
    if eligible.empty:
        return {"min": 0, "median": 0.0, "max": 0}
    per_day = eligible.groupby("date")["symbol"].nunique()
    return {"min": int(per_day.min()), "median": float(per_day.median()), "max": int(per_day.max())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build point-in-time universe membership.")
    parser.add_argument("--config", default="config/universe.yaml")
    parser.add_argument("--data-dir", default="data/ticks")
    parser.add_argument("--out", default="data/universe/universe_membership.parquet")
    parser.add_argument("--source", choices=["parquet", "db"], default="parquet")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--min-bar-count", type=int, default=DEFAULT_MIN_BAR_COUNT)
    parser.add_argument(
        "--compare-existing",
        action="store_true",
        help="print eligible/day stats for the existing --out file before overwriting it",
    )
    args = parser.parse_args(argv)

    with (PROJECT_ROOT / args.config).open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}

    out = PROJECT_ROOT / args.out
    before_stats = None
    if args.compare_existing and out.exists():
        before_stats = _eligible_per_day_stats(pd.read_parquet(out))

    if args.source == "db":
        dsn = args.dsn
        if not dsn:
            from okx_quant.core.config import load_config

            dsn = load_config(
                settings_path=str(PROJECT_ROOT / "config" / "settings.yaml"), require_secrets=False
            ).storage.timescale_dsn
        if not dsn:
            raise SystemExit("--source db requires --dsn or a configured storage.timescale_dsn")
        quote = str(cfg.get("quote", "USDT"))
        instrument_type = str(cfg.get("instrument_type", "SWAP"))
        candles = load_candles_from_db(
            dsn,
            bar="1m",
            source_primary=str(cfg.get("venue", "binance")),
            inst_id_pattern=f"%-{quote}-{instrument_type}",
            min_bar_count=args.min_bar_count,
        )
    else:
        candles = _load_candles(PROJECT_ROOT / args.data_dir)

    membership = build_membership(candles, cfg)
    membership["source"] = args.source
    out.parent.mkdir(parents=True, exist_ok=True)
    membership.to_parquet(out, index=False)

    after_stats = _eligible_per_day_stats(membership)
    print(f"wrote {len(membership)} rows to {out} (source={args.source})")
    print(f"eligible/day after:  {after_stats}")
    if before_stats is not None:
        print(f"eligible/day before: {before_stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
