import json

from backtesting.pipeline_family_minting import decide_family_minting
from scripts.run_pipeline_family_minting_check import main


def _registry() -> str:
    return "\n".join(
        [
            "| Family ID | K_used | K_limit | Basis (rows counted as retries) |",
            "|---|---:|---:|---|",
            "| F-FUNDING-CARRY | 1 | 2 | E-024 original -> E-026 realism re-cost |",
            "| F-XS-MOMENTUM | 2 | 2 | E-003 original -> E-004 leak-fix -> E-005 sizing-fix |",
            "| F-PAIRS-OU | 0 | 2 | E-025 only real run |",
            "| F-SENTIMENT | 0 | 2 | E-027 only real run |",
            "",
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E-101 | 2026-06-30 | H-101 | F-FUNDING-CARRY | setup | 48 | `results/funding/summary.json` | refuted / shelved | current row |",
            "| E-102 | 2026-06-30 | H-102 | F-OTHER | setup | 12 | `results/other/summary.json` | checkpoint | current row |",
            "| E-103 | 2026-06-23 | H-002 | F-XS-MOMENTUM | original grid | 8 | `results/xs/original/summary.json` | invalid / superseded | original run |",
            "| E-104 | 2026-06-24 | H-002 | F-XS-MOMENTUM | leak-fix grid | 8 | `results/xs/leakfix/summary.json` | refuted | leak fix |",
            "| E-105 | 2026-06-24 | H-002 | F-XS-MOMENTUM | sizing-fix grid; per-run recorded `n_trials=8` under the old convention | 8 | `results/xs/portfoliovol/summary.json` | refuted | Under the family-cumulative rule, F-XS-MOMENTUM has at least 24 trials from E-103/E-104/E-105 before any future retry. |",
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
    assert result["k_used"] == 1
    assert result["k_limit"] == 2
    assert result["at_k_limit"] is False
    assert "inherited_K" not in result


def test_at_limit_family_reports_real_k_budget(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    result = decide_family_minting(
        [1.0, -1.0, 1.0, -1.0],
        {"F-XS-MOMENTUM": [1.0, -1.0, 1.0, -1.0]},
        "F-XS-MOMENTUM",
        "declared retry at limit",
        registry_path,
    )

    assert result["decision"] == "ASSIGN"
    assert result["inherited_n_trials"] == 24
    assert result["nearest_family_cumulative_n_trials"] == 24
    assert result["k_used"] == 2
    assert result["k_limit"] == 2
    assert result["at_k_limit"] is True


def test_zero_retry_families_report_zero_k_used(tmp_path):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    pairs = decide_family_minting(
        [1.0, 2.0, 3.0],
        {"F-PAIRS-OU": [1.0, 2.0, 3.0]},
        "F-PAIRS-OU",
        "pairs retry",
        registry_path,
    )
    sentiment = decide_family_minting(
        [1.0, 2.0, 3.0],
        {"F-SENTIMENT": [1.0, 2.0, 3.0]},
        "F-SENTIMENT",
        "sentiment retry",
        registry_path,
    )

    assert pairs["k_used"] == 0
    assert pairs["k_limit"] == 2
    assert pairs["at_k_limit"] is False
    assert sentiment["k_used"] == 0
    assert sentiment["k_limit"] == 2
    assert sentiment["at_k_limit"] is False


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
