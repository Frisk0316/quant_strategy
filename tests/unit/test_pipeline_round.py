from __future__ import annotations

import copy
import hashlib

import pytest

from backtesting.pipeline_round import (
    join_candidate_inputs,
    prepare_round_manifest,
    reconcile_round,
    seal_round_manifest,
    verify_resume,
)


def _candidate(index: int, track: str, artifact_path, artifact_sha256: str) -> dict:
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
        "datasets": [
            {
                "dataset_id": f"dataset-{index}",
                "locator": "external_observations",
                "row_count": 100 + index,
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-02-01T00:00:00Z",
            }
        ],
        "expected_gross_capture_bps": 4.0,
        "modeled_cost_bps": 8.0,
        "gross_estimate_provenance": "paper section 4 ex-ante estimate",
        "breadth": 2.0,
        "breadth_provenance": {"path": str(artifact_path), "sha256": artifact_sha256},
    }


def _manifest(tmp_path) -> tuple[dict, set[str]]:
    artifact = tmp_path / "realized_positions.json"
    artifact.write_text('{"positions": [{"symbol": "BTC", "weight": 1.0}]}', encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    candidates = [
        _candidate(i, "new_research" if i < 8 else "existing_iteration", artifact, digest)
        for i in range(10)
    ]
    return {"round_id": "synthetic", "candidates": candidates}, {row["runner"] for row in candidates}


def _matching_dataset(_dsn, claim):
    return {"row_count": claim["row_count"], "start": claim["start"], "end": claim["end"]}


@pytest.mark.asyncio
async def test_seals_valid_8_2_10_manifest_and_refuses_invalid_slates(tmp_path):
    manifest, runners = _manifest(tmp_path)
    sealed = await seal_round_manifest(
        manifest,
        registered_runners=runners,
        dsn="postgresql://mock",
        dataset_query=_matching_dataset,
        artifact_root=tmp_path,
    )
    assert sealed["round_type"] == "complete_round"
    assert sealed["counted_candidate_count"] == 10
    assert sealed["candidates"][0]["gross_over_cost"] == 0.5  # I68 records; B3's ratio gate is not duplicated.
    assert len(sealed["manifest_hash"]) == 64

    cases = [
        ({"candidates": manifest["candidates"][:9]}, "candidate_count_outside_10_15"),
        ({"candidates": [_candidate(i, "new_research", tmp_path / "realized_positions.json", manifest["candidates"][0]["breadth_provenance"]["sha256"]) for i in range(10)]}, "existing_iteration_count_below_2"),
        (copy.deepcopy(manifest), "runner_not_registered"),
        (copy.deepcopy(manifest), "pending_llm"),
        (copy.deepcopy(manifest), "duplicate_or_missing_family"),
    ]
    cases[2][0]["candidates"][0]["runner"] = "missing"
    cases[3][0]["candidates"][0]["draft_status"] = "pending_llm"
    cases[4][0]["candidates"][1]["family_id"] = cases[4][0]["candidates"][0]["family_id"]
    for bad, reason in cases:
        prepared = await prepare_round_manifest(
            bad,
            registered_runners=runners,
            dsn="postgresql://mock",
            dataset_query=_matching_dataset,
            artifact_root=tmp_path,
        )
        assert prepared["round_type"] == "limited_probe"
        with pytest.raises(ValueError, match=reason):
            await seal_round_manifest(
                bad,
                registered_runners=runners,
                dsn="postgresql://mock",
                dataset_query=_matching_dataset,
                artifact_root=tmp_path,
            )


def test_join_drops_pending_and_duplicate_family_provenance(tmp_path):
    manifest, _ = _manifest(tmp_path)
    ready = manifest["candidates"][0]
    pending = {**manifest["candidates"][1], "draft_status": "pending_llm"}
    duplicate = {**ready, "candidate_id": "duplicate"}
    assert join_candidate_inputs([ready, pending, duplicate], []) == [{**ready, "track": "new_research"}]


@pytest.mark.asyncio
async def test_i68_refuses_missing_or_mismatched_numbers_and_requires_live_dsn(tmp_path):
    manifest, runners = _manifest(tmp_path)
    with pytest.raises(ValueError, match="dsn_required"):
        await seal_round_manifest(manifest, registered_runners=runners, artifact_root=tmp_path)

    missing_fields = [
        ("datasets", "C-0:missing_dataset_claims"),
        ("expected_gross_capture_bps", "C-0:missing_or_invalid_expected_gross_capture_bps"),
        ("modeled_cost_bps", "C-0:missing_or_invalid_modeled_cost_bps"),
        ("gross_estimate_provenance", "C-0:missing_or_invalid_gross_estimate_provenance"),
    ]
    for field, reason in missing_fields:
        bad = copy.deepcopy(manifest)
        bad["candidates"][0].pop(field)
        prepared = await prepare_round_manifest(
            bad,
            registered_runners=runners,
            dsn="postgresql://mock",
            dataset_query=_matching_dataset,
            artifact_root=tmp_path,
        )
        assert prepared["counted_candidate_count"] == 9
        with pytest.raises(ValueError, match=reason):
            await seal_round_manifest(
                bad,
                registered_runners=runners,
                dsn="postgresql://mock",
                dataset_query=_matching_dataset,
                artifact_root=tmp_path,
            )

    def mismatched_dataset(_dsn, claim):
        observed = _matching_dataset(_dsn, claim)
        if claim["dataset_id"] == "dataset-0":
            observed = {**observed, "row_count": 99, "end": "2024-01-31T00:00:00Z"}
        return observed

    with pytest.raises(ValueError, match="C-0:dataset-0:dataset_row_count_mismatch") as exc:
        await seal_round_manifest(
            manifest,
            registered_runners=runners,
            dsn="postgresql://mock",
            dataset_query=mismatched_dataset,
            artifact_root=tmp_path,
        )
    assert "C-0:dataset-0:dataset_range_mismatch" in str(exc.value)


@pytest.mark.asyncio
async def test_i68_coerces_unreferenced_breadth_to_one_and_does_not_count_candidate(tmp_path):
    manifest, runners = _manifest(tmp_path)
    manifest["candidates"][0].pop("breadth_provenance")
    prepared = await prepare_round_manifest(
        manifest,
        registered_runners=runners,
        dsn="postgresql://mock",
        dataset_query=_matching_dataset,
        artifact_root=tmp_path,
    )

    row = prepared["candidates"][0]
    assert prepared["round_type"] == "limited_probe"
    assert prepared["counted_candidate_count"] == 9
    assert row["breadth"] == 1.0
    assert row["breadth_coercion"] == {"declared": 2.0, "used": 1.0, "reason": "missing_breadth_derivation"}
    assert row["counted"] is False


@pytest.mark.asyncio
async def test_hash_bound_resume_accepts_identical_and_refuses_mutation(tmp_path):
    manifest, runners = _manifest(tmp_path)
    sealed = await seal_round_manifest(
        manifest,
        registered_runners=runners,
        dsn="postgresql://mock",
        dataset_query=_matching_dataset,
        artifact_root=tmp_path,
    )
    verify_resume(sealed, sealed["manifest_hash"])
    mutated = copy.deepcopy(sealed)
    mutated["candidates"][0]["family_id"] = "changed"
    with pytest.raises(ValueError, match="manifest_hash_mismatch"):
        verify_resume(mutated, sealed["manifest_hash"])


@pytest.mark.asyncio
async def test_reconciliation_refuses_missing_terminal_artifact(tmp_path):
    manifest, runners = _manifest(tmp_path)
    sealed = await seal_round_manifest(
        manifest,
        registered_runners=runners,
        dsn="postgresql://mock",
        dataset_query=_matching_dataset,
        artifact_root=tmp_path,
    )
    stage2 = {
        row["candidate_id"]: {"status": "fail", "manifest_hash": sealed["manifest_hash"]}
        for row in sealed["candidates"][1:]
    }
    with pytest.raises(ValueError, match="C-0:missing_or_invalid_stage2_terminal"):
        reconcile_round(sealed, stage2, {})
