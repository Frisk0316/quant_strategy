from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from backtesting import pipeline_stage2_registry as registry
from backtesting.moneyness_vol_probe import (
    DVOL_DATASETS,
    E025,
    E044,
    E050,
    H014,
    REFERENCE_PATHS,
    extract_bucket_shares,
    extract_dvol_ratio,
    extract_vrp_regime_series,
    preflight_distinctness_references,
    validate_power_declaration,
)


def _row(dataset_id: str, hour: int, value: float) -> dict:
    published_at = datetime(2024, 1, 1, hour, tzinfo=timezone.utc)
    return {
        "dataset_id": dataset_id,
        "published_at": published_at,
        "value_num": value,
        "quality_status": "raw",
    }


def test_extract_bucket_shares_from_fixture_rows():
    rows = [
        {
            "dataset_id": "optflow_deribit_btc",
            "published_at": "2024-01-01T08:00:00Z",
            "quality_status": "raw",
            "fields": {
                "premium_volume": 10.0,
                "otm_put_buy_amt": 2.0,
                "atm_premium": 2.0,
                "itm_premium": 3.0,
                "otm_premium": 5.0,
            },
        }
    ]

    frame = extract_bucket_shares(rows)

    assert frame.loc[0, "hedge_demand_share"] == pytest.approx(0.2)
    assert frame.loc[0, "moneyness_share"] == pytest.approx(0.5)


def test_extract_dvol_ratio_from_fixture_rows():
    rows = [
        _row(DVOL_DATASETS["BTC-USDT-SWAP"], 8, 50.0),
        _row(DVOL_DATASETS["ETH-USDT-SWAP"], 8, 75.0),
    ]

    ratio = extract_dvol_ratio(rows)

    assert ratio.iloc[0] == pytest.approx(1.5)


def test_extract_vrp_regime_series_from_fixture_rows():
    rows = []
    for hour, btc_dvol, btc_rv, eth_dvol, eth_rv in (
        (8, 50.0, 40.0, 75.0, 60.0),
        (9, 52.0, 38.0, 76.0, 58.0),
    ):
        rows.extend(
            [
                _row("dvol_deribit_btc_1h", hour, btc_dvol),
                _row("rv30_deribit_btc_1h", hour, btc_rv),
                _row("dvol_deribit_eth_1h", hour, eth_dvol),
                _row("rv30_deribit_eth_1h", hour, eth_rv),
            ]
        )

    frame = extract_vrp_regime_series(rows, median_window_hours=2)

    assert frame.iloc[-1]["btc_vrp"] == pytest.approx(14.0)
    assert frame.iloc[-1]["eth_vrp"] == pytest.approx(18.0)
    assert bool(frame.iloc[-1]["btc_calm"]) is True
    assert bool(frame.iloc[-1]["eth_calm"]) is True


def test_i49_preflight_refuses_missing_dated_e025_before_probe(tmp_path):
    undated = tmp_path / "c1_pairs_ou_summary.json"
    undated.write_text(json.dumps({"cpcv": {"path_returns": [[0.0] * 100]}}), encoding="utf-8")
    days = {
        f"2024-01-{day:02d}": float(day)
        for day in range(1, 29)
    }
    days.update(
        {
            f"2024-02-{day:02d}": float(day)
            for day in range(1, 29)
        }
    )
    days.update(
        {
            f"2024-03-{day:02d}": float(day)
            for day in range(1, 29)
        }
    )
    windows = {
        hypothesis: {"start": "2024-01-01", "end_exclusive": "2024-04-01"}
        for hypothesis in ("H-024", "H-025", "H-026", "H-027")
    }

    with pytest.raises(ValueError, match="no dated daily_returns"):
        preflight_distinctness_references(
            formal_windows=windows,
            reference_series={E044: days, E050: days, H014: days},
            reference_paths={E025: undated},
        )


def test_default_e025_reference_is_dated_csv():
    assert REFERENCE_PATHS[E025].as_posix().endswith(
        "c1_pairs_ou/combo_daily_returns.csv"
    )


def test_registry_wires_all_four_frozen_candidates():
    assert {
        "F-OPT-HEDGE-DEMAND",
        "F-OPT-MONEYNESS-STRUCTURE",
        "F-XVOL-RATIO",
        "F-VRP-TIMING",
    }.issubset(registry.STAGE2_PROBES)
    assert validate_power_declaration(
        "F-VRP-TIMING",
        {"breadth": 2.0, "n_trials": 8},
    ) == {"breadth": 2.0, "n_trials": 8}
