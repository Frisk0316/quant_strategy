"""Paper-to-alpha helpers for the research-only crypto alpha lab."""
from __future__ import annotations

import json
import re
import socket
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

from crypto_alpha_lab.schemas import AlphaCandidate, PaperScoring

ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_API = "https://api.crossref.org/works"
FORBIDDEN_FIREWALL_KEYS = ("oos_price", "price_series", "fold_boundary")
LITERATURE_CACHE_DIR = Path("data/literature_cache")

# Keyless, free sources only. SSRN / RePEc / NBER have no clean keyless API, but
# their DOI'd works are reachable through Crossref and Semantic Scholar, so those
# two aggregators cover the long tail without bespoke scrapers or paywall access.
# ponytail: add a new scheme = one _fetch_* helper + one row in _FETCHERS.


class _FetchFailure(RuntimeError):
    def __init__(self, cause: BaseException, event: Mapping[str, Any]) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.event = dict(event)


def _arxiv_id(url: str) -> str:
    raw = url.rsplit("/", 1)[-1]
    clean = re.sub(r"v\d+$", "", raw)
    return f"arxiv-{clean}"


def _slug_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def _compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_jats(value: Any) -> str:
    return _compact_text(unescape(re.sub(r"<[^>]+>", " ", str(value or ""))))


def _cache_path(url: str, cache_dir: Path) -> Path:
    return cache_dir / f"{sha256(url.encode('utf-8')).hexdigest()}.bin"


def _retry_after_seconds(headers: Any, default: float) -> float:
    value = headers.get("Retry-After") if headers else None
    if value is None:
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            target = parsedate_to_datetime(str(value))
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return default


def _fetch_bytes(
    fetch: Callable[..., Any],
    url: str,
    *,
    timeout: int,
    cache_dir: Path | None,
    sleeper: Callable[[float], Any],
) -> tuple[bytes, dict[str, Any]]:
    if cache_dir is not None:
        path = _cache_path(url, cache_dir)
        if path.exists():
            return path.read_bytes(), {"cache": "hit", "retries": 0}
    else:
        path = None

    retries = 0
    cache_label = "miss" if path is not None else "disabled"
    for attempt in range(3):
        try:
            response = fetch(url, timeout=timeout)
            status = getattr(response, "status", None)
            if status is None and hasattr(response, "getcode"):
                status = response.getcode()
            if int(status or 200) == 429:
                raise HTTPError(url, 429, "Too Many Requests", getattr(response, "headers", None), None)
            data = response.read()
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            return data, {"cache": cache_label, "retries": retries}
        except HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise _FetchFailure(exc, {"cache": cache_label, "retries": retries}) from exc
            retries += 1
            sleeper(_retry_after_seconds(exc.headers, float(attempt + 1)))
        except (TimeoutError, socket.timeout, URLError) as exc:
            if attempt == 2:
                raise _FetchFailure(exc, {"cache": cache_label, "retries": retries}) from exc
            retries += 1
            sleeper(float(attempt + 1))
    raise RuntimeError("unreachable fetch retry state")


def _cache_summary(events: Sequence[Mapping[str, Any]]) -> str:
    values = {str(event.get("cache") or "n/a") for event in events}
    if not values:
        return "n/a"
    if len(values) == 1:
        return values.pop()
    return "mixed"


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
        title = _compact_text(entry.findtext("atom:title", default="", namespaces=ns))
        abstract = _compact_text(entry.findtext("atom:summary", default="", namespaces=ns))
        published = entry.findtext("atom:published", default="", namespaces=ns) or ""
        authors = tuple(
            (author.findtext("atom:name", default="", namespaces=ns) or "").strip()
            for author in entry.findall("atom:author", ns)
        )
        row = {
            "paper_id": _arxiv_id(paper_url),
            "title": title,
            "authors": authors,
            "year": int(published[:4]) if published[:4].isdigit() else 0,
            "source_type": "preprint",
            "url": paper_url,
            "source": source,
        }
        if abstract:
            row["abstract"] = abstract
        papers.append(row)
    return papers


