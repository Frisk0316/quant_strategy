import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, result_to_dict
import backtesting.pipeline_stage2_registry as registry


@pytest.mark.asyncio
async def test_run_data_probe_rejects_missing_power_inputs_before_connect(tmp_path, monkeypatch):
    async def forbidden_connect(_dsn):
        raise AssertionError("connect called")

    monkeypatch.setattr(registry, "_connect", forbidden_connect)

    with pytest.raises(ValueError, match="statistical power inputs"):
        await registry.run_data_probe(
            dsn="postgresql://example",
            output_root=tmp_path,
            universe_path=tmp_path / "universe.parquet",
            candidates=["funding"],
            statistical_power=None,
        )


@pytest.mark.asyncio
async def test_stage2_registry_uses_family_ids_and_uniform_probe_signature(monkeypatch):
    calls = []

    async def fake_funding(conn, *, universe_path, start, end, thresholds):
        calls.append(("funding", conn, universe_path, start, end, type(thresholds).__name__))
        return FeasibilityResult("batch", "candidate", "dir", "H-1", "F-FUNDING-XS-DISPERSION", ())

    async def fake_xvenue(conn, *, start, end, thresholds):
        calls.append(("xvenue", conn, start, end, type(thresholds).__name__))
        return FeasibilityResult("batch", "candidate", "dir", "H-2", "F-XVENUE-LEADLAG", ())

    async def fake_oi_universe(conn, *, universe_path, start, end, thresholds):
        calls.append(("oi", conn, universe_path, start, end, type(thresholds).__name__))
        return FeasibilityResult("batch", "candidate", "dir", "H-3", "F-OI-POSITIONING", ())

    monkeypatch.setattr(registry, "probe_funding", fake_funding)
    monkeypatch.setattr(registry, "probe_xvenue", fake_xvenue)
    monkeypatch.setattr(registry, "probe_oi_universe", fake_oi_universe)

    ctx = {
        "universe_path": "universe.parquet",
        "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 1, 2, tzinfo=timezone.utc),
    }

    assert set(registry.STAGE2_PROBES) == {
        "F-FUNDING-XS-DISPERSION",
        "F-OI-POSITIONING",
        "F-XVENUE-LEADLAG",
        "F-XVENUE-FUNDING-SPREAD",
    }

    funding = await registry.STAGE2_PROBES["F-FUNDING-XS-DISPERSION"]("conn", ctx)
    oi = await registry.STAGE2_PROBES["F-OI-POSITIONING"]("conn", ctx)
    xvenue = await registry.STAGE2_PROBES["F-XVENUE-LEADLAG"]("conn", ctx)

    assert funding.family_id == "F-FUNDING-XS-DISPERSION"
    assert oi.family_id == "F-OI-POSITIONING"
    assert xvenue.family_id == "F-XVENUE-LEADLAG"
    assert calls == [
        ("funding", "conn", Path("universe.parquet"), ctx["start"], ctx["end"], "FundingThresholds"),
        ("oi", "conn", Path("universe.parquet"), ctx["start"], ctx["end"], "OIThresholds"),
        ("xvenue", "conn", ctx["start"], ctx["end"], "VenueThresholds"),
    ]


def _otherwise_passing_stage2() -> FeasibilityResult:
    return FeasibilityResult(
        "batch",
        "candidate",
        "candidate_dir",
        "H-019",
        "F-ONCHAIN-FLOW",
        (
            FeasibilityCheck("data_availability", "PASS", "ok"),
            FeasibilityCheck("distinctness", "PASS", "ok"),
            FeasibilityCheck("cost_after_edge", "PASS", "ok"),
        ),
    )


