from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

import okx_quant.api.routes_data as routes_data


def _app_with_rows(monkeypatch, rows, *, dataset_exists=True):
    import asyncpg

    class FakeConn:
        async def fetchrow(self, sql, *params):
            return {"dataset_id": params[0]} if dataset_exists else None

        async def fetch(self, sql, *params):
            return rows

        async def close(self):
            return None

    async def fake_connect(dsn):
        assert dsn == "postgresql://unused"
        return FakeConn()

    monkeypatch.setattr(asyncpg, "connect", fake_connect)
    app = FastAPI()
    app.include_router(routes_data.make_data_router("postgresql://unused"), prefix="/api/data")
    return TestClient(app)


def test_external_series_returns_points_and_unit(monkeypatch):
    rows = [
        {
            "observed_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "value_num": 50.5,
            "fields": {"unit": "dvol_index_points"},
        },
        {
            "observed_at": datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            "value_num": 51.5,
            "fields": {"unit": "dvol_index_points"},
        },
    ]

    response = _app_with_rows(monkeypatch, rows).get(
        "/api/data/external-series?dataset_id=dvol_deribit_btc_1h&start=2024-01-01T00:00:00Z&end=2024-01-02T00:00:00Z"
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset_id": "dvol_deribit_btc_1h",
        "unit": "dvol_index_points",
        "points": [
            {"t": "2024-01-01T00:00:00+00:00", "v": 50.5},
            {"t": "2024-01-01T01:00:00+00:00", "v": 51.5},
        ],
    }


def test_external_series_known_empty_dataset_returns_empty_points(monkeypatch):
    response = _app_with_rows(monkeypatch, []).get("/api/data/external-series?dataset_id=dvol_deribit_btc_1h")

    assert response.status_code == 200
    assert response.json() == {"dataset_id": "dvol_deribit_btc_1h", "unit": None, "points": []}


def test_external_series_unknown_dataset_404s(monkeypatch):
    response = _app_with_rows(monkeypatch, [], dataset_exists=False).get("/api/data/external-series?dataset_id=missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown external dataset: missing"


def test_external_series_downsamples_above_cap(monkeypatch):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"observed_at": start + timedelta(hours=i), "value_num": float(i), "fields": {"unit": "x"}}
        for i in range(5001)
    ]

    response = _app_with_rows(monkeypatch, rows).get("/api/data/external-series?dataset_id=dvol_deribit_btc_1h")

    payload = response.json()
    assert len(payload["points"]) == 5000
    assert payload["points"][0] == {"t": "2024-01-01T00:00:00+00:00", "v": 0.0}
    assert payload["points"][-1] == {"t": (start + timedelta(hours=5000)).isoformat(), "v": 5000.0}
