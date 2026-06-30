import json

from backtesting.pipeline_checkpoint1 import evaluate_summary, family_registry_from_text, result_to_dict
from scripts.run_pipeline_checkpoint1_check import main


def _registry(artifact: str = "results/batch/candidate/summary.json", trials: int = 24) -> str:
    return "\n".join(
        [
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            f"| E-101 | 2026-06-30 | H-101 | F-CHECK | setup | {trials} | `{artifact}` | checkpoint | current row |",
        ]
    )


def _xs_registry() -> str:
    return "\n".join(
        [
            "| Family ID | K_used | K_limit | Basis (rows counted as retries) |",
            "|---|---:|---:|---|",
            "| F-XS-MOMENTUM | 2 | 2 | E-003 original -> E-004 leak-fix -> E-005 sizing-fix |",
            "| F-FUNDING-CARRY | 1 | 2 | E-024 original -> E-026 realism re-cost |",
            "",
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E-003 | 2026-06-23 | H-002 | F-XS-MOMENTUM | original grid | 8 | `results/xs/original/summary.json` | invalid / superseded | superseded |",
            "| E-004 | 2026-06-24 | H-002 | F-XS-MOMENTUM | leak fix grid | 8 | `results/xs/leakfix/summary.json` | refuted | supersedes E-003 |",
            "| E-005 | 2026-06-24 | H-002 | F-XS-MOMENTUM | sizing fix grid; per-run recorded `n_trials=8` under old convention | 8 | `results/xs/portfoliovol/summary.json` | refuted | Under the family-cumulative rule, F-XS-MOMENTUM has at least 24 trials from E-003/E-004/E-005 before any future retry. |",
            "| E-024 | 2026-06-29 | H-007 | F-FUNDING-CARRY | first carry grid; family-cumulative `n_trials=24` passed as caller-declared | 24 | `results/carry/original/summary.json` | checkpoint / statistical-pass / promotion-blocked | first real run |",
            "| E-026 | 2026-06-29 | H-007 | F-FUNDING-CARRY | realism re-cost. Family-cumulative `n_trials=48` = prior 24 + retry grid 24. | 48 | `results/carry/realism/summary.json` | refuted / realism-recost-fail | recost retry |",
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


def test_family_registry_uses_family_cumulative_trials_without_double_counting_overrides():
    registry = family_registry_from_text(_xs_registry())

    assert registry["F-XS-MOMENTUM"].cumulative_n_trials == 24
    assert registry["F-XS-MOMENTUM"].k_used == 2
    assert registry["F-XS-MOMENTUM"].k_limit == 2
    assert registry["F-FUNDING-CARRY"].cumulative_n_trials == 48


def test_checkpoint1_reconciles_xs_artifact_to_family_cumulative_trials():
    result = evaluate_summary(
        _summary(
            family_id="F-XS-MOMENTUM",
            family_cumulative_n_trials=24,
            cpcv={"n_trials": 24, "n_trials_provenance": "caller_declared"},
        ),
        _xs_registry(),
        summary_path="results/xs/portfoliovol/summary.json",
    )
    payload = result_to_dict(result)
    checks = {row["name"]: row for row in payload["checks"]}

    assert checks["n_trials_reconcile"]["status"] == "PASS"


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
