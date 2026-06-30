import json

from backtesting.pipeline_idea_generator import (
    enumerate_gaps,
    rank_and_cap,
    register_batch,
)
from scripts.run_pipeline_idea_generator import main


def _taxonomy() -> str:
    return "\n".join(
        [
            "| Family ID | 機制 | 經濟理由 | 資料 | status / 裁決 | distinctness 鄰居 | crowding/decay |",
            "|---|---|---|---|---|---|---|",
            "| F-FUNDING-CARRY | carry | reason | available | occupied / **refuted-shelved**(H-007) | F-X | 高 |",
            "| F-FUNDING-XS-DISPERSION | funding dispersion | reason | **available**(30 標的 funding 齊) | frontier-unvetted | F-FUNDING-CARRY | 高 |",
            "| F-XVENUE-LEADLAG | xvenue lead lag | reason | **partial-available**(多所 candles) | frontier-unvetted | F-XS-MOMENTUM | 中 |",
            "| F-OI-POSITIONING | OI positioning | reason | **blocked**(OI 史未 ingest) | frontier-unvetted | F-FUNDING-XS-DISPERSION | 中 |",
        ]
    )


def _registry() -> str:
    return "\n".join(
        [
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E-101 | 2026-06-30 | H-101 | F-FUNDING-CARRY | setup | 48 | `results/funding/summary.json` | refuted / shelved | current row |",
        ]
    )


def test_enumerate_gaps_filters_refuted_and_data_blocked_families():
    result = enumerate_gaps(_taxonomy(), _registry())

    eligible = {row["family_id"] for row in result["eligible"]}
    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert {"F-FUNDING-XS-DISPERSION", "F-XVENUE-LEADLAG"} <= eligible
    assert skipped["F-FUNDING-CARRY"] == "refuted_no_twist"
    assert skipped["F-OI-POSITIONING"] == "data_blocked"


def test_rank_and_cap_is_deterministic_and_marks_overflow():
    gaps = [
        {
            "family_id": f"F-{idx:02d}",
            "mechanism": "m",
            "data_feasible": True,
            "data_rank": 0 if idx % 2 == 0 else 1,
            "crowding_rank": idx % 3,
            "planned_grid_size": idx + 1,
        }
        for idx in range(20)
    ]

    selected, skipped = rank_and_cap(gaps, cap=15)

    assert len(selected) == 15
    assert [row["prior_rank"] for row in selected] == list(range(1, 16))
    assert all(row["reason"] == "cap_overflow" for row in skipped)


def test_register_batch_writes_sidecar_and_ledger_draft_after_family_minting(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")
    candidates = [
        {
            "provisional_candidate_id": "B-001",
            "family_id_or_NEW": "NEW",
            "mechanism": "funding dispersion",
            "data_feasible": True,
            "prior_rank": 1,
            "planned_grid_size": 6,
            "draft_status": "drafted",
            "representative_signal": [1.0, 2.0, 3.0],
            "reference_signals": {"F-FUNDING-CARRY": [1.0, 2.0, 3.0]},
            "feedback_spawned": True,
        }
    ]

    payload = register_batch(candidates, "idea_batch_test", registry_path, output_root=tmp_path)

    batch_path = tmp_path / "idea_batch_test" / "idea_batch.json"
    ledger_draft = tmp_path / "idea_batch_test" / "hypothesis_ledger_draft.md"
    saved = json.loads(batch_path.read_text(encoding="utf-8"))

    assert payload["batch_id"] == "idea_batch_test"
    assert saved["candidates"][0]["family_minting_decision"] == "SKIP_RECOMMENDED"
    assert saved["candidates"][0]["feedback_spawned"] is True
    assert "B-001" in ledger_draft.read_text(encoding="utf-8")


def test_register_batch_accepts_a_half_drafts_in_same_batch(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    payload = register_batch(
        [],
        "mixed_batch",
        registry_path,
        output_root=tmp_path,
        a_half_drafts=[
            {
                "provisional_candidate_id": "A-001",
                "family_id_or_NEW": "F-FUNDING-CARRY",
                "mechanism": "paper-derived carry filter",
                "data_feasible": True,
                "prior_rank": 1,
                "planned_grid_size": 4,
                "draft_status": "drafted",
                "feedback_spawned": False,
            }
        ],
    )

    assert payload["source"] == "mixed"
    assert payload["candidates"][0]["source"] == "A_literature"
    assert payload["candidates"][0]["family_minting_decision"] == "ASSIGN"


def test_idea_generator_cli_writes_batch(tmp_path):
    taxonomy_path = tmp_path / "taxonomy.md"
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    taxonomy_path.write_text(_taxonomy(), encoding="utf-8")
    registry_path.write_text(_registry(), encoding="utf-8")

    exit_code = main(
        [
            "--taxonomy",
            str(taxonomy_path),
            "--ledger",
            str(registry_path),
            "--batch-id",
            "cli_batch",
            "--output-root",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads((tmp_path / "cli_batch" / "idea_batch.json").read_text(encoding="utf-8"))
    assert payload["n_eligible_before_cap"] == 2
