import json

import scripts.run_source_provenance_validation as runner


def _validation_summary(*, source="PASS", ct_val="PASS", db="PASS", ohlcv="db_parity_pass"):
    return {
        "validation_id": "unit_validation",
        "run_id": "unit_run",
        "artifact_dir": "results/unit_run",
        "output_dir": "results/unit_run/validation/unit_validation",
        "ohlcv_source_validation": ohlcv,
        "source_data_validation": {
            "status": source,
            "ohlcv_source_validation": ohlcv,
            "checks": {
                "ct_val_provenance": {"status": ct_val},
                "db_parity": {"status": db},
            },
        },
    }


def test_source_provenance_gate_passes_only_on_db_backed_evidence():
    report = runner.evaluate_source_provenance(_validation_summary())

    assert report["status"] == "PASS"
    assert report["required_checks"] == {
        "source_data_validation": "PASS",
        "ct_val_provenance": "PASS",
        "db_parity": "PASS",
        "ohlcv_source_validation": "db_parity_pass",
    }
    assert report["blocking_reasons"] == []


def test_source_provenance_gate_blocks_fixture_db_skip():
    report = runner.evaluate_source_provenance(
        _validation_summary(db="SKIP", ohlcv="artifact_pass_db_skipped")
    )

    assert report["status"] == "FAIL"
    assert "db_parity_not_pass" in report["blocking_reasons"]
    assert "ohlcv_source_validation_not_db_parity_pass" in report["blocking_reasons"]


def test_source_provenance_cli_validates_existing_result_json(tmp_path, capsys):
    result_path = tmp_path / "validation_result.json"
    result_path.write_text(json.dumps(_validation_summary()), encoding="utf-8")

    exit_code = runner.main(["--validation-result", str(result_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "PASS"
    assert payload["evidence"]["validation_result_path"] == str(result_path)


def test_source_provenance_cli_fails_on_db_skip_result_json(tmp_path, capsys):
    result_path = tmp_path / "validation_result.json"
    result_path.write_text(
        json.dumps(_validation_summary(db="SKIP", ohlcv="artifact_pass_db_skipped")),
        encoding="utf-8",
    )

    exit_code = runner.main(["--validation-result", str(result_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "FAIL"
    assert "db_parity_not_pass" in payload["blocking_reasons"]
