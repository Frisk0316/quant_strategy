import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, result_to_dict
import backtesting.pipeline_stage2_registry as registry


def _xvenue_power():
    return {
        "breadth": 1,
        "n_obs": 900,
        "n_trials": 4,
        "plausible_net_sharpe": 2.0,
    }


def _taker_power():
    return {"breadth": 6, "n_trials": 4}


def _feasible_reference_ranges():
    return {
        "F-FUNDING-XS-DISPERSION": {
            "start": "2024-01-01",
            "end_exclusive": "2026-06-17",
        },
        "F-VOL-REGIME-OPT": {
            "start": "2022-05-12",
            "end_exclusive": "2026-02-28",
        },
    }


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
    monkeypatch.setattr(registry, "validate_xvenue_leadlag_evidence", lambda evidence: evidence)

    statistical_power = _xvenue_power()
    ctx = {
        "universe_path": "universe.parquet",
        "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 1, 2, tzinfo=timezone.utc),
        "statistical_power": statistical_power,
        "calibration_evidence": {
            "statistical_power": statistical_power,
            "formal_window": {"start": "2020-04-01", "end_exclusive": "2026-06-17"},
        },
        "reference_ranges": _feasible_reference_ranges(),
    }

    assert set(registry.STAGE2_PROBES) == {
        "F-FUNDING-XS-DISPERSION",
        "F-FUNDING-SETTLEMENT-DRIFT",
        "F-OI-POSITIONING",
        "F-XVENUE-LEADLAG",
        "F-XVENUE-FUNDING-SPREAD",
        "F-TAKER-FLOW",
        "F-OPT-HEDGE-DEMAND",
        "F-OPT-MONEYNESS-STRUCTURE",
        "F-XVOL-RATIO",
        "F-VRP-TIMING",
        "F-INTRABAR-PERIODICITY",
        "F-OPT-EXPIRY-GAMMA",
        "F-VOL-OF-VOL",
        "F-MACRO-EVENT-DRIFT",
        "F-VARIANCE-DECOMP",
        "F-OPT-LARGE-TRADE-INFO",
        "F-XASSET-MACRO-LEAD",
        "F-CME-LEADERSHIP",
        "F-S5-RESIDUAL-MEANREV",
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


@pytest.mark.asyncio
async def test_slate_i49_refusal_happens_before_connect_or_artifact(tmp_path, monkeypatch):
    async def forbidden_connect(_dsn):
        raise AssertionError("DB connection opened before whole-slate I49")

    monkeypatch.setattr(registry, "_connect", forbidden_connect)
    monkeypatch.setattr(
        registry,
        "preflight_slate_references",
        lambda: (_ for _ in ()).throw(ValueError("I49 contract stop")),
    )

    with pytest.raises(ValueError, match="I49 contract stop"):
        await registry.run_slate_stage2(
            dsn="postgresql://example",
            output_root=tmp_path,
        )

    assert not any(tmp_path.rglob("*"))


def test_slate_registry_has_all_eight_candidate_specs():
    assert [registry.CANDIDATES[key].hypothesis_id for key in registry.SLATE_CANDIDATES] == [
        "H-030",
        "H-031",
        "H-035",
        "H-033",
        "H-036",
        "H-032",
        "H-034",
        "H-037",
    ]


@pytest.mark.asyncio
async def test_registered_xvenue_probe_refuses_missing_frozen_evidence_before_probe(monkeypatch):
    async def forbidden_probe(*_args, **_kwargs):
        raise AssertionError("xvenue probe ran without frozen calibration evidence")

    monkeypatch.setattr(registry, "probe_xvenue", forbidden_probe)

    with pytest.raises(ValueError, match="requires frozen calibration evidence"):
        await registry.STAGE2_PROBES["F-XVENUE-LEADLAG"](
            "conn",
            {
                "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "end": datetime(2024, 1, 2, tzinfo=timezone.utc),
            },
        )


@pytest.mark.asyncio
async def test_registered_xvenue_probe_refuses_missing_reference_ranges_before_probe_or_artifact(
    tmp_path, monkeypatch
):
    async def forbidden_probe(*_args, **_kwargs):
        raise AssertionError("xvenue probe ran without declared reference ranges")

    power = _xvenue_power()
    monkeypatch.setattr(registry, "probe_xvenue", forbidden_probe)
    monkeypatch.setattr(registry, "validate_xvenue_leadlag_evidence", lambda evidence: evidence)

    with pytest.raises(ValueError, match="declared reference_ranges are required"):
        await registry.STAGE2_PROBES["F-XVENUE-LEADLAG"](
            "conn",
            {
                "output_root": tmp_path,
                "start": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "end": datetime(2026, 6, 17, tzinfo=timezone.utc),
                "statistical_power": power,
                "calibration_evidence": {
                    "statistical_power": power,
                    "formal_window": {
                        "start": "2020-04-01",
                        "end_exclusive": "2026-06-17",
                    },
                },
            },
        )

    assert not any(tmp_path.rglob("*"))


@pytest.mark.asyncio
async def test_run_data_probe_refuses_e057_distinctness_before_connect_or_artifact(
    tmp_path, monkeypatch
):
    async def forbidden_connect(_dsn):
        raise AssertionError("DB connection opened before distinctness feasibility validation")

    power = _xvenue_power()
    monkeypatch.setattr(registry, "_connect", forbidden_connect)
    monkeypatch.setattr(registry, "validate_xvenue_leadlag_evidence", lambda evidence: evidence)

    with pytest.raises(ValueError, match="distinctness contract defect"):
        await registry.run_data_probe(
            dsn="postgresql://example",
            output_root=tmp_path,
            universe_path=tmp_path / "unused.parquet",
            candidates=["xvenue"],
            statistical_power=power,
            calibration_evidence={
                "statistical_power": power,
                "formal_window": {
                    "start": "2020-01-01",
                    "end_exclusive": "2020-04-01",
                },
            },
            reference_ranges=_feasible_reference_ranges(),
        )

    assert not any(tmp_path.rglob("*"))


@pytest.mark.asyncio
async def test_registered_taker_probe_refuses_missing_reference_ranges_before_probe_or_artifact(
    tmp_path, monkeypatch
):
    async def forbidden_probe(*_args, **_kwargs):
        raise AssertionError("taker probe ran without declared reference ranges")

    monkeypatch.setattr(registry, "probe_taker_flow", forbidden_probe)

    with pytest.raises(ValueError, match="declared reference_ranges are required"):
        await registry.STAGE2_PROBES["F-TAKER-FLOW"](
            "conn",
            {
                "output_root": tmp_path,
                "universe_path": tmp_path / "unused.parquet",
                "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "end": datetime(2026, 6, 17, tzinfo=timezone.utc),
                "statistical_power": _taker_power(),
            },
        )

    assert not any(tmp_path.rglob("*"))


@pytest.mark.asyncio
async def test_registered_taker_probe_derives_power_instead_of_using_caller_estimates(
    tmp_path, monkeypatch
):
    async def fake_probe(_conn, ctx):
        assert ctx["statistical_power"] == _taker_power()
        return FeasibilityResult(
            "e058_taker_flow_stage2_20260724",
            "B-f-taker-flow",
            "f_taker_flow",
            "H-022",
            "F-TAKER-FLOW",
            (
                FeasibilityCheck("data_availability", "PASS", "ok"),
                FeasibilityCheck("distinctness", "PASS", "ok"),
                FeasibilityCheck(
                    "cost_after_edge",
                    "PASS",
                    "ok",
                    {"n_obs": 779, "plausible_net_sharpe": 0.8},
                ),
            ),
        )

    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(
        "| F-TAKER-FLOW | 0 | 2 | E-058 zero-trial Stage-2 probe |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(registry, "probe_taker_flow", fake_probe)

    result = await registry.STAGE2_PROBES["F-TAKER-FLOW"](
        "conn",
        {
            "universe_path": tmp_path / "unused.parquet",
            "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "end": datetime(2026, 6, 17, tzinfo=timezone.utc),
            "statistical_power": {
                "breadth": 6,
                "n_obs": 900,
                "n_trials": 4,
                "plausible_net_sharpe": 99.0,
            },
            "reference_ranges": _feasible_reference_ranges(),
            "experiment_registry_path": registry_path,
        },
    )

    power = {check.name: check for check in result.checks}["statistical_power"]
    assert power.details["n_obs"] == 779
    assert power.details["plausible_net_sharpe"] == 0.8
    assert power.details["registry_cumulative_n_trials"] == 0
    assert power.details["caller_declared_n_trials"] == 4


@pytest.mark.asyncio
async def test_run_data_probe_refuses_missing_taker_power_before_connect_or_artifact(
    tmp_path, monkeypatch
):
    async def forbidden_connect(_dsn):
        raise AssertionError("DB connection opened before E-058 power validation")

    monkeypatch.setattr(registry, "_connect", forbidden_connect)

    with pytest.raises(ValueError, match="n_trials"):
        await registry.run_data_probe(
            dsn="postgresql://example",
            output_root=tmp_path,
            universe_path=tmp_path / "unused.parquet",
            candidates=["taker"],
            statistical_power={"breadth": 6},
            reference_ranges=_feasible_reference_ranges(),
        )

    assert not any(tmp_path.rglob("*"))


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


def test_taker_writer_uses_exact_immutable_artifact_path(tmp_path):
    result = FeasibilityResult(
        "e058_taker_flow_stage2_20260724",
        "B-f-taker-flow",
        "f_taker_flow",
        "H-022",
        "F-TAKER-FLOW",
        (
            FeasibilityCheck("data_availability", "PASS", "ok"),
            FeasibilityCheck("distinctness", "PASS", "ok"),
            FeasibilityCheck("cost_after_edge", "PASS", "ok"),
            FeasibilityCheck("statistical_power", "PASS", "ok"),
        ),
    )

    path = registry._write_result(tmp_path, result)

    assert path == (
        tmp_path / "e058_taker_flow_stage2_20260724" / "stage2_feasibility.json"
    )
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        registry._write_result(tmp_path, result)


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
