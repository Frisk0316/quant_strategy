"""PostgreSQL store for external feature observations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import pandas as pd


class ExternalDataStore:
    """Async wrapper for external_datasets and external_observations."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def from_dsn(
        cls,
        dsn: str,
        min_size: int = 1,
        max_size: int = 4,
    ) -> "ExternalDataStore":
        pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def __aenter__(self) -> "ExternalDataStore":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def upsert_dataset(self, dataset_id: str, config: dict[str, Any]) -> None:
        metadata = {
            key: value
            for key, value in config.items()
            if key not in {
                "provider",
                "frequency",
                "value_kind",
                "max_age_seconds",
                "source_url",
                "attribution",
                "active",
            }
        }
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO external_datasets (
                    dataset_id, provider, frequency, value_kind, max_age_seconds,
                    source_url, attribution, active, metadata, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
                ON CONFLICT (dataset_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    frequency = EXCLUDED.frequency,
                    value_kind = EXCLUDED.value_kind,
                    max_age_seconds = EXCLUDED.max_age_seconds,
                    source_url = EXCLUDED.source_url,
                    attribution = EXCLUDED.attribution,
                    active = EXCLUDED.active,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                dataset_id,
                str(config["provider"]),
                str(config["frequency"]),
                str(config["value_kind"]),
                int(config["max_age_seconds"]),
                config.get("source_url"),
                config.get("attribution"),
                bool(config.get("active", True)),
                json.dumps(metadata),
            )

    async def start_fetch_job(
        self,
        dataset_id: str,
        provider: str,
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> str:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO external_fetch_jobs (dataset_id, provider, start_at, end_at, status)
                VALUES ($1, $2, $3, $4, 'running')
                RETURNING job_id::text
                """,
                dataset_id,
                provider,
                _as_utc_dt(start),
                _as_utc_dt(end),
            )
        return str(row["job_id"])

    async def finish_fetch_job(
        self,
        job_id: str,
        *,
        status: str,
        rows_fetched: int = 0,
        rows_inserted: int = 0,
        rows_updated: int = 0,
        rows_skipped: int = 0,
        error_message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE external_fetch_jobs
                SET status = $2,
                    rows_fetched = $3,
                    rows_inserted = $4,
                    rows_updated = $5,
                    rows_skipped = $6,
                    error_message = $7,
                    details = $8::jsonb,
                    finished_at = NOW()
                WHERE job_id = $1::uuid
                """,
                job_id,
                status,
                int(rows_fetched),
                int(rows_inserted),
                int(rows_updated),
                int(rows_skipped),
                error_message,
                json.dumps(details or {}),
            )

    async def upsert_observations(self, dataset_id: str, rows: list[dict[str, Any]]) -> dict[str, int]:
        if not rows:
            return {"rows": 0, "inserted": 0, "updated": 0}
        before = await self._existing_observed_at(dataset_id, [row["observed_at"] for row in rows])
        payload = [
            (
                dataset_id,
                _as_utc_dt(row["observed_at"]),
                _as_utc_dt(row.get("published_at")) if row.get("published_at") else None,
                _to_optional_float(row.get("value_num")),
                row.get("value_text"),
                json.dumps(row.get("fields") or {}),
                str(row.get("quality_status") or "raw"),
                json.dumps(row.get("raw_payload") or {}),
            )
            for row in rows
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO external_observations (
                    dataset_id, observed_at, published_at, value_num, value_text,
                    fields, quality_status, raw_payload, ingested_at
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::jsonb, NOW())
                ON CONFLICT (dataset_id, observed_at) DO UPDATE SET
                    published_at = EXCLUDED.published_at,
                    value_num = EXCLUDED.value_num,
                    value_text = EXCLUDED.value_text,
                    fields = EXCLUDED.fields,
                    quality_status = EXCLUDED.quality_status,
                    raw_payload = EXCLUDED.raw_payload,
                    ingested_at = NOW()
                """,
                payload,
            )
        updated = sum(1 for row in rows if _as_utc_dt(row["observed_at"]) in before)
        inserted = len(rows) - updated
        return {"rows": len(rows), "inserted": inserted, "updated": updated}

    async def update_checkpoint(
        self,
        dataset_id: str,
        *,
        direction: str,
        cursor_time: Optional[datetime],
        request_count: int,
        row_count: int,
        status: str,
        last_error: Optional[str] = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO external_ingestion_checkpoints (
                    dataset_id, direction, cursor_time, request_count, row_count,
                    status, last_error, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (dataset_id, direction) DO UPDATE SET
                    cursor_time = EXCLUDED.cursor_time,
                    request_count = external_ingestion_checkpoints.request_count + EXCLUDED.request_count,
                    row_count = external_ingestion_checkpoints.row_count + EXCLUDED.row_count,
                    status = EXCLUDED.status,
                    last_error = EXCLUDED.last_error,
                    updated_at = NOW()
                """,
                dataset_id,
                direction,
                _as_utc_dt(cursor_time),
                int(request_count),
                int(row_count),
                status,
                last_error,
            )

    async def get_observations(
        self,
        dataset_id: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT dataset_id, observed_at, published_at, value_num, value_text,
                       fields, quality_status, raw_payload, ingested_at
                FROM external_observations
                WHERE dataset_id = $1
                  AND ($2::timestamptz IS NULL OR observed_at >= $2)
                  AND ($3::timestamptz IS NULL OR observed_at < $3)
                ORDER BY observed_at ASC
                """,
                dataset_id,
                _as_utc_dt(start),
                _as_utc_dt(end),
            )
        if not rows:
            return pd.DataFrame(columns=[
                "dataset_id", "observed_at", "published_at", "value_num",
                "value_text", "fields", "quality_status", "raw_payload", "ingested_at",
            ])
        frame = pd.DataFrame([dict(row) for row in rows])
        for col in ("fields", "raw_payload"):
            frame[col] = frame[col].apply(_decode_json)
        for col in ("observed_at", "published_at", "ingested_at"):
            frame[col] = pd.to_datetime(frame[col], utc=True, errors="coerce")
        return frame

    async def summarize_observations(self, dataset_id: str) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)::int AS observation_count,
                    MIN(observed_at) AS first_observed_at,
                    MAX(observed_at) AS last_observed_at,
                    MAX(ingested_at) AS last_ingested_at
                FROM external_observations
                WHERE dataset_id = $1
                """,
                dataset_id,
            )
        return dict(row) if row else {}

    async def _existing_observed_at(self, dataset_id: str, observed_at: list[datetime]) -> set[datetime]:
        if not observed_at:
            return set()
        values = [_as_utc_dt(value) for value in observed_at]
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT observed_at
                FROM external_observations
                WHERE dataset_id = $1 AND observed_at = ANY($2::timestamptz[])
                """,
                dataset_id,
                values,
            )
        return {_as_utc_dt(row["observed_at"]) for row in rows}


def _as_utc_dt(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed
