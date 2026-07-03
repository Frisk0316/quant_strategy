from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from okx_quant.data.external_clients import OKXLiquidationClient
from scripts.market_data import ingest_external

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_okx_liquidation_client_normalizes_sides_notional_and_raw_fields(monkeypatch):
    client = OKXLiquidationClient()
    seen = {}

    def fake_get(params):
        seen.update(params)
        return {
            "code": "0",
            "data": [
                {
                    "instId": "BTC-USDT-SWAP",
                    "instType": "SWAP",
                    "uly": "BTC-USDT",
                    "details": [
                        {"ts": "1704070800000", "posSide": "long", "side": "sell", "sz": "2", "bkPx": "40000"},
                        {"ts": "1704074400000", "posSide": "short", "side": "buy", "sz": "3", "bkPx": "41000"},
                    ],
                }
            ],
        }

    monkeypatch.setattr(client, "_get", fake_get)

    rows = client.fetch(
        inst_type="SWAP",
        inst_id="BTC-USDT-SWAP",
        contract_value=0.01,
        start=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 3, tzinfo=timezone.utc),
    )

    assert seen["instType"] == "SWAP"
    assert seen["uly"] == "BTC-USDT"
    assert "instId" not in seen
    assert seen["state"] == "filled"
    assert [row["fields"]["pos_side"] for row in rows] == ["long", "short"]
    assert [row["fields"]["side"] for row in rows] == ["sell", "buy"]
    assert [row["value_num"] for row in rows] == [800.0, 1230.0]
    assert rows[0]["observed_at"] == datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["fields"]["unit"] == "USDT_notional"
    assert rows[0]["fields"]["source_value_field"] == "sz*bkPx*contract_value"
    assert rows[0]["raw_payload"]["detail"]["bkPx"] == "40000"


def test_okx_liquidation_client_keeps_partial_rows_without_notional(monkeypatch):
    client = OKXLiquidationClient()

    monkeypatch.setattr(
        client,
        "_get",
        lambda params: {
            "code": "0",
            "data": [
                {
                    "instId": "ETH-USDT-SWAP",
                    "details": [
                        {"ts": "1704070800000", "posSide": "long", "side": "sell", "sz": "5"},
                    ],
                }
            ],
        },
    )

    rows = client.fetch(inst_type="SWAP", inst_id="ETH-USDT-SWAP", contract_value=0.01)

    assert len(rows) == 1
    assert rows[0]["value_num"] is None
    assert rows[0]["fields"]["notional_status"] == "missing_price_or_size"
    assert rows[0]["raw_payload"]["detail"]["sz"] == "5"


def test_okx_liquidation_client_backs_off_on_rate_limit():
    calls = 0
    sleeps = []

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0.25"}, request=request)
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    {
                        "instId": "BTC-USDT-SWAP",
                        "details": [
                            {"ts": "1704070800000", "posSide": "long", "side": "sell", "sz": "1", "bkPx": "40000"},
                        ],
                    }
                ],
            },
            request=request,
        )

    client = OKXLiquidationClient(transport=httpx.MockTransport(handler), sleep=sleeps.append, retries=1)

    rows = client.fetch(inst_type="SWAP", inst_id="BTC-USDT-SWAP", contract_value=0.01)

    assert calls == 2
    assert sleeps == [0.25]
    assert rows[0]["value_num"] == 400.0


def test_builtin_liquidation_contract_values_match_seed_specs():
    """OKX liquidation notional uses sz*bkPx*ct_val; a wrong ct_val silently
    mis-scales every ingested row (ETH 0.01-vs-0.1 would be 10x understated).
    Pin BUILT_IN_DATASETS to the ADR-0007 seed SQL truth source."""
    seed_sql = (REPO_ROOT / "sql" / "seed_venue_instrument_specs.sql").read_text(encoding="utf-8")
    seed_ct_vals = {
        symbol: float(ct_val)
        for symbol, ct_val in re.findall(
            r"\('okx',\s*'([A-Z0-9-]+)',\s*([0-9.]+)", seed_sql
        )
    }
    checked = 0
    for dataset_id, cfg in ingest_external.BUILT_IN_DATASETS.items():
        if cfg.get("adapter") != "okx_liquidation":
            continue
        inst_id = cfg["inst_id"]
        assert inst_id in seed_ct_vals, f"{dataset_id}: {inst_id} missing from seed SQL"
        assert cfg["contract_value"] == seed_ct_vals[inst_id], (
            f"{dataset_id}: contract_value {cfg['contract_value']} != "
            f"seed ct_val {seed_ct_vals[inst_id]} for {inst_id}"
        )
        checked += 1
    assert checked >= 2  # BTC and ETH at minimum


def test_builtin_liquidation_dataset_dry_run_dispatch(tmp_path, monkeypatch):
    config_path = tmp_path / "external_data.yaml"
    config_path.write_text("datasets: {}\n", encoding="utf-8")
    built = []

    class FakeClient:
        def fetch(self, **kwargs):
            built.append(kwargs)
            return []

    monkeypatch.setattr(ingest_external, "_build_client", lambda dataset_id, cfg: FakeClient())
    datasets = ingest_external._load_external_config(str(config_path))

    assert datasets["liq_okx_btc"]["adapter"] == "okx_liquidation"
    assert datasets["liq_okx_btc"]["fail_on_empty_fetch"] is True
    assert ingest_external._fetch_rows("liq_okx_btc", datasets["liq_okx_btc"], None, None) == []
    assert built == [{
        "inst_type": "SWAP",
        "uly": "BTC-USDT",
        "inst_family": None,
        "inst_id": "BTC-USDT-SWAP",
        "state": "filled",
        "contract_value": 0.01,
        "start": None,
        "end": None,
    }]
