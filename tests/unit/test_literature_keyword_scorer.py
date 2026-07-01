import json
from pathlib import Path

from scripts import literature_keyword_scorer as scorer
from scripts import run_pipeline_literature_ideas as literature
from crypto_alpha_lab.schemas import PaperScoring


def _paper(paper_id: str, title: str) -> dict[str, object]:
    return {
        "paper_id": paper_id,
        "title": title,
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

    assert calls == [(("arxiv:q-fin.TR",), ("2018", "2026"), "opener")]
    assert [paper["paper_id"] for paper in saved_papers] == ["funding", "leadlag"]
    assert set(saved_scores) == {"funding", "leadlag"}
    assert payload["paper_count"] == 2
    assert payload["paper_ids"] == ["funding", "leadlag"]
    for row in saved_scores.values():
        score = PaperScoring(**row)
        assert "scoring_method=mechanical_keyword_placeholder" in score.notes


def test_keyword_scoring_uses_conservative_valid_defaults():
    score = scorer.keyword_score_paper({"paper_id": "plain", "title": "A General Finance Survey", "year": 0})

    assert score.paper_id == "plain"
    assert score.year == 1900
    assert score.alpha_category == "alternative_data"
    assert score.expected_horizon == "daily"
    assert score.priority_score() < 3.8


def test_scores_feed_existing_literature_driver_without_missing_ids(tmp_path, monkeypatch):
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

    candidate = payload["candidates"][0]
    assert candidate["source"] == "A_literature"
    assert candidate["draft_status"] == "pending_llm"
    assert candidate["allow_live_trading"] is False


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
