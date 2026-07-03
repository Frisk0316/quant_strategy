import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from crypto_alpha_lab.adapters import to_parent_stage1_draft
from crypto_alpha_lab.pipeline import (
    build_scoring_prompt,
    fetch_papers,
    promote,
    score_papers,
    write_weekly_screen,
)
from crypto_alpha_lab.schemas import AlphaCandidate, PaperScoring


def _scoring(**overrides):
    payload = {
        "paper_id": "he-2024",
        "title": "Funding Premia",
        "authors": ("A",),
        "year": 2024,
        "source_type": "preprint",
        "url": "https://arxiv.org/abs/2401.00001",
        "alpha_category": "carry",
        "expected_horizon": "multi_day",
        "required_data": ("spot_price", "perp_price", "funding_rate"),
        "evidence_quality": 5,
        "crypto_relevance": 5,
        "data_availability": 5,
        "implementation_fit": 5,
        "cost_awareness": 5,
        "novelty": 3,
        "leakage_risk": 1,
        "overfit_risk": 1,
    }
    payload.update(overrides)
    return PaperScoring(**payload)


def test_fetch_papers_parses_keyless_arxiv_feed():
    xml = b"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title> Funding Premia in Crypto </title>
        <summary>
          We study funding premia in crypto perpetual futures.
        </summary>
        <published>2024-01-02T00:00:00Z</published>
        <author><name>Alice</name></author>
        <author><name>Bob</name></author>
      </entry>
    </feed>
    """

    def opener(url, timeout=10):
        assert "export.arxiv.org/api/query" in url
        assert "cat%3Aq-fin" in url
        return BytesIO(xml)

    papers = fetch_papers(["arxiv:q-fin"], ("2024-01-01", "2024-01-07"), opener=opener)

    assert papers == [
        {
            "paper_id": "arxiv-2401.00001",
            "title": "Funding Premia in Crypto",
            "abstract": "We study funding premia in crypto perpetual futures.",
            "authors": ("Alice", "Bob"),
            "year": 2024,
            "source_type": "preprint",
            "url": "http://arxiv.org/abs/2401.00001v1",
            "source": "arxiv:q-fin",
        }
    ]


def test_score_promote_and_write_weekly_screen(tmp_path):
    scored = score_papers([{"scoring": _scoring().model_dump()}])
    promoted = promote(scored, threshold=3.8)

    assert scored[0].priority_score() >= 3.8
    assert promoted[0].candidate_id == "alpha-he-2024"
    assert promoted[0].allow_live_trading is False

    write_weekly_screen(tmp_path, "2026-06-30", scored)
    assert (tmp_path / "search_log_2026-06-30.md").exists()
    payload = json.loads((tmp_path / "screen_2026-06-30.json").read_text(encoding="utf-8"))
    assert payload[0]["paper_id"] == "he-2024"


def test_adapter_maps_alpha_candidate_to_parent_stage1_draft():
    candidate = AlphaCandidate(
        candidate_id="funding-alpha",
        title="Funding Alpha",
        paper_ids=("he-2024",),
        hypothesis="Funding should predict returns after cost.",
        signal_definition="funding spread",
        entry_rule="enter on positive expected carry",
        exit_rule="exit on reversal",
        sizing_rule="vol capped",
        required_data=("funding_rate",),
        expected_horizon="multi_day",
        backtest_path="walk_forward",
        validation_plan=("WF",),
    )

    draft = to_parent_stage1_draft(candidate, alpha_category="carry")

    assert draft["source"] == "A_literature"
    assert draft["family_id_or_NEW"] == "F-FUNDING-CARRY"
    assert draft["draft_status"] == "drafted"
    assert draft["provisional_candidate_id"] == "funding-alpha"


def test_scoring_prompt_firewall_rejects_market_data_and_fold_boundaries():
    with pytest.raises(ValueError, match="firewall"):
        build_scoring_prompt(
            {"title": "bad", "oos_price_series": [1, 2, 3]},
            taxonomy_metadata={"families": ["F-X"]},
            ledger_metadata={"fold_boundary": "2025-01-01"},
        )


def test_fetch_papers_parses_semantic_scholar_json():
    payload = json.dumps(
        {
            "data": [
                {
                    "title": "Crypto  Carry  Premia",
                    "abstract": "Evidence from perpetual futures.",
                    "year": 2025,
                    "url": "https://www.semanticscholar.org/paper/abc",
                    "externalIds": {"DOI": "10.1111/jofi.12345"},
                    "authors": [{"name": "Alice"}, {"name": "Bob"}],
                }
            ]
        }
    ).encode()

    def opener(url, timeout=10):
        assert "api.semanticscholar.org" in url
        assert "abstract" in url
        return BytesIO(payload)

    papers = fetch_papers(
        ["semanticscholar:crypto carry"], ("2024-01-01", "2026-12-31"), opener=opener
    )

    assert papers == [
        {
            "paper_id": "s2-10-1111-jofi-12345",
            "title": "Crypto Carry Premia",
            "abstract": "Evidence from perpetual futures.",
            "authors": ("Alice", "Bob"),
            "year": 2025,
            "source_type": "journal_article",
            "url": "https://www.semanticscholar.org/paper/abc",
            "source": "semanticscholar:crypto carry",
        }
    ]


def test_fetch_papers_parses_crossref_json():
    payload = json.dumps(
        {
            "message": {
                "items": [
                    {
                        "DOI": "10.2139/ssrn.999",
                        "title": ["Funding Premia in Perpetuals"],
                        "abstract": "<jats:p>Funding <jats:i>premia</jats:i> in perpetuals.</jats:p>",
                        "issued": {"date-parts": [[2025, 6]]},
                        "URL": "https://doi.org/10.2139/ssrn.999",
                        "author": [{"given": "Jane", "family": "Doe"}],
                    }
                ]
            }
        }
    ).encode()

    def opener(url, timeout=10):
        assert "api.crossref.org" in url
        return BytesIO(payload)

    papers = fetch_papers(
        ["crossref:funding premia"], ("2024-01-01", "2026-12-31"), opener=opener
    )

    assert papers[0]["paper_id"] == "doi-10-2139-ssrn-999"
    assert papers[0]["abstract"] == "Funding premia in perpetuals."
    assert papers[0]["year"] == 2025
    assert papers[0]["authors"] == ("Jane Doe",)
    assert papers[0]["source_type"] == "journal_article"


def test_fetch_papers_retries_429_and_uses_disk_cache(tmp_path):
    payload = json.dumps(
        {
            "data": [
                {
                    "title": "Cached Carry",
                    "abstract": "Cached abstract.",
                    "year": 2025,
                    "externalIds": {},
                    "authors": [],
                }
            ]
        }
    ).encode()
    calls: list[str] = []
    sleeps: list[float] = []

    def opener(url, timeout=10):
        calls.append(url)
        if len(calls) == 1:
            raise HTTPError(url, 429, "Too Many Requests", {"Retry-After": "0"}, None)
        return BytesIO(payload)

    log: list[dict[str, object]] = []
    papers = fetch_papers(
        ["semanticscholar:crypto carry"],
        ("2024-01-01", "2026-12-31"),
        opener=opener,
        cache_dir=tmp_path / "literature_cache",
        sleeper=sleeps.append,
        log_out=log,
    )

    assert papers[0]["abstract"] == "Cached abstract."
    assert len(calls) == 2
    assert sleeps == [0.0]
    assert log == [
        {
            "source": "semanticscholar",
            "query": "crypto carry",
            "status": "ok",
            "count": 1,
            "cache": "miss",
            "retries": 1,
        }
    ]

    calls.clear()
    cache_log: list[dict[str, object]] = []
    cached = fetch_papers(
        ["semanticscholar:crypto carry"],
        ("2024-01-01", "2026-12-31"),
        opener=opener,
        cache_dir=tmp_path / "literature_cache",
        log_out=cache_log,
    )

    assert cached == papers
    assert calls == []
    assert cache_log[0]["cache"] == "hit"
    assert cache_log[0]["retries"] == 0


def test_fetch_papers_logs_retry_count_when_source_fails(tmp_path):
    calls: list[str] = []

    def opener(url, timeout=10):
        calls.append(url)
        raise HTTPError(url, 429, "Too Many Requests", {"Retry-After": "0"}, None)

    log: list[dict[str, object]] = []
    papers = fetch_papers(
        ["semanticscholar:crypto carry"],
        ("2024-01-01", "2026-12-31"),
        opener=opener,
        cache_dir=tmp_path / "literature_cache",
        sleeper=lambda _delay: None,
        log_out=log,
    )

    assert papers == []
    assert len(calls) == 3
    assert log == [
        {
            "source": "semanticscholar",
            "query": "crypto carry",
            "status": "error:HTTPError",
            "count": 0,
            "cache": "miss",
            "retries": 2,
        }
    ]


def test_fetch_papers_filters_outside_date_window():
    payload = json.dumps(
        {
            "data": [
                {"title": "Old", "year": 2019, "externalIds": {}, "authors": []},
                {"title": "New", "year": 2025, "externalIds": {}, "authors": []},
            ]
        }
    ).encode()

    def opener(url, timeout=10):
        return BytesIO(payload)

    papers = fetch_papers(["semanticscholar:x"], ("2024-01-01", "2026-12-31"), opener=opener)

    assert [paper["title"] for paper in papers] == ["New"]


def test_fetch_papers_rejects_unknown_source():
    with pytest.raises(ValueError, match="unsupported source"):
        fetch_papers(["ftp:whatever"], ("2024-01-01", "2024-12-31"))
