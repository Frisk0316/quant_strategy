"""Read-only local scout for taker-flow, liquidation, and delivery-futures data."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._db_writer import resolve_dsn

START = datetime(2020, 1, 1, tzinfo=timezone.utc)
WIDE_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
CORE_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
TAKER_BASE_JSON_PATH = "raw_payload.raw[9]"
TAKER_QUOTE_JSON_PATH = "raw_payload.raw[10]"

S1_COVERAGE_SQL = """
SELECT
    EXTRACT(YEAR FROM k.ts)::integer AS year,
    mi.normalized_symbol AS native_symbol,
    COUNT(*)::bigint AS row_count,
    COUNT(*) FILTER (WHERE k.raw_payload #>> '{raw,9}' IS NOT NULL)::bigint AS taker_base_rows,
    COUNT(*) FILTER (WHERE k.raw_payload #>> '{raw,10}' IS NOT NULL)::bigint AS taker_quote_rows,
    COUNT(*) FILTER (
        WHERE k.raw_payload #>> '{raw,9}' IS NOT NULL
          AND k.raw_payload #>> '{raw,10}' IS NOT NULL
    )::bigint AS both_taker_rows,
    MIN(k.ts) AS earliest_ts,
    MAX(k.ts) AS latest_ts
FROM market_klines k
JOIN market_instruments mi ON mi.instrument_id = k.instrument_id
WHERE mi.exchange = 'binance'
  AND mi.normalized_symbol = ANY($1::text[])
  AND k.bar = '1m'
  AND k.ts >= $2
  AND k.ts < $3
  AND (k.ts >= $4 OR mi.normalized_symbol = ANY($5::text[]))
GROUP BY EXTRACT(YEAR FROM k.ts), mi.normalized_symbol
ORDER BY year, native_symbol
"""

S1_SAMPLE_SQL = """
WITH requested AS (
    SELECT * FROM unnest($1::text[], $2::integer[]) AS t(native_symbol, sample_year)
)
SELECT
    r.sample_year AS year,
    r.native_symbol,
    s.ts,
    s.taker_buy_base,
    s.taker_buy_quote
FROM requested r
LEFT JOIN LATERAL (
    SELECT
        k.ts,
        k.raw_payload #>> '{raw,9}' AS taker_buy_base,
        k.raw_payload #>> '{raw,10}' AS taker_buy_quote
    FROM market_klines k
    JOIN market_instruments mi ON mi.instrument_id = k.instrument_id
    WHERE mi.exchange = 'binance'
      AND mi.normalized_symbol = r.native_symbol
      AND k.bar = '1m'
      AND k.ts >= make_date(r.sample_year, 1, 1)::timestamptz
      AND k.ts < make_date(r.sample_year + 1, 1, 1)::timestamptz
    ORDER BY k.ts
    LIMIT 1
) s ON TRUE
ORDER BY year, native_symbol
"""

LIQUIDATION_SQL = """
SELECT
    d.dataset_id,
    d.provider,
    COUNT(o.observed_at)::bigint AS row_count,
    MIN(o.observed_at) AS earliest_ts,
    MAX(o.observed_at) AS latest_ts
FROM external_datasets d
LEFT JOIN external_observations o ON o.dataset_id = d.dataset_id
WHERE LOWER(d.provider) = 'binance'
  AND LOWER(d.dataset_id) LIKE '%liquid%'
GROUP BY d.dataset_id, d.provider
ORDER BY d.dataset_id
"""

DELIVERY_INVENTORY_SQL = """
SELECT
    'market_instruments' AS table_name,
    exchange,
    inst_id,
    market_type,
    contract_type
FROM market_instruments
WHERE exchange = 'binance'
  AND (LOWER(contract_type) <> 'perpetual' OR inst_id ~ '_[0-9]{6}$')
UNION ALL
SELECT
    'instruments' AS table_name,
    exchange,
    inst_id,
    NULL::text AS market_type,
    inst_type AS contract_type
FROM instruments
WHERE exchange = 'binance'
  AND (UPPER(inst_type) = 'FUTURES' OR inst_id ~ '_[0-9]{6}$')
ORDER BY table_name, inst_id
"""

FUNDING_BASIS_SQL = """
WITH requested(base, perp, spot) AS (
    VALUES
        ('BTC', 'BTC-USDT-SWAP', 'BTC-USDT'),
        ('ETH', 'ETH-USDT-SWAP', 'ETH-USDT')
),
funding_daily AS (
    SELECT
        split_part(inst_id, '-', 1) AS base,
        (ts AT TIME ZONE 'UTC')::date AS day,
        SUM(funding_rate) * 365.0 AS annualized_funding_proxy
    FROM funding_rates
    WHERE source = 'binance'
      AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
      AND ts >= $1
      AND ts < $2
    GROUP BY split_part(inst_id, '-', 1), (ts AT TIME ZONE 'UTC')::date
),
daily_closes AS (
    SELECT DISTINCT ON (inst_id, (ts AT TIME ZONE 'UTC')::date)
        inst_id,
        (ts AT TIME ZONE 'UTC')::date AS day,
        close
    FROM canonical_candles_by_source
    WHERE source_primary = 'binance'
      AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'BTC-USDT', 'ETH-USDT')
      AND bar = '1m'
      AND ts >= $1
      AND ts < $2
    ORDER BY inst_id, (ts AT TIME ZONE 'UTC')::date, ts DESC
),
basis_daily AS (
    SELECT
        r.base,
        p.day,
        p.close / NULLIF(s.close, 0.0) - 1.0 AS perp_spot_basis
    FROM requested r
    JOIN daily_closes p ON p.inst_id = r.perp
    JOIN daily_closes s ON s.inst_id = r.spot AND s.day = p.day
)
SELECT
    f.base,
    COUNT(*)::bigint AS common_days,
    MIN(f.day) AS earliest_day,
    MAX(f.day) AS latest_day,
    CORR(f.annualized_funding_proxy, b.perp_spot_basis) AS correlation
FROM funding_daily f
JOIN basis_daily b ON b.base = f.base AND b.day = f.day
GROUP BY f.base
ORDER BY f.base
"""


def parse_binance_taker_fields(raw_payload: Mapping[str, Any]) -> tuple[float, float] | None:
    """Return Binance kline taker-buy base/quote fields from raw array slots 9/10."""
    raw = raw_payload.get("raw")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) <= 10:
        return None
    try:
        base, quote = float(raw[9]), float(raw[10])
    except (TypeError, ValueError):
        return None
    return (base, quote) if math.isfinite(base) and math.isfinite(quote) else None


def _native_symbol(symbol: str) -> str:
    base = symbol.upper().removesuffix("-USDT-SWAP")
    return f"{base}USDT"


def _expected_symbols(path: Path) -> dict[int, list[str]]:
    import pandas as pd

    frame = pd.read_parquet(path, columns=["date", "symbol", "eligible"])
    frame = frame.loc[frame["eligible"]].copy()
    frame["year"] = pd.to_datetime(frame["date"]).dt.year
    expected = {year: CORE_SYMBOLS.copy() for year in range(2020, 2024)}
    for year in range(2024, 2027):
        expected[year] = sorted({_native_symbol(value) for value in frame.loc[frame["year"] == year, "symbol"]})
    return expected


def _coverage(records: Sequence[Any], expected: Mapping[int, Sequence[str]]) -> tuple[str, list[dict]]:
    by_key = {(int(row["year"]), str(row["native_symbol"])): dict(row) for row in records}
    years: list[dict] = []
    complete = True
    for year, symbols in sorted(expected.items()):
        rows = [by_key[(year, symbol)] for symbol in symbols if (year, symbol) in by_key]
        observed = {str(row["native_symbol"]) for row in rows}
        partial = sorted(
            str(row["native_symbol"])
            for row in rows
            if int(row["both_taker_rows"]) != int(row["row_count"])
        )
        missing = sorted(set(symbols) - observed)
        total = sum(int(row["row_count"]) for row in rows)
        both = sum(int(row["both_taker_rows"]) for row in rows)
        complete = complete and not missing and not partial and total > 0
        years.append(
            {
                "year": year,
                "expected_symbols": len(symbols),
                "observed_symbols": len(observed),
                "row_count": total,
                "both_taker_rows": both,
                "field_coverage": both / total if total else None,
                "missing_symbols": missing,
                "partial_symbols": partial,
                "earliest_ts": min((row["earliest_ts"] for row in rows), default=None),
                "latest_ts": max((row["latest_ts"] for row in rows), default=None),
            }
        )
    return ("YES" if complete else "NO", years)


def _local_files() -> dict[str, list[dict]]:
    liquidation: list[dict] = []
    delivery: list[dict] = []
    delivery_name = re.compile(r"(?:BTC|ETH)(?:USD|USDT)_\d{6}", re.IGNORECASE)
    data_root = ROOT / "data"
    for path in data_root.rglob("*") if data_root.exists() else []:
        if not path.is_file():
            continue
        item = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size}
        if "liquidationsnapshot" in path.name.lower():
            liquidation.append(item)
        if delivery_name.search(path.name):
            delivery.append(item)
    return {"liquidation_snapshot": liquidation, "delivery_futures": delivery}


def local_funding_basis_correlation(data_root: Path = ROOT / "data") -> list[dict]:
    """Compute the bounded S3 pre-estimate from existing parquet inputs only."""
    import pandas as pd

    funding_path = data_root / "funding" / "binance_universe_funding.parquet"
    if not funding_path.exists():
        return []
    funding = pd.read_parquet(funding_path, columns=["inst_id", "ts", "funding_rate"])
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)

    def daily_close(path: Path) -> Any:
        if not path.exists():
            return pd.Series(dtype=float)
        frame = pd.read_parquet(path, columns=["ts", "close"])
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame = frame.loc[(frame["ts"] >= WIDE_START) & (frame["ts"] < datetime(2026, 6, 17, tzinfo=timezone.utc))]
        if frame.empty:
            return pd.Series(dtype=float)
        frame["day"] = frame["ts"].dt.floor("D")
        return frame.sort_values("ts").groupby("day")["close"].last()

    output: list[dict] = []
    for base in ("BTC", "ETH"):
        perp_path = data_root / "ticks" / f"{base}_USDT_SWAP" / "candles_1m.parquet"
        spot_path = data_root / "ticks" / f"{base}_USDT" / "candles_1m.parquet"
        perp, spot = daily_close(perp_path), daily_close(spot_path)
        basis = (perp / spot - 1.0).rename("perp_spot_basis")
        rates = funding.loc[funding["inst_id"] == f"{base}-USDT-SWAP"].copy()
        rates = rates.loc[(rates["ts"] >= WIDE_START) & (rates["ts"] < datetime(2026, 6, 17, tzinfo=timezone.utc))]
        rates["day"] = rates["ts"].dt.floor("D")
        annualized = (rates.groupby("day")["funding_rate"].sum() * 365.0).rename(
            "annualized_funding_proxy"
        )
        joined = pd.concat([annualized, basis], axis=1, join="inner").dropna()
        correlation = joined.corr().iloc[0, 1] if len(joined) >= 2 else None
        output.append(
            {
                "base": base,
                "common_days": len(joined),
                "earliest_day": joined.index.min() if not joined.empty else None,
                "latest_day": joined.index.max() if not joined.empty else None,
                "correlation": float(correlation) if correlation is not None and math.isfinite(correlation) else None,
                "basis_definition": "UTC daily last perp close / spot close - 1",
                "funding_definition": "UTC daily sum(funding_rate) * 365",
                "perp_path": perp_path.relative_to(ROOT).as_posix(),
                "spot_path": spot_path.relative_to(ROOT).as_posix(),
                "funding_path": funding_path.relative_to(ROOT).as_posix(),
            }
        )
    return output


def _jsonable(records: Sequence[Any]) -> list[dict]:
    return [dict(row) for row in records]


async def _connect(dsn: str):
    import asyncpg

    return await asyncpg.connect(
        dsn,
        server_settings={
            "application_name": "scout_free_datasets_read_only",
            "default_transaction_read_only": "on",
            "statement_timeout": "120000",
        },
    )


async def scout(dsn: str, membership: Path) -> dict:
    expected = _expected_symbols(membership)
    all_symbols = sorted({symbol for symbols in expected.values() for symbol in symbols})
    sample_pairs = [(symbol, year) for year, symbols in expected.items() for symbol in symbols]
    sample_symbols = [symbol for symbol, _year in sample_pairs]
    sample_years = [year for _symbol, year in sample_pairs]
    conn = await _connect(dsn)
    try:
        coverage_rows = await conn.fetch(S1_COVERAGE_SQL, all_symbols, START, END, WIDE_START, CORE_SYMBOLS)
        answer, yearly = _coverage(coverage_rows, expected)
        samples = await conn.fetch(S1_SAMPLE_SQL, list(sample_symbols), list(sample_years))
        liquidations = await conn.fetch(LIQUIDATION_SQL)
        delivery = await conn.fetch(DELIVERY_INVENTORY_SQL)
        correlation = await conn.fetch(FUNDING_BASIS_SQL, WIDE_START, datetime(2026, 6, 17, tzinfo=timezone.utc))
    finally:
        await conn.close()

    local_files = _local_files()
    parquet_correlation = local_funding_basis_correlation()
    return {
        "status": "COMPLETE",
        "generated_at": datetime.now(timezone.utc),
        "network_requests": 0,
        "s1": {
            "raw_payload_preserves_taker_fields": answer,
            "json_paths": {
                "taker_buy_base": TAKER_BASE_JSON_PATH,
                "taker_buy_quote": TAKER_QUOTE_JSON_PATH,
            },
            "yearly_coverage": yearly,
            "samples": _jsonable(samples),
        },
        "s2": {
            "local_files": local_files["liquidation_snapshot"],
            "db_datasets": _jsonable(liquidations),
        },
        "s3": {
            "local_files": local_files["delivery_futures"],
            "db_contracts": _jsonable(delivery),
            "db_funding_basis_correlation": _jsonable(correlation),
            "parquet_funding_basis_correlation": parquet_correlation,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="Override DATABASE_URL/config DSN")
    parser.add_argument(
        "--membership",
        type=Path,
        default=Path("data/universe/universe_membership.parquet"),
    )
    args = parser.parse_args(argv)
    dsn = resolve_dsn(args.dsn)
    if not dsn:
        print(json.dumps({"status": "SKIP", "reason": "No DSN; no DB or network request made."}))
        return 0
    try:
        report = asyncio.run(scout(dsn, args.membership))
    except Exception as exc:
        local_files = _local_files()
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": f"Read-only DB scout failed closed: {exc}",
                    "network_requests": 0,
                    "local_evidence": {
                        "liquidation_files": local_files["liquidation_snapshot"],
                        "delivery_files": local_files["delivery_futures"],
                        "parquet_funding_basis_correlation": local_funding_basis_correlation(),
                    },
                },
                indent=2,
                default=str,
            )
        )
        return 1
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
