import json

from backtesting.pipeline_checkpoint1 import evaluate_summary, result_to_dict
from scripts.run_pipeline_checkpoint1_check import main


def _registry(artifact: str = "results/batch/candidate/summary.json", trials: int = 24) -> str:
    return "\n".join(
        [
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            f"| E-101 | 2026-06-30 | H-101 | F-CHECK | setup | {trials} | `{artifact}` | checkpoint | current row |",
        ]
    )


def _summary(**overrides):
    payload = {
        "batch_id": "batch",
        "candidate_id": "candidate",
        "family_id": "F-CHECK",
        "family_cumulative_n_trials": 24,
        "cpcv": {"n_trials": 24, "n_trials_provenance": "caller_declared"},
        "leak_test_passed": True,
        "dsr": 0.96,
        "psr": 0.97,
        "idealized_fill": False,
        "portable_validation_gate": False,
        "promotion_gate_passed": False,
        "ct_val_all_authoritative": True,
        "ct_val_sources": {
            "BTC-USDT-SWAP": {
                "exchange": "binance",
                "authoritative": True,
            }
        },
        "data_source": {"primary_exchange": "binance"},
    }
    payload.update(overrides)
    return payload


def test_checkpoint1_passes_machine_checks_and_keeps_human_review_items():
    result = evaluate_summary(
        _summary(),
        _registry(),
        summary_path="results/batch/candidate/summary.json",
    )
    payload = result_to_dict(result)
    checks = {row["name"]: row for row in payload["checks"]}

    assert payload["checkpoint1_auto_status"] == "PASS"
    assert checks["n_trials_reconcile"]["status"] == "PASS"
    assert checks["portable_gate_or_honest_block"]["status"] == "PASS"
    assert payload["human_review_items"] == [
        "leak_lag_spotcheck",
        "diff_block_reason_honest",
        "verdict",
        "retry_vs_new_family",
    ]


def test_checkpoint1_fails_when_summary_trials_do_not_match_registry():
    result = evaluate_summary(
        _summary(family_cumulative_n_trials=8, cpcv={"n_trials": 8}),
        _registry(trials=24),
        summary_path="results/batch/candidate/summary.json",
    )
    payload = result_to_dict(result)
    checks = {row["name"]: row for row in payload["checks"]}

    assert payload["checkpoint1_auto_status"] == "FAIL"
    assert checks["n_trials_reconcile"]["status"] == "FAIL"


def test_checkpoint1_fails_idealized_fill_dsr_order_and_threshold():
    cases = [
        (_summary(idealized_fill=True), "idealized_fill_excluded"),
        (_summary(dsr=0.98, psr=0.97), "dsr_le_psr"),
        (_summary(dsr=0.94, psr=0.97), "dsr_psr_threshold"),
    ]

    for summary, failing_check in cases:
        payload = result_to_dict(
            evaluate_summary(
                summary,
                _registry(),
                summary_path="results/batch/candidate/summary.json",
            )
        )
        checks = {row["name"]: row for row in payload["checks"]}
        assert payload["checkpoint1_auto_status"] == "FAIL"
        assert checks[failing_check]["status"] == "FAIL"


def test_checkpoint1_marks_missing_dsr_as_needs_human():
    payload = result_to_dict(
        evaluate_summary(
            _summary(dsr=None, psr=None),
            _registry(),
            summary_path="results/batch/candidate/summary.json",
        )
    )

    assert payload["checkpoint1_auto_status"] == "NEEDS_HUMAN"
    assert {row["status"] for row in payload["checks"]} == {"PASS", "NEEDS_HUMAN"}


def test_checkpoint1_cli_writes_output(tmp_path):
    summary_path = tmp_path / "summary.json"
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    output_path = tmp_path / "checkpoint1_auto.json"
    summary_path.write_text(json.dumps(_summary()), encoding="utf-8")
    registry_path.write_text(_registry(str(summary_path).replace("\\", "/")), encoding="utf-8")

    exit_code = main(
        [
            "--summary",
            str(summary_path),
            "--registry",
            str(registry_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["checkpoint1_auto_status"] == "PASS"
