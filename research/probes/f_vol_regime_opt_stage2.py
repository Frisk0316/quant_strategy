"""E-041: rerun E-040 calibration with its three authorized review fixes.

The sample is fixed from the E-039 month-first rows: the three lowest and
three highest IVP dates per symbol.  Tardis files are read as a stream and the
chain state is stopped at the global event timestamp nearest 08:00 UTC.

Usage:
  python research/probes/f_vol_regime_opt_stage2.py
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import io
import json
import os
import statistics
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from research.probes.f_vol_regime_opt_probe import bs
except ModuleNotFoundError:  # direct script execution
    from f_vol_regime_opt_probe import bs


STAGE1_DIR = Path("results/stage1_probe_20260713_f_vol_regime_opt")
DEFAULT_OUT = Path("results/stage2_probe_20260713_f_vol_regime_opt_r1")
URL = "https://datasets.tardis.dev/v1/deribit/options_chain/{y}/{m}/{d}/OPTIONS.csv.gz"
TARGET_HOUR = 8
SAMPLE_PER_SYMBOL = 6
VERDICT_THRESHOLD = 0.8
RICH_SHORT_LEGS = ("call_25d", "put_25d")
REQUIRED_COLUMNS = {
    "symbol",
    "timestamp",
    "local_timestamp",
    "type",
    "strike_price",
    "expiration",
    "bid_price",
    "ask_price",
    "underlying_price",
    "delta",
}
CSV_FIELDS = [
    "date",
    "symbol",
    "selection_bucket",
    "selection_rank",
    "ivp_quartile",
    "regime",
    "ivp",
    "selection_daily_dvol",
    "dvol",
    "dvol_dataset_id",
    "dvol_observed_at",
    "dvol_published_at",
    "snapshot_timestamp",
    "quote_timestamp",
    "quote_local_timestamp",
    "expiry",
    "days_to_expiry",
    "leg",
    "instrument",
    "strike",
    "actual_delta",
    "bid",
    "ask",
    "mid",
    "spread",
    "spread_pct_mid",
    "underlying_price",
    "synthetic_bs_on_dvol",
    "real_to_synthetic_ratio",
]


class SizeLimitError(RuntimeError):
    pass


class LimitedReader:
    def __init__(self, raw, limit: int):
        self.raw = raw
        self.limit = limit
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        data = self.raw.read(size)
        self.bytes_read += len(data)
        if self.bytes_read > self.limit:
            raise SizeLimitError(
                f"compressed stream exceeded {self.limit} bytes "
                f"(read {self.bytes_read})"
            )
        return data


def _iso_us(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def load_samples(path: Path, symbol: str) -> tuple[list[dict], dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        candidates = [
            row
            for row in csv.DictReader(handle)
            if row["date"].endswith("-01") and row.get("regime")
        ]
    candidates.sort(key=lambda row: (float(row["ivp"]), row["date"]))
    if len(candidates) < SAMPLE_PER_SYMBOL:
        raise ValueError(f"{symbol}: only {len(candidates)} classified month-first rows")

    for rank, row in enumerate(candidates):
        row["selection_rank"] = rank + 1
        row["ivp_quartile"] = f"Q{min(4, rank * 4 // len(candidates) + 1)}"

    selected = candidates[:3] + candidates[-3:]
    for row in selected[:3]:
        row["selection_bucket"] = "bottom_3_ivp"
    for row in selected[3:]:
        row["selection_bucket"] = "top_3_ivp"
    return selected, {
        "symbol": symbol,
        "candidate_count": len(candidates),
        "rule": "three lowest and three highest IVP classified month-first dates; ties by date",
        "selected": [
            {
                key: row[key]
                for key in (
                    "date",
                    "ivp",
                    "regime",
                    "selection_rank",
                    "ivp_quartile",
                    "selection_bucket",
                )
            }
            for row in selected
        ],
    }


def read_chain_snapshot(rows, target_us: int, currencies: set[str]) -> tuple[dict, int]:
    """Return the as-of chain at the global event time nearest target_us."""
    state: dict[str, dict] = {}
    last_before = None
    previous = None
    iterator = iter(rows)

    def keep(row: dict) -> None:
        symbol = row.get("symbol", "")
        if any(symbol.startswith(f"{currency}-") for currency in currencies):
            state[symbol] = row

    for row in iterator:
        timestamp = int(row["local_timestamp"])
        if previous is not None and timestamp < previous:
            raise ValueError("Tardis local_timestamp is not monotonic")
        previous = timestamp
        if timestamp <= target_us:
            keep(row)
            last_before = timestamp
            continue

        if last_before is not None and target_us - last_before <= timestamp - target_us:
            return state, last_before

        snapshot = timestamp
        keep(row)
        for row in iterator:
            timestamp = int(row["local_timestamp"])
            if timestamp != snapshot:
                break
            keep(row)
        return state, snapshot

    if last_before is None:
        raise ValueError("no chain rows around 08:00 UTC")
    return state, last_before


def download_snapshot(
    date: str,
    currencies: set[str],
    max_bytes: int,
    timeout: int,
) -> tuple[dict, dict]:
    y, m, d = date.split("-")
    url = URL.format(y=y, m=m, d=d)
    target = int(
        datetime.fromisoformat(f"{date}T{TARGET_HOUR:02d}:00:00+00:00").timestamp()
        * 1_000_000
    )
    request = urllib.request.Request(url, headers={"User-Agent": "quant-strategy-e041/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_length = response.headers.get("Content-Length")
        limited = LimitedReader(response, max_bytes)
        with gzip.GzipFile(fileobj=limited) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                reader = csv.DictReader(text)
                missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(f"Tardis schema missing columns: {sorted(missing)}")
                state, snapshot = read_chain_snapshot(reader, target, currencies)
        return state, {
            "date": date,
            "url": url,
            "content_length": int(content_length) if content_length else None,
            "compressed_bytes_read": limited.bytes_read,
            "snapshot_timestamp": _iso_us(snapshot),
            "snapshot_offset_seconds": (snapshot - target) / 1_000_000,
            "contracts_in_state": len(state),
        }


async def load_hourly_dvol(
    dsn: str,
    samples: dict[str, list[dict]],
    connect=None,
) -> list[dict]:
    if connect is None:
        import asyncpg

        connect = asyncpg.connect
    conn = await connect(dsn)
    records = []
    try:
        for symbol, selected in samples.items():
            dataset_id = f"dvol_deribit_{symbol.lower()}_1h"
            for sample in selected:
                snapshot = datetime.fromisoformat(
                    f"{sample['date']}T{TARGET_HOUR:02d}:00:00+00:00"
                )
                row = await conn.fetchrow(
                    """
                    SELECT observed_at, published_at, value_num
                    FROM external_observations
                    WHERE dataset_id = $1
                      AND published_at <= $2
                      AND observed_at <= $2
                      AND value_num IS NOT NULL
                    ORDER BY published_at DESC, observed_at DESC
                    LIMIT 1
                    """,
                    dataset_id,
                    snapshot,
                )
                if row is None:
                    raise ValueError(
                        f"{sample['date']} {symbol}: no hourly DVOL published by 08:00 UTC"
                    )
                dvol = float(row["value_num"])
                if dvol <= 0:
                    raise ValueError(
                        f"{sample['date']} {symbol}: non-positive hourly DVOL {dvol}"
                    )
                sample.update(
                    {
                        "selection_daily_dvol": float(sample["dvol"]),
                        "dvol": dvol,
                        "dvol_dataset_id": dataset_id,
                        "dvol_observed_at": row["observed_at"].isoformat(),
                        "dvol_published_at": row["published_at"].isoformat(),
                    }
                )
                records.append(
                    {
                        "date": sample["date"],
                        "symbol": symbol,
                        "dataset_id": dataset_id,
                        "observed_at": row["observed_at"].isoformat(),
                        "published_at": row["published_at"].isoformat(),
                        "value": dvol,
                    }
                )
    finally:
        await conn.close()
    return records


def database_url() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is required for hourly DVOL; no daily fallback")
    return dsn


def _quote(row: dict) -> dict | None:
    try:
        bid = float(row["bid_price"])
        ask = float(row["ask_price"])
        quote = {
            "row": row,
            "kind": row["type"].strip(),
            "strike": float(row["strike_price"]),
            "expiration_us": int(row["expiration"]),
            "bid": bid,
            "ask": ask,
            "delta": float(row["delta"]),
            "underlying": float(row["underlying_price"]),
        }
    except (KeyError, TypeError, ValueError):
        return None
    if bid <= 0 or ask < bid or quote["underlying"] <= 0:
        return None
    return quote


def extract_legs(state: dict, snapshot_us: int, sample: dict, symbol: str) -> list[dict]:
    quotes = [
        quote
        for row in state.values()
        if row["symbol"].startswith(f"{symbol}-")
        and (quote := _quote(row)) is not None
        and quote["expiration_us"] > snapshot_us
    ]
    if not quotes:
        raise ValueError(f"{sample['date']} {symbol}: no valid two-sided option quotes")

    expiries = sorted({quote["expiration_us"] for quote in quotes})
    target_expiry = snapshot_us + 30 * 86_400 * 1_000_000
    expiry = min(expiries, key=lambda value: (abs(value - target_expiry), value))
    quotes = [quote for quote in quotes if quote["expiration_us"] == expiry]
    calls = [quote for quote in quotes if quote["kind"] == "call"]
    puts = [quote for quote in quotes if quote["kind"] == "put"]
    if not calls or not puts:
        raise ValueError(f"{sample['date']} {symbol}: selected expiry lacks calls or puts")

    call25 = min(calls, key=lambda quote: (abs(quote["delta"] - 0.25), quote["strike"]))
    put25 = min(puts, key=lambda quote: (abs(quote["delta"] + 0.25), quote["strike"]))
    put10 = min(puts, key=lambda quote: (abs(quote["delta"] + 0.10), quote["strike"]))
    common_strikes = {quote["strike"] for quote in calls} & {
        quote["strike"] for quote in puts
    }
    if not common_strikes:
        raise ValueError(f"{sample['date']} {symbol}: no common ATM call/put strike")
    underlying = statistics.median(quote["underlying"] for quote in quotes)
    atm_strike = min(common_strikes, key=lambda strike: (abs(strike - underlying), strike))
    atm_call = min(
        (quote for quote in calls if quote["strike"] == atm_strike),
        key=lambda quote: quote["row"]["symbol"],
    )
    atm_put = min(
        (quote for quote in puts if quote["strike"] == atm_strike),
        key=lambda quote: quote["row"]["symbol"],
    )

    selected = {
        "call_25d": call25,
        "put_25d": put25,
        "put_10d": put10,
        "atm_call": atm_call,
        "atm_put": atm_put,
    }
    sigma = float(sample["dvol"]) / 100
    tenor = (expiry - snapshot_us) / 1_000_000 / (365 * 86_400)
    output = []
    for leg, quote in selected.items():
        mid = (quote["bid"] + quote["ask"]) / 2
        kind = "c" if quote["kind"] == "call" else "p"
        synthetic = bs(
            quote["underlying"], quote["strike"], sigma, tenor, kind
        ) / quote["underlying"]
        if synthetic <= 0:
            raise ValueError(f"{sample['date']} {symbol} {leg}: non-positive BS premium")
        output.append(
            {
                "date": sample["date"],
                "symbol": symbol,
                "selection_bucket": sample["selection_bucket"],
                "selection_rank": sample["selection_rank"],
                "ivp_quartile": sample["ivp_quartile"],
                "regime": sample["regime"],
                "ivp": float(sample["ivp"]),
                "selection_daily_dvol": float(
                    sample.get("selection_daily_dvol", sample["dvol"])
                ),
                "dvol": float(sample["dvol"]),
                "dvol_dataset_id": sample.get("dvol_dataset_id"),
                "dvol_observed_at": sample.get("dvol_observed_at"),
                "dvol_published_at": sample.get("dvol_published_at"),
                "snapshot_timestamp": _iso_us(snapshot_us),
                "quote_timestamp": _iso_us(int(quote["row"]["timestamp"])),
                "quote_local_timestamp": _iso_us(int(quote["row"]["local_timestamp"])),
                "expiry": _iso_us(expiry),
                "days_to_expiry": tenor * 365,
                "leg": leg,
                "instrument": quote["row"]["symbol"],
                "strike": quote["strike"],
                "actual_delta": quote["delta"],
                "bid": quote["bid"],
                "ask": quote["ask"],
                "mid": mid,
                "spread": quote["ask"] - quote["bid"],
                "spread_pct_mid": 100 * (quote["ask"] - quote["bid"]) / mid,
                "underlying_price": quote["underlying"],
                "synthetic_bs_on_dvol": synthetic,
                "real_to_synthetic_ratio": mid / synthetic,
            }
        )
    return output


def _stats(rows: list[dict]) -> dict:
    ratios = [row["real_to_synthetic_ratio"] for row in rows]
    spreads = [row["spread_pct_mid"] for row in rows]
    return {
        "n": len(rows),
        "ratio_mean": statistics.fmean(ratios),
        "ratio_median": statistics.median(ratios),
        "ratio_min": min(ratios),
        "ratio_max": max(ratios),
        "spread_pct_mid_mean": statistics.fmean(spreads),
        "spread_pct_mid_median": statistics.median(spreads),
    }


def aggregate(rows: list[dict]) -> dict:
    def grouped(*keys: str) -> dict:
        groups = defaultdict(list)
        for row in rows:
            groups["/".join(str(row[key]) for key in keys)].append(row)
        return {key: _stats(values) for key, values in sorted(groups.items())}

    return {
        "by_leg": grouped("leg"),
        "by_ivp_quartile": grouped("ivp_quartile"),
        "by_leg_and_ivp_quartile": grouped("leg", "ivp_quartile"),
        "by_symbol_leg_and_ivp_quartile": grouped("symbol", "leg", "ivp_quartile"),
    }


def verdict(rows: list[dict]) -> dict:
    checks = []
    for symbol in ("BTC", "ETH"):
        for leg in RICH_SHORT_LEGS:
            ratios = [
                row["real_to_synthetic_ratio"]
                for row in rows
                if row["symbol"] == symbol
                and row["leg"] == leg
                and row["ivp_quartile"] == "Q4"
            ]
            mean = statistics.fmean(ratios) if ratios else None
            checks.append(
                {
                    "symbol": symbol,
                    "leg": leg,
                    "ivp_quartile": "Q4",
                    "n": len(ratios),
                    "ratio_mean": mean,
                    "passed": mean is not None and mean >= VERDICT_THRESHOLD,
                }
            )
    passed = all(check["passed"] for check in checks)
    return {
        "status": "PASS" if passed else "FAIL",
        "evaluated": True,
        "threshold": VERDICT_THRESHOLD,
        "rule": (
            "PASS iff each BTC/ETH Q4 mean real_mid/synthetic ratio for the "
            "25-delta short call and short put is >= 0.8; the 10-delta put is "
            "a purchased hedge and is excluded from this one-sided threshold"
        ),
        "checks": checks,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage1-dir", type=Path, default=STAGE1_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-daily-download-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    command_argv = [sys.executable, *sys.argv]
    command = subprocess.list2cmdline(command_argv)
    samples = {}
    sampling = []
    for symbol in ("BTC", "ETH"):
        selected, meta = load_samples(args.stage1_dir / f"series_{symbol.lower()}.csv", symbol)
        samples[symbol] = selected
        sampling.append(meta)

    by_date = defaultdict(list)
    for symbol, selected in samples.items():
        for sample in selected:
            by_date[sample["date"]].append((symbol, sample))

    result = {
        "schema_version": 2,
        "experiment_id": "E-041",
        "supersedes_experiment_id": "E-040",
        "hypothesis_id": "H-014",
        "family_id": "F-VOL-REGIME-OPT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "command_argv": command_argv,
        "trials": 0,
        "k_consumed": 0,
        "sampling": sampling,
        "method": {
            "source": "Tardis.dev free first-of-month Deribit options_chain CSV",
            "snapshot": "as-of chain at the global local_timestamp nearest 08:00 UTC",
            "expiry": "listed expiry nearest 30 calendar days",
            "legs": ["call_25d", "put_25d", "put_10d", "atm_call", "atm_put"],
            "synthetic": "E-039 vanilla Black-Scholes r=0, IV=latest hourly DVOL with published_at <= the day's 08:00 UTC snapshot, actual listed strike/tenor, coin premium=USD premium/underlying, haircut=0",
            "max_daily_download_bytes": args.max_daily_download_bytes,
            "download_guard": "compressed bytes read; Content-Length is recorded but not used as a pre-check",
            "behavior_deltas_from_e040": [
                "Content-Length pre-check replaced by the same fixed 2 GiB compressed bytes-read guard",
                "synthetic denominator uses hourly DVOL published as-of 08:00 UTC and fails closed without DB",
                "probe_status is separate from verdict.status, which exists only when evaluated=true",
            ],
        },
        "downloads": [],
    }
    extracted = []
    try:
        result["hourly_dvol"] = asyncio.run(load_hourly_dvol(database_url(), samples))
        for date, day_samples in sorted(by_date.items()):
            currencies = {symbol for symbol, _sample in day_samples}
            state, download = download_snapshot(
                date, currencies, args.max_daily_download_bytes, args.timeout
            )
            result["downloads"].append(download)
            snapshot_us = int(
                datetime.fromisoformat(download["snapshot_timestamp"].replace("Z", "+00:00"))
                .timestamp()
                * 1_000_000
            )
            for symbol, sample in day_samples:
                extracted.extend(extract_legs(state, snapshot_us, sample, symbol))
            print(f"processed {date}: {', '.join(sorted(currencies))}")

        write_csv(args.out / "per_day_legs.csv", extracted)
        result.update(
            {
                "probe_status": "COMPLETE",
                "processed_day_symbol_pairs": len(extracted) // 5,
                "per_day_csv": "per_day_legs.csv",
                "aggregates": aggregate(extracted),
                "verdict": verdict(extracted),
            }
        )
    except Exception as error:
        write_csv(args.out / "per_day_legs.csv", extracted)
        result.update(
            {
                "probe_status": "FAIL_CLOSED",
                "processed_day_symbol_pairs": len(extracted) // 5,
                "per_day_csv": "per_day_legs.csv",
                "aggregates": aggregate(extracted) if extracted else {},
                "verdict": {
                    "evaluated": False,
                    "threshold": VERDICT_THRESHOLD,
                    "reason": "fail_closed_before_complete sample; no substitute data used",
                },
                "error": {"type": type(error).__name__, "message": str(error)},
            }
        )
        with (args.out / "stage2_feasibility.json").open("w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
        print(f"FAIL_CLOSED: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(2) from None

    with (args.out / "stage2_feasibility.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    print(f"written: {args.out / 'stage2_feasibility.json'}")


if __name__ == "__main__":
    main()
