"""Smoke test: the user-manual manifest is valid and references existing files."""
import json
from pathlib import Path

MANUAL_DIR = Path(__file__).resolve().parents[2] / "docs" / "manual"


def test_manifest_is_valid_and_files_exist():
    manifest = json.loads((MANUAL_DIR / "manual.json").read_text(encoding="utf-8"))
    assert isinstance(manifest.get("title"), str) and manifest["title"]
    chapters = manifest.get("chapters")
    assert isinstance(chapters, list) and chapters
    slugs = set()
    for ch in chapters:
        for key in ("slug", "title", "file", "status"):
            assert ch.get(key), f"chapter missing {key}: {ch}"
        assert ch["status"] in {"written", "stub"}, ch["status"]
        assert ch["slug"] not in slugs, f"duplicate slug {ch['slug']}"
        slugs.add(ch["slug"])
        assert (MANUAL_DIR / ch["file"]).is_file(), f"missing file {ch['file']}"
