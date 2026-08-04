from __future__ import annotations

from datetime import datetime, timedelta, timezone

from okx_quant.data.external_clients.cftc_cot import CFTCCOTClient


def test_tff_fixture_maps_positions_and_tuesday_friday_publication(monkeypatch):
    client = CFTCCOTClient()
    fixture = {
        "id": "260728133741F",
        "market_and_exchange_names": "BITCOIN - CHICAGO MERCANTILE EXCHANGE",
        "contract_market_name": "BITCOIN",
        "cftc_contract_market_code": "133741",
        "cftc_market_code": "CME",
        "cftc_commodity_code": "133",
        "commodity_name": "BITCOIN",
        "report_date_as_yyyy_mm_dd": "2026-07-28T00:00:00.000",
        "open_interest_all": "25000",
        "lev_money_positions_long": "8000",
        "lev_money_positions_short": "5000",
        "lev_money_positions_spread": "1000",
        "dealer_positions_long_all": "2000",
        "dealer_positions_short_all": "6000",
    }
    captured = {}

    def fake_get(endpoint, params):
        captured.update(params)
        return [fixture]

    monkeypatch.setattr(client, "_get", fake_get)
    rows = client.fetch(report_type="tff", contract_market_code="133741")

    assert len(rows) == 1
    assert rows[0]["observed_at"] == datetime(2026, 7, 28, tzinfo=timezone.utc)
    assert rows[0]["published_at"] == datetime(
        2026,
        7,
        31,
        19,
        30,
        tzinfo=timezone.utc,
    )
    assert rows[0]["published_at"] >= rows[0]["observed_at"] + timedelta(days=2)
    assert rows[0]["value_num"] == 3000
    assert rows[0]["fields"]["position_class"] == "leveraged_money"
    assert "cftc_contract_market_code = '133741'" in captured["$where"]


def test_disaggregated_gold_fixture_maps_managed_money(monkeypatch):
    client = CFTCCOTClient()
    fixture = {
        "id": "260728088691F",
        "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
        "contract_market_name": "GOLD",
        "cftc_contract_market_code": "088691",
        "report_date_as_yyyy_mm_dd": "2026-07-28T00:00:00.000",
        "open_interest_all": "500000",
        "m_money_positions_long_all": "150000",
        "m_money_positions_short_all": "60000",
        "m_money_positions_spread": "20000",
    }
    monkeypatch.setattr(client, "_get", lambda endpoint, params: [fixture])

    [row] = client.fetch(
        report_type="disaggregated",
        contract_market_code="088691",
    )

    assert row["value_num"] == 90000
    assert row["fields"]["position_class"] == "managed_money"
    assert row["fields"]["open_interest"] == 500000
