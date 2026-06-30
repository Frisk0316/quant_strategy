"""Paper-to-alpha helpers for the research-only crypto alpha lab."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

from crypto_alpha_lab.schemas import AlphaCandidate, PaperScoring

ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_API = "https://api.crossref.org/works"
FORBIDDEN_FIREWALL_KEYS = ("oos_price", "price_series", "fold_boundary")

# Keyless, free sources only. SSRN / RePEc / NBER have no clean keyless API, but
# their DOI'd works are reachable through Crossref and Semantic Scholar, so those
# two aggregators cover the long tail without bespoke scrapers or paywall access.
# ponytail: add a new scheme = one _fetch_* helper + one row in _FETCHERS.


def _arxiv_id(url: str) -> str:
    raw = url.rsplit("/", 1)[-1]
    clean = re.sub(r"v\d+$", "", raw)
    return f"arxiv-{clean}"


def _slug_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def _window_years(date_window: tuple[str, str]) -> tuple[int, int]:
    def _year(text: str, default: int) -> int:
        return int(text[:4]) if text[:4].isdigit() else default

    return _year(date_window[0], 0), _year(date_window[1], 9999)


def _fetch_arxiv(fetch: Callable[..., Any], category: str, source: str) -> list[dict[str, Any]]:
    url = f"{ARXIV_API}?{urlencode({'search_query': f'cat:{category}', 'start': 0, 'max_results': 50})}"
    root = ElementTree.fromstring(fetch(url, timeout=10).read())
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        paper_url = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
        published = entry.findtext("atom:published", default="", namespaces=ns) or ""
        authors = tuple(
            (author.findtext("atom:name", default="", namespaces=ns) or "").strip()
            for author in entry.findall("atom:author", ns)
        )
        papers.append(
            {
                "paper_id": _arxiv_id(paper_url),
                "title": title,
                "authors": authors,
                "year": int(published[:4]) if published[:4].isdigit() else 0,
                "source_type": "preprint",
                "url": paper_url,
                "source": source,
            }
        )
    return papers


def _fetch_semantic_scholar(fetch: Callable[..., Any], query: str, source: str) -> list[dict[str, Any]]:
    params = {"query": query, "limit": 50, "fields": "title,authors,year,externalIds,url"}
    data = json.loads(fetch(f"{SEMANTIC_SCHOLAR_API}?{urlencode(params)}", timeout=10).read())
    papers: list[dict[str, Any]] = []
    for item in data.get("data") or []:
        ext = item.get("externalIds") or {}
        ident = ext.get("DOI") or ext.get("ArXiv") or item.get("paperId") or item.get("title", "")
        papers.append(
            {
                "paper_id": f"s2-{_slug_id(str(ident))}",
                "title": " ".join((item.get("title") or "").split()),
                "authors": tuple((a.get("name") or "").strip() for a in item.get("authors") or []),
                "year": int(item.get("year") or 0),
                "source_type": "journal_article" if ext.get("DOI") else "preprint",
                "url": item.get("url") or "",
                "source": source,
            }
        )
    return papers


def _fetch_crossref(fetch: Callable[..., Any], query: str, source: str) -> list[dict[str, Any]]:
    data = json.loads(fetch(f"{CROSSREF_API}?{urlencode({'query': query, 'rows': 50})}", timeout=10).read())
    papers: list[dict[str, Any]] = []
    for item in (data.get("message") or {}).get("items") or []:
        titles = item.get("title") or [""]
        parts = (item.get("issued") or {}).get("date-parts") or [[0]]
        year = parts[0][0] if parts and parts[0] else 0
        authors = tuple(
            f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author") or []
        )
        papers.append(
            {
                "paper_id": f"doi-{_slug_id(item.get('DOI') or '')}",
                "title": " ".join((titles[0] or "").split()),
                "authors": authors,
                "year": int(year or 0),
                "source_type": "journal_article",
                "url": item.get("URL") or "",
                "source": source,
            }
        )
    return papers


_FETCHERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "arxiv": _fetch_arxiv,
    "semanticscholar": _fetch_semantic_scholar,
    "crossref": _fetch_crossref,
}


def fetch_papers(
    sources: Sequence[str],
    date_window: tuple[str, str],
    *,
    opener: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    """Fetch keyless public paper metadata from arXiv, Semantic Scholar, or Crossref.

    Each source is ``"<scheme>:<query>"`` (e.g. ``"arxiv:q-fin"``,
    ``"semanticscholar:crypto funding carry"``, ``"crossref:basis trade crypto"``).
    Results are filtered to ``date_window`` (inclusive years; year 0 = unknown, kept).
    """

    fetch = opener or urlopen
    start_year, end_year = _window_years(date_window)
    papers: list[dict[str, Any]] = []
    for source in sources:
        scheme, _, arg = source.partition(":")
        handler = _FETCHERS.get(scheme)
        if handler is None or not arg:
            raise ValueError(f"unsupported source: {source}")
        for paper in handler(fetch, arg, source):
            year = paper.get("year") or 0
            if year and not (start_year <= year <= end_year):
                continue
            papers.append(paper)
    return papers


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            any(token in str(key).lower() for token in FORBIDDEN_FIREWALL_KEYS)
            or _contains_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return any(_contains_forbidden(item) for item in value)
    return False


def build_scoring_prompt(
    raw_paper: Mapping[str, Any],
    *,
    taxonomy_metadata: Mapping[str, Any],
    ledger_metadata: Mapping[str, Any],
) -> str:
    """Build a scoring prompt after checking the data firewall."""

    if _contains_forbidden(raw_paper) or _contains_forbidden(taxonomy_metadata) or _contains_forbidden(ledger_metadata):
        raise ValueError("firewall: scoring prompt cannot include market data or fold boundaries")
    return "\n".join(
        [
            "Score this crypto alpha paper for research triage.",
            json.dumps(dict(raw_paper), ensure_ascii=False, sort_keys=True),
            json.dumps(dict(taxonomy_metadata), ensure_ascii=False, sort_keys=True),
            json.dumps(dict(ledger_metadata), ensure_ascii=False, sort_keys=True),
        ]
    )


def score_papers(
    raw_papers: Sequence[Mapping[str, Any]],
    *,
    scorer: Callable[[Mapping[str, Any]], Mapping[str, Any] | PaperScoring] | None = None,
) -> list[PaperScoring]:
    """Validate supplied paper scores or call a caller-provided scorer."""

    scored: list[PaperScoring] = []
    for paper in raw_papers:
        if "scoring" in paper:
            payload = paper["scoring"]
        elif scorer:
            payload = scorer(paper)
        else:
            raise ValueError("scorer required for unscored papers")
        scored.append(payload if isinstance(payload, PaperScoring) else PaperScoring(**payload))
    return scored


def _candidate_id(paper_id: str) -> str:
    return "alpha-" + re.sub(r"[^a-z0-9]+", "-", paper_id.lower()).strip("-")


def _backtest_path(horizon: str) -> str:
    if horizon == "tick":
        return "event_replay"
    if horizon in {"daily", "multi_day"}:
        return "walk_forward"
    return "vectorized_scan"


def promote(scored: Sequence[PaperScoring], *, threshold: float = 3.8) -> list[AlphaCandidate]:
    """Promote high-scoring papers into research-only alpha candidates."""

    promoted: list[AlphaCandidate] = []
    for paper in scored:
        if paper.priority_score() < threshold:
            continue
        promoted.append(
            AlphaCandidate(
                candidate_id=_candidate_id(paper.paper_id),
                title=paper.title,
                paper_ids=(paper.paper_id,),
                hypothesis=f"{paper.title} may define a testable crypto alpha after costs.",
                signal_definition="paper-derived signal; requires human Stage 1 tightening",
                entry_rule="enter only after Stage 1 defines a pre-registered threshold",
                exit_rule="exit per Stage 1 pre-registration",
                sizing_rule="research-only volatility cap until parent sizing rules are specified",
                required_data=paper.required_data or ("market_data",),
                expected_horizon=paper.expected_horizon,
                backtest_path=_backtest_path(paper.expected_horizon),
                validation_plan=("parent Stage 1 review", "walk-forward or CPCV as applicable"),
                risk_controls=("no live trading", "data firewall before scoring"),
                expected_failure_modes=paper.known_failure_modes,
                parent_framework_touchpoints=("stage1-hypothesis", "pipeline_idea_generator"),
                status="screened",
                allow_live_trading=False,
            )
        )
    return promoted


def write_weekly_screen(papers_dir: str | Path, date: str, scored: Sequence[PaperScoring]) -> None:
    out = Path(papers_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"search_log_{date}.md").write_text(
        f"# Search Log {date}\n\nScored papers: {len(scored)}\n",
        encoding="utf-8",
    )
    (out / f"screen_{date}.json").write_text(
        json.dumps([paper.model_dump(mode="json") for paper in scored], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
