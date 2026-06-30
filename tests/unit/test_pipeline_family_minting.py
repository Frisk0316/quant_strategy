import json

from backtesting.pipeline_family_minting import decide_family_minting
from scripts.run_pipeline_family_minting_check import main


def _registry() -> str:
    return "\n".join(
        [
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E-101 | 2026-06-30 | H-101 | F-FUNDING-CARRY | setup | 48 | `results/funding/summary.json` | refuted / shelved | current row |",
            "| E-102 | 2026-06-30 | H-102 | F-OTHER | setup | 12 | `results/other/summary.json` | checkpoint | current row |",
        ]
    )


def test_identical_signal_assigns_and_cannot_mint(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    result = decide_family_minting(
        [1.0, 2.0, 3.0, 4.0],
        {"F-OTHER": [1.0, 2.0, 3.0, 4.0]},
        "NEW",
        "same shape with new label",
        registry_path,
    )

    assert result["decision"] == "ASSIGN"
    assert result["nearest_family_id"] == "F-OTHER"
    assert result["provisional_new_family"] is False
    assert result["inherited_n_trials"] == 12


def test_new_funding_claim_highly_correlated_to_refuted_family_is_skip_recommended(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    result = decide_family_minting(
        [1.0, 2.0, 3.0, 4.0],
        {"F-FUNDING-CARRY": [1.0, 2.0, 3.0, 4.1]},
        "NEW",
        "funding dispersion but same carry exposure",
        registry_path,
    )

    assert result["decision"] == "SKIP_RECOMMENDED"
    assert result["nearest_family_id"] == "F-FUNDING-CARRY"
    assert result["nearest_family_cumulative_n_trials"] == 48
    assert result["provisional_new_family"] is False


def test_orthogonal_new_claim_gets_provisional_mint_with_human_review(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    result = decide_family_minting(
        [1.0, -1.0, 1.0, -1.0],
        {"F-OTHER": [1.0, 1.0, -1.0, -1.0]},
        "NEW",
        "different economic mechanism",
        registry_path,
    )

    assert result["decision"] == "MINT"
    assert result["provisional_new_family"] is True
    assert result["inherited_n_trials"] == 0
    assert "mechanism_novelty" in result["human_review_items"]


def test_claimed_existing_family_assigns_and_inherits_registry_trials(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    result = decide_family_minting(
        [1.0, -1.0, 1.0, -1.0],
        {"F-OTHER": [1.0, 1.0, -1.0, -1.0]},
        "F-FUNDING-CARRY",
        "declared retry",
        registry_path,
    )

    assert result["decision"] == "ASSIGN"
    assert result["nearest_family_id"] == "F-FUNDING-CARRY"
    assert result["inherited_n_trials"] == 48
    assert result["inherited_K"] == 48


def test_borderline_correlation_needs_human(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    result = decide_family_minting(
        [0.0, 1.0, 2.0, 3.0],
        {"F-OTHER": [0.0, 1.0, 2.0, 1.5]},
        "NEW",
        "maybe new mechanism",
        registry_path,
    )

    assert 0.70 <= result["max_abs_corr"] < 0.90
    assert result["decision"] == "NEEDS_HUMAN"
    assert "borderline_distinctness" in result["human_review_items"]


def test_family_minting_cli_writes_json(tmp_path):
    candidate_path = tmp_path / "candidate.json"
    refs_path = tmp_path / "refs.json"
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    output_path = tmp_path / "family_minting.json"
    candidate_path.write_text(
        json.dumps(
            {
                "batch_id": "batch",
                "candidate_id": "candidate",
                "claimed_family_id_or_NEW": "NEW",
                "claimed_mechanism": "different economic mechanism",
                "signal": [1.0, -1.0, 1.0, -1.0],
            }
        ),
        encoding="utf-8",
    )
    refs_path.write_text(json.dumps({"F-OTHER": [1.0, 1.0, -1.0, -1.0]}), encoding="utf-8")
    registry_path.write_text(_registry(), encoding="utf-8")

    exit_code = main(
        [
            "--candidate",
            str(candidate_path),
            "--refs",
            str(refs_path),
            "--ledger",
            str(registry_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "MINT"
    assert payload["human_review_items"]
