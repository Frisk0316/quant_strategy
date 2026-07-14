"""ADR-0011 shadow-only signal, intent, fill, journal, and report checks."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from okx_quant.execution.deribit_shadow import runner
from okx_quant.execution.deribit_shadow.runner import (
    Journal,
    build_bias_report,
    build_intent_legs,
    compute_signal_rows,
    load_config,
    run_cycle,
    validate_intent_set,
)
from research.probes.f_vol_regime_opt_probe import build_series


CONFIG = Path("config/h014_shadow.yaml")


def _signal(currency: str, *, rich: bool = True) -> dict:
    px = 50_000.0 if currency == "BTC" else 3_000.0
    return {
        "date": "2026-07-13",
        "currency": currency,
        "instrument": f"{currency}-USDT-SWAP",
        "dvol": 60.0,
        "px": px,
        "rv": 40.0,
        "vrp": 20.0,
        "z": 0.75 if rich else 0.0,
        "ivp": 90.0 if rich else 50.0,
        "rich": rich,
        "as_of": "2026-07-14T00:00:00Z",
        "source": "db_f26_asof",
    }


class FakePublicClient:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def instruments(self, currency: str) -> list[dict]:
        expiry = int((self.now + timedelta(days=30)).timestamp() * 1000)
        base = 50_000 if currency == "BTC" else 3_000
        rows = []
        for strike in (base * 1.1, base * 1.2):
            rows.append(
                {
                    "instrument_name": f"{currency}-EXP-{strike:g}-C",
                    "expiration_timestamp": expiry,
                    "option_type": "call",
                    "strike": strike,
                }
            )
        for strike in (base * 0.9, base * 0.8, base * 0.7):
            rows.append(
                {
                    "instrument_name": f"{currency}-EXP-{strike:g}-P",
                    "expiration_timestamp": expiry,
                    "option_type": "put",
                    "strike": strike,
                }
            )
        return rows

    def order_book(self, instrument: str) -> dict:
        base = 50_000 if instrument.startswith("BTC") else 3_000
        return {
            "timestamp": int(self.now.timestamp() * 1000),
            "bids": [[0.010, 2.0]],
            "asks": [[0.012, 3.0]],
            "mark_price": 0.011,
            "mark_iv": 62.0,
            "underlying_price": base,
        }

    def day_vwap(self, instrument: str, day: date) -> dict:
        return {"vwap_coin": 0.011, "amount": 4.0, "trade_count": 2}

    def delivery_price(self, currency: str, expiry: date) -> float:
        return 60_000.0 if currency == "BTC" else 3_500.0


def test_config_is_shadow_only_and_frozen(tmp_path: Path):
    config = load_config(CONFIG)
    assert config["mode"] == "shadow_only"
    assert config["public_api_url"].endswith("/public")

    changed = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    changed["signal"]["ivp_min"] = 84
    path = tmp_path / "changed.yaml"
    path.write_text(yaml.safe_dump(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="user approval"):
        load_config(path)

    changed = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    changed["deribit_api_key"] = "must-never-be-present"
    path.write_text(yaml.safe_dump(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="credentials are forbidden"):
        load_config(path)

    changed = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    changed["public_api_url"] = "https://www.deribit.com:443/api/v2/public"
    path.write_text(yaml.safe_dump(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="credential-free Deribit public API"):
        load_config(path)


def test_signal_reproduces_research_series_on_five_days():
    start = date(2024, 1, 1)
    days = [(start + timedelta(days=i)).isoformat() for i in range(430)]
    dvol = {day: 60 + 8 * math.sin(i / 17) + 0.01 * i for i, day in enumerate(days)}
    closes = {day: 40_000 * math.exp(0.0005 * i + 0.02 * math.sin(i / 11)) for i, day in enumerate(days)}
    expected = build_series(dvol, closes)
    actual = compute_signal_rows(dvol, closes)
    samples = [row for row in expected if "ivp" in row and "z" in row][-5:]
    by_day = {row["date"]: row for row in actual}
    assert len(samples) == 5
    for row in samples:
        assert abs(by_day[row["date"]]["ivp"] - row["ivp"]) < 0.5
        assert abs(by_day[row["date"]]["z"] - row["z"]) < 0.05


@pytest.mark.asyncio
async def test_db_signal_uses_published_at_asof_and_no_public_client():
    start = date(2024, 1, 1)
    as_of = datetime.combine(start + timedelta(days=421), datetime.min.time(), tzinfo=timezone.utc)

    class FakeConnection:
        def __init__(self, *, stale: bool = False) -> None:
            self.queries = []
            self.stale = stale

        async def fetch(self, query, *args):
            self.queries.append((query, args))
            if "external_observations" in query:
                return [
                    {
                        "day": start + timedelta(days=i),
                        "value_num": 55 + 7 * math.sin(i / 19) + i * 0.01,
                        "published_at": datetime.combine(
                            start + timedelta(days=i), datetime.min.time(), tzinfo=timezone.utc
                        )
                        + timedelta(hours=23),
                    }
                    for i in range(421)
                ]
            return [
                {
                    "day": start + timedelta(days=i),
                    "close": 40_000 * math.exp(i * 0.0004 + 0.015 * math.sin(i / 13)),
                    "source_ts": None,
                }
                for i in range(420 if self.stale else 421)
            ]

    conn = FakeConnection()
    signals = await runner._signals_from_connection(conn, load_config(CONFIG), as_of)
    assert set(signals) == {"BTC", "ETH"}
    assert signals["BTC"]["date"] == (as_of.date() - timedelta(days=1)).isoformat()
    dvol_sql, dvol_args = conn.queries[0]
    assert "published_at <= $2" in dvol_sql
    assert "PARTITION BY (observed_at AT TIME ZONE 'UTC')::date" in dvol_sql
    assert dvol_args[1] == as_of
    assert all("www.deribit.com" not in query for query, _ in conn.queries)
    assert "INTERVAL '8 hours'" in conn.queries[1][0]
    with pytest.raises(RuntimeError, match="stale DB signal"):
        await runner._signals_from_connection(FakeConnection(stale=True), load_config(CONFIG), as_of)


def test_naked_put_and_unit_cap_rejected():
    short_put = {
        "currency": "BTC",
        "expiry": "2026-08-14",
        "kind": "put",
        "side": "sell",
        "strike": 45_000,
        "units": 1 / 30,
    }
    with pytest.raises(ValueError, match="naked short put"):
        validate_intent_set([short_put], tranche_units=1 / 30, open_units=0)
    with pytest.raises(ValueError, match="unit cap"):
        validate_intent_set([], tranche_units=1 / 30, open_units=1.0)


def test_intent_uses_current_nearest_30d_chain_and_put_spread():
    now = datetime(2026, 7, 14, 9, tzinfo=timezone.utc)
    client = FakePublicClient(now)
    legs = build_intent_legs("BTC", _signal("BTC"), client.instruments("BTC"), now)
    validate_intent_set(legs, tranche_units=1 / 30, open_units=0)
    assert [leg["leg"] for leg in legs] == ["call_25d", "put_25d", "put_10d"]
    assert next(leg for leg in legs if leg["leg"] == "put_10d")["strike"] < next(
        leg for leg in legs if leg["leg"] == "put_25d"
    )["strike"]


@pytest.mark.asyncio
async def test_cycle_fills_sells_at_bid_buys_at_ask_and_dedupes(tmp_path: Path, monkeypatch):
    now = datetime(2026, 7, 14, 9, tzinfo=timezone.utc)
    config = load_config(CONFIG)
    config["journal_path"] = str(tmp_path / "journal.jsonl")

    async def fake_signals(*_args, **_kwargs):
        return {currency: _signal(currency) for currency in ("BTC", "ETH")}

    monkeypatch.setattr(runner, "load_signals", fake_signals)
    client = FakePublicClient(now)
    first = await run_cycle(config, "unused", now=now, client=client)
    original = Path(config["journal_path"]).read_text(encoding="utf-8")
    second = await run_cycle(config, "unused", now=now, client=client)
    assert {row["status"] for row in first["intents"]} == {"filled"}
    assert second["intents"] == []
    assert Path(config["journal_path"]).read_text(encoding="utf-8") == original
    intents = [row for row in Journal(config["journal_path"]).records if row["event_type"] == "intent"]
    for intent in intents:
        prices = {leg["side"]: leg["fill"]["price_coin"] for leg in intent["legs"]}
        assert prices == {"sell": 0.010, "buy": 0.012}
        assert {leg["book"]["spread"] for leg in intent["legs"]} == {0.002}


@pytest.mark.asyncio
async def test_stale_audit_record_does_not_block_corrected_signal(tmp_path: Path, monkeypatch):
    now = datetime(2026, 7, 14, 9, tzinfo=timezone.utc)
    config = load_config(CONFIG)
    config["journal_path"] = str(tmp_path / "journal.jsonl")
    stale = _signal("BTC", rich=False)
    stale["date"] = "2026-07-10"
    Journal(config["journal_path"]).append(
        {
            "schema_version": 1,
            "event_id": "intent:h014:2026-07-14:BTC",
            "event_type": "intent",
            "intent_id": "h014:2026-07-14:BTC",
            "ts": "2026-07-14T08:01:00Z",
            "event_date": "2026-07-14",
            "currency": "BTC",
            "signal": stale,
            "status": "not_rich",
            "intent": None,
            "legs": [],
        }
    )

    async def fake_signals(*_args, **_kwargs):
        return {currency: _signal(currency, rich=False) for currency in ("BTC", "ETH")}

    monkeypatch.setattr(runner, "load_signals", fake_signals)
    summary = await run_cycle(config, "unused", now=now, client=FakePublicClient(now))
    assert summary["intents"] == [
        {"currency": "BTC", "status": "not_rich"},
        {"currency": "ETH", "status": "not_rich"},
    ]
    assert build_bias_report(config["journal_path"])["exit_criteria"][
        "ignored_stale_signal_records"
    ] == 1


def test_settlement_reuses_r8_accounting(tmp_path: Path):
    now = datetime(2026, 7, 14, 9, tzinfo=timezone.utc)
    journal = Journal(tmp_path / "journal.jsonl")
    position_id = "h014:old:BTC:call_25d"
    journal.append(
        {
            "schema_version": 1,
            "event_id": "intent:old",
            "event_type": "intent",
            "intent_id": "h014:old:BTC",
            "ts": "2026-06-14T09:00:00Z",
            "event_date": "2026-06-14",
            "currency": "BTC",
            "signal": _signal("BTC"),
            "status": "filled",
            "intent": {"entry_date": "2026-06-14", "expiry": "2026-07-14", "units": 1 / 30},
            "legs": [
                {
                    "position_id": position_id,
                    "leg": "call_25d",
                    "instrument": "BTC-14JUL26-55000-C",
                    "kind": "call",
                    "side": "sell",
                    "strike": 55_000,
                    "expiry_timestamp": int(datetime(2026, 7, 14, 8, tzinfo=timezone.utc).timestamp() * 1000),
                    "units": 1 / 30,
                    "book": {"mark_iv": 60.0},
                    "fill": {"price_coin": 0.01},
                }
            ],
            "pnl_coin": -0.00001,
        }
    )
    counts = runner._mark_or_settle(FakePublicClient(now), journal, {"BTC": _signal("BTC")}, now)
    assert counts["settlements"] == 1
    record = journal.records[-1]
    payoff = (60_000 - 55_000) / 60_000
    assert record["payoff_coin"] == pytest.approx(payoff)
    assert record["settlement_fee_coin"] == pytest.approx(0.00015 / 30)


def test_three_day_bias_report_outputs_exit_metrics(tmp_path: Path):
    journal = Journal(tmp_path / "journal.jsonl")
    day1_signal = _signal("BTC")
    day1_signal["date"] = "2026-06-30"
    legs = []
    for leg, side, fill in (("call_25d", "sell", 0.010), ("put_25d", "sell", 0.009), ("put_10d", "buy", 0.004)):
        legs.append(
            {
                "position_id": f"p:{leg}",
                "leg": leg,
                "side": side,
                "instrument": leg,
                "fill": {"price_coin": fill},
            }
        )
    journal.append(
        {
            "schema_version": 1,
            "event_id": "intent:day1",
            "event_type": "intent",
            "intent_id": "day1",
            "ts": "2026-07-01T09:00:00Z",
            "event_date": "2026-07-01",
            "currency": "BTC",
            "signal": day1_signal,
            "status": "filled",
            "intent": {"entry_date": "2026-07-01", "expiry": "2026-08-01", "units": 1 / 30},
            "legs": legs,
            "pnl_coin": -0.00002,
        }
    )
    for leg in legs:
        journal.append(
            {
                "schema_version": 1,
                "event_id": f"vwap:{leg['position_id']}",
                "event_type": "vwap",
                "ts": "2026-07-02T09:00:00Z",
                "event_date": "2026-07-02",
                "currency": "BTC",
                "position_id": leg["position_id"],
                "leg": leg["leg"],
                "side": leg["side"],
                "fill_price_coin": leg["fill"]["price_coin"],
                "vwap_coin": leg["fill"]["price_coin"] + 0.001,
            }
        )
    journal.append(
        {
            "schema_version": 1,
            "event_id": "mark:p:call_25d",
            "event_type": "mark",
            "ts": "2026-07-02T09:00:00Z",
            "event_date": "2026-07-02",
            "currency": "BTC",
            "position_id": "p:call_25d",
            "tracking_error_coin": 0.0004,
            "pnl_coin": 0.0001,
        }
    )
    for day, status in (("2026-07-02", "missed_entry"), ("2026-07-03", "not_rich")):
        signal = _signal("BTC", rich=status != "not_rich")
        signal["date"] = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        journal.append(
            {
                "schema_version": 1,
                "event_id": f"intent:{day}",
                "event_type": "intent",
                "intent_id": day,
                "ts": f"{day}T09:00:00Z",
                "event_date": day,
                "currency": "BTC",
                "signal": signal,
                "status": status,
                "intent": None,
                "legs": [],
            }
        )
    report = build_bias_report(journal.path)
    criteria = report["exit_criteria"]
    assert criteria["missed_entry_rate"] == pytest.approx(0.5)
    assert set(criteria["fill_bias_per_leg"]) == {"call_25d", "put_25d", "put_10d"}
    assert criteria["mark_tracking_error_coin"]["samples"] == 1
    assert criteria["distinct_journal_weeks"] == 1
    assert criteria["eight_week_journal_met"] is False
    assert criteria["live_adr_discussion_unlocked"] is False
    assert criteria["live_trading_approved"] is False
    assert criteria["ignored_stale_signal_records"] == 0
    assert len(report["shadow_equity_curve_coin"]["BTC"]) == 2


def test_report_does_not_treat_sparse_span_as_eight_week_journal(tmp_path: Path):
    journal = Journal(tmp_path / "journal.jsonl")
    for index, event_day in enumerate((date(2026, 1, 1), date(2026, 3, 1))):
        signal = _signal("BTC", rich=False)
        signal["date"] = (event_day - timedelta(days=1)).isoformat()
        journal.append(
            {
                "schema_version": 1,
                "event_id": f"intent:sparse:{index}",
                "event_type": "intent",
                "intent_id": f"sparse:{index}",
                "ts": f"{event_day.isoformat()}T09:00:00Z",
                "event_date": event_day.isoformat(),
                "currency": "BTC",
                "signal": signal,
                "status": "not_rich",
                "intent": None,
                "legs": [],
            }
        )
    criteria = build_bias_report(journal.path)["exit_criteria"]
    assert criteria["journal_weeks"] >= 8
    assert criteria["distinct_journal_weeks"] == 2
    assert criteria["eight_week_journal_met"] is False


def test_public_client_rejects_non_allowlisted_method():
    client = runner.DeribitPublicClient(
        "https://www.deribit.com/api/v2/public",
        transport=runner.httpx.MockTransport(lambda _request: pytest.fail("network called")),
    )
    try:
        with pytest.raises(ValueError, match="not allowed"):
            client._get("private/buy")
    finally:
        client.close()
