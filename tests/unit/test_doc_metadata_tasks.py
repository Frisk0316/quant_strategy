"""Guard tests for the tasks/ lifecycle enforcement in check_doc_metadata.py."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "docs" / "check_doc_metadata.py"

spec = importlib.util.spec_from_file_location("check_doc_metadata", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

VALID_FM = """---
status: current
type: handoff
owner: human
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# body
"""


def _run(monkeypatch, tmp_path, files: dict[str, str]) -> int:
    docs = tmp_path / "docs"
    tasks = tmp_path / "tasks"
    docs.mkdir()
    tasks.mkdir()
    for rel, content in files.items():
        target = tasks / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "DOCS_DIR", docs)
    monkeypatch.setattr(mod, "TASKS_DIR", tasks)
    return mod.main()


def test_new_dated_task_without_frontmatter_fails(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, {"2026-07-13-new-task.md": "# no fm"}) == 1


def test_undated_task_without_frontmatter_fails(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, {"random-notes.md": "# no fm"}) == 1


def test_nested_task_without_frontmatter_fails(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, {"sub/2026-07-13-nested.md": "# no fm"}) == 1


def test_backdated_name_not_in_frozen_list_fails(monkeypatch, tmp_path):
    name = "2026-06-01-backdated-new-file.md"
    assert name not in mod.TASKS_LEGACY_EXEMPT
    assert _run(monkeypatch, tmp_path, {name: "# no fm"}) == 1


def test_frozen_legacy_name_is_exempt(monkeypatch, tmp_path):
    name = sorted(mod.TASKS_LEGACY_EXEMPT)[0]
    assert _run(monkeypatch, tmp_path, {name: "# no fm"}) == 0


def test_exact_template_files_are_exempt(monkeypatch, tmp_path):
    files = {name: "# no fm" for name in mod.TASK_TEMPLATE_EXEMPT}
    assert _run(monkeypatch, tmp_path, files) == 0


def test_template_substring_is_not_an_exemption(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, {"NEW_THING_TEMPLATE.md": "# no fm"}) == 1


def test_task_with_valid_frontmatter_passes(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, {"2026-07-13-good.md": VALID_FM}) == 0


def test_task_metadata_fields_must_be_non_empty(monkeypatch, tmp_path, capsys):
    empty_fm = "---\n" + "\n".join(f"{field}:" for field in mod.REQUIRED_FIELDS) + "\n---\n"
    assert _run(monkeypatch, tmp_path, {"empty-fields.md": empty_fm}) == 1
    out = capsys.readouterr().out
    assert all(field in out for field in mod.REQUIRED_FIELDS)


def test_yaml_empty_metadata_scalars_fail(monkeypatch, tmp_path):
    for index, value in enumerate(('""', "''", "# comment only", "null", "~")):
        invalid = VALID_FM.replace("owner: human", f"owner: {value}")
        case_dir = tmp_path / str(index)
        case_dir.mkdir()
        assert _run(monkeypatch, case_dir, {"empty-owner.md": invalid}) == 1


def test_quoted_valid_status_is_normalized(monkeypatch, tmp_path):
    quoted = VALID_FM.replace("status: current", 'status: "current"')
    assert _run(monkeypatch, tmp_path, {"quoted-status.md": quoted}) == 0


def test_task_status_must_be_known(monkeypatch, tmp_path):
    invalid = VALID_FM.replace("status: current", "status: invented")
    assert _run(monkeypatch, tmp_path, {"invalid-status.md": invalid}) == 1


def test_frozen_list_matches_repo_reality():
    """Every frozen legacy name exists and every non-exempt file has frontmatter."""
    tasks = REPO_ROOT / "tasks"
    for name in mod.TASKS_LEGACY_EXEMPT:
        assert (tasks / name).exists(), f"frozen entry missing on disk: {name}"
    for path in tasks.rglob("*.md"):
        if path.parent == tasks and path.name in mod.TASK_TEMPLATE_EXEMPT | mod.TASKS_LEGACY_EXEMPT:
            continue
        assert path.read_text(encoding="utf-8").startswith("---"), path
