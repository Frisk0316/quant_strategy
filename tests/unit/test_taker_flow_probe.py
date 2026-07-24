import pandas as pd
import pytest

from backtesting.taker_flow_probe import (
    FORMAL_WINDOW,
    REFERENCE_RANGES,
    build_taker_flow_proxy,
    check_distinctness_feasibility,
    parse_taker_fields,
    probe_taker_flow,
    validate_power_declaration,
)


def test_parse_taker_fields_reads_strict_binance_slots():
    raw = [0] * 12
    raw[9], raw[10] = "12.5", "34.75"

    assert parse_taker_fields({"raw": raw}) == (12.5, 34.75)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"raw": [0] * 10},
        {"raw": [0] * 9 + ["bad", "2"]},
        {"raw": [0] * 9 + [-1, "2"]},
        {"raw": [0] * 9 + [True, "2"]},
    ],
)
def test_parse_taker_fields_degrades_malformed_arrays_to_missing(payload):
    assert parse_taker_fields(payload) is None


def test_distinctness_feasibility_accepts_declared_r66_ranges():
    result = check_distinctness_feasibility(FORMAL_WINDOW, REFERENCE_RANGES)

    references = result["references"]
    assert references["F-FUNDING-XS-DISPERSION"]["achievable_common_days"] == 779
    assert references["F-VOL-REGIME-OPT"]["achievable_common_days"] == 670
    assert result["joint_achievable_common_days"] == 670


def test_power_declaration_discards_generic_caller_estimates():
    assert validate_power_declaration(
        {
            "breadth": 6,
            "n_obs": 900,
            "n_trials": 4,
            "plausible_net_sharpe": 0.8,
        }
    ) == {"breadth": 6.0, "n_trials": 4}


@pytest.mark.parametrize(
    ("reference_ranges", "message"),
    [
        (
            {"F-FUNDING-XS-DISPERSION": REFERENCE_RANGES["F-FUNDING-XS-DISPERSION"]},
            "missing declared reference ranges",
        ),
        (
            {
                "F-FUNDING-XS-DISPERSION": REFERENCE_RANGES[
                    "F-FUNDING-XS-DISPERSION"
                ],
                "F-VOL-REGIME-OPT": {
                    "start": "2026-01-01",
                    "end_exclusive": "2026-02-01",
                },
            },
            "insufficient achievable common days",
        ),
    ],
)
def test_distinctness_feasibility_refuses_missing_or_insufficient_ranges(
    reference_ranges, message
):
    with pytest.raises(ValueError, match=message):
        check_distinctness_feasibility(FORMAL_WINDOW, reference_ranges)


def test_proxy_formula_ranking_weekly_weights_and_t_plus_one_open():
    dates = pd.date_range("2024-01-01", periods=150)
    symbols = [f"S{i}" for i in range(10)]
    transitions = [50, 60, 70, 80, 90] * 2
    rows = []
    for offset, day in enumerate(dates):
        for index, symbol in enumerate(symbols):
            net_flow_ratio = (1 if index < 5 else -1) * (
                0.6 if offset >= transitions[index] else 0.0
            )
            price = (
                110.0
                if day >= pd.Timestamp("2024-05-01") and symbol in {"S3", "S4"}
                else 90.0
                if day >= pd.Timestamp("2024-05-01") and symbol in {"S8", "S9"}
                else 100.0
            )
            rows.append(
                {
                    "day": day,
                    "symbol": symbol,
                    "open": price,
                    "close": price,
                    "volume": 1_000.0,
                    "taker_buy_base": (1.0 + net_flow_ratio) * 500.0,
                }
            )
    panel = pd.DataFrame(rows)
    universe = {day.date().isoformat(): tuple(symbols) for day in dates}

    proxy = build_taker_flow_proxy(panel, universe)
    monday = pd.Timestamp("2024-04-29")
    tuesday = monday + pd.Timedelta(days=1)
    s4 = panel.loc[(panel["symbol"] == "S4") & panel["day"].le(monday)].tail(30)
    expected_ratio = (
        2.0 * s4["taker_buy_base"].sum() - s4["volume"].sum()
    ) / s4["volume"].sum()
    assert proxy["net_flow_ratio"].at[monday, "S4"] == pytest.approx(expected_ratio)

    own_history = proxy["net_flow_ratio"]["S4"].loc[:monday].dropna().tail(90)
    expected_own_z = (own_history.iloc[-1] - own_history.mean()) / own_history.std()
    assert proxy["own_z"].at[monday, "S4"] == pytest.approx(expected_own_z)
    own_z = proxy["own_z"].loc[monday]
    expected_xs_z = (own_z["S4"] - own_z.mean()) / own_z.std()
    assert proxy["xs_z"].at[monday, "S4"] == pytest.approx(expected_xs_z)

    expected_weights = dict.fromkeys(symbols, 0.0)
    expected_weights.update({"S3": 0.25, "S4": 0.25, "S8": -0.25, "S9": -0.25})
    assert proxy["weights"].loc[monday].to_dict() == pytest.approx(expected_weights)
    assert not proxy["positions"].loc[monday].any()
    assert proxy["positions"].loc[tuesday].to_dict() == pytest.approx(expected_weights)
    assert proxy["gross_returns"].loc[tuesday] == pytest.approx(0.10)


@pytest.mark.asyncio
async def test_probe_degrades_empty_panel_to_three_failed_checks(tmp_path):
    universe_path = tmp_path / "universe.parquet"
    pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "symbol": "BTC-USDT-SWAP",
                "eligible": False,
                "adv_usd": 1.0,
            }
        ]
    ).to_parquet(universe_path, index=False)

    class Transaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class EmptyConnection:
        def transaction(self, *, readonly):
            assert readonly is True
            return Transaction()

        async def execute(self, _query):
            return None

        async def fetch(self, *_args):
            return []

    result = await probe_taker_flow(
        EmptyConnection(),
        {
            "universe_path": universe_path,
            "start": "2024-01-01",
            "end": "2026-06-17",
            "statistical_power": {"breadth": 6, "n_trials": 4},
            "reference_ranges": REFERENCE_RANGES,
            "reference_series": {
                "F-FUNDING-XS-DISPERSION": {},
                "F-VOL-REGIME-OPT": {},
            },
        },
    )

    checks = {check.name: check for check in result.checks}
    assert set(checks) == {"data_availability", "distinctness", "cost_after_edge"}
    assert {check.status for check in checks.values()} == {"FAIL"}
    assert checks["cost_after_edge"].details["n_obs"] == 0
