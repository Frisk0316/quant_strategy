import json
import subprocess
import sys
from pathlib import Path

import pytest

from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult
from backtesting.pipeline_idea_generator import (
    enumerate_gaps,
    load_feedback_tags,
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


def _taxonomy_with_occupied_overlay_and_blocked() -> str:
    return "\n".join(
        [
            "| Family ID | mechanism | data | status | distinctness | notes |",
            "|---|---|---|---|---|---|",
            "| F-FUNDING-CARRY | funding carry | available | occupied | F-S7 | same mechanism |",
            "| F-S5-RESIDUAL-MEANREV | residual mean reversion | available | occupied | F-PAIRS-OU | same mechanism |",
            "| F-S6-TS-MOMENTUM | time-series momentum | available | occupied | F-XS-MOMENTUM | same mechanism |",
            "| F-VOL-REGIME | volatility regime filter | available | untested-documented overlay, not standalone alpha | F-S6 | no base family |",
            "| F-FUNDING-XS-DISPERSION | funding dispersion | available | frontier-unvetted | F-FUNDING-CARRY | distinct carry spread |",
            "| F-XVENUE-LEADLAG | cross-venue lead lag | partial-available | frontier-unvetted | F-XS-MOMENTUM | candles only |",
            "| F-OFI-MAKER-SKEW | order-flow imbalance | blocked L2 book | untested-documented | F-VPIN-MM | missing data |",
            "| F-VPIN-MM | VPIN microstructure | blocked trade tape | untested-documented | F-OFI-MAKER-SKEW | missing data |",
            "| F-CME-GAP | CME gap | blocked CME source | untested-documented | calendar | missing data |",
            "| F-OI-POSITIONING | open interest positioning | blocked OI ingest | frontier-unvetted | F-FUNDING-XS-DISPERSION | missing data |",
            "| F-LIQUIDATION-CASCADE | liquidation cascade | blocked liquidation feed | frontier-unvetted | F-OI-POSITIONING | missing data |",
            "| F-ONCHAIN-FLOW | on-chain flow | blocked on-chain feed | frontier-unvetted | F-SENTIMENT | missing data |",
            "| F-VOL-RISK-PREMIUM | volatility risk premium | blocked options/IV | frontier-unvetted | F-VOL-REGIME | missing data |",
        ]
    )


def _hypothesis_ledger() -> str:
    return "\n".join(
        [
            "| ID | Family ID | Family cumulative n_trials | Hypothesis | Source | Status | Experiment(s) | Resolution / notes |",
            "|---|---|---:|---|---|---|---|---|",
            "| H-004 | F-S5-RESIDUAL-MEANREV | 72 | residual edge | spec | inconclusive | E-014 | data-universe artifact |",
            "| H-005 | F-S6-TS-MOMENTUM | 48 | momentum edge | spec | inconclusive | E-015 | statistical fail, not final refutation |",
            "| H-007 | F-FUNDING-CARRY | 48 | carry edge | spec | refuted / shelved | E-026 | realism fail |",
        ]
    )


def _registry_conflicting_with_hypothesis_status() -> str:
    return "\n".join(
        [
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E-201 | 2026-06-30 | H-004 | F-S5-RESIDUAL-MEANREV | setup | 72 | `results/s5/summary.json` | shelved / data artifact | registry text should not decide verdict |",
            "| E-202 | 2026-06-30 | H-005 | F-S6-TS-MOMENTUM | setup | 48 | `results/s6/summary.json` | refuted / statistical-fail | registry text should not decide verdict |",
            "| E-203 | 2026-06-30 | H-007 | F-FUNDING-CARRY | setup | 48 | `results/carry/summary.json` | refuted / shelved | same as hypothesis |",
        ]
    )


def _stage2_data(family_id: str, status: str) -> FeasibilityResult:
    return FeasibilityResult(
        batch_id="probe_batch",
        candidate_id=f"probe-{family_id.lower()}",
        candidate_dir=family_id.lower(),
        hypothesis_id="H-PROBE",
        family_id=family_id,
        checks=(
            FeasibilityCheck("data_availability", status, "probe result"),
            FeasibilityCheck("distinctness", "PASS", "not used by B-half data probe"),
            FeasibilityCheck("cost_after_edge", "PASS", "not used by B-half data probe"),
        ),
    )


def test_enumerate_gaps_filters_refuted_and_data_blocked_families():
    result = enumerate_gaps(_taxonomy(), _registry())

    eligible = {row["family_id"] for row in result["eligible"]}
    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert {"F-FUNDING-XS-DISPERSION", "F-XVENUE-LEADLAG"} <= eligible
    assert skipped["F-FUNDING-CARRY"] == "refuted_no_twist"
    assert skipped["F-OI-POSITIONING"] == "data_blocked"


def test_enumerate_gaps_uses_stage2_probe_before_taxonomy_fallback():
    def probe(row):
        if row.get("Family ID") == "F-OI-POSITIONING":
            return _stage2_data("F-OI-POSITIONING", "PASS")
        return None

    result = enumerate_gaps(_taxonomy(), _registry(), data_availability_probe=probe)

    eligible = {row["family_id"] for row in result["eligible"]}
    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert "F-OI-POSITIONING" in eligible
    assert "F-OI-POSITIONING" not in skipped


def test_enumerate_gaps_blocks_when_stage2_probe_fails_even_if_taxonomy_says_available():
    def probe(row):
        if row.get("Family ID") == "F-FUNDING-XS-DISPERSION":
            return _stage2_data("F-FUNDING-XS-DISPERSION", "FAIL")
        return None

    result = enumerate_gaps(_taxonomy(), _registry(), data_availability_probe=probe)

    eligible = {row["family_id"] for row in result["eligible"]}
    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert "F-FUNDING-XS-DISPERSION" not in eligible
    assert skipped["F-FUNDING-XS-DISPERSION"] == "data_blocked"


def test_enumerate_gaps_falls_back_to_taxonomy_when_probe_has_no_answer():
    result = enumerate_gaps(_taxonomy(), _registry(), data_availability_probe=lambda row: None)
    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert skipped["F-OI-POSITIONING"] == "data_blocked"


def test_enumerate_gaps_uses_hypothesis_ledger_status_before_experiment_outcome():
    result = enumerate_gaps(
        _taxonomy_with_occupied_overlay_and_blocked(),
        _registry_conflicting_with_hypothesis_status(),
        hypothesis_ledger_text=_hypothesis_ledger(),
    )

    eligible = {row["family_id"] for row in result["eligible"]}
    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert "F-S5-RESIDUAL-MEANREV" not in eligible
    assert "F-S6-TS-MOMENTUM" not in eligible
    assert skipped["F-S5-RESIDUAL-MEANREV"] == "inconclusive_no_twist"
    assert skipped["F-S6-TS-MOMENTUM"] == "inconclusive_no_twist"
    assert skipped["F-FUNDING-CARRY"] == "refuted_no_twist"


def test_enumerate_gaps_skips_overlay_without_base_before_data_fallback():
    result = enumerate_gaps(
        _taxonomy_with_occupied_overlay_and_blocked(),
        _registry_conflicting_with_hypothesis_status(),
        hypothesis_ledger_text=_hypothesis_ledger(),
    )

    eligible = {row["family_id"] for row in result["eligible"]}
    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert "F-VOL-REGIME" not in eligible
    assert skipped["F-VOL-REGIME"] == "overlay_needs_base"


def test_enumerate_gaps_keeps_known_data_blocked_families_blocked():
    result = enumerate_gaps(
        _taxonomy_with_occupied_overlay_and_blocked(),
        _registry_conflicting_with_hypothesis_status(),
        hypothesis_ledger_text=_hypothesis_ledger(),
    )

    skipped = {row["family_id"]: row["reason"] for row in result["skipped"]}

    assert skipped["F-OFI-MAKER-SKEW"] == "data_blocked"
    assert skipped["F-VPIN-MM"] == "data_blocked"
    assert skipped["F-CME-GAP"] == "data_blocked"
    assert skipped["F-OI-POSITIONING"] == "data_blocked"
    assert skipped["F-LIQUIDATION-CASCADE"] == "data_blocked"
    assert skipped["F-ONCHAIN-FLOW"] == "data_blocked"
    assert skipped["F-VOL-RISK-PREMIUM"] == "data_blocked"


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


def test_feedback_tags_only_change_rank_and_mark_feedback_spawned():
    plain = enumerate_gaps(_taxonomy(), _registry())
    tagged = enumerate_gaps(
        _taxonomy(),
        _registry(),
        feedback_tags={
            "F-FUNDING-XS-DISPERSION": {
                "verdict": "proposed",
                "reasons": ["breadth_fail"],
                "guidance": "avoid",
            }
        },
    )

    plain_selected, plain_skipped = rank_and_cap(plain["eligible"])
    tagged_selected, tagged_skipped = rank_and_cap(tagged["eligible"])

    assert {row["family_id"] for row in plain_selected} == {row["family_id"] for row in tagged_selected}
    assert [row["family_id"] for row in plain_selected] != [row["family_id"] for row in tagged_selected]
    assert {row["family_id"]: row["reason"] for row in plain["skipped"]} == {
        row["family_id"]: row["reason"] for row in tagged["skipped"]
    }
    feedback_row = next(row for row in tagged_selected if row["family_id"] == "F-FUNDING-XS-DISPERSION")
    assert feedback_row["feedback_spawned"] is True
    assert feedback_row["feedback_rank_penalty"] == 20
    assert feedback_row["feedback_reasons"] == ["breadth_fail"]
    assert all(row["reason"] == "cap_overflow" for row in plain_skipped + tagged_skipped)


def test_feedback_tags_loader_missing_file_is_no_bias(tmp_path):
    assert load_feedback_tags(tmp_path / "missing.yaml") == {}


def test_feedback_tags_loader_rejects_bad_schema(tmp_path):
    path = tmp_path / "bad_tags.yaml"
    path.write_text("families:\n  F-BAD: {verdict: proposed, reasons: [x], guidance: boost}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid guidance"):
        load_feedback_tags(path)


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
    hypothesis_path = tmp_path / "HYPOTHESIS_LEDGER.md"
    taxonomy_path.write_text(_taxonomy(), encoding="utf-8")
    registry_path.write_text(_registry(), encoding="utf-8")
    hypothesis_path.write_text(_hypothesis_ledger(), encoding="utf-8")

    exit_code = main(
        [
            "--taxonomy",
            str(taxonomy_path),
            "--ledger",
            str(registry_path),
            "--hypothesis-ledger",
            str(hypothesis_path),
            "--batch-id",
            "cli_batch",
            "--output-root",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads((tmp_path / "cli_batch" / "idea_batch.json").read_text(encoding="utf-8"))
    metrics = json.loads((tmp_path / "cli_batch" / "funnel_metrics.json").read_text(encoding="utf-8"))
    assert payload["n_eligible_before_cap"] == 2
    assert metrics["selected"] == payload["n_selected"]
    assert metrics["skipped"] == {row["reason"]: 1 for row in payload["skipped"]}


def test_idea_generator_cli_uses_hypothesis_ledger_for_taxonomy_batch(tmp_path):
    taxonomy_path = tmp_path / "taxonomy.md"
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    hypothesis_path = tmp_path / "HYPOTHESIS_LEDGER.md"
    taxonomy_path.write_text(_taxonomy_with_occupied_overlay_and_blocked(), encoding="utf-8")
    registry_path.write_text(_registry_conflicting_with_hypothesis_status(), encoding="utf-8")
    hypothesis_path.write_text(_hypothesis_ledger(), encoding="utf-8")

    exit_code = main(
        [
            "--taxonomy",
            str(taxonomy_path),
            "--ledger",
            str(registry_path),
            "--hypothesis-ledger",
            str(hypothesis_path),
            "--batch-id",
            "taxonomy_batch",
            "--output-root",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads((tmp_path / "taxonomy_batch" / "idea_batch.json").read_text(encoding="utf-8"))
    selected = {row["family_id"] for row in payload["candidates"]}
    skipped = {row["family_id"]: row["reason"] for row in payload["skipped"]}

    assert payload["n_eligible_before_cap"] == 2
    assert selected == {"F-FUNDING-XS-DISPERSION", "F-XVENUE-LEADLAG"}
    assert skipped["F-VOL-REGIME"] == "overlay_needs_base"
    assert skipped["F-S6-TS-MOMENTUM"] == "inconclusive_no_twist"


def test_idea_generator_script_runs_from_repo_root(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    taxonomy_path = tmp_path / "taxonomy.md"
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    hypothesis_path = tmp_path / "HYPOTHESIS_LEDGER.md"
    taxonomy_path.write_text(_taxonomy(), encoding="utf-8")
    registry_path.write_text(_registry(), encoding="utf-8")
    hypothesis_path.write_text(_hypothesis_ledger(), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_pipeline_idea_generator.py",
            "--taxonomy",
            str(taxonomy_path),
            "--ledger",
            str(registry_path),
            "--hypothesis-ledger",
            str(hypothesis_path),
            "--batch-id",
            "script_batch",
            "--output-root",
            str(tmp_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((tmp_path / "script_batch" / "idea_batch.json").read_text(encoding="utf-8"))
    assert payload["n_eligible_before_cap"] == 2
