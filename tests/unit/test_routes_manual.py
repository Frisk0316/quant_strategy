import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from okx_quant.api.routes_manual import make_manual_router
from scripts.run_server import create_app as create_standalone_app


def _client(tmp_path: Path) -> TestClient:
    (tmp_path / "manual.json").write_text(
        json.dumps(
            {
                "title": "使用者手冊",
                "chapters": [
                    {
                        "slug": "architecture",
                        "title": "系統架構",
                        "file": "00-architecture.md",
                        "status": "written",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "00-architecture.md").write_text(
        "---\nstatus: current\n---\n\n# 系統架構\n\nhello", encoding="utf-8"
    )
    app = FastAPI()
    app.include_router(make_manual_router(tmp_path), prefix="/api/manual")
    return TestClient(app)


def test_manifest_returned(tmp_path):
    r = _client(tmp_path).get("/api/manual")
    assert r.status_code == 200
    assert r.json()["chapters"][0]["slug"] == "architecture"


def test_chapter_markdown_returned(tmp_path):
    r = _client(tmp_path).get("/api/manual/architecture")
    assert r.status_code == 200
    assert "# 系統架構" in r.text
    assert "status: current" not in r.text


def test_unknown_chapter_404(tmp_path):
    r = _client(tmp_path).get("/api/manual/nope")
    assert r.status_code == 404


def test_standalone_server_registers_manual_router(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    app = create_standalone_app(tmp_path, repo_root / "frontend")

    response = TestClient(app).get("/api/manual")

    assert response.status_code == 200
    assert response.json()["chapters"]
