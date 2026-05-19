from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from backtesting.data_loader import asof_join_features
from okx_quant.data.external_clients.fear_greed import FearGreedClient
from okx_quant.data.external_clients.fred import FREDClient
from okx_quant.data.external_clients.nasdaq_data_link import NasdaqDataLinkClient
from okx_quant.data.external_clients.yfinance_client import YFinanceClient


def test_fear_greed_client_normalizes_payload(monkeypatch):
    client = FearGreedClient()
    monkeypatch.setattr(
        client,
        "_get",
        lambda params: {
            "data": [{
                "value": "17",
                "value_classification": " extreme fear ",
                "timestamp": "1704067200",
                "time_until_update": "123",
            }]
        },
    )

    rows = client.fetch()

    assert rows[0]["observed_at"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == 17.0
    assert rows[0]["value_text"] == "Extreme Fear"
    assert rows[0]["fields"]["time_until_update"] == "123"


def test_fred_client_skips_missing_values_and_applies_lag(monkeypatch):
    client = FREDClient(api_key="test", publish_lag_days=1)
    monkeypatch.setattr(
        client,
        "_get",
        lambda params: {
            "observations": [
                {"date": "2024-01-01", "value": "."},
                {"date": "2024-01-02", "value": "4.01"},
            ]
        },
    )

    rows = client.fetch(series_id="DGS10")

    assert len(rows) == 1
    assert rows[0]["observed_at"] == datetime(2024, 1, 2, tzinfo=timezone.utc)
    assert rows[0]["published_at"] == datetime(2024, 1, 3, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == 4.01


def test_fred_client_rejects_zero_publish_lag():
    with pytest.raises(ValueError, match="publish_lag_days must be >= 1"):
        FREDClient(api_key="test", publish_lag_days=0)


def test_nasdaq_data_link_client_normalizes_ohlcv(monkeypatch):
    client = NasdaqDataLinkClient(api_key="test", publish_lag_days=1)
    monkeypatch.setattr(
        client,
        "_get",
        lambda dataset_code, params: {
            "dataset": {
                "column_names": ["Date", "Open", "High", "Low", "Settle", "Volume"],
                "data": [["2024-01-05", 43000, 44000, 42000, 43500, 1000]],
            }
        },
    )

    rows = client.fetch(dataset_code="CHRIS/CME_BTC1")

    assert rows[0]["observed_at"] == datetime(2024, 1, 5, tzinfo=timezone.utc)
    assert rows[0]["published_at"] == datetime(2024, 1, 6, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == 43500.0
    assert rows[0]["fields"]["open"] == 43000.0
    assert rows[0]["fields"]["close"] == 43500.0


def test_yfinance_client_normalizes_ohlcv(monkeypatch):
    client = YFinanceClient(publish_lag_days=1)
    frame = pd.DataFrame(
        {
            "Open": [43000.0],
            "High": [44000.0],
            "Low": [42000.0],
            "Close": [43500.0],
            "Volume": [1000],
        },
        index=pd.DatetimeIndex(["2024-01-05"], name="Date", tz="UTC"),
    )
    monkeypatch.setattr(client, "_download", lambda ticker, start, end, interval: frame)

    rows = client.fetch(ticker="BTC=F", start=datetime(2024, 1, 1, tzinfo=timezone.utc))

    assert rows[0]["observed_at"] == datetime(2024, 1, 5, tzinfo=timezone.utc)
    assert rows[0]["published_at"] == datetime(2024, 1, 6, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == 43500.0
    assert rows[0]["fields"]["ticker"] == "BTC=F"
    assert rows[0]["fields"]["research_only"] is True


def test_yfinance_client_rejects_zero_publish_lag():
    with pytest.raises(ValueError, match="publish_lag_days must be >= 1"):
        YFinanceClient(publish_lag_days=0)


def test_asof_join_features_marks_fresh_stale_and_missing():
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2024-01-01 00:00Z", "2024-01-02 00:00Z"]),
        "published_at": pd.to_datetime(["2024-01-01 00:00Z", "2024-01-02 00:00Z"]),
        "value_num": [10.0, 20.0],
        "value_text": ["A", "B"],
        "fields": [{}, {}],
    })
    timestamps = pd.to_datetime([
        "2023-12-31 23:00Z",
        "2024-01-01 12:00Z",
        "2024-01-04 00:00Z",
    ])

    joined = asof_join_features(timestamps, observations, max_age_seconds=36 * 3600, prefix="fng")

    assert bool(joined.iloc[0]["fng_missing"]) is True
    assert bool(joined.iloc[1]["fng_fresh"]) is True
    assert joined.iloc[1]["fng_value_text"] == "A"
    assert bool(joined.iloc[2]["fng_stale"]) is True
