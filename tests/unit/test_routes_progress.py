from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from okx_quant.api.routes_progress import (
    _load_workstreams,
    build_progress_payload,
    make_progress_router,
)


def _write(tmp_path: Path, text: str) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir(exist_ok=True)
    (cfg / "workstreams.yaml").write_text(text, encoding="utf-8")


def test_load_workstreams_splits_milestones(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: XS momentum
    status: blocked
    milestones: [spec, impl, backtest, wf_cpcv, demo, live]
    current: wf_cpcv
    state: "PSR 0.82 < 0.95"
    next: "rerun after sizing fix"
    links: [docs/x.md]
    updated: 2026-06-26
""")
    cards, err = _load_workstreams(tmp_path)
    assert err is None
    assert len(cards) == 1
    card = cards[0]
    assert card["error"] is None
    assert card["status"] == "blocked"
    assert card["links"] == ["docs/x.md"]
    states = {m["name"]: m["state"] for m in card["milestones"]}
    assert states == {
        "spec": "done", "impl": "done", "backtest": "done",
        "wf_cpcv": "current", "demo": "pending", "live": "pending",
    }


def test_status_done_marks_all_done(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: Manual
    status: done
    milestones: [draft, write, verify]
    current: verify
""")
    cards, _ = _load_workstreams(tmp_path)
    assert all(m["state"] == "done" for m in cards[0]["milestones"])


def test_current_not_in_milestones_is_card_error(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: Bad
    milestones: [a, b]
    current: zzz
""")
    cards, err = _load_workstreams(tmp_path)
    assert err is None
    assert cards[0]["error"]
    assert cards[0]["milestones"] == []


def test_missing_current_is_card_error_when_not_done(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: NoCurrent
    milestones: [a, b]
""")
    cards, _ = _load_workstreams(tmp_path)
    assert cards[0]["error"]


def test_malformed_yaml_returns_payload_error(tmp_path: Path):
    _write(tmp_path, "workstreams: [unclosed\n")
    cards, err = _load_workstreams(tmp_path)
    assert cards == []
    assert err and "parse error" in err


def test_missing_file_is_empty_not_error(tmp_path: Path):
    cards, err = _load_workstreams(tmp_path)
    assert cards == []
    assert err is None


def test_progress_route_returns_200_with_workstreams_shape(tmp_path: Path):
    app = FastAPI()
    app.include_router(make_progress_router(tmp_path), prefix="/api/progress")
    resp = TestClient(app).get("/api/progress")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["workstreams"] == []
    assert payload["error"] is None
    assert payload["file_links_enabled"] is False
    assert "timeline" not in payload
    assert "branches" not in payload
    assert TestClient(app).get("/api/progress/file", params={"path": "docs/plan.md"}).status_code == 404


def test_progress_route_serves_only_configured_files(tmp_path: Path):
    _write(tmp_path, """
workstreams:
  - name: Docs
    status: done
    milestones: [verify]
    current: verify
    links: [docs/plan.md, docs/missing.md, docs/raw.txt, ../outside.md]
""")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "plan.md").write_text("# Plan", encoding="utf-8")
    (docs / "raw.txt").write_text("raw", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    app = FastAPI()
    app.include_router(make_progress_router(tmp_path, serve_files=True), prefix="/api/progress")
    client = TestClient(app)

    assert client.get("/api/progress/file", params={"path": "docs/plan.md"}).text == "# Plan"
    for path in ("secret.txt", "docs/missing.md", "docs/raw.txt", "../outside.md"):
        assert client.get("/api/progress/file", params={"path": path}).status_code == 404


def test_shipped_workstreams_yaml_is_valid():
    repo_root = Path(__file__).resolve().parents[2]
    cards, err = _load_workstreams(repo_root)
    assert err is None, err
    assert cards, "expected seeded workstreams"
    bad = [c["name"] for c in cards if c["error"]]
    assert not bad, f"cards with errors: {bad}"


def test_shipped_ledger_files_require_file_serving():
    repo_root = Path(__file__).resolve().parents[2]
    ledger_paths = [
        "docs/HYPOTHESIS_LEDGER.md",
        "docs/EXPERIMENT_REGISTRY.md",
        "docs/STRATEGY_HISTORY.md",
    ]
    cards, _ = _load_workstreams(repo_root)
    pipeline = next(c for c in cards if c["name"] == "Strategy research pipeline — full-auto roadmap")
    assert [link for link in pipeline["links"] if link in ledger_paths] == ledger_paths

    enabled = FastAPI()
    enabled.include_router(make_progress_router(repo_root, serve_files=True), prefix="/api/progress")
    enabled_client = TestClient(enabled)
    assert enabled_client.get("/api/progress").json()["file_links_enabled"] is True
    for path in ledger_paths:
        assert enabled_client.get("/api/progress/file", params={"path": path}).status_code == 200
    assert enabled_client.get("/api/progress/file", params={"path": "AI_CONTEXT.md"}).status_code == 404

    disabled = FastAPI()
    disabled.include_router(make_progress_router(repo_root, serve_files=False), prefix="/api/progress")
    disabled_client = TestClient(disabled)
    assert disabled_client.get("/api/progress").json()["file_links_enabled"] is False
    for path in ledger_paths:
        assert disabled_client.get("/api/progress/file", params={"path": path}).status_code == 404
