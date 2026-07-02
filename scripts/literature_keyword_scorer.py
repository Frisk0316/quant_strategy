"""Mechanical keyword scorer for one-shot literature idea batches."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
LAB_SRC = ROOT / "research" / "crypto-alpha-lab" / "src"
for path in (ROOT, LAB_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from crypto_alpha_lab.pipeline import build_scoring_prompt, fetch_papers
from crypto_alpha_lab.schemas import PaperScoring

DEFAULT_SOURCES = (
    "arxiv:q-fin.TR",
    "arxiv:q-fin.ST",
    "semanticscholar:funding rate arbitrage",
    "semanticscholar:cross-sectional cryptocurrency momentum",
    "semanticscholar:cross-exchange lead-lag crypto",
    "crossref:basis trading crypto perpetual",
)
DEFAULT_DATE_WINDOW = ("2018", "2026")

_SOURCE_TYPES = {"preprint", "working_paper", "journal_article", "review", "negative_evidence"}

_FAMILIES: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "carry",
        "multi_day",
        "carry",
        ("funding", "perpetual", "basis", "carry", "arbitrage"),
        ("spot_price", "perp_price", "funding_rate"),
    ),
    (
        "microstructure",
        "intraday",
        "leadlag",
        ("lead-lag", "lead lag", "cross-exchange", "cross exchange", "latency", "venue"),
        ("venue_scoped_ohlcv",),
    ),
    (
        "momentum",
        "multi_day",
        "momentum",
        ("cross-sectional", "cross sectional", "momentum", "trend"),
        ("ohlcv", "universe_membership"),
    ),
    (
        "volatility",
        "daily",
        "volatility",
        ("volatility", "dvol", "implied vol", "variance", "option"),
        ("ohlcv", "volatility_index"),
    ),
    (
        "stat_arb",
        "multi_day",
        "stat_arb",
        ("pairs", "mean reversion", "statistical arbitrage", "relative value"),
        ("ohlcv",),
    ),
    (
        "alternative_data",
        "daily",
        "alternative_data",
        ("sentiment", "news", "on-chain", "open interest", "liquidation"),
        ("external_observations",),
    ),
)


def _text(paper: Mapping[str, Any]) -> str:
    return " ".join(
        str(paper.get(key) or "")
        for key in ("title", "abstract", "summary", "source", "paper_id")
    ).lower()


def _abstract(paper: Mapping[str, Any]) -> str:
    return " ".join(str(paper.get("abstract") or paper.get("summary") or "").split())


def _authors(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item))
    return ()


def _year(value: Any) -> int:
    try:
        year = int(value or 1900)
    except (TypeError, ValueError):
        year = 1900
    return min(2100, max(1900, year))


def _source_type(value: Any) -> str:
    text = str(value or "working_paper")
    return text if text in _SOURCE_TYPES else "working_paper"


def _profile(paper: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...], list[str]]:
    haystack = _text(paper)
    best = ("alternative_data", "daily", ("market_data",), [])
    for category, horizon, _name, keywords, required_data in _FAMILIES:
        hits = [keyword for keyword in keywords if keyword in haystack]
        if len(hits) > len(best[3]):
            best = (category, horizon, required_data, hits)
    return best


def keyword_score_paper(paper: Mapping[str, Any]) -> PaperScoring:
    """Return a conservative schema-valid score from paper metadata only."""

    paper_id = str(paper.get("paper_id") or "").strip()
    if not paper_id:
        raise ValueError("paper missing paper_id")
    category, horizon, required_data, hits = _profile(paper)
    known = bool(hits)
    has_abstract = bool(_abstract(paper))
    hit_score = min(5, len(hits) + 2) if known else 1
    data_fit = 3 if has_abstract and known else 1
    implementation_fit = 3 if has_abstract and known else 1
    return PaperScoring(
        paper_id=paper_id,
        title=str(paper.get("title") or paper_id),
        authors=_authors(paper.get("authors")),
        year=_year(paper.get("year")),
        venue=paper.get("venue"),
        source_type=_source_type(paper.get("source_type")),  # type: ignore[arg-type]
        url=paper.get("url"),
        doi=paper.get("doi"),
        alpha_category=category,  # type: ignore[arg-type]
        expected_horizon=horizon,  # type: ignore[arg-type]
        required_data=required_data,
        evidence_quality=hit_score if has_abstract and known else min(hit_score, 2),
        crypto_relevance=5 if ("crypto" in _text(paper) or "perpetual" in _text(paper)) else (3 if known else 1),
        data_availability=data_fit,
        implementation_fit=implementation_fit,
        cost_awareness=3 if has_abstract and category in {"carry", "microstructure", "execution"} else (1 if known else 0),
        novelty=3 if has_abstract and known else 1,
        leakage_risk=1 if has_abstract and known else 2,
        overfit_risk=1 if has_abstract and known else 2,
        known_failure_modes=(
            "mechanical keyword score requires Claude Stage-1 review",
            "not promotion evidence",
        ),
        notes=(
            "scoring_method=mechanical_keyword_placeholder; "
            f"metadata_only={str(not has_abstract).lower()}; "
            f"matched_keywords={','.join(hits) if hits else 'none'}"
        ),
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _review_bundle(papers: Sequence[Mapping[str, Any]], scores: Mapping[str, PaperScoring], top_n: int) -> list[dict[str, Any]]:
    ranked = sorted(
        (paper for paper in papers if _abstract(paper)),
        key=lambda paper: (-scores[str(paper.get("paper_id"))].priority_score(), str(paper.get("paper_id") or "")),
    )
    return [
        {
            "paper_id": str(paper.get("paper_id") or ""),
            "title": str(paper.get("title") or paper.get("paper_id") or ""),
            "abstract": _abstract(paper),
            "venue": paper.get("venue"),
            "year": _year(paper.get("year")),
            "url": paper.get("url"),
        }
        for paper in ranked[:top_n]
    ]


def score_literature(
    *,
    sources: Sequence[str] = DEFAULT_SOURCES,
    date_window: tuple[str, str] = DEFAULT_DATE_WINDOW,
    papers_out: str | Path,
    scores_out: str | Path,
    review_bundle_out: str | Path | None = None,
    top_n: int = 15,
    opener: Any | None = None,
) -> dict[str, Any]:
    papers = list(fetch_papers(tuple(sources), date_window, opener=opener))
    for paper in papers:
        build_scoring_prompt(paper, taxonomy_metadata={}, ledger_metadata={})

    score_models: dict[str, PaperScoring] = {}
    scores: dict[str, dict[str, Any]] = {}
    for paper in papers:
        score = keyword_score_paper(paper)
        if score.paper_id in scores:
            raise ValueError(f"duplicate paper_id: {score.paper_id}")
        score_models[score.paper_id] = score
        scores[score.paper_id] = score.model_dump(mode="json")

    papers_path = Path(papers_out)
    scores_path = Path(scores_out)
    review_path = Path(review_bundle_out) if review_bundle_out is not None else scores_path.with_name("review_bundle.json")
    papers_path.parent.mkdir(parents=True, exist_ok=True)
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    papers_path.write_text(json.dumps(_jsonable(papers), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scores_path.write_text(json.dumps(scores, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_path.write_text(
        json.dumps(_review_bundle(papers, score_models, top_n), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "paper_count": len(papers),
        "paper_ids": [str(paper.get("paper_id") or "") for paper in papers],
        "review_bundle": str(review_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", dest="sources", action="append")
    parser.add_argument("--date-window-start", default=DEFAULT_DATE_WINDOW[0])
    parser.add_argument("--date-window-end", default=DEFAULT_DATE_WINDOW[1])
    parser.add_argument("--papers-out", required=True, type=Path)
    parser.add_argument("--scores-out", required=True, type=Path)
    parser.add_argument("--review-bundle-out", type=Path)
    parser.add_argument("--top-n", type=int, default=15)
    args = parser.parse_args(argv)

    payload = score_literature(
        sources=tuple(args.sources or DEFAULT_SOURCES),
        date_window=(args.date_window_start, args.date_window_end),
        papers_out=args.papers_out,
        scores_out=args.scores_out,
        review_bundle_out=args.review_bundle_out,
        top_n=args.top_n,
    )
    print(f"wrote {payload['paper_count']} papers to {args.papers_out} and scores to {args.scores_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
