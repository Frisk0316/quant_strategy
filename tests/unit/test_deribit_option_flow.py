from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pytest

from okx_quant.data.external_clients.deribit_option_flow import (
    DeribitOptionFlowClient,
    aggregate_hourly_option_flow,
    parse_option_instrument,
)
from scripts.market_data import backfill_deribit_option_flow as backfill
from scripts.market_data.backfill_deribit_option_flow import _empty_chunk_error, _parse_dt, resume_start


def _trade(ts: datetime, instrument: str, direction: str, amount: float, price: float, iv: float = 50.0, **extra):
    return {
        "timestamp": int(ts.timestamp() * 1000),
        "instrument_name": instrument,
        "direction": direction,
        "amount": amount,
        "price": price,
        "iv": iv,
        **extra,
    }


def test_parse_option_instrument_excludes_usdc_linear():
    inverse = parse_option_instrument("BTC-26JAN24-58000-C", currency="BTC")
    linear = parse_option_instrument("SOL_USDC-26JAN24-100-C", currency="SOL")

    assert inverse == {
        "base": "BTC",
        "strike": 58000.0,
        "option_type": "C",
        "premium_unit": "BTC",
        "is_inverse": True,
    }
    assert linear["is_inverse"] is False
    assert linear["premium_unit"] == "USDC"


