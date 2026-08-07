from __future__ import annotations

import hashlib
import json

import pytest

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult


CHECK_NAMES = ("data_availability", "distinctness", "cost_after_edge", "statistical_power")


def _result(*, failed: str | None = None) -> FeasibilityResult:
    return FeasibilityResult(
        batch_id="synthetic",
        candidate_id="C-0",
        candidate_dir="c_0",
        hypothesis_id="H-0",
        family_id="F-SYNTHETIC",
        checks=tuple(
            FeasibilityCheck(name, "FAIL" if name == failed else "PASS", "synthetic")
            for name in CHECK_NAMES
        ),
    )


def _candidate(tmp_path, *, breadth: float = 1.5) -> dict:
    artifact = tmp_path / "positions.json"
    artifact.write_text(
        json.dumps(
            {
                "series": [
                    {"ts": "2024-01-01T00:00:00Z", "positions": {"BTC": 1.0, "ETH": 0.0}},
                    {"ts": "2024-01-02T00:00:00Z", "positions": {"BTC": 1.0, "ETH": -1.0}},
                ]
            }
        ),
        encoding="utf-8",
    )
    return {
        "candidate_id": "C-0",
        "candidate_dir": "c_0",
        "hypothesis_id": "H-0",
        "family_id": "F-SYNTHETIC",
        "window": {"start": "2024-01-01T00:00:00Z", "end": "2024-01-03T00:00:00Z"},
        "universe": {"path": str(tmp_path / "universe.parquet")},
        "statistical_power": {
            "breadth": breadth,
            "n_obs": 2,
            "n_trials": 1,
            "plausible_net_sharpe": 1.0,
        },
        "breadth": breadth,
        "breadth_provenance": {
            "path": str(artifact),
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "field": "/series",
            "formula": "mean_nonzero_positions",
            "window": ["2024-01-01T00:00:00Z", "2024-01-03T00:00:00Z"],
            "n_obs": 2,
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(("failed", "expected"), [(None, "pass"), ("distinctness", "fail")])
async def test_stage2_round_runner_maps_probe_and_uses_only_manifest_context(
    tmp_path, monkeypatch, failed, expected
):
    from backtesting import pipeline_round_runners as runners

    seen = {}

    async def probe(conn, ctx):
        seen.update(ctx)
        assert conn is connection
        return _result(failed=failed)

    class Connection:
        closed = False

        async def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setitem(runners.STAGE2_PROBES, "F-SYNTHETIC", probe)
    monkeypatch.setattr(runners, "_connect", lambda _dsn: connection)

    runner = runners.stage2_round_runner("F-SYNTHETIC")
    result = await runner(
        _candidate(tmp_path),
        {"dsn": "postgresql://mock", "artifact_root": tmp_path, "result_derived_value": "forbidden"},
    )

    assert result["stage2"]["status"] == expected
    assert [row["name"] for row in result["stage2"]["checks"]] == list(CHECK_NAMES)
    assert seen["start"].isoformat() == "2024-01-01T00:00:00+00:00"
    assert seen["end"].isoformat() == "2024-01-03T00:00:00+00:00"
    assert seen["universe_path"] == tmp_path / "universe.parquet"
    assert seen["statistical_power"]["breadth"] == 1.5
    assert "result_derived_value" not in seen
    assert connection.closed is True


@pytest.mark.asyncio
async def test_stage2_round_runner_maps_probe_exception_to_error(tmp_path, monkeypatch):
    from backtesting import pipeline_round_runners as runners

    async def probe(_conn, _ctx):
        raise LookupError("synthetic")

    class Connection:
        async def close(self):
            return None

    monkeypatch.setitem(runners.STAGE2_PROBES, "F-SYNTHETIC", probe)
    monkeypatch.setattr(runners, "_connect", lambda _dsn: Connection())

    result = await runners.stage2_round_runner("F-SYNTHETIC")(
        _candidate(tmp_path),
        {"dsn": "postgresql://mock", "artifact_root": tmp_path},
    )

    assert result == {"stage2": {"status": "error", "checks": [], "error": "LookupError"}}


@pytest.mark.asyncio
async def test_breadth_mismatch_refuses_before_probe(tmp_path, monkeypatch):
    from backtesting import pipeline_round_runners as runners

    called = False

    async def probe(_conn, _ctx):
        nonlocal called
        called = True
        return _result()

    monkeypatch.setitem(runners.STAGE2_PROBES, "F-SYNTHETIC", probe)
    with pytest.raises(ValueError, match="breadth_recompute_mismatch:C-0"):
        await runners.stage2_round_runner("F-SYNTHETIC")(
            _candidate(tmp_path, breadth=2.0),
            {"dsn": "postgresql://mock", "artifact_root": tmp_path},
        )
    assert called is False


def test_reviewed_round_runner_registry_starts_empty_and_forbids_wildcards(monkeypatch):
    from backtesting import pipeline_round_runners as runners

    async def probe(_conn, _ctx):
        return _result()

    assert runners.REVIEWED_ROUND_RUNNERS == {}
    assert runners.ROUND_RUNNERS == {}
    assert runners.AUTHORIZED_STAGE3_ROUND_RUNNERS == {}
    with pytest.raises(ValueError, match="stage2_probe_not_registered:F-MISSING"):
        runners.stage2_round_runner("F-MISSING")

    monkeypatch.setitem(runners.STAGE2_PROBES, "F-SYNTHETIC", probe)
    built = runners.build_round_runners({"synthetic_runner": "F-SYNTHETIC"})
    assert set(built) == {"synthetic_runner"}
    with pytest.raises(ValueError, match="wildcard_round_runner_forbidden"):
        runners.build_round_runners({"*": "F-SYNTHETIC"})
