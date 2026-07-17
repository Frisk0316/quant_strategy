import json
from datetime import datetime, timezone

import pytest

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.pipeline_feasibility import result_to_dict as stage2_to_dict
from backtesting.pipeline_orchestrator import (
    advance_candidate,
    derive_candidate_dir,
    pre_register_batch,
    render_shortlist,
    run_orchestrator,
)


def _idea_batch(*candidates):
    return {
        "schema_version": 1,
        "batch_id": "idea_batch_20260701_taxonomy_002",
        "source": "B_taxonomy",
        "candidates": list(candidates),
    }


def _candidate(candidate_id="B-f-funding-xs-dispersion", family_id="F-FUNDING-XS-DISPERSION"):
    return {
        "provisional_candidate_id": candidate_id,
        "family_id_or_NEW": family_id,
        "draft_status": "pending_llm",
    }


def _power():
    return {"breadth": 1, "n_obs": 900, "n_trials": 4, "plausible_net_sharpe": 2.0}


def _power_inputs(candidate_id="B-f-funding-xs-dispersion"):
    return {candidate_id: _power()}


def _context(tmp_path, batch_id="idea_batch_20260701_taxonomy_002"):
    return {
        "batch_id": batch_id,
        "output_root": tmp_path,
        "candidate_dir": "f_funding_xs_dispersion",
        "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 1, 2, tzinfo=timezone.utc),
        "universe_path": tmp_path / "universe.parquet",
        "dsn": "postgresql://example",
        "statistical_power_inputs": _power_inputs(),
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _failed_stage2(reason="no data", details=None):
    return FeasibilityResult(
        "idea_batch_20260701_taxonomy_002",
        "B-f-funding-xs-dispersion",
        "f_funding_xs_dispersion",
        "H-009",
        "F-FUNDING-XS-DISPERSION",
        (FeasibilityCheck("data_availability", "FAIL", reason, details or {}),),
    )


def _passing_stage2():
    return FeasibilityResult(
        "idea_batch_20260701_taxonomy_002",
        "B-f-funding-xs-dispersion",
        "f_funding_xs_dispersion",
        "H-009",
        "F-FUNDING-XS-DISPERSION",
        (
            FeasibilityCheck("data_availability", "PASS", "ok", {"rows": 20}),
            FeasibilityCheck("distinctness", "PASS", "ok"),
            FeasibilityCheck("cost_after_edge", "PASS", "ok"),
        ),
    )


def _stage2_failed_state(tmp_path, *, include_hypothesis_id=True):
    batch_id = "idea_batch_20260701_taxonomy_002"
    stage2_path = tmp_path / batch_id / "f_funding_xs_dispersion" / "stage2_feasibility.json"
    _write_json(stage2_path, stage2_to_dict(_failed_stage2(details={"rows": 0})))
    candidate = {
        "candidate_id": "B-f-funding-xs-dispersion",
        "candidate_dir": "f_funding_xs_dispersion",
        "family_id": "F-FUNDING-XS-DISPERSION",
        "status": "stage2_fail",
        "status_history": [{"status": "idea_registered", "at": "t0"}, {"status": "stage2_fail", "at": "t1"}],
        "stage2_feasibility_path": str(stage2_path).replace("\\", "/"),
        "summary_path": None,
        "checkpoint1_auto_path": None,
    }
    if include_hypothesis_id:
        candidate["hypothesis_id"] = "H-009"
    state = {
        "schema_version": 1,
        "batch_id": batch_id,
        "created_at": "2026-07-01T00:00:00+00:00",
        "source": "taxonomy",
        "max_runtime_seconds": 600,
        "candidates": [candidate],
    }
    state_path = tmp_path / batch_id / "orchestrator_state.json"
    _write_json(state_path, state)
    return state_path, stage2_path


def test_derive_candidate_dir_matches_existing_taxonomy_sidecars():
    assert derive_candidate_dir("B-f-funding-xs-dispersion") == "f_funding_xs_dispersion"
    assert derive_candidate_dir("B-f-xvenue-leadlag") == "f_xvenue_leadlag"
    assert derive_candidate_dir("A-paper-alpha") == "paper_alpha"


def test_pre_register_batch_requires_hypothesis_id_for_every_candidate():
    with pytest.raises(ValueError, match="missing hypothesis_id"):
        pre_register_batch(
            _idea_batch(_candidate("B-f-funding-xs-dispersion")),
            hypothesis_ids={},
            batch_id="idea_batch_20260701_taxonomy_002",
            max_runtime_seconds=600,
            created_at="2026-07-01T00:00:00+00:00",
        )


def test_pre_register_batch_derives_state_fields_and_preserves_new_family():
    state = pre_register_batch(
        _idea_batch(_candidate("B-new-family", "NEW")),
        hypothesis_ids={"B-new-family": "H-999"},
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        created_at="2026-07-01T00:00:00+00:00",
    )

    row = state["candidates"][0]
    assert state["source"] == "taxonomy"
    assert row["candidate_id"] == "B-new-family"
    assert row["candidate_dir"] == "new_family"
    assert row["family_id"] == "NEW"
    assert row["hypothesis_id"] == "H-999"
    assert row["status"] == "idea_registered"
    assert row["status_history"] == [{"status": "idea_registered", "at": "2026-07-01T00:00:00+00:00"}]


def test_pre_register_batch_preserves_feedback_spawned_flag():
    candidate = dict(_candidate(), feedback_spawned=True)
    state = pre_register_batch(
        _idea_batch(candidate),
        hypothesis_ids={"B-f-funding-xs-dispersion": "H-009"},
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        created_at="2026-07-01T00:00:00+00:00",
    )

    assert state["candidates"][0]["feedback_spawned"] is True


def test_orchestrator_cli_requires_max_runtime_seconds():
    from scripts.run_pipeline_orchestrator import main

    with pytest.raises(SystemExit) as exc:
        main(["--batch-id", "batch", "--idea-batch-path", "idea.json", "--hypothesis-ids", "ids.json"])

    assert exc.value.code == 2


def test_reprobe_cli_does_not_require_hypothesis_ids(tmp_path, monkeypatch):
    from scripts import run_pipeline_orchestrator as cli

    called = {}

    async def fake_run_orchestrator(**kwargs):
        called.update(kwargs)
        return tmp_path / "batch" / "orchestrator_state.json"

    monkeypatch.setattr(cli, "run_orchestrator", fake_run_orchestrator)

    result = cli.main(
        [
            "--batch-id",
            "batch",
            "--max-runtime-seconds",
            "1",
            "--output-root",
            str(tmp_path),
            "--reprobe",
        ]
    )
    assert result == 0
    assert called["reprobe"] is True
    assert called["hypothesis_ids_path"] is None
    assert called["power_inputs"] == {}


@pytest.mark.asyncio
async def test_advance_candidate_marks_missing_stage2_family_as_awaiting(tmp_path):
    state = pre_register_batch(
        _idea_batch(_candidate("B-new-family", "NEW")),
        hypothesis_ids={"B-new-family": "H-999"},
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        created_at="2026-07-01T00:00:00+00:00",
    )
    row = state["candidates"][0]

    await advance_candidate(
        row,
        conn="conn",
        context=_context(tmp_path),
        stage2_probes={},
        stage3_runners={},
        registry_text="",
    )

    assert row["status"] == "awaiting_stage2_implementation"
    assert "Codex" in render_shortlist(state)


@pytest.mark.asyncio
async def test_advance_candidate_writes_stage2_fail_sidecar(tmp_path):
    seen = {}

    async def fail_probe(_conn, _context):
        seen.update(_context)
        return FeasibilityResult(
            "idea_batch_20260701_taxonomy_002",
            "B-f-funding-xs-dispersion",
            "f_funding_xs_dispersion",
            "H-009",
            "F-FUNDING-XS-DISPERSION",
            (FeasibilityCheck("data_availability", "FAIL", "no data"),),
        )

    state = pre_register_batch(
        _idea_batch(_candidate()),
        hypothesis_ids={"B-f-funding-xs-dispersion": "H-009"},
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        created_at="2026-07-01T00:00:00+00:00",
    )
    row = state["candidates"][0]

    await advance_candidate(
        row,
        conn="conn",
        context=_context(tmp_path),
        stage2_probes={"F-FUNDING-XS-DISPERSION": fail_probe},
        stage3_runners={},
        registry_text="",
    )

    path = tmp_path / "idea_batch_20260701_taxonomy_002" / "f_funding_xs_dispersion" / "stage2_feasibility.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert row["status"] == "stage2_fail"
    assert row["stage2_feasibility_path"] == str(path).replace("\\", "/")
    assert payload["stage2_status"] == "FAIL"
    assert seen["statistical_power"] == _power()


@pytest.mark.asyncio
async def test_advance_candidate_rejects_missing_power_inputs_before_probe_or_artifact(tmp_path):
    called = False

    async def probe(_conn, _context):
        nonlocal called
        called = True
        return _failed_stage2()

    state = pre_register_batch(
        _idea_batch(_candidate()),
        hypothesis_ids={"B-f-funding-xs-dispersion": "H-009"},
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        created_at="2026-07-01T00:00:00+00:00",
    )
    row = state["candidates"][0]
    context = _context(tmp_path)
    context["statistical_power_inputs"] = {}

    with pytest.raises(ValueError, match="statistical power inputs for candidate"):
        await advance_candidate(
            row,
            conn="conn",
            context=context,
            stage2_probes={"F-FUNDING-XS-DISPERSION": probe},
            stage3_runners={},
            registry_text="",
        )

    assert called is False
    assert row["status"] == "idea_registered"
    assert row["stage2_feasibility_path"] is None


@pytest.mark.asyncio
async def test_advance_candidate_stage2_pass_without_runner_awaits_stage3(tmp_path):
    async def pass_probe(_conn, _context):
        return FeasibilityResult(
            "idea_batch_20260701_taxonomy_002",
            "B-f-funding-xs-dispersion",
            "f_funding_xs_dispersion",
            "H-009",
            "F-FUNDING-XS-DISPERSION",
            (
                FeasibilityCheck("data_availability", "PASS", "ok"),
                FeasibilityCheck("distinctness", "PASS", "ok"),
                FeasibilityCheck("cost_after_edge", "PASS", "ok"),
            ),
        )

    state = pre_register_batch(
        _idea_batch(_candidate()),
        hypothesis_ids={"B-f-funding-xs-dispersion": "H-009"},
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        created_at="2026-07-01T00:00:00+00:00",
    )
    row = state["candidates"][0]

    await advance_candidate(
        row,
        conn="conn",
        context=_context(tmp_path),
        stage2_probes={"F-FUNDING-XS-DISPERSION": pass_probe},
        stage3_runners={},
        registry_text="",
    )
    await advance_candidate(
        row,
        conn="conn",
        context=_context(tmp_path),
        stage2_probes={"F-FUNDING-XS-DISPERSION": pass_probe},
        stage3_runners={},
        registry_text="",
    )

    assert row["status"] == "awaiting_stage3_implementation"


@pytest.mark.asyncio
async def test_terminal_status_is_append_only_noop(tmp_path):
    row = {
        "candidate_id": "B-f-funding-xs-dispersion",
        "candidate_dir": "f_funding_xs_dispersion",
        "family_id": "F-FUNDING-XS-DISPERSION",
        "hypothesis_id": "H-009",
        "status": "stage2_fail",
        "status_history": [{"status": "idea_registered", "at": "t0"}, {"status": "stage2_fail", "at": "t1"}],
    }

    await advance_candidate(
        row,
        conn="conn",
        context=_context(tmp_path),
        stage2_probes={},
        stage3_runners={},
        registry_text="",
    )

    assert row["status_history"] == [{"status": "idea_registered", "at": "t0"}, {"status": "stage2_fail", "at": "t1"}]


@pytest.mark.asyncio
async def test_run_orchestrator_does_not_write_ledger_files_and_reuses_existing_state(tmp_path, monkeypatch):
    from backtesting import pipeline_orchestrator as orchestrator

    async def fake_connect(_dsn):
        class Conn:
            async def close(self):
                return None

        return Conn()

    async def fail_probe(_conn, _context):
        return FeasibilityResult(
            "idea_batch_20260701_taxonomy_002",
            "B-f-funding-xs-dispersion",
            "f_funding_xs_dispersion",
            "H-009",
            "F-FUNDING-XS-DISPERSION",
            (FeasibilityCheck("data_availability", "FAIL", "no data"),),
        )

    idea_batch_path = tmp_path / "idea_batch.json"
    hypothesis_ids_path = tmp_path / "hypothesis_ids.json"
    ledger_path = tmp_path / "HYPOTHESIS_LEDGER.md"
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    idea_batch_path.write_text(json.dumps(_idea_batch(_candidate())), encoding="utf-8")
    hypothesis_ids_path.write_text(json.dumps({"B-f-funding-xs-dispersion": "H-009"}), encoding="utf-8")
    ledger_path.write_text("ledger-original", encoding="utf-8")
    registry_path.write_text("registry-original", encoding="utf-8")

    monkeypatch.setattr(orchestrator, "_connect", fake_connect)
    monkeypatch.setattr(orchestrator, "STAGE2_PROBES", {"F-FUNDING-XS-DISPERSION": fail_probe})
    monkeypatch.setattr(orchestrator, "EXPERIMENT_REGISTRY_PATH", registry_path)

    state_path = await run_orchestrator(
        idea_batch_path=idea_batch_path,
        hypothesis_ids_path=hypothesis_ids_path,
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        output_root=tmp_path,
        dsn="postgresql://example",
        universe_path=tmp_path / "universe.parquet",
        start="2024-01-01",
        end_exclusive="2024-01-02",
        power_inputs=_power_inputs(),
    )
    first_state = json.loads(state_path.read_text(encoding="utf-8"))

    state_path = await run_orchestrator(
        idea_batch_path=idea_batch_path,
        hypothesis_ids_path=hypothesis_ids_path,
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        output_root=tmp_path,
        dsn="postgresql://example",
        universe_path=tmp_path / "universe.parquet",
        start="2024-01-01",
        end_exclusive="2024-01-02",
        power_inputs=_power_inputs(),
    )
    second_state = json.loads(state_path.read_text(encoding="utf-8"))
    metrics = json.loads((tmp_path / "idea_batch_20260701_taxonomy_002" / "funnel_metrics.json").read_text())

    assert first_state == second_state
    assert ledger_path.read_text(encoding="utf-8") == "ledger-original"
    assert registry_path.read_text(encoding="utf-8") == "registry-original"
    assert (tmp_path / "idea_batch_20260701_taxonomy_002" / "shortlist.md").exists()
    assert metrics["selected"] == 1
    assert metrics["stage2_fail"] == 1
    assert metrics["stage2_pass"] == 0


@pytest.mark.asyncio
async def test_reprobe_unchanged_result_keeps_state_byte_identical_and_writes_advisory(tmp_path, monkeypatch):
    from backtesting import pipeline_orchestrator as orchestrator

    async def fake_connect(_dsn):
        class Conn:
            async def close(self):
                return None

        return Conn()

    async def same_probe(_conn, _context):
        return _failed_stage2(details={"rows": 0})

    state_path, _stage2_path = _stage2_failed_state(tmp_path)
    before = state_path.read_bytes()
    monkeypatch.setattr(orchestrator, "_connect", fake_connect)
    monkeypatch.setattr(orchestrator, "STAGE2_PROBES", {"F-FUNDING-XS-DISPERSION": same_probe})

    assert await run_orchestrator(
        idea_batch_path=None,
        hypothesis_ids_path=None,
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        output_root=tmp_path,
        dsn="postgresql://example",
        universe_path=tmp_path / "universe.parquet",
        start="2024-01-01",
        end_exclusive="2024-01-02",
        power_inputs=_power_inputs(),
        reprobe=True,
    ) == state_path

    advisory = json.loads((tmp_path / "idea_batch_20260701_taxonomy_002" / "reprobe_advisory.json").read_text())
    row = advisory["candidates"][0]
    assert state_path.read_bytes() == before
    assert row["candidate_id"] == "B-f-funding-xs-dispersion"
    assert row["changed"] is False
    assert row["previous_status"] == "FAIL"
    assert row["current_status"] == "FAIL"
    assert row["previous_metrics"] == row["current_metrics"]


@pytest.mark.asyncio
async def test_reprobe_changed_result_appends_status_only_and_does_not_run_stage3(tmp_path, monkeypatch):
    from backtesting import pipeline_orchestrator as orchestrator

    async def fake_connect(_dsn):
        class Conn:
            async def close(self):
                return None

        return Conn()

    async def pass_probe(_conn, _context):
        return _passing_stage2()

    state_path, stage2_path = _stage2_failed_state(tmp_path)
    old_stage2_bytes = stage2_path.read_bytes()
    monkeypatch.setattr(orchestrator, "_connect", fake_connect)
    monkeypatch.setattr(orchestrator, "STAGE2_PROBES", {"F-FUNDING-XS-DISPERSION": pass_probe})

    await run_orchestrator(
        idea_batch_path=None,
        hypothesis_ids_path=None,
        batch_id="idea_batch_20260701_taxonomy_002",
        max_runtime_seconds=600,
        output_root=tmp_path,
        dsn="postgresql://example",
        universe_path=tmp_path / "universe.parquet",
        start="2024-01-01",
        end_exclusive="2024-01-02",
        power_inputs=_power_inputs(),
        reprobe=True,
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    row = state["candidates"][0]
    advisory = json.loads((tmp_path / "idea_batch_20260701_taxonomy_002" / "reprobe_advisory.json").read_text())
    assert stage2_path.read_bytes() == old_stage2_bytes
    assert row["status"] == "stage2_pass_on_reprobe"
    assert row["summary_path"] is None
    assert row["stage2_feasibility_path"] == str(stage2_path).replace("\\", "/")
    assert row["status_history"][:2] == [
        {"status": "idea_registered", "at": "t0"},
        {"status": "stage2_fail", "at": "t1"},
    ]
    assert row["status_history"][2]["status"] == "stage2_pass_on_reprobe"
    assert advisory["candidates"][0]["changed"] is True
    assert advisory["candidates"][0]["previous_status"] == "FAIL"
    assert advisory["candidates"][0]["current_status"] == "PASS"


@pytest.mark.asyncio
async def test_reprobe_fails_closed_when_state_candidate_missing_hypothesis_id(tmp_path, monkeypatch):
    from backtesting import pipeline_orchestrator as orchestrator

    async def fake_connect(_dsn):
        class Conn:
            async def close(self):
                return None

        return Conn()

    async def same_probe(_conn, _context):
        return _failed_stage2(details={"rows": 0})

    _stage2_failed_state(tmp_path, include_hypothesis_id=False)
    monkeypatch.setattr(orchestrator, "_connect", fake_connect)
    monkeypatch.setattr(orchestrator, "STAGE2_PROBES", {"F-FUNDING-XS-DISPERSION": same_probe})

    with pytest.raises(ValueError, match="missing hypothesis_id"):
        await run_orchestrator(
            idea_batch_path=None,
            hypothesis_ids_path=None,
            batch_id="idea_batch_20260701_taxonomy_002",
            max_runtime_seconds=600,
            output_root=tmp_path,
            dsn="postgresql://example",
            universe_path=tmp_path / "universe.parquet",
            start="2024-01-01",
            end_exclusive="2024-01-02",
            reprobe=True,
        )