def test_hourly_bucketing_and_imbalance_formula_at_utc_boundary():
    rows = aggregate_hourly_option_flow(
        "BTC",
        [
            _trade(datetime(2024, 1, 1, 0, 59, 59, tzinfo=timezone.utc), "BTC-26JAN24-58000-C", "buy", 2.0, 0.1, 40.0),
            _trade(datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc), "BTC-26JAN24-58000-P", "buy", 1.0, 0.3, 60.0, liquidation=True),
            _trade(datetime(2024, 1, 1, 1, 30, 0, tzinfo=timezone.utc), "BTC-26JAN24-59000-C", "sell", 1.0, 0.2, 80.0),
            _trade(datetime(2024, 1, 1, 1, 45, 0, tzinfo=timezone.utc), "BTC-26JAN24-57000-P", "sell", 4.0, 0.1, 100.0),
        ],
    )

    assert [row["observed_at"] for row in rows] == [
        datetime(2024, 1, 1, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    ]
    assert rows[0]["published_at"] == datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
    assert rows[1]["published_at"] == datetime(2024, 1, 1, 2, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == pytest.approx((0.0 - 0.2) / 0.2)
    assert rows[1]["value_num"] == pytest.approx((0.3 - 0.0) / 0.3)
    assert rows[1]["fields"] == {
        "call_buy_amt": 0.0,
        "call_sell_amt": 0.2,
        "put_buy_amt": 0.3,
        "put_sell_amt": 0.4,
        "premium_volume": 0.9,
        "premium_unit": "BTC",
        "avg_trade_iv": 80.0,
        "trade_count": 3,
        "liq_trade_count": 1,
        "unit": "imbalance_ratio",
        "excluded_linear_usdc_count": 0,
        "moneyness_atm_band": 0.025,
        "atm_premium": 0.0,
        "itm_premium": 0.0,
        "otm_premium": 0.0,
        "atm_trades": 0,
        "itm_trades": 0,
        "otm_trades": 0,
        "otm_put_buy_amt": 0.0,
        "otm_call_buy_amt": 0.0,
        "unbucketed_trade_count": 3,
    }


def test_usdc_only_hour_emits_exclusion_row():
    rows = aggregate_hourly_option_flow(
        "BTC",
        [
            _trade(
                datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
                "BTC_USDC-26JAN24-58000-C",
                "buy",
                2.0,
                100.0,
            ),
        ],
    )

    assert len(rows) == 1
    assert rows[0]["observed_at"] == datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
    assert rows[0]["published_at"] == datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["value_num"] is None
    assert rows[0]["fields"]["trade_count"] == 0
    assert rows[0]["fields"]["excluded_linear_usdc_count"] == 1
    assert rows[0]["raw_payload"]["sample"] == []


def test_option_flow_client_paginates_has_more(monkeypatch):
    client = DeribitOptionFlowClient()
    calls = []
    pages = [
        {"result": {"trades": [{"trade_id": "2", "timestamp": 2000}], "has_more": True}},
        {"result": {"trades": [{"trade_id": "1", "timestamp": 1000}], "has_more": False}},
    ]

    def fake_get(params):
        calls.append(dict(params))
        return pages.pop(0)

    monkeypatch.setattr(client, "_get", fake_get)

    trades = client.fetch_trades(
        currency="BTC",
        start=datetime.fromtimestamp(0, tz=timezone.utc),
        end=datetime.fromtimestamp(3, tz=timezone.utc),
    )

    assert [trade["trade_id"] for trade in trades] == ["1", "2"]
    assert calls[0]["count"] == 1000
    assert calls[0]["sorting"] == "desc"
    assert calls[1]["end_timestamp"] == 1999


def test_resume_start_uses_next_hour_after_checkpoint():
    requested = datetime(2024, 1, 1, tzinfo=timezone.utc)
    checkpoint = datetime(2024, 1, 2, 5, tzinfo=timezone.utc)

    assert resume_start(requested, checkpoint) == checkpoint + timedelta(hours=1)
    assert resume_start(requested, None) == requested


@pytest.mark.asyncio
async def test_checkpoint_cursor_uses_last_success_cursor_after_failure(monkeypatch):
    checkpoint = datetime(2024, 2, 6, 23, tzinfo=timezone.utc)

    class FakeConn:
        async def fetchrow(self, sql, dataset_id):
            assert "status='success'" not in sql
            return {"cursor_time": checkpoint}

        async def close(self):
            return None

    async def fake_connect(dsn):
        return FakeConn()

    monkeypatch.setattr(backfill.asyncpg, "connect", fake_connect)

    assert await backfill._checkpoint_cursor("postgresql://unused", "optflow_deribit_btc") == checkpoint


def test_parse_dt_rejects_non_hour_aligned_bounds():
    with pytest.raises(ValueError, match="hour-aligned"):
        _parse_dt("2024-01-01T00:30:00+00:00")


def test_main_rejects_non_positive_chunk_days(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backfill_deribit_option_flow.py",
            "--start",
            "2024-01-01T00:00:00Z",
            "--end",
            "2024-01-02T00:00:00Z",
            "--chunk-days",
            "0",
        ],
    )
    monkeypatch.setattr(backfill.asyncio, "run", lambda _coro: pytest.fail("backfill should not start"))

    with pytest.raises(SystemExit, match="chunk-days must be positive"):
        backfill.main()


def test_empty_option_flow_chunk_can_advance():
    assert _empty_chunk_error("optflow_deribit_btc", {"fail_on_empty_fetch": True}, []) is None
    assert _empty_chunk_error("optflow_deribit_btc", {"fail_on_empty_fetch": False}, []) is None


def test_option_flow_moneyness_bucket_fields(monkeypatch):
    client = DeribitOptionFlowClient()
    ts = 1_700_000_000_000  # all in one hour bucket
    trades = [
        # atm call buy, itm put buy, otm put buy, otm call sell
        {"instrument_name": "BTC-26DEC26-100000-C", "timestamp": ts, "direction": "buy",
         "amount": 1.0, "price": 0.05, "iv": 50.0, "index_price": 100_000.0},
        {"instrument_name": "BTC-26DEC26-120000-P", "timestamp": ts + 1, "direction": "buy",
         "amount": 1.0, "price": 0.2, "iv": 55.0, "index_price": 100_000.0},
        {"instrument_name": "BTC-26DEC26-80000-P", "timestamp": ts + 2, "direction": "buy",
         "amount": 2.0, "price": 0.01, "iv": 80.0, "index_price": 100_000.0},
        {"instrument_name": "BTC-26DEC26-120000-C", "timestamp": ts + 3, "direction": "sell",
         "amount": 1.0, "price": 0.02, "iv": 70.0, "index_price": 100_000.0},
    ]
    monkeypatch.setattr(
        client, "_get", lambda params: {"result": {"trades": trades, "has_more": False}}
    )
    from datetime import datetime, timedelta, timezone
    start = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
    fields = client.fetch(currency="BTC", start=start, end=start + timedelta(hours=1))[0]["fields"]

    assert fields["moneyness_atm_band"] == 0.025
    assert fields["atm_trades"] == 1
    assert fields["itm_trades"] == 1
    assert fields["otm_trades"] == 2
    assert fields["unbucketed_trade_count"] == 0
    # bucket premiums partition total premium volume
    total = fields["atm_premium"] + fields["itm_premium"] + fields["otm_premium"]
    assert abs(total - fields["premium_volume"]) < 1e-9
    # only taker-BUY OTM amounts are tracked per side
    assert fields["otm_put_buy_amt"] > 0
    assert fields["otm_call_buy_amt"] == 0.0
