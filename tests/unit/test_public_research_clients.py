from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from okx_quant.data.external_clients import (
    CoinMetricsCommunityClient,
    WikimediaPageviewsClient,
)
from scripts.market_data import ingest_external
from okx_quant.data.external_clients import wikimedia_pageviews


def test_wikimedia_pageviews_chunks_and_keeps_end_exclusive(monkeypatch):
    client = WikimediaPageviewsClient()
    urls = []

    def fake_get(url):
        urls.append(url)
        return {
            "items": [
                {"timestamp": "2024010100", "views": 10},
                {"timestamp": "2024010200", "views": 20},
                {"timestamp": "2024010300", "views": 30},
            ]
        }

    monkeypatch.setattr(client, "_get", fake_get)
    rows = client.fetch(
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )

    assert urls == [
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "en.wikipedia.org/all-access/user/Bitcoin/daily/2024010100/2024010200"
    ]
    assert [row["value_num"] for row in rows] == [10.0, 20.0]
    assert rows[0]["published_at"] == datetime(2024, 1, 2, tzinfo=timezone.utc)
    assert rows[0]["fields"] == {
        "project": "en.wikipedia.org",
        "article": "Bitcoin",
        "access": "all-access",
        "agent": "user",
        "unit": "views",
        "publish_lag_days": 1,
    }
    assert rows[0]["raw_payload"]["views"] == 10


def test_wikimedia_pageviews_chunks_long_windows(monkeypatch):
    client = WikimediaPageviewsClient()
    urls = []
    monkeypatch.setattr(client, "_get", lambda url: urls.append(url) or {"items": []})

    client.fetch(
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )

    assert [url.rsplit("/", 2)[-2:] for url in urls] == [
        ["2024010100", "2024123000"],
        ["2024123100", "2025010100"],
    ]


def test_wikimedia_retries_429_and_5xx_with_a_bound(monkeypatch):
    responses = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(503),
        httpx.Response(200, json={"items": []}),
    ]
    real_client = httpx.Client
    transport = httpx.MockTransport(lambda _request: responses.pop(0))
    monkeypatch.setattr(
        wikimedia_pageviews.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    delays = []
    client = WikimediaPageviewsClient(retries=2, sleep=delays.append)

    assert client._get("https://wikimedia.org/test") == {"items": []}
    assert delays == [0.0, 1.0]
    assert responses == []


def test_coinmetrics_checks_catalog_paginates_and_keeps_end_exclusive(monkeypatch):
    client = CoinMetricsCommunityClient()
    calls = []
    next_url = (
        "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?"
        "next_page_token=next"
    )

    def fake_get(url, params=None):
        calls.append((url, params))
        if "catalog-v2" in url:
            return {
                "data": [
                    {
                        "asset": "btc",
                        "metrics": [
                            {"metric": "AdrActCnt", "frequencies": [{"frequency": "1d"}]}
                        ],
                    }
                ]
            }
        if url == client.endpoint:
            return {
                "data": [
                    {
                        "asset": "btc",
                        "time": "2024-01-01T00:00:00.000000000Z",
                        "AdrActCnt": "100",
                    }
                ],
                "next_page_token": "next",
                "next_page_url": next_url,
            }
        return {
            "data": [
                {
                    "asset": "btc",
                    "time": "2024-01-02T00:00:00.000000000Z",
                    "AdrActCnt": "200",
                }
            ]
        }

    monkeypatch.setattr(client, "_get", fake_get)
    rows = client.fetch(
        asset="btc",
        metric="AdrActCnt",
        unit="active_addresses",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert len(calls) == 3
    assert calls[1][1]["start_time"] == "2024-01-01T00:00:00Z"
    assert calls[1][1]["end_time"] == "2024-01-02T00:00:00Z"
    assert calls[2] == (next_url, None)
    assert [row["value_num"] for row in rows] == [100.0]
    assert rows[0]["fields"]["metric"] == "AdrActCnt"
    assert rows[0]["fields"]["unit"] == "active_addresses"
    assert rows[0]["raw_payload"]["AdrActCnt"] == "100"


def test_coinmetrics_fails_closed_when_catalog_lacks_metric(monkeypatch):
    client = CoinMetricsCommunityClient()
    monkeypatch.setattr(client, "_get", lambda *_args, **_kwargs: {"data": []})

    with pytest.raises(ValueError, match="does not expose btc/AdrActCnt/1d"):
        client.fetch(asset="btc", metric="AdrActCnt")


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        (
            {
                "adapter": "wikimedia_pageviews",
                "project": "en.wikipedia.org",
                "article": "Bitcoin",
                "access": "all-access",
                "agent": "user",
            },
            {
                "project": "en.wikipedia.org",
                "article": "Bitcoin",
                "access": "all-access",
                "agent": "user",
                "start": None,
                "end": None,
            },
        ),
        (
            {
                "adapter": "coinmetrics_community",
                "asset": "eth",
                "metric": "AdrActCnt",
                "metric_frequency": "1d",
                "unit": "active_addresses",
            },
            {
                "asset": "eth",
                "metric": "AdrActCnt",
                "frequency": "1d",
                "unit": "active_addresses",
                "start": None,
                "end": None,
            },
        ),
    ],
)
def test_ingest_dispatches_public_research_clients(monkeypatch, cfg, expected):
    class FakeClient:
        def fetch(self, **kwargs):
            assert kwargs == expected
            return []

    monkeypatch.setattr(ingest_external, "_build_client", lambda *_args: FakeClient())
    assert ingest_external._fetch_rows("dataset", cfg, None, None) == []
