from __future__ import annotations

from datetime import datetime, timezone

import pytest

from okx_quant.data.external_clients.cboe import CBOEClient


def test_index_csv_mapping_and_one_day_publish_lag(monkeypatch):
    client = CBOEClient()
    monkeypatch.setattr(
        client,
        "_get_text",
        lambda url: (
            "DATE,OPEN,HIGH,LOW,CLOSE\n"
            "07/28/2026,17.00,18.00,16.50,17.50\n"
        ),
    )

    [row] = client.fetch(
        source_url="https://cdn.cboe.com/example.csv",
        series="VIX",
        kind="index",
    )

    assert row["observed_at"] == datetime(2026, 7, 28, tzinfo=timezone.utc)
    assert row["published_at"] == datetime(2026, 7, 29, tzinfo=timezone.utc)
    assert row["value_num"] == 17.5
    assert row["fields"]["open"] == 17


def test_total_put_call_csv_skips_official_preamble(monkeypatch):
    client = CBOEClient()
    monkeypatch.setattr(
        client,
        "_get_text",
        lambda url: (
            "Volume and Put/Call Ratio data is compiled for convenience,,,,\n"
            ", PRODUCT: TOTAL,,EXCHANGE: Cboe,\n"
            "DATE,CALLS,PUTS,TOTAL,P/C Ratio\n"
            "7/28/2026,100,120,220,1.20\n"
        ),
    )

    [row] = client.fetch(
        source_url="https://cdn.cboe.com/totalpc.csv",
        series="TOTAL_PUT_CALL",
        kind="put_call",
    )

    assert row["value_num"] == 1.2
    assert row["fields"]["calls"] == 100
    assert row["fields"]["puts"] == 120


def test_csv_header_drift_fails_closed(monkeypatch):
    client = CBOEClient()
    monkeypatch.setattr(client, "_get_text", lambda url: "not,the,expected,header\n")

    with pytest.raises(ValueError, match="header not found"):
        client.fetch(
            source_url="https://cdn.cboe.com/moved.csv",
            series="VIX",
            kind="index",
        )
