import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import run_pipeline_literature_ideas as literature


def _registry() -> str:
    return "\n".join(
        [
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E-101 | 2026-06-30 | H-101 | F-FUNDING-CARRY | setup | 48 | `results/funding/summary.json` | refuted / shelved | current row |",
        ]
    )


def _paper(paper_id: str, title: str = "Funding Premia") -> dict[str, object]:
    return {
        "paper_id": paper_id,
        "title": title,
        "authors": ("A",),
        "year": 2025,
        "source_type": "preprint",
        "url": f"https://example.test/{paper_id}",
        "source": "arxiv:q-fin.TR",
    }


def _score(paper_id: str, *, evidence_quality: int = 5) -> dict[str, object]:
    return {
        "paper_id": paper_id,
        "title": f"Score {paper_id}",
        "authors": ("A",),
        "year": 2025,
        "source_type": "preprint",
        "url": f"https://example.test/{paper_id}",
        "alpha_category": "carry",
        "expected_horizon": "multi_day",
        "required_data": ("spot_price", "perp_price", "funding_rate"),
        "evidence_quality": evidence_quality,
        "crypto_relevance": evidence_quality,
        "data_availability": evidence_quality,
        "implementation_fit": evidence_quality,
        "cost_awareness": evidence_quality,
        "novelty": 3,
        "leakage_risk": 0,
        "overfit_risk": 0,
    }


def test_literature_driver_writes_pending_llm_batch_and_weekly_screen(tmp_path, monkeypatch):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    def fake_fetch(sources, date_window, opener=None):
        assert sources == ["arxiv:q-fin.TR"]
        assert date_window == ("2018", "2026")
        assert opener is object_opener
        return [_paper("hi"), _paper("lo")]

    object_opener = object()
    monkeypatch.setattr(literature, "fetch_papers", fake_fetch)

    payload = literature.generate_literature_batch(
        sources=["arxiv:q-fin.TR"],
        date_window=("2018", "2026"),
        batch_id="idea_batch_20260701_literature_test",
        ledger_path=registry_path,
        output_root=tmp_path,
        scores=[_score("hi"), _score("lo", evidence_quality=1)],
        opener=object_opener,
        weekly_date="2026-07-01",
    )

    batch_dir = tmp_path / "idea_batch_20260701_literature_test"
    saved = json.loads((batch_dir / "idea_batch.json").read_text(encoding="utf-8"))
    candidate = saved["candidates"][0]

    assert payload["batch_id"] == "idea_batch_20260701_literature_test"
    assert saved["source"] in {"A_literature", "mixed"}
    assert candidate["source"] == "A_literature"
    assert candidate["draft_status"] == "pending_llm"
    assert candidate["allow_live_trading"] is False
    assert "family_minting" not in candidate
    assert "family_minting_decision" not in candidate
    assert {row["paper_id"]: row["reason"] for row in saved["skipped"]} == {"lo": "below_threshold"}
    assert (batch_dir / "hypothesis_ledger_draft.md").exists()
    assert (batch_dir / "weekly_screen" / "search_log_2026-07-01.md").exists()
    assert (batch_dir / "weekly_screen" / "screen_2026-07-01.json").exists()


def test_literature_driver_caps_promoted_drafts_before_register(tmp_path, monkeypatch):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")
    papers = [_paper(f"paper-{idx:02d}") for idx in range(16)]
    monkeypatch.setattr(literature, "fetch_papers", lambda *args, **kwargs: papers)

    payload = literature.generate_literature_batch(
        sources=["arxiv:q-fin.TR"],
        date_window=("2018", "2026"),
        batch_id="idea_batch_cap",
        ledger_path=registry_path,
        output_root=tmp_path,
        scores=[_score(str(paper["paper_id"])) for paper in papers],
        cap=15,
        weekly_date="2026-07-01",
    )

    assert payload["n_selected"] == 15
    assert payload["n_eligible_before_cap"] == 16
    assert payload["skipped"][-1] == {"paper_id": "paper-15", "reason": "cap_overflow"}


def test_literature_driver_firewall_raises_before_writing_batch(tmp_path, monkeypatch):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")
    monkeypatch.setattr(
        literature,
        "fetch_papers",
        lambda *args, **kwargs: [dict(_paper("leaky"), price_series=[1, 2, 3])],
    )

    with pytest.raises(ValueError, match="firewall"):
        literature.generate_literature_batch(
            sources=["arxiv:q-fin.TR"],
            date_window=("2018", "2026"),
            batch_id="idea_batch_firewall",
            ledger_path=registry_path,
            output_root=tmp_path,
            scores=[_score("leaky")],
            weekly_date="2026-07-01",
        )

    assert not (tmp_path / "idea_batch_firewall").exists()


def test_literature_driver_fails_closed_when_fetch_fails(tmp_path, monkeypatch):
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")

    def fail_fetch(*args, **kwargs):
        raise RuntimeError("network closed")

    monkeypatch.setattr(literature, "fetch_papers", fail_fetch)

    with pytest.raises(RuntimeError, match="network closed"):
        literature.generate_literature_batch(
            sources=["arxiv:q-fin.TR"],
            date_window=("2018", "2026"),
            batch_id="idea_batch_fetch_fail",
            ledger_path=registry_path,
            output_root=tmp_path,
            scores=[_score("never")],
            weekly_date="2026-07-01",
        )

    assert not (tmp_path / "idea_batch_fetch_fail").exists()


def test_literature_driver_cli_writes_fixture_batch_with_scores(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    papers_path = tmp_path / "papers.json"
    scores_path = tmp_path / "scores.json"
    registry_path.write_text(_registry(), encoding="utf-8")
    papers_path.write_text(json.dumps([_paper("hi")]), encoding="utf-8")
    scores_path.write_text(json.dumps([_score("hi")]), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_pipeline_literature_ideas.py",
            "--papers",
            str(papers_path),
            "--scores",
            str(scores_path),
            "--ledger",
            str(registry_path),
            "--batch-id",
            "idea_batch_cli",
            "--output-root",
            str(tmp_path),
            "--weekly-date",
            "2026-07-01",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((tmp_path / "idea_batch_cli" / "idea_batch.json").read_text(encoding="utf-8"))
    assert payload["candidates"][0]["draft_status"] == "pending_llm"


def test_literature_driver_cli_accepts_utf8_bom_fixture_files(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    papers_path = tmp_path / "papers.json"
    scores_path = tmp_path / "scores.json"
    registry_path.write_text(_registry(), encoding="utf-8")
    papers_path.write_bytes(json.dumps([_paper("hi")]).encode("utf-8-sig"))
    scores_path.write_bytes(json.dumps([_score("hi")]).encode("utf-8-sig"))

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_pipeline_literature_ideas.py",
            "--papers",
            str(papers_path),
            "--scores",
            str(scores_path),
            "--ledger",
            str(registry_path),
            "--batch-id",
            "idea_batch_bom",
            "--output-root",
            str(tmp_path),
            "--weekly-date",
            "2026-07-01",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((tmp_path / "idea_batch_bom" / "idea_batch.json").read_text(encoding="utf-8"))
    assert payload["n_selected"] == 1


def test_literature_driver_help_runs():
    completed = subprocess.run(
        [sys.executable, "scripts/run_pipeline_literature_ideas.py", "--help"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "--scores" in completed.stdout
