from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from okx_quant.data.external_clients.deribit_dvol import DeribitDVOLClient


def test_deribit_dvol_client_pages_backward_from_continuation_timestamp(monkeypatch):
    sleeps = []
    client = DeribitDVOLClient(sleep=sleeps.append)
    calls = []
    pages = [
        {
            "result": {
                "data": [
                    [1704070800000, 51.0, 52.0, 50.0, 51.5],
                    [1704074400000, 52.0, 53.0, 51.0, 52.5],
                ],
                "continuation": 1704070800000,
            }
        },
        {
            "result": {
                "data": [
                    [1704067200000, 50.0, 51.0, 49.0, 50.5],
                    [1704070800000, 51.0, 52.0, 50.0, 51.5],
                ],
            }
        },
    ]

    def fake_get(params):
        calls.append(dict(params))
        return pages.pop(0)

    monkeypatch.setattr(client, "_get", fake_get)

    rows = client.fetch(
        currency="BTC",
        resolution="3600",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 3, tzinfo=timezone.utc),
    )

    assert [row["observed_at"] for row in rows] == [
        datetime(2024, 1, 1, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
    ]
    assert [row["published_at"] for row in rows] == [
        datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 2, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 3, tzinfo=timezone.utc),
    ]
    assert calls[0]["start_timestamp"] == 1704067200000
    assert calls[0]["end_timestamp"] == 1704078000000
    assert "continuation" not in calls[0]
    assert calls[1]["end_timestamp"] == 1704070800000
    assert "continuation" not in calls[1]
    assert sleeps == [0.2]


def test_deribit_dvol_client_retries_429_and_deribit_rate_limit(monkeypatch):
    calls = []
    request = httpx.Request("GET", "https://www.deribit.com/api/v2/public/get_volatility_index_data")
    responses = [
        httpx.Response(429, headers={"Retry-After": "1"}, json={"error": {"code": 429}}, request=request),
        httpx.Response(200, json={"error": {"code": 10028}}, request=request),
        httpx.Response(200, json={"result": {"data": []}}, request=request),
    ]

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, endpoint, params):
            calls.append((endpoint, dict(params)))
            return responses.pop(0)

    sleeps = []
    monkeypatch.setattr("okx_quant.data.external_clients.deribit_dvol.httpx.Client", FakeClient)

    client = DeribitDVOLClient(sleep=sleeps.append, retries=2)

    assert client._get({"currency": "BTC"}) == {"result": {"data": []}}
    assert len(calls) == 3
    assert sleeps == [1.0, 1.0]


def test_deribit_dvol_client_rejects_unknown_resolution(monkeypatch):
    client = DeribitDVOLClient()
    monkeypatch.setattr(
        client,
        "_get",
        lambda _params: {"result": {"data": [[1704067200000, 50.0, 51.0, 49.0, 50.5]]}},
    )

    with pytest.raises(ValueError, match="unsupported DVOL resolution"):
        client.fetch(currency="BTC", resolution="300")
