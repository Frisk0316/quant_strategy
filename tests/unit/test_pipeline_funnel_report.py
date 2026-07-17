import json
from pathlib import Path

from scripts.run_pipeline_funnel_report import collect_metrics, collect_pipeline_funnel, main, render_markdown


def test_funnel_report_marks_legacy_batches_without_metrics_as_na(tmp_path, capsys):
    with_metrics = tmp_path / "idea_batch_with_metrics"
    without_metrics = tmp_path / "idea_batch_without_metrics"
    with_metrics.mkdir()
    without_metrics.mkdir()
    (with_metrics / "funnel_metrics.json").write_text(
        json.dumps(
            {
                "batch_id": "idea_batch_with_metrics",
                "driver": "literature",
                "fetched": 2,
                "scored": 2,
                "above_threshold": 1,
                "selected": 1,
            }
        ),
        encoding="utf-8",
    )

    rows = collect_metrics(tmp_path)
    table = render_markdown(rows)

    assert rows[0]["missing_metrics"] is False
    assert rows[1]["missing_metrics"] is True
    assert "| idea_batch_with_metrics | literature | 2 | 2 | 1 | 1 | n/a | n/a | n/a |" in table
    assert "| idea_batch_without_metrics | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |" in table

    assert main(["--results-root", str(tmp_path)]) == 0
    stdout = capsys.readouterr().out
    assert "idea_batch_without_metrics" in stdout


def test_pipeline_funnel_projects_ledger_and_latest_valid_stage3_row(tmp_path):
    results = tmp_path / "results"
    for name, data_status, power_status in (
        ("first", "PASS", "PASS"),
        ("duplicate", "FAIL", "FAIL"),
        ("missing", "PASS", "FAIL"),
    ):
        path = results / name
        path.mkdir(parents=True)
        family_id = "F-TEST" if name != "missing" else "F-MISSING"
        hypothesis_id = "H-123" if name != "missing" else "H-124"
        (path / "stage2_feasibility.json").write_text(
            json.dumps(
                {
                    "hypothesis_id": hypothesis_id,
                    "family_id": family_id,
                    "checks": [
                        {"name": "data_availability", "status": data_status},
                        {"name": "statistical_power", "status": power_status},
                    ],
                }
            ),
            encoding="utf-8",
        )

    ledger = tmp_path / "HYPOTHESIS_LEDGER.md"
    ledger.write_text(
        "\n".join(
            (
                "| ID | Family ID | Family cumulative n_trials | Hypothesis (falsifiable) | Source | Status | Experiment(s) | Notes |",
                "|---|---|---:|---|---|---|---|---|",
                "| H-123 | F-TEST | 999 | claim | source | testing | E-001 | canonical status |",
                "| H-124 | F-MISSING | 999 | claim | source | proposed | - | no run |",
                "| H-125 | F-KONLY | 999 | claim | source | shelved | - | K-only family |",
            )
        ),
        encoding="utf-8",
    )
    registry = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry.write_text(
        "\n".join(
            (
                "| Family ID | K_used | K_limit | Basis |",
                "|---|---:|---:|---|",
                "| F-TEST | 1 | 2 | one retry |",
                "| F-MISSING | 0 | 2 | no run |",
                "| F-KONLY | 2 | 2 | prior retries |",
                "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact | Outcome | Notes |",
                "|---|---|---|---|---|---|---|---|---|",
                "| E-001 | 2026-01-01 | H-123 | F-TEST | first | 2 | `results/old/summary.json` | checkpoint / non-passing | WF 0.1, CPCV 0.2, DSR 0.3, PSR 0.4. |",
                "| E-002 | 2026-01-02 | H-123 | F-TEST | family cumulative `n_trials=6` | 4 | `results/latest/summary.json` | shelved / statistical-fail | WF OOS Sharpe 0.5, CPCV OOS Sharpe 0.6, DSR = PSR 0.7; `statistical_gate_passed:false`. |",
                "| E-003 | 2026-01-03 | H-123 | F-TEST | bad | 4 | `results/invalid/summary.json` | invalid / superseded | WF 9, CPCV 9, DSR 9, PSR 9. |",
                "| E-004 | 2026-01-04 | H-123 | F-TEST | bad | 99 | pending - `results/planned/summary.json` | planned | WF 8, CPCV 8, DSR 8, PSR 8. |",
                "| E-006 | 2026-01-06 | H-123 | F-TEST | bad | 4 | `results/stage2/summary.json` | stage2_failed | WF 6, CPCV 6, DSR 6, PSR 6. |",
                "| E-005 | 2026-01-05 | H-123 | F-TEST | bad | 4 | `results/blocked/summary.json` | data_blocked | WF 7, CPCV 7, DSR 7, PSR 7. |",
                "| E-007 | 2026-01-07 | H-123 | F-TEST | bad | 4 | `results/closed/summary.json` | fail-closed | WF 5, CPCV 5, DSR 5, PSR 5. |",
            )
        ),
        encoding="utf-8",
    )

    report = collect_pipeline_funnel(results, registry, ledger)
    rows = {row["family_id"]: row for row in report["families"]}
    expected_fields = {
        "family_id",
        "hypothesis_id",
        "status",
        "source",
        "hypothesis_text",
        "experiments",
        "wf",
        "cpcv",
        "dsr",
        "psr",
        "n_trials",
        "k_used",
        "k_limit",
        "candidates",
        "data_feasible",
        "power_feasible",
        "stage3_run",
        "gate_pass",
    }

    assert set(rows["F-TEST"]) == expected_fields
    expected_v1 = {
        "family_id": "F-TEST",
        "hypothesis_id": "H-123",
        "status": "testing",
        "wf": 0.5,
        "cpcv": 0.6,
        "dsr": 0.7,
        "psr": 0.7,
        "n_trials": 6,
        "k_used": 1,
        "k_limit": 2,
        "candidates": 1,
        "data_feasible": 1,
        "power_feasible": 1,
        "stage3_run": 1,
        "gate_pass": 0,
    }
    assert {field: rows["F-TEST"][field] for field in expected_v1} == expected_v1
    assert report["schema_version"] == 3
    assert report["stage2_artifact_errors"] == []
    assert rows["F-TEST"]["source"] == "source"
    assert rows["F-TEST"]["hypothesis_text"] == "claim"
    assert [experiment["id"] for experiment in rows["F-TEST"]["experiments"]] == [
        f"E-{number:03d}" for number in range(1, 8)
    ]
    assert rows["F-TEST"]["experiments"][0] == {
        "id": "E-001",
        "date": "2026-01-01",
        "setup": "first",
        "outcome": "checkpoint / non-passing",
        "notes": "WF 0.1, CPCV 0.2, DSR 0.3, PSR 0.4.",
    }
    assert rows["F-MISSING"]["status"] == "proposed"
    assert rows["F-MISSING"]["experiments"] == []
    assert rows["F-MISSING"]["n_trials"] == 0
    assert rows["F-MISSING"]["wf"] is None
    assert rows["F-MISSING"]["cpcv"] is None
    assert rows["F-MISSING"]["dsr"] is None
    assert rows["F-MISSING"]["psr"] is None
    assert rows["F-KONLY"]["status"] == "shelved"
    assert rows["F-KONLY"]["candidates"] == 1
    assert rows["F-KONLY"]["data_feasible"] == 0
    assert rows["F-KONLY"]["stage3_run"] == 0
    assert rows["F-KONLY"]["k_used"] == 2
    assert report["totals"]["k_spent"] == 3


