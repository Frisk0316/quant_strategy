import asyncio
import csv
import gzip
import importlib.util
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[2] / "research" / "probes" / "f_vol_regime_opt_stage2.py"
spec = importlib.util.spec_from_file_location("f_vol_regime_opt_stage2", SCRIPT)
stage2 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(stage2)


def test_stage2_sampling_snapshot_legs_and_verdict(tmp_path):
    series = tmp_path / "series.csv"
    with series.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "dvol", "ivp", "regime"])
        writer.writeheader()
        for month in range(1, 9):
            writer.writerow(
                {
                    "date": f"2025-{month:02d}-01",
                    "dvol": 60,
                    "ivp": month * 10,
                    "regime": "NORMAL",
                }
            )
    selected, meta = stage2.load_samples(series, "BTC")
    assert [row["date"] for row in selected] == [
        "2025-01-01",
        "2025-02-01",
        "2025-03-01",
        "2025-06-01",
        "2025-07-01",
        "2025-08-01",
    ]
    assert meta["candidate_count"] == 8
    assert {row["ivp_quartile"] for row in selected[:3]} <= {"Q1", "Q2"}
    assert {row["ivp_quartile"] for row in selected[-3:]} <= {"Q3", "Q4"}

    target = 1_000_000
    rows = [
        {"symbol": "BTC-X-C", "local_timestamp": "900000", "bid_price": "1"},
        {"symbol": "BTC-X-C", "local_timestamp": "1000001", "bid_price": "2"},
        {"symbol": "BTC-X-P", "local_timestamp": "1000001", "bid_price": "3"},
        {"symbol": "BTC-X-C", "local_timestamp": "1000100", "bid_price": "4"},
    ]
    state, snapshot = stage2.read_chain_snapshot(rows, target, {"BTC"})
    assert snapshot == 1_000_001
    assert state["BTC-X-C"]["bid_price"] == "2"
    assert state["BTC-X-P"]["bid_price"] == "3"

    snapshot_dt = datetime(2025, 1, 1, 8, tzinfo=timezone.utc)
    snapshot_us = int(snapshot_dt.timestamp() * 1_000_000)
    expiry_us = snapshot_us + 30 * 86_400 * 1_000_000
    quotes = {}
    for kind, strike, delta, bid, ask in [
        ("call", 90, 0.70, 0.12, 0.14),
        ("put", 90, -0.20, 0.05, 0.07),
        ("call", 100, 0.50, 0.09, 0.11),
        ("put", 100, -0.50, 0.08, 0.10),
        ("call", 110, 0.25, 0.05, 0.07),
        ("put", 110, -0.10, 0.02, 0.04),
        ("put", 105, -0.25, 0.04, 0.06),
    ]:
        suffix = "C" if kind == "call" else "P"
        instrument = f"BTC-31JAN25-{strike}-{suffix}"
        quotes[instrument] = {
            "symbol": instrument,
            "timestamp": str(snapshot_us),
            "local_timestamp": str(snapshot_us),
            "type": kind,
            "strike_price": str(strike),
            "expiration": str(expiry_us),
            "bid_price": str(bid),
            "ask_price": str(ask),
            "underlying_price": "100",
            "delta": str(delta),
        }
    sample = {
        "date": "2025-01-01",
        "selection_bucket": "top_3_ivp",
        "selection_rank": 8,
        "ivp_quartile": "Q4",
        "regime": "RICH",
        "ivp": 90,
        "dvol": 60,
    }
    legs = stage2.extract_legs(quotes, snapshot_us, sample, "BTC")
    assert {row["leg"] for row in legs} == {
        "call_25d",
        "put_25d",
        "put_10d",
        "atm_call",
        "atm_put",
    }
    assert {row["strike"] for row in legs if row["leg"].startswith("atm_")} == {100}
    assert all(row["mid"] > 0 and row["synthetic_bs_on_dvol"] > 0 for row in legs)

    verdict_rows = []
    for symbol in ("BTC", "ETH"):
        for leg in stage2.RICH_SHORT_LEGS:
            verdict_rows.append(
                {
                    "symbol": symbol,
                    "leg": leg,
                    "ivp_quartile": "Q4",
                    "real_to_synthetic_ratio": 0.81,
                }
            )
    assert stage2.verdict(verdict_rows)["status"] == "PASS"
    verdict_rows[0]["real_to_synthetic_ratio"] = 0.79
    assert stage2.verdict(verdict_rows)["status"] == "FAIL"


def test_stage2_r1_uses_bytes_read_guard_not_content_length(monkeypatch):
    date = "2025-01-01"
    target_us = int(datetime(2025, 1, 1, 8, tzinfo=timezone.utc).timestamp() * 1_000_000)
    fields = sorted(stage2.REQUIRED_COLUMNS)
    data = io.StringIO()
    writer = csv.DictWriter(data, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "symbol": "BTC-31JAN25-100-C",
            "timestamp": target_us,
            "local_timestamp": target_us,
            "type": "call",
            "strike_price": 100,
            "expiration": target_us + 30 * 86_400 * 1_000_000,
            "bid_price": 0.1,
            "ask_price": 0.2,
            "underlying_price": 100,
            "delta": 0.5,
        }
    )

    class Response(io.BytesIO):
        headers = {"Content-Length": str(3 * 1024**3)}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    payload = gzip.compress(data.getvalue().encode())
    monkeypatch.setattr(
        stage2.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(payload),
    )
    state, meta = stage2.download_snapshot(date, {"BTC"}, 1024**2, 1)
    assert state
    assert meta["content_length"] == 3 * 1024**3
    assert meta["compressed_bytes_read"] < 1024**2

    with pytest.raises(stage2.SizeLimitError):
        stage2.LimitedReader(io.BytesIO(b"123"), 2).read()


def test_stage2_r1_loads_hourly_dvol_as_of_0800():
    calls = []

    class Connection:
        async def fetchrow(self, _query, dataset_id, snapshot):
            calls.append((dataset_id, snapshot))
            return {
                "observed_at": snapshot - timedelta(hours=1),
                "published_at": snapshot,
                "value_num": 57.5,
            }

        async def close(self):
            pass

    async def connect(dsn):
        assert dsn == "postgresql://test"
        return Connection()

    samples = {
        "BTC": [{"date": "2025-01-01", "dvol": "60"}],
        "ETH": [{"date": "2025-02-01", "dvol": "70"}],
    }
    records = asyncio.run(stage2.load_hourly_dvol("postgresql://test", samples, connect))
    assert [call[0] for call in calls] == ["dvol_deribit_btc_1h", "dvol_deribit_eth_1h"]
    assert all(call[1].hour == 8 and call[1].tzinfo == timezone.utc for call in calls)
    assert samples["BTC"][0]["selection_daily_dvol"] == 60
    assert samples["BTC"][0]["dvol"] == 57.5
    assert len(records) == 2
