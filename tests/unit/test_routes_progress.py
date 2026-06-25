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
    assert "timeline" not in payload
    assert "branches" not in payload


def test_shipped_workstreams_yaml_is_valid():
    repo_root = Path(__file__).resolve().parents[2]
    cards, err = _load_workstreams(repo_root)
    assert err is None, err
    assert cards, "expected seeded workstreams"
    bad = [c["name"] for c in cards if c["error"]]
    assert not bad, f"cards with errors: {bad}"
