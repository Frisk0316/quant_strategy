from __future__ import annotations

import copy

import pytest

from backtesting.pipeline_round import (
    join_candidate_inputs,
    prepare_round_manifest,
    reconcile_round,
    seal_round_manifest,
    verify_resume,
)


def _candidate(index: int, track: str) -> dict:
    return {
        "candidate_id": f"C-{index}",
        "family_id": f"F-{index}",
        "track": track,
        "provenance_id": f"P-{index}",
        "verified_paper": track == "new_research",
        "iteration_rationale": "material ex-ante change" if track == "existing_iteration" else None,
        "draft_status": "complete",
        "execution_status": "ready",
        "runner": f"runner-{index}",
    }


def _manifest() -> tuple[dict, set[str]]:
    candidates = [_candidate(i, "new_research" if i < 8 else "existing_iteration") for i in range(10)]
    return {"round_id": "synthetic", "candidates": candidates}, {row["runner"] for row in candidates}


def test_seals_valid_8_2_10_manifest_and_refuses_invalid_slates():
    manifest, runners = _manifest()
    sealed = seal_round_manifest(manifest, registered_runners=runners)
    assert sealed["round_type"] == "complete_round"
    assert len(sealed["manifest_hash"]) == 64

    cases = [
        ({"candidates": manifest["candidates"][:9]}, "candidate_count_outside_10_15"),
        ({"candidates": [_candidate(i, "new_research") for i in range(10)]}, "existing_iteration_count_below_2"),
        (copy.deepcopy(manifest), "runner_not_registered"),
        (copy.deepcopy(manifest), "pending_llm"),
        (copy.deepcopy(manifest), "duplicate_or_missing_family"),
    ]
    cases[2][0]["candidates"][0]["runner"] = "missing"
    cases[3][0]["candidates"][0]["draft_status"] = "pending_llm"
    cases[4][0]["candidates"][1]["family_id"] = cases[4][0]["candidates"][0]["family_id"]
    for bad, reason in cases:
        assert prepare_round_manifest(bad, registered_runners=runners)["round_type"] == "limited_probe"
        with pytest.raises(ValueError, match=reason):
            seal_round_manifest(bad, registered_runners=runners)


def test_join_drops_pending_and_duplicate_family_provenance():
    ready = _candidate(0, "new_research")
    pending = {**_candidate(1, "new_research"), "draft_status": "pending_llm"}
    duplicate = {**ready, "candidate_id": "duplicate"}
    assert join_candidate_inputs([ready, pending, duplicate], []) == [ready]


def test_hash_bound_resume_accepts_identical_and_refuses_mutation():
    manifest, runners = _manifest()
    sealed = seal_round_manifest(manifest, registered_runners=runners)
    verify_resume(sealed, sealed["manifest_hash"])
    mutated = copy.deepcopy(sealed)
    mutated["candidates"][0]["family_id"] = "changed"
    with pytest.raises(ValueError, match="manifest_hash_mismatch"):
        verify_resume(mutated, sealed["manifest_hash"])


def test_reconciliation_refuses_missing_terminal_artifact():
    manifest, runners = _manifest()
    sealed = seal_round_manifest(manifest, registered_runners=runners)
    stage2 = {
        row["candidate_id"]: {"status": "fail", "manifest_hash": sealed["manifest_hash"]}
        for row in sealed["candidates"][1:]
    }
    with pytest.raises(ValueError, match="C-0:missing_or_invalid_stage2_terminal"):
        reconcile_round(sealed, stage2, {})
