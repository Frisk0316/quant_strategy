import pytest

from backtesting.pipeline_stage3_registry import STAGE3_RUNNERS, _LEGACY_BATCH_ID, _legacy_runner


def test_legacy_stage3_runner_refuses_non_legacy_batch():
    runner = STAGE3_RUNNERS["F-PAIRS-OU"]

    with pytest.raises(RuntimeError, match="refusing to run"):
        runner({"batch_id": "idea_batch_20260701_taxonomy_002"})


def test_legacy_stage3_runner_calls_wrapped_function_only_for_legacy_batch():
    called = []
    runner = _legacy_runner(lambda: called.append("ran") or {"ok": True}, "F-PAIRS-OU")

    assert runner({"batch_id": _LEGACY_BATCH_ID}) == {"ok": True}
    assert called == ["ran"]


def test_funding_xs_dispersion_frontier_family_is_registered():
    assert "F-FUNDING-XS-DISPERSION" in STAGE3_RUNNERS


def test_oi_positioning_frontier_family_is_registered():
    assert "F-OI-POSITIONING" in STAGE3_RUNNERS


def test_unimplemented_frontier_families_are_not_registered_as_stage3_runners():
    assert "F-XVENUE-LEADLAG" not in STAGE3_RUNNERS
