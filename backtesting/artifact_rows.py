"""Derived row index helpers for large backtest artifacts.

The row table is a read optimization only. Payloads are copied from existing
artifact records and must not become a trading-result source of truth.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROW_INDEX_ARTIFACT_TYPES = {
    "price_series",
    "indicator_series",
    "equity",
    "returns",
    "drawdown",
    "fills",
    "trades",
    "orders",
    "signals",
    "execution_markers",
    "risk_events",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS backtest_artifact_rows (
    run_id TEXT NOT NULL REFERENCES backtest_runs(run_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    inst_id TEXT NOT NULL DEFAULT '',
    ts_ms BIGINT,
    datetime_text TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, artifact_type, ordinal)
)
"""

INDEX_SQL = [
    """
    CREATE INDEX IF NOT EXISTS backtest_artifact_rows_symbol_ord_idx
        ON backtest_artifact_rows (run_id, artifact_type, inst_id, ordinal)
    """,
    """
    CREATE INDEX IF NOT EXISTS backtest_artifact_rows_symbol_ts_idx
        ON backtest_artifact_rows (run_id, artifact_type, inst_id, ts_ms)
    """,
    """
    CREATE INDEX IF NOT EXISTS backtest_artifact_rows_type_idx
        ON backtest_artifact_rows (run_id, artifact_type)
    """,
]


@dataclass(frozen=True)
class ArtifactRow:
    run_id: str
    artifact_type: str
    ordinal: int
    inst_id: str
    ts_ms: int | None
    datetime_text: str
    payload: dict[str, Any]

    def db_tuple(self) -> tuple[str, str, int, str, int | None, str, str]:
        return (
            self.run_id,
            self.artifact_type,
            self.ordinal,
            self.inst_id,
            self.ts_ms,
            self.datetime_text,
            json.dumps(_json_safe(self.payload), ensure_ascii=False, default=str),
        )


def build_artifact_row_records(run_id: str, artifact_type: str, payload: Any) -> list[ArtifactRow]:
    """Build derived row-index records from list-like artifact payloads."""
    if not isinstance(payload, list):
        return []
    rows: list[ArtifactRow] = []
    ordinal = 0
    for record in payload:
        if not isinstance(record, dict):
            continue
        row = dict(record)
        rows.append(
            ArtifactRow(
                run_id=run_id,
                artifact_type=artifact_type,
                ordinal=ordinal,
                inst_id=_extract_symbol(row),
                ts_ms=_extract_ts_ms(row),
                datetime_text=_extract_datetime_text(row),
                payload=row,
            )
        )
        ordinal += 1
    return rows


def normalized_records_hash(records: Iterable[dict[str, Any]]) -> str:
    normalized = [_json_safe(dict(row)) for row in records if isinstance(row, dict)]
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def row_payloads_hash(rows: Iterable[ArtifactRow | dict[str, Any]]) -> str:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, ArtifactRow):
            payloads.append(row.payload)
        elif isinstance(row, dict):
            payload = row.get("payload", row)
            if isinstance(payload, dict):
                payloads.append(payload)
    return normalized_records_hash(payloads)


def select_downsample_indices(total: int, n: int) -> list[int]:
    """Match the existing evenly-spaced chart sampling semantics."""
    if total <= 0:
        return []
    if n <= 0 or total <= n:
        return list(range(total))
    step = total / n
    indices = {int(i * step) for i in range(n)}
    indices.add(total - 1)
    return sorted(indices)


def validation_artifact_type(validation_id: str, artifact_name: str) -> str:
    return f"validation/{Path(validation_id).name}/{Path(artifact_name).name}"


async def ensure_artifact_rows_schema(conn: Any) -> None:
    await conn.execute(SCHEMA_SQL)
    for sql in INDEX_SQL:
        await conn.execute(sql)


