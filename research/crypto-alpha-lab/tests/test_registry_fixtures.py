import json
from pathlib import Path

from crypto_alpha_lab.schemas import AlphaCandidate, PaperScoring


ROOT = Path(__file__).resolve().parents[1]


def test_initial_paper_screen_is_valid_and_unique() -> None:
    records = json.loads((ROOT / "papers" / "initial_screen_2026-05-26.json").read_text())
    papers = [PaperScoring.model_validate(record) for record in records]
    paper_ids = [paper.paper_id for paper in papers]

    assert len(papers) >= 8
    assert len(paper_ids) == len(set(paper_ids))
    assert max(paper.priority_score() for paper in papers) >= 4.0


def test_initial_alpha_candidates_link_to_screened_papers() -> None:
    paper_records = json.loads((ROOT / "papers" / "initial_screen_2026-05-26.json").read_text())
    known_paper_ids = {PaperScoring.model_validate(record).paper_id for record in paper_records}

    candidate_records = json.loads(
        (ROOT / "alpha_specs" / "initial_candidates_2026-05-26.json").read_text()
    )
    candidates = [AlphaCandidate.model_validate(record) for record in candidate_records]

    assert {candidate.status for candidate in candidates} >= {"ready_for_backtest", "watchlist"}
    for candidate in candidates:
        assert candidate.allow_live_trading is False
        assert set(candidate.paper_ids) <= known_paper_ids
        assert candidate.validation_plan
        assert candidate.expected_failure_modes
