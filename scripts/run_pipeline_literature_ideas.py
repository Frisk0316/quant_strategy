"""CLI for research-only literature idea batch generation."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
LAB_SRC = ROOT / "research" / "crypto-alpha-lab" / "src"
for path in (ROOT, LAB_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtesting.pipeline_idea_generator import DEFAULT_CAP, register_batch
from crypto_alpha_lab.adapters import to_parent_stage1_draft
from crypto_alpha_lab.pipeline import (
    build_scoring_prompt,
    fetch_papers,
    promote,
    score_papers,
    write_weekly_screen,
)
from crypto_alpha_lab.schemas import PaperScoring

DEFAULT_SOURCES = (
    "arxiv:q-fin.TR",
    "arxiv:q-fin.ST",
    "semanticscholar:crypto perpetual funding",
    "crossref:crypto basis trade",
)
DEFAULT_DATE_WINDOW = ("2018", "2026")
DEFAULT_THRESHOLD = 3.8


def default_batch_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"idea_batch_{stamp}_literature_001"


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _score_map(scores: Sequence[Mapping[str, Any]] | Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if isinstance(scores, Mapping):
        if isinstance(scores.get("scores"), list):
            return _score_map(scores["scores"])
        return {str(key): value for key, value in scores.items() if isinstance(value, Mapping)}
    return {str(score["paper_id"]): score for score in scores}


def _score_prompt_metadata(
    sources: Sequence[str],
    date_window: tuple[str, str],
    ledger_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {"sources": list(sources), "date_window": list(date_window)},
        {"experiment_registry": Path(ledger_path).as_posix()},
    )


def _score_with_firewall(
    papers: Sequence[Mapping[str, Any]],
    *,
    sources: Sequence[str],
    date_window: tuple[str, str],
    ledger_path: str | Path,
    scores: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None,
    scorer: Callable[[Mapping[str, Any], str], Mapping[str, Any] | PaperScoring] | None,
) -> list[PaperScoring]:
    taxonomy_metadata, ledger_metadata = _score_prompt_metadata(sources, date_window, ledger_path)
    prompts = [
        build_scoring_prompt(
            paper,
            taxonomy_metadata=taxonomy_metadata,
            ledger_metadata=ledger_metadata,
        )
        for paper in papers
    ]
    static_scores = _score_map(scores) if scores is not None else None

    def score_one(paper: Mapping[str, Any]) -> Mapping[str, Any] | PaperScoring:
        paper_id = str(paper.get("paper_id") or "")
        prompt = prompts[[str(item.get("paper_id") or "") for item in papers].index(paper_id)]
        if scorer is not None:
            return scorer(paper, prompt)
        if static_scores is None:
            raise ValueError("--scores or scorer required for literature scoring")
        if paper_id not in static_scores:
            raise ValueError(f"missing score for paper_id: {paper_id}")
        return static_scores[paper_id]

    return score_papers(papers, scorer=score_one)


def _drafts_from_scores(scored: Sequence[PaperScoring], *, threshold: float, cap: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    eligible = sorted(
        (score for score in scored if score.priority_score() >= threshold),
        key=lambda score: (-score.priority_score(), score.paper_id),
    )
    below = [
        {
            "paper_id": score.paper_id,
            "reason": "below_threshold",
        }
        for score in scored
        if score.priority_score() < threshold
    ]
    promoted = promote(eligible, threshold=threshold)
    selected = promoted[:cap]
    overflow = promoted[cap:]

    scores_by_paper = {score.paper_id: score for score in eligible}
    drafts: list[dict[str, Any]] = []
    for rank, candidate in enumerate(selected, start=1):
        score = scores_by_paper[candidate.paper_ids[0]]
        draft = to_parent_stage1_draft(candidate, alpha_category=score.alpha_category)
        draft["draft_status"] = "pending_llm"
        draft["allow_live_trading"] = False
        draft["priority_score"] = score.priority_score()
        draft["prior_rank"] = rank
        drafts.append(draft)

    capped = [
        {
            "paper_id": candidate.paper_ids[0],
            "reason": "cap_overflow",
        }
        for candidate in overflow
    ]
    return drafts, [*below, *capped], len(promoted)


def generate_literature_batch(
    *,
    sources: Sequence[str] = DEFAULT_SOURCES,
    date_window: tuple[str, str] = DEFAULT_DATE_WINDOW,
    batch_id: str | None = None,
    ledger_path: str | Path = "docs/EXPERIMENT_REGISTRY.md",
    output_root: str | Path = "results",
    threshold: float = DEFAULT_THRESHOLD,
    cap: int = DEFAULT_CAP,
    scores: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    scorer: Callable[[Mapping[str, Any], str], Mapping[str, Any] | PaperScoring] | None = None,
    opener: Callable[..., Any] | None = None,
    papers: Sequence[Mapping[str, Any]] | None = None,
    weekly_date: str | None = None,
) -> dict[str, Any]:
    batch = batch_id or default_batch_id()
    batch_dir = Path(output_root) / batch
    if batch_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing batch: {batch_dir}")

    raw_papers = list(papers) if papers is not None else fetch_papers(sources, date_window, opener=opener)
    scored = _score_with_firewall(
        raw_papers,
        sources=sources,
        date_window=date_window,
        ledger_path=ledger_path,
        scores=scores,
        scorer=scorer,
    )
    drafts, skipped, n_eligible_before_cap = _drafts_from_scores(scored, threshold=threshold, cap=cap)
    payload = register_batch(
        [],
        batch,
        ledger_path,
        output_root=output_root,
        a_half_drafts=drafts,
        skipped=skipped,
        n_eligible_before_cap=n_eligible_before_cap,
    )
    write_weekly_screen(batch_dir / "weekly_screen", weekly_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"), scored)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", dest="sources", action="append")
    parser.add_argument("--date-window-start", default=DEFAULT_DATE_WINDOW[0])
    parser.add_argument("--date-window-end", default=DEFAULT_DATE_WINDOW[1])
    parser.add_argument("--scores")
    parser.add_argument("--papers")
    parser.add_argument("--ledger", default="docs/EXPERIMENT_REGISTRY.md")
    parser.add_argument("--batch-id")
    parser.add_argument("--output-root", default="results")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    parser.add_argument("--weekly-date")
    args = parser.parse_args(argv)

    payload = generate_literature_batch(
        sources=tuple(args.sources or DEFAULT_SOURCES),
        date_window=(args.date_window_start, args.date_window_end),
        batch_id=args.batch_id,
        ledger_path=args.ledger,
        output_root=args.output_root,
        threshold=args.threshold,
        cap=args.cap,
        scores=_read_json(args.scores) if args.scores else None,
        papers=_read_json(args.papers) if args.papers else None,
        weekly_date=args.weekly_date,
    )
    print(f"wrote {args.output_root}/{payload['batch_id']}/idea_batch.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