def test_statistical_power_fail_is_written_into_same_stage2_artifact(tmp_path):
    result = registry.add_statistical_power_check(
        _otherwise_passing_stage2(),
        breadth=1,
        n_obs=900,
        n_trials=4,
        plausible_net_sharpe=0.6,
    )
    path = registry._write_result(tmp_path, result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    power = {row["name"]: row for row in payload["checks"]}["statistical_power"]

    assert payload["stage2_status"] == "FAIL"
    assert power["status"] == "FAIL"
    assert "plausible_net_sharpe=0.6000" in power["reason"]
    assert "min_detectable_sharpe=1.7206" in power["reason"]
    assert power["details"]["n_trials_provenance"] == "caller_declared"
    assert power["details"]["grid_trials_on_unoverridden_fail"] == 0


def test_h014_like_breadth_and_length_pass_power_screen():
    check = registry.build_statistical_power_check(
        breadth=2,
        n_obs=1388,
        n_trials=4,
        plausible_net_sharpe=1.13,
    )

    assert check.status == "PASS"
    assert check.details["min_detectable_sharpe"] == pytest.approx(0.978511, abs=1e-3)


def test_power_override_requires_written_ex_ante_rationale():
    inputs = {
        "breadth": 1,
        "n_obs": 900,
        "n_trials": 4,
        "plausible_net_sharpe": 0.6,
    }

    assert registry.build_statistical_power_check(**inputs, override_rationale="  ").status == "FAIL"
    overridden = registry.build_statistical_power_check(
        **inputs,
        override_rationale="independent event mechanism raises the conservative edge floor",
    )

    assert overridden.status == "PASS"
    assert overridden.details["measured_status"] == "FAIL"
    assert overridden.details["overridden"] is True
    assert result_to_dict(
        registry.add_statistical_power_check(
            _otherwise_passing_stage2(),
            **inputs,
            override_rationale="independent event mechanism raises the conservative edge floor",
        )
    )["stage2_status"] == "PASS"


def test_registered_probe_uses_family_cumulative_trials_from_registry(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(
        "| E-048 | 2026-07-14 | H-019 | F-ONCHAIN-FLOW | baseline | 4 | "
        "`results/f_onchain_flow/summary.json` | statistical-fail | original |\n",
        encoding="utf-8",
    )

    result = registry._with_context_power_screen(
        _otherwise_passing_stage2(),
        {
            "experiment_registry_path": registry_path,
            "statistical_power": {
                "breadth": 1,
                "n_obs": 900,
                "n_trials": 1,
                "plausible_net_sharpe": 0.6,
            },
        },
    )
    power = {check.name: check for check in result.checks}["statistical_power"]

    assert power.details["n_trials"] == 4
    assert power.details["registry_cumulative_n_trials"] == 4
    assert power.details["caller_declared_n_trials"] == 1
    assert power.details["n_trials_provenance"] == "max_registry_actual_and_ex_ante_declared_cumulative"

    prospective = registry._with_context_power_screen(
        _otherwise_passing_stage2(),
        {
            "experiment_registry_path": registry_path,
            "statistical_power": {
                "breadth": 1,
                "n_obs": 900,
                "n_trials": 8,
                "plausible_net_sharpe": 0.6,
            },
        },
    )
    prospective_power = {check.name: check for check in prospective.checks}["statistical_power"]

    assert prospective_power.details["n_trials"] == 8


def test_power_thresholds_cannot_relax_below_policy_floor():
    with pytest.raises(ValueError, match="cannot be below 0.95"):
        registry.build_statistical_power_check(
            breadth=1,
            n_obs=900,
            n_trials=4,
            plausible_net_sharpe=0.6,
            thresholds=registry.StatisticalPowerThresholds(psr_probability=0.90),
        )


def test_context_power_screen_writes_fail_closed_artifact_for_invalid_inputs(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(
        "| E-048 | 2026-07-14 | H-019 | F-ONCHAIN-FLOW | baseline | 4 | "
        "`results/f_onchain_flow/summary.json` | statistical-fail | original |\n",
        encoding="utf-8",
    )
    contexts = (
        {
            "experiment_registry_path": registry_path,
            "statistical_power": {
                "breadth": 0,
                "n_obs": 900,
                "n_trials": 4,
                "plausible_net_sharpe": 0.6,
            },
        },
        {
            "experiment_registry_path": tmp_path / "missing-registry.md",
            "statistical_power": {
                "breadth": 1,
                "n_obs": 900,
                "n_trials": 4,
                "plausible_net_sharpe": 0.6,
            },
        },
    )

    for index, context in enumerate(contexts):
        result = registry._with_context_power_screen(_otherwise_passing_stage2(), context)
        path = registry._write_result(tmp_path / str(index), result)
        payload = json.loads(path.read_text(encoding="utf-8"))
        power = {row["name"]: row for row in payload["checks"]}["statistical_power"]

        assert payload["stage2_status"] == "FAIL"
        assert power["status"] == "FAIL"
        assert power["reason"].startswith("statistical power screen failed closed:")
        assert power["details"]["grid_trials_on_unoverridden_fail"] == 0
        assert power["details"]["error_type"] in {"FileNotFoundError", "ValueError"}
