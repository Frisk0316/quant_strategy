"""Backfill Binance funding for every symbol eligible in a PIT universe."""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from okx_quant.core.config import load_config  # noqa: E402
from okx_quant.data.candle_store import CandleStore  # noqa: E402
from okx_quant.data.exchange_clients.binance_public import BinancePublicClient  # noqa: E402

EIGHT_HOURS_MS = 8 * 60 * 60 * 1000


def _parse_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _repo_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def canonical_to_binance_symbol(inst_id: str) -> str:
    parts = inst_id.upper().split("-")
    if parts[-1] in {"SWAP", "PERP", "FUTURES"}:
        parts = parts[:-1]
    return "".join(parts)


def load_eligible_symbols(path: Path, *, start: datetime, end: datetime) -> list[str]:
    df = pd.read_parquet(path)
    required = {"date", "symbol", "eligible"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"universe membership missing columns: {sorted(missing)}")

    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    mask = (
        (frame["date"] >= start.date())
        & (frame["date"] < end.date())
        & frame["eligible"].astype(bool)
    )
    return sorted(str(symbol) for symbol in frame.loc[mask, "symbol"].dropna().unique())


def _normalize_row(inst_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    funding_rate = float(row["funding_rate"])
    raw_payload = row.get("raw_payload")
    if not isinstance(raw_payload, Mapping):
        raw_payload = dict(row)
    return {
        "source": "binance",
        "inst_id": inst_id,
        "ts_ms": int(row["ts_ms"]),
        "funding_rate": funding_rate,
        "realized_rate": (
            float(row["realized_rate"]) if row.get("realized_rate") is not None else funding_rate
        ),
        "mark_price": float(row["mark_price"]) if row.get("mark_price") is not None else None,
        "next_funding_ts_ms": row.get("next_funding_ts_ms"),
        "raw_payload": raw_payload,
    }


def _infer_intervals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for left, right in zip(rows, rows[1:]):
        left["funding_interval_hours"] = (int(right["ts_ms"]) - int(left["ts_ms"])) / 3_600_000.0
    return rows


def fetch_symbol_funding(
    client: Any,
    inst_id: str,
    *,
    start: datetime,
    end: datetime,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    start_ms = _to_ms(start)
    end_ms = _to_ms(end)
    cursor = start_ms
    native_symbol = canonical_to_binance_symbol(inst_id)
    by_ts: dict[int, dict[str, Any]] = {}

    while cursor < end_ms:
        window_end = min(cursor + limit * EIGHT_HOURS_MS - 1, end_ms - 1)
        page = client.get_funding_rates(
            native_symbol,
            start_ms=cursor,
            end_ms=window_end,
            limit=limit,
        )
        if not page:
            cursor = window_end + 1
            continue
        for row in page:
            ts_ms = int(row["ts_ms"])
            if start_ms <= ts_ms < end_ms:
                by_ts[ts_ms] = _normalize_row(inst_id, row)
        if len(page) < limit:
            cursor = window_end + 1
            if end_ms - cursor < EIGHT_HOURS_MS:
                break
        else:
            next_cursor = max(int(row["ts_ms"]) for row in page) + 1
            cursor = next_cursor if next_cursor > cursor else window_end + 1

    return _infer_intervals([by_ts[ts] for ts in sorted(by_ts)])


def rows_to_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    columns = [
        "source",
        "inst_id",
        "ts",
        "ts_ms",
        "funding_rate",
        "realized_rate",
        "mark_price",
        "funding_interval_hours",
        "next_funding_ts_ms",
        "raw_payload_json",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(dict(row) for row in rows)
    frame["ts"] = pd.to_datetime(frame["ts_ms"], unit="ms", utc=True)
    frame["raw_payload_json"] = frame.get("raw_payload", pd.Series(dtype=object)).map(
        lambda value: json.dumps(value, sort_keys=True, default=_json_default)
        if isinstance(value, Mapping)
        else None
    )
    return frame.reindex(columns=columns).sort_values(["inst_id", "ts"]).reset_index(drop=True)


def build_coverage_report(
    rows_by_symbol: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    expected_interval_hours: float = 8.0,
    tolerance_seconds: float = 1.0,
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    max_gap_seconds = expected_interval_hours * 3600 + tolerance_seconds
    for inst_id in sorted(rows_by_symbol):
        timestamps = sorted({_from_ms(int(row["ts_ms"])) for row in rows_by_symbol[inst_id]})
        stale_intervals = []
        for previous, current in zip(timestamps, timestamps[1:]):
            gap_seconds = (current - previous).total_seconds()
            if gap_seconds > max_gap_seconds:
                stale_intervals.append(
                    {
                        "start": previous.isoformat(),
                        "end": current.isoformat(),
                        "gap_hours": round(gap_seconds / 3600.0, 6),
                    }
                )
        report.append(
            {
                "inst_id": inst_id,
                "rows": len(timestamps),
                "first_ts": timestamps[0].isoformat() if timestamps else None,
                "last_ts": timestamps[-1].isoformat() if timestamps else None,
                "gap_count": len(stale_intervals),
                "stale_intervals": stale_intervals,
            }
        )
    return report


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def _upsert_db(
    *,
    dsn: str,
    rows_by_symbol: Mapping[str, Sequence[dict[str, Any]]],
    store_factory: Callable[[str], Any] | None,
) -> dict[str, Any]:
    factory = store_factory or CandleStore.from_dsn
    store = await _maybe_await(factory(dsn))
    inserted = 0
    try:
        for inst_id, rows in rows_by_symbol.items():
            if not rows:
                continue
            await store.register_instrument(
                inst_id=inst_id,
                base_ccy=inst_id.split("-")[0],
                exchange="binance",
                inst_type="SWAP",
            )
            result = await store.upsert_funding_rates(list(rows), source="binance", inst_id=inst_id)
            await store.refresh_funding_intervals("binance", inst_id)
            inserted += int(result.get("inserted", len(rows)))
    finally:
        await store.close()
    return {"status": "ok", "rows_inserted": inserted}


def _write_db(
    *,
    dsn: str | None,
    rows_by_symbol: Mapping[str, Sequence[dict[str, Any]]],
    store_factory: Callable[[str], Any] | None,
) -> dict[str, Any]:
    if not dsn:
        return {"status": "skipped", "reason": "dsn_missing"}
    try:
        return asyncio.run(_upsert_db(dsn=dsn, rows_by_symbol=rows_by_symbol, store_factory=store_factory))
    except Exception as exc:
        return {"status": "error", "error_type": type(exc).__name__, "error": str(exc)}


def _default_stage2_runner(**kwargs: Any) -> Any:
    from backtesting.pipeline_stage2_registry import run_data_probe

    return asyncio.run(run_data_probe(**kwargs))


def _run_stage2(
    *,
    db_status: Mapping[str, Any],
    dsn: str | None,
    membership_path: Path,
    stage2_output_root: Path | None,
    stage2_runner: Callable[..., Any] | None,
) -> dict[str, Any]:
    if db_status.get("status") != "ok" or not dsn:
        return {"status": "skipped", "reason": "db_unavailable"}
    if stage2_output_root is None:
        return {"status": "skipped", "reason": "stage2_output_root_not_set"}
    try:
        runner = stage2_runner or _default_stage2_runner
        outputs = runner(
            dsn=dsn,
            output_root=stage2_output_root,
            universe_path=membership_path,
            candidates=["funding"],
        )
        return {
            "status": "ok",
            "output_root": str(stage2_output_root),
            "artifacts": [str(path) for _result, path in outputs],
        }
    except Exception as exc:
        return {"status": "error", "error_type": type(exc).__name__, "error": str(exc)}


def backfill_universe_funding(
    *,
    membership_path: Path,
    start: datetime,
    end: datetime,
    parquet_path: Path,
    report_path: Path,
    dsn: str | None,
    client: Any | None = None,
    stage2_output_root: Path | None = Path("results/stage2_reprobe_20260703_funding"),
    store_factory: Callable[[str], Any] | None = None,
    stage2_runner: Callable[..., Any] | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    owned_client = client is None
    client = client or BinancePublicClient()
    try:
        symbols = load_eligible_symbols(membership_path, start=start, end=end)
        rows_by_symbol = {
            inst_id: fetch_symbol_funding(client, inst_id, start=start, end=end, limit=limit)
            for inst_id in symbols
        }
    finally:
        if owned_client:
            client.close()

    all_rows = [row for rows in rows_by_symbol.values() for row in rows]
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    rows_to_frame(all_rows).to_parquet(parquet_path, index=False)

    report = build_coverage_report(rows_by_symbol)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    db_status = _write_db(dsn=dsn, rows_by_symbol=rows_by_symbol, store_factory=store_factory)
    stage2_status = _run_stage2(
        db_status=db_status,
        dsn=dsn,
        membership_path=membership_path,
        stage2_output_root=stage2_output_root,
        stage2_runner=stage2_runner,
    )
    return {
        "symbols": symbols,
        "rows": len(all_rows),
        "parquet_path": str(parquet_path),
        "report_path": str(report_path),
        "db": db_status,
        "stage2": stage2_status,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--membership-path", type=Path, default=Path("data/universe/universe_membership.parquet"))
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-06-17")
    parser.add_argument("--parquet-out", type=Path, default=Path("data/funding/binance_universe_funding.parquet"))
    parser.add_argument("--report-out", type=Path, default=Path("data/funding/binance_universe_funding_coverage.json"))
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--stage2-output-root", type=Path, default=Path("results/stage2_reprobe_20260703_funding"))
    parser.add_argument("--skip-stage2-probe", action="store_true")
    args = parser.parse_args(argv)

    dsn = None
    if not args.no_db:
        cfg = load_config(settings_path=args.config, require_secrets=False)
        dsn = args.dsn or cfg.storage.timescale_dsn

    summary = backfill_universe_funding(
        membership_path=_repo_path(args.membership_path),
        start=_parse_dt(args.start),
        end=_parse_dt(args.end),
        parquet_path=_repo_path(args.parquet_out),
        report_path=_repo_path(args.report_out),
        dsn=dsn,
        stage2_output_root=None if args.skip_stage2_probe else _repo_path(args.stage2_output_root),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["db"]["status"] == "error" or summary["stage2"]["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
