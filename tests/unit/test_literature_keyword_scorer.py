import json
from pathlib import Path

import pytest

from scripts import literature_keyword_scorer as scorer
from scripts import run_pipeline_literature_ideas as literature
from crypto_alpha_lab.schemas import PaperScoring


def _paper(paper_id: str, title: str, abstract: str | None = "Crypto abstract.") -> dict[str, object]:
    return {
        "paper_id": paper_id,
        "title": title,
        "abstract": abstract,
        "authors": ("A",),
        "year": 2025,
        "source_type": "preprint",
        "url": f"https://example.test/{paper_id}",
        "source": "arxiv:q-fin.TR",
    }


def _registry() -> str:
    return "\n".join(
        [
            "| ID | Date | Hypothesis | Family ID | Setup | Trials | Artifact / run_id | Outcome | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E-101 | 2026-06-30 | H-101 | F-FUNDING-CARRY | setup | 48 | `results/funding/summary.json` | refuted / shelved | current row |",
        ]
    )


def test_score_literature_fetches_once_and_writes_matching_snapshot(tmp_path, monkeypatch):
    calls = []
    papers = [
        _paper("funding", "Funding Rate Arbitrage in Crypto Perpetual Futures"),
        _paper("leadlag", "Cross-Exchange Lead-Lag in Bitcoin Markets"),
    ]

    def fake_fetch(sources, date_window, opener=None):
        calls.append((tuple(sources), date_window, opener))
        return papers

    monkeypatch.setattr(scorer, "fetch_papers", fake_fetch)

    papers_out = tmp_path / "raw_papers_snapshot.json"
    scores_out = tmp_path / "scores.json"
    payload = scorer.score_literature(
        sources=("arxiv:q-fin.TR",),
        date_window=("2018", "2026"),
        papers_out=papers_out,
        scores_out=scores_out,
        opener="opener",
    )

    saved_papers = json.loads(papers_out.read_text(encoding="utf-8"))
    saved_scores = json.loads(scores_out.read_text(encoding="utf-8"))
    review_bundle = json.loads((tmp_path / "review_bundle.json").read_text(encoding="utf-8"))

    assert calls == [(("arxiv:q-fin.TR",), ("2018", "2026"), "opener")]
    assert [paper["paper_id"] for paper in saved_papers] == ["funding", "leadlag"]
    assert set(saved_scores) == {"funding", "leadlag"}
    assert [paper["paper_id"] for paper in review_bundle] == ["funding", "leadlag"]
    assert payload["paper_count"] == 2
    assert payload["paper_ids"] == ["funding", "leadlag"]
    for row in saved_scores.values():
        score = PaperScoring(**row)
        assert "scoring_method=mechanical_keyword_placeholder" in score.notes


def test_keyword_scoring_uses_conservative_valid_defaults():
    score = scorer.keyword_score_paper(
        {"paper_id": "plain", "title": "A General Finance Survey", "year": 0}
    )

    assert score.paper_id == "plain"
    assert score.year == 1900
    assert score.alpha_category == "alternative_data"
    assert score.expected_horizon == "daily"
    assert "metadata_only=true" in score.notes
    assert score.data_availability <= 2
    assert score.implementation_fit <= 2
    assert score.priority_score() < 3.8


def test_score_literature_review_bundle_requires_abstract_and_firewall(tmp_path, monkeypatch):
    papers = [
        _paper("with-abstract", "Funding Rate Arbitrage in Crypto Perpetual Futures", "Abstract body."),
        _paper("metadata-only", "Cross-Exchange Lead-Lag in Bitcoin Markets", None),
    ]
    monkeypatch.setattr(scorer, "fetch_papers", lambda *args, **kwargs: papers)

    scorer.score_literature(
        sources=("arxiv:q-fin.TR",),
        date_window=("2018", "2026"),
        papers_out=tmp_path / "raw_papers_snapshot.json",
        scores_out=tmp_path / "scores.json",
    )

    review_bundle = json.loads((tmp_path / "review_bundle.json").read_text(encoding="utf-8"))
    assert review_bundle == [
        {
            "paper_id": "with-abstract",
            "title": "Funding Rate Arbitrage in Crypto Perpetual Futures",
            "abstract": "Abstract body.",
            "venue": None,
            "year": 2025,
            "url": "https://example.test/with-abstract",
        }
    ]

    monkeypatch.setattr(
        scorer,
        "fetch_papers",
        lambda *args, **kwargs: [dict(papers[0], fold_boundary="2025-01-01")],
    )
    with pytest.raises(ValueError, match="firewall"):
        scorer.score_literature(
            sources=("arxiv:q-fin.TR",),
            date_window=("2018", "2026"),
            papers_out=tmp_path / "bad_papers.json",
            scores_out=tmp_path / "bad_scores.json",
        )
    assert not (tmp_path / "bad_scores.json").exists()


def test_mechanical_scores_feed_driver_but_do_not_select_candidates(tmp_path, monkeypatch):
    papers = [_paper("funding", "Funding Rate Arbitrage in Crypto Perpetual Futures")]
    monkeypatch.setattr(scorer, "fetch_papers", lambda *args, **kwargs: papers)
    papers_out = tmp_path / "raw_papers_snapshot.json"
    scores_out = tmp_path / "scores.json"
    scorer.score_literature(
        sources=("arxiv:q-fin.TR",),
        date_window=("2018", "2026"),
        papers_out=papers_out,
        scores_out=scores_out,
    )

    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    registry_path.write_text(_registry(), encoding="utf-8")
    payload = literature.generate_literature_batch(
        sources=["arxiv:q-fin.TR"],
        date_window=("2018", "2026"),
        batch_id="idea_batch_keyword_test",
        ledger_path=registry_path,
        output_root=tmp_path,
        papers=json.loads(papers_out.read_text(encoding="utf-8")),
        scores=json.loads(scores_out.read_text(encoding="utf-8")),
        weekly_date="2026-07-01",
    )

    assert payload["candidates"] == []
    assert payload["skipped"] == [{"paper_id": "funding", "reason": "placeholder_score"}]


def test_cli_writes_snapshot_and_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(
        scorer,
        "fetch_papers",
        lambda *args, **kwargs: [_paper("basis", "Basis Trading Crypto Perpetual Futures")],
    )

    papers_out = tmp_path / "raw_papers_snapshot.json"
    scores_out = tmp_path / "scores.json"
    rc = scorer.main(
        [
            "--source",
            "arxiv:q-fin.TR",
            "--papers-out",
            str(papers_out),
            "--scores-out",
            str(scores_out),
        ]
    )

    assert rc == 0
    assert json.loads(papers_out.read_text(encoding="utf-8"))[0]["paper_id"] == "basis"
    assert set(json.loads(scores_out.read_text(encoding="utf-8"))) == {"basis"}
    assert json.loads((tmp_path / "review_bundle.json").read_text(encoding="utf-8"))[0]["paper_id"] == "basis"
