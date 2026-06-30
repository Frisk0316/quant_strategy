import json

from scripts.run_pipeline_batch2_checkpoint import (
    _base_summary,
    _c3_gate_failure_reason,
    _shortlist_reason,
    _stage2_data_fail_summary,
    _stage2_result_to_summary_fields,
    run_c3,
)
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


def test_stage2_data_fail_summary_writes_feasibility_artifact(tmp_path, monkeypatch):
    import scripts.run_pipeline_batch2_checkpoint as runner

    monkeypatch.setattr(runner, "OUT", tmp_path)

    summary = _stage2_data_fail_summary(
        "c2_funding_carry",
        "c2_funding_carry",
        "F-FUNDING-CARRY",
        "data_probe_unavailable: RuntimeError: no db",
        "H-007",
        "funding carry is treated as the existing funding-carry family with this run counted as a retry",
    )

    artifact = tmp_path / "c2_funding_carry" / "stage2_feasibility.json"
    assert artifact.exists()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["stage2_status"] == "FAIL"
    assert checks["data_availability"]["reason"] == "data_probe_unavailable: RuntimeError: no db"
    assert checks["distinctness"]["status"] == "PASS"
    assert checks["cost_after_edge"]["reason"] == "cost smell test cannot run without required data"
    assert summary["stage2_status"] == "FAIL"
    assert summary["stage2_checks"]["data_availability"]["status"] == "FAIL"


def test_c3_gate_failure_reason_preserves_zero_event_reason_and_reports_nonzero_details():
    assert _c3_gate_failure_reason({"event_count": 0}) == "fear_greed_btc event_count=0"

    reason = _c3_gate_failure_reason({"event_count": 3, "missing_ratio": 0.2, "stale_ratio": 0.4})

    assert reason == "fear_greed_btc external-feature gate failed: event_count=3, missing_ratio=0.2, stale_ratio=0.4"


def test_c3_feature_gate_pass_runs_stage3_grid(tmp_path, monkeypatch):
    import scripts.run_pipeline_batch2_checkpoint as runner
    import pandas as pd

    async def fake_gate():
        return {
            "event_count": 897,
            "market_event_count": 1281600,
            "missing_ratio": 0.0,
            "stale_ratio": 0.0,
            "feature_gate_passed": True,
        }

    def fake_precompute(params, grid, run_backtest, label):
        assert label == "c3"
        assert grid == {
            "extreme_fear_threshold": [20.0, 25.0, 30.0],
            "exit_value_threshold": [50.0, 55.0, 60.0],
        }
        return [
            {
                "metrics": {"sharpe": 0.1},
                "params": params,
                "daily_returns": [],
                "nonzero_daily_returns": 1,
            }
            for _ in range(9)
        ]

    def fake_refit(records, n_trials):
        assert len(records) == 9
        assert n_trials == 9
        return {
            "validation_mode": "fold_refit_param_selection",
            "wf_oos_sharpe": 0.1,
            "cpcv_oos_sharpe": 0.2,
            "dsr": 0.3,
            "psr": 0.4,
            "wf_selected_param_counts": {},
            "cpcv_selected_param_counts": {},
            "cpcv": {
                "path_returns": [[0.01]],
                "path_return_lengths": [1],
                "n_trials": 9,
                "n_trials_provenance": "caller_declared",
            },
        }

    monkeypatch.setattr(runner, "OUT", tmp_path)
    monkeypatch.setattr(runner, "_c3_feature_gate", fake_gate)
    idx = pd.date_range("2024-01-01", periods=2, freq="h")
    close = pd.DataFrame({"BTC-USDT-SWAP": [100.0, 101.0]}, index=idx)
    funding = pd.DataFrame({"BTC-USDT-SWAP": [0.0, 0.0]}, index=idx)
    fng = pd.DataFrame({"value_num": [10.0]})
    monkeypatch.setattr(runner, "load_c3_inputs", lambda *args, **kwargs: (close, funding, fng), raising=False)
    monkeypatch.setattr(runner, "_precompute_records", fake_precompute)
    monkeypatch.setattr(runner, "_refit_validation", fake_refit)
    monkeypatch.setattr(runner, "_best_full_sample_record", lambda records: records[0])
    monkeypatch.setattr(runner, "_records_have_activity", lambda records: True)
    monkeypatch.setattr(runner, "_param_subset", lambda record, keys: {"extreme_fear_threshold": 20.0})

    summary = runner.run_c3()

    assert summary["stage2_status"] == "PASS"
    assert summary["status"] == "refuted"
    assert summary["grid_size_this_run"] == 9
    assert summary["family_cumulative_n_trials"] == 9
    assert summary["nonzero_grid_activity"] is True
    assert summary["promotion_gate_passed"] is False
    assert summary["cpcv"]["path_returns"] == [[0.01]]
    assert summary["external_feature_gate"]["event_count"] == 897


def test_shortlist_reason_reports_c3_stage2_pass_without_stage3_and_preserves_stage2_fail():
    assert (
        _shortlist_reason(
            {
                "candidate_id": "c3_sentiment",
                "status": "stage2_passed_stage3_not_run",
                "stage2_status": "PASS",
                "statistical_gate_passed": False,
                "portable_validation_gate": False,
            }
        )
        == "Stage-2 passed; Stage-3 replay not run by offline helper"
    )

    assert (
        _shortlist_reason(
            {
                "candidate_id": "c3_sentiment",
                "stage2_status": "FAIL",
                "stage2_reason": "fear_greed_btc event_count=0",
                "external_feature_gate": {"event_count": 0},
            }
        )
        == "Stage-2 data gate failed: `fear_greed_btc` event_count=0"
    )
