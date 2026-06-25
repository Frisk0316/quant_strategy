from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from okx_quant.api.routes_progress import classify_actor, make_progress_router, parse_status_md


def test_classify_actor_reads_ai_trailers():
    assert classify_actor("AI-Origin: Codex\n") == "codex"
    assert classify_actor("Co-Authored-By: Claude <claude@example.com>\n") == "claude"
    assert classify_actor("AI-Origin: Claude\n") == "claude"
    assert classify_actor("regular human commit\n") == "you"


def test_parse_status_md_reads_fixed_table_and_plan_tasks(tmp_path: Path):
    plan = tmp_path / "plan.md"
    plan.write_text("- [x] one\n- [ ] two\nplain text\n", encoding="utf-8")
    status = f"""
# Branch Status Board
| Branch | State | Whose turn | Next / blocked on | Plan | Updated |
|--------|-------|-----------|-------------------|------|---------|
| feature/a | wip | codex | finish panel | {plan.name} | 2026-06-25 |
| feature/b | done | you | prune branch |  | 2026-06-24 |
"""

    rows = parse_status_md(status, base_dir=tmp_path)

    assert rows[0]["branch"] == "feature/a"
    assert rows[0]["state"] == "wip"
    assert rows[0]["whose_turn"] == "codex"
    assert rows[0]["tasks_done"] == 1
    assert rows[0]["tasks_total"] == 2
    assert rows[1]["tasks_total"] is None


def test_progress_route_returns_200_for_non_git_repo(tmp_path: Path):
    app = FastAPI()
    app.include_router(make_progress_router(tmp_path), prefix="/api/progress")

    response = TestClient(app).get("/api/progress")

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]
    assert payload["timeline"] == []
    assert payload["branches"] == []