def test_pipeline_funnel_reads_hypothesis_text_from_real_ledger(tmp_path):
    root = Path(__file__).resolve().parents[2]
    report = collect_pipeline_funnel(
        tmp_path,
        root / "docs" / "EXPERIMENT_REGISTRY.md",
        root / "docs" / "HYPOTHESIS_LEDGER.md",
    )

    row = next(row for row in report["families"] if row["hypothesis_id"] == "H-001")
    assert row["hypothesis_text"].startswith("Cross-venue PnL metrics converge")


def test_pipeline_funnel_isolates_malformed_stage2_artifact(tmp_path):
    results = tmp_path / "results"
    valid = results / "valid" / "stage2_feasibility.json"
    broken = results / "broken" / "stage2_feasibility.json"
    valid.parent.mkdir(parents=True)
    broken.parent.mkdir(parents=True)
    valid.write_text(
        json.dumps(
            {
                "hypothesis_id": "H-123",
                "family_id": "F-TEST",
                "checks": [
                    {"name": "data_availability", "status": "PASS"},
                    {"name": "statistical_power", "status": "PASS"},
                ],
            }
        ),
        encoding="utf-8",
    )
    broken.write_text("{not-json", encoding="utf-8")
    ledger = tmp_path / "HYPOTHESIS_LEDGER.md"
    registry = tmp_path / "EXPERIMENT_REGISTRY.md"
    ledger.write_text("", encoding="utf-8")
    registry.write_text("", encoding="utf-8")

    report = collect_pipeline_funnel(results, registry, ledger)

    assert report["stage2_artifacts_scanned"] == 2
    assert report["totals"]["data_feasible"] == 1
    assert report["stage2_artifact_errors"] == [
        {
            "path": str(broken).replace("\\", "/"),
            "error_type": "JSONDecodeError",
            "error": report["stage2_artifact_errors"][0]["error"],
        }
    ]
