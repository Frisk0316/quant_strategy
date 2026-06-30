from __future__ import annotations

import pytest

from backtesting.pipeline_feasibility import (
    FeasibilityCheck,
    FeasibilityResult,
    evaluate_stage2_result,
    result_from_dict,
    result_to_dict,
)


def test_stage2_pass_requires_all_three_checks() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c1_pairs_ou",
        candidate_dir="c1_pairs_ou",
        hypothesis_id="H-006",
        family_id="F-PAIRS-OU",
        checks=(
            FeasibilityCheck("data_availability", "PASS", "venue-scoped BTC/ETH data exists"),
            FeasibilityCheck("distinctness", "PASS", "first proper validation of the OU family"),
            FeasibilityCheck("cost_after_edge", "PASS", "cheap spread edge exceeds fee and slippage smell test"),
        ),
    )

    assert evaluate_stage2_result(result) == "PASS"


def test_stage2_fails_when_required_check_is_missing() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c1_pairs_ou",
        candidate_dir="c1_pairs_ou",
        hypothesis_id="H-006",
        family_id="F-PAIRS-OU",
        checks=(
            FeasibilityCheck("data_availability", "PASS", "venue-scoped BTC/ETH data exists"),
            FeasibilityCheck("distinctness", "PASS", "first proper validation of the OU family"),
        ),
    )

    assert evaluate_stage2_result(result) == "FAIL"


def test_stage2_fails_when_any_required_check_fails() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c3_sentiment",
        candidate_dir="c3_sentiment",
        hypothesis_id="H-008",
        family_id="F-SENTIMENT",
        checks=(
            FeasibilityCheck("data_availability", "FAIL", "fear_greed_btc event_count=0"),
            FeasibilityCheck("distinctness", "PASS", "sentiment family is distinct"),
            FeasibilityCheck("cost_after_edge", "FAIL", "cost smell test cannot run without feature data"),
        ),
    )

    assert evaluate_stage2_result(result) == "FAIL"


def test_result_from_dict_rejects_unknown_status() -> None:
    payload = {
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [
            {"name": "data_availability", "status": "MAYBE", "reason": "ambiguous"}
        ],
    }

    with pytest.raises(ValueError, match="unknown Stage 2 status"):
        result_from_dict(payload)


def test_result_from_dict_rejects_non_object_payload() -> None:
    with pytest.raises(ValueError, match="Stage 2 payload must be an object"):
        result_from_dict([])


def test_result_from_dict_rejects_duplicate_required_check_names() -> None:
    payload = {
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [
            {"name": "data_availability", "status": "FAIL", "reason": "missing data"},
            {"name": "data_availability", "status": "PASS", "reason": "last-wins mask"},
            {"name": "distinctness", "status": "PASS", "reason": "distinct"},
            {"name": "cost_after_edge", "status": "PASS", "reason": "cost ok"},
        ],
    }

    with pytest.raises(ValueError, match="duplicate Stage 2 check"):
        result_from_dict(payload)


def test_result_from_dict_rejects_lowercase_status() -> None:
    payload = {
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [
            {"name": "data_availability", "status": "pass", "reason": "lowercase"}
        ],
    }

    with pytest.raises(ValueError, match="unknown Stage 2 status"):
        result_from_dict(payload)


def test_result_from_dict_rejects_string_schema_version() -> None:
    payload = {
        "schema_version": "1",
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [],
    }

    with pytest.raises(ValueError, match="unsupported Stage 2 schema_version"):
        result_from_dict(payload)


def test_result_from_dict_rejects_float_schema_version() -> None:
    payload = {
        "schema_version": 1.0,
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [],
    }

    with pytest.raises(ValueError, match="unsupported Stage 2 schema_version"):
        result_from_dict(payload)


def test_result_from_dict_rejects_bool_schema_version() -> None:
    payload = {
        "schema_version": True,
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [],
    }

    with pytest.raises(ValueError, match="unsupported Stage 2 schema_version"):
        result_from_dict(payload)


def test_result_from_dict_rejects_non_object_check() -> None:
    payload = {
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": ["not an object"],
    }

    with pytest.raises(ValueError, match="Stage 2 check must be an object"):
        result_from_dict(payload)


def test_result_from_dict_rejects_null_check_details() -> None:
    payload = {
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [
            {
                "name": "data_availability",
                "status": "FAIL",
                "reason": "missing data",
                "details": None,
            }
        ],
    }

    with pytest.raises(ValueError, match="Stage 2 check details must be an object"):
        result_from_dict(payload)


def test_result_to_dict_includes_computed_stage2_status() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c3_sentiment",
        candidate_dir="c3_sentiment",
        hypothesis_id="H-008",
        family_id="F-SENTIMENT",
        checks=(
            FeasibilityCheck(
                "data_availability",
                "FAIL",
                "fear_greed_btc event_count=0",
                {"dataset_id": "fear_greed_btc", "event_count": 0},
            ),
            FeasibilityCheck("distinctness", "PASS", "sentiment family is distinct"),
            FeasibilityCheck("cost_after_edge", "FAIL", "cost smell test cannot run without feature data"),
        ),
    )

    payload = result_to_dict(result)

    assert payload["schema_version"] == 1
    assert payload["stage2_status"] == "FAIL"
    assert payload["checks"][0]["details"]["event_count"] == 0
