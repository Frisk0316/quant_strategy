from scripts.run_pipeline_batch2_checkpoint import _base_summary, _stage2_result_to_summary_fields
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult


def test_batch2_base_summary_has_gate_fields_and_blocks_without_portable_gate():
    validation = {
        "validation_mode": "fold_refit_param_selection",
        "wf_oos_sharpe": 1.2,
        "cpcv_oos_sharpe": 1.1,
        "dsr": 0.99,
        "psr": 0.99,
        "wf_selected_param_counts": {},
        "cpcv_selected_param_counts": {},
        "cpcv": {
            "path_returns": [[0.01]],
            "path_return_lengths": [1],
            "n_trials_provenance": "caller_declared",
        },
    }

    summary = _base_summary("c1_pairs_ou", "F-PAIRS-OU", 24, validation, leak_test_passed=True)

    assert summary["batch_id"] == "pipeline_batch2_20260625"
    assert summary["family_cumulative_n_trials"] == 24
    assert summary["leak_test_passed"] is True
    assert summary["portable_validation_gate"] is False
    assert summary["idealized_fill"] is False
    assert summary["ct_val_all_authoritative"] is True
    assert summary["promotion_gate_passed"] is False
    assert summary["status"] == "checkpoint_review_required"
    assert summary["pass_a_status"] == "skipped_missing_required_parquet_cache"
    assert summary["pass_b_status"] == "db_venue_scoped_refit_wf_cpcv_completed"


def test_batch2_base_summary_marks_statistical_fail_as_refuted():
    validation = {
        "validation_mode": "fold_refit_param_selection",
        "wf_oos_sharpe": -1.0,
        "cpcv_oos_sharpe": -0.5,
        "dsr": 0.1,
        "psr": 0.2,
        "wf_selected_param_counts": {},
        "cpcv_selected_param_counts": {},
        "cpcv": {
            "path_returns": [[-0.01]],
            "path_return_lengths": [1],
            "n_trials_provenance": "caller_declared",
        },
    }

    summary = _base_summary("c1_pairs_ou", "F-PAIRS-OU", 24, validation, leak_test_passed=True)

    assert summary["statistical_gate_passed"] is False
    assert summary["status"] == "refuted"


def test_stage2_result_to_summary_fields_carries_check_artifact_status():
    result = FeasibilityResult(
        batch_id="pipeline_batch2_20260625",
        candidate_id="c3_sentiment",
        candidate_dir="c3_sentiment",
        hypothesis_id="H-008",
        family_id="F-SENTIMENT",
        checks=(
            FeasibilityCheck("data_availability", "FAIL", "fear_greed_btc event_count=0"),
            FeasibilityCheck(
                "distinctness",
                "PASS",
                "sentiment family is distinct from currently enabled price-only strategies",
            ),
            FeasibilityCheck(
                "cost_after_edge",
                "FAIL",
                "cost smell test cannot run without the required external feature",
            ),
        ),
    )

    fields = _stage2_result_to_summary_fields(result)

    assert fields["stage2_status"] == "FAIL"
    assert (
        fields["stage2_reason"]
        == "fear_greed_btc event_count=0; cost smell test cannot run without the required external feature"
    )
    assert fields["stage2_checks"]["data_availability"]["status"] == "FAIL"