def _fetch_semantic_scholar(fetch: Callable[..., Any], query: str, source: str) -> list[dict[str, Any]]:
    params = {"query": query, "limit": 50, "fields": "title,abstract,authors,year,externalIds,url"}
    data = json.loads(fetch(f"{SEMANTIC_SCHOLAR_API}?{urlencode(params)}", timeout=10).read())
    papers: list[dict[str, Any]] = []
    for item in data.get("data") or []:
        ext = item.get("externalIds") or {}
        ident = ext.get("DOI") or ext.get("ArXiv") or item.get("paperId") or item.get("title", "")
        row = {
            "paper_id": f"s2-{_slug_id(str(ident))}",
            "title": _compact_text(item.get("title")),
            "authors": tuple((a.get("name") or "").strip() for a in item.get("authors") or []),
            "year": int(item.get("year") or 0),
            "source_type": "journal_article" if ext.get("DOI") else "preprint",
            "url": item.get("url") or "",
            "source": source,
        }
        abstract = _compact_text(item.get("abstract"))
        if abstract:
            row["abstract"] = abstract
        papers.append(row)
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
        row = {
            "paper_id": f"doi-{_slug_id(item.get('DOI') or '')}",
            "title": _compact_text(titles[0]),
            "authors": authors,
            "year": int(year or 0),
            "source_type": "journal_article",
            "url": item.get("URL") or "",
            "source": source,
        }
        abstract = _clean_jats(item.get("abstract"))
        if abstract:
            row["abstract"] = abstract
        papers.append(row)
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
    cache_dir: str | Path | None = None,
    sleeper: Callable[[float], Any] | None = None,
    log_out: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch keyless public paper metadata from arXiv, Semantic Scholar, or Crossref.

    Each source is ``"<scheme>:<query>"`` (e.g. ``"arxiv:q-fin"``,
    ``"semanticscholar:crypto funding carry"``, ``"crossref:basis trade crypto"``).
    Results are filtered to ``date_window`` (inclusive years; year 0 = unknown, kept).
    """

    fetch = opener or urlopen
    cache_base = Path(cache_dir) if cache_dir is not None else (LITERATURE_CACHE_DIR if opener is None else None)
    start_year, end_year = _window_years(date_window)
    papers: list[dict[str, Any]] = []
    for source in sources:
        scheme, _, arg = source.partition(":")
        handler = _FETCHERS.get(scheme)
        if handler is None or not arg:
            raise ValueError(f"unsupported source: {source}")
        events: list[dict[str, Any]] = []

        def cached_fetch(url: str, timeout: int = 10) -> BytesIO:
            data, event = _fetch_bytes(
                fetch,
                url,
                timeout=timeout,
                cache_dir=cache_base,
                sleeper=sleeper or time.sleep,
            )
            events.append(event)
            return BytesIO(data)

        try:
            rows = handler(cached_fetch, arg, source)
        except Exception as exc:
            if log_out is None:
                raise (exc.cause if isinstance(exc, _FetchFailure) else exc)
            if isinstance(exc, _FetchFailure):
                events.append(exc.event)
                status = f"error:{type(exc.cause).__name__}"
            else:
                status = f"error:{type(exc).__name__}"
            log_out.append(
                {
                    "source": scheme,
                    "query": arg,
                    "status": status,
                    "count": 0,
                    "cache": _cache_summary(events),
                    "retries": sum(int(event.get("retries") or 0) for event in events),
                }
            )
            continue

        kept = 0
        for paper in rows:
            year = paper.get("year") or 0
            if year and not (start_year <= year <= end_year):
                continue
            papers.append(paper)
            kept += 1
        if log_out is not None:
            log_out.append(
                {
                    "source": scheme,
                    "query": arg,
                    "status": "ok",
                    "count": kept,
                    "cache": _cache_summary(events),
                    "retries": sum(int(event.get("retries") or 0) for event in events),
                }
            )
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


def write_weekly_screen(
    papers_dir: str | Path,
    date: str,
    scored: Sequence[PaperScoring],
    *,
    search_log: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    out = Path(papers_dir)
    out.mkdir(parents=True, exist_ok=True)
    log_lines = [
        f"# Search Log {date}",
        "",
        f"Scored papers: {len(scored)}",
        "",
        "| source | query | status | count | cache | retries |",
        "|---|---|---|---:|---|---:|",
    ]
    for row in search_log or []:
        log_lines.append(
            "| {source} | {query} | {status} | {count} | {cache} | {retries} |".format(
                source=row.get("source", ""),
                query=row.get("query", ""),
                status=row.get("status", ""),
                count=row.get("count", 0),
                cache=row.get("cache", ""),
                retries=row.get("retries", 0),
            )
        )
    (out / f"search_log_{date}.md").write_text(
        "\n".join(log_lines) + "\n",
        encoding="utf-8",
    )
    (out / f"screen_{date}.json").write_text(
        json.dumps([paper.model_dump(mode="json") for paper in scored], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
