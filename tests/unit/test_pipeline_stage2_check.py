from __future__ import annotations

import json

from scripts.run_pipeline_stage2_check import main


def _write_payload(path, checks):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "pipeline_test",
                "candidate_id": "c3_sentiment",
                "candidate_dir": "c3_sentiment",
                "hypothesis_id": "H-008",
                "family_id": "F-SENTIMENT",
                "checks": checks,
            }
        ),
        encoding="utf-8",
    )


def test_stage2_check_cli_returns_zero_for_pass(tmp_path, capsys) -> None:
    path = tmp_path / "stage2_feasibility.json"
    _write_payload(
        path,
        [
            {"name": "data_availability", "status": "PASS", "reason": "data exists"},
            {"name": "distinctness", "status": "PASS", "reason": "distinct family"},
            {"name": "cost_after_edge", "status": "PASS", "reason": "edge exceeds costs"},
        ],
    )

    assert main([str(path)]) == 0
    assert capsys.readouterr().out.strip() == "PASS"


def test_stage2_check_cli_returns_one_for_fail(tmp_path, capsys) -> None:
    path = tmp_path / "stage2_feasibility.json"
    _write_payload(
        path,
        [
            {"name": "data_availability", "status": "FAIL", "reason": "feature absent"},
            {"name": "distinctness", "status": "PASS", "reason": "distinct family"},
            {"name": "cost_after_edge", "status": "FAIL", "reason": "smell test blocked"},
        ],
    )

    assert main([str(path)]) == 1
    assert capsys.readouterr().out.strip() == "FAIL"


def test_stage2_check_cli_can_write_computed_status(tmp_path) -> None:
    path = tmp_path / "stage2_feasibility.json"
    _write_payload(
        path,
        [
            {"name": "data_availability", "status": "PASS", "reason": "data exists"},
            {"name": "distinctness", "status": "PASS", "reason": "distinct family"},
            {"name": "cost_after_edge", "status": "PASS", "reason": "edge exceeds costs"},
        ],
    )

    assert main(["--write-status", str(path)]) == 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage2_status"] == "PASS"