async def upsert_artifact_rows(
    *,
    dsn: str,
    run_id: str,
    artifacts: dict[str, Any],
    artifact_types: set[str] | None = None,
) -> dict[str, int]:
    """Replace derived rows for the supplied artifacts and return row counts."""
    import asyncpg

    selected = set(artifact_types or ROW_INDEX_ARTIFACT_TYPES)
    candidates = {
        artifact_type: artifacts.get(artifact_type)
        for artifact_type in selected
        if artifact_type in artifacts
    }
    if not candidates:
        return {}

    conn = await asyncpg.connect(dsn)
    try:
        await ensure_artifact_rows_schema(conn)
        counts: dict[str, int] = {}
        async with conn.transaction():
            for artifact_type, payload in candidates.items():
                rows = build_artifact_row_records(run_id, artifact_type, payload)
                counts[artifact_type] = len(rows)
                await conn.execute(
                    """
                    DELETE FROM backtest_artifact_rows
                    WHERE run_id = $1 AND artifact_type = $2
                    """,
                    run_id,
                    artifact_type,
                )
                if not rows:
                    continue
                await conn.copy_records_to_table(
                    "backtest_artifact_rows",
                    records=[row.db_tuple() for row in rows],
                    columns=[
                        "run_id",
                        "artifact_type",
                        "ordinal",
                        "inst_id",
                        "ts_ms",
                        "datetime_text",
                        "payload",
                    ],
                )
        return counts
    finally:
        await conn.close()


async def read_artifact_rows(
    *,
    dsn: str | None,
    run_id: str,
    artifact_type: str,
    symbol: str | None = None,
    limit: int = 0,
    offset: int = 0,
    n: int = 0,
) -> list[dict[str, Any]]:
    """Read derived artifact payload rows with DB-side filtering and slicing."""
    if not dsn:
        return []
    try:
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            return await _read_artifact_rows_from_conn(
                conn,
                run_id=run_id,
                artifact_type=artifact_type,
                symbol=symbol,
                limit=limit,
                offset=offset,
                n=n,
            )
        finally:
            await conn.close()
    except Exception:
        return []


async def _read_artifact_rows_from_conn(
    conn: Any,
    *,
    run_id: str,
    artifact_type: str,
    symbol: str | None = None,
    limit: int = 0,
    offset: int = 0,
    n: int = 0,
) -> list[dict[str, Any]]:
    where, params = _where_clause(run_id, artifact_type, symbol)
    if n > 0:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM backtest_artifact_rows WHERE {where}", *params)
        total = int(count or 0)
        if total == 0:
            return []
        if total > n:
            indices = select_downsample_indices(total, n)
            params_with_indices = [*params, indices]
            index_param = f"${len(params_with_indices)}"
            rows = await conn.fetch(
                f"""
                SELECT payload
                FROM (
                    SELECT payload, (row_number() OVER (ORDER BY ordinal) - 1)::int AS row_idx
                    FROM backtest_artifact_rows
                    WHERE {where}
                ) sampled
                WHERE row_idx = ANY({index_param}::int[])
                ORDER BY row_idx
                """,
                *params_with_indices,
            )
            return [_decode_payload(row["payload"]) for row in rows]

    sql = f"SELECT payload FROM backtest_artifact_rows WHERE {where} ORDER BY ordinal"
    params_with_slice = list(params)
    if offset > 0:
        params_with_slice.append(offset)
        sql += f" OFFSET ${len(params_with_slice)}"
    if limit > 0:
        params_with_slice.append(limit)
        sql += f" LIMIT ${len(params_with_slice)}"
    rows = await conn.fetch(sql, *params_with_slice)
    return [_decode_payload(row["payload"]) for row in rows]


def _where_clause(run_id: str, artifact_type: str, symbol: str | None) -> tuple[str, list[Any]]:
    params: list[Any] = [run_id, artifact_type]
    where = "run_id = $1 AND artifact_type = $2"
    if symbol:
        params.append(symbol)
        where += f" AND inst_id = ${len(params)}"
    return where, params


def _extract_symbol(row: dict[str, Any]) -> str:
    for key in ("inst_id", "symbol", "instrument", "instrument_id", "perp_symbol", "spot_symbol"):
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return ""


def _extract_datetime_text(row: dict[str, Any]) -> str:
    for key in ("datetime", "timestamp", "time"):
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return ""


def _extract_ts_ms(row: dict[str, Any]) -> int | None:
    for key in ("ts", "timestamp", "time", "datetime", "entry_ts", "exit_ts"):
        value = row.get(key)
        if value is None or value == "":
            continue
        parsed = _parse_ts_ms(value)
        if parsed is not None:
            return parsed
    return None


def _parse_ts_ms(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        raw = float(value)
        if abs(raw) > 1_000_000_000_000:
            return int(raw)
        if abs(raw) > 1_000_000_000:
            return int(raw * 1000)
        return int(raw)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            number = None
        if number is not None and math.isfinite(number):
            return _parse_ts_ms(number)
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    return None


def _decode_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return str(value)
