"""Assemble the worklog site from repository-local files."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Internal tracking codes must not reach the published page.
_CODE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\b[EH]-\d+\b",
        r"\bF-[A-Z0-9_-]+\b",
        r"\bADR-\d+\b",
        r"\bWS-[A-Z]\b",
        r"\bPR\s*#\d+(?:/#?\d+)*\b",
        r"#\d+\b",
        r"\bK \d/\d\b",
        r"\b[CFIP]\d{1,3}(?:\.\d+)?(?:/[CFIP]?\d{1,3})*\b",
    )
]
_TYPE_LABELS = {
    "feat": "功能",
    "fix": "修正",
    "docs": "文件",
    "chore": "維護",
    "refactor": "重構",
    "test": "測試",
    "perf": "效能",
    "ci": "CI",
}
# Merged daily rows older than this are trusted from the previously published
# history, because local transcripts age out (default ~30-day retention).
HISTORY_CUTOFF_DAYS = 21


def scrub_codes(value: str) -> str:
    for pattern in _CODE_PATTERNS:
        value = pattern.sub("", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = re.sub(r"\s+([,:;.)])", r"\1", value)
    value = re.sub(r"\(\s+", "(", value)
    value = re.sub(r"\(\s*\)|\[\s*\]", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" -–—:,/")


def _git_commits(root: Path) -> list[dict[str, Any]]:
    marker_format = "%x1e%h%x1f%cI%x1f%an%x1f%s%x1f%b%x1d"
    output = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "log",
            "--since=365 days ago",
            f"--pretty=format:{marker_format}",
            "--numstat",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    commits = []
    for record in output.split("\x1e"):
        if not record.strip():
            continue
        header, _, stats = record.partition("\x1d")
        fields = header.strip("\r\n").split("\x1f", 4)
        if len(fields) != 5:
            raise ValueError("unexpected git log output")
        changed = sum(
            1
            for line in stats.splitlines()
            if len(line.split("\t")) >= 3
            and all(part.isdigit() or part == "-" for part in line.split("\t")[:2])
        )
        commits.append(
            {
                "hash": fields[0],
                "date": fields[1],
                "author": fields[2],
                "subject": fields[3],
                "body": fields[4].strip(),
                "files_changed": changed,
            }
        )
    return commits


def _ai_outputs(root: Path) -> list[dict[str, str]]:
    paths = list((root / "tasks").glob("*.md"))
    paths += list((root / "docs" / "worklogs").glob("*.md"))
    rows = []
    for path in paths:
        name = path.name.casefold()
        match = _DATE.search(path.name)
        date = match.group(0) if match else datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).date().isoformat()
        title = ""
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                title = scrub_codes(line[2:].strip())
                break
        if not title:
            continue
        if "codex-tasks" in name:
            kind = "codex-tasks"
        elif "handoff" in name:
            kind = "handoff"
        elif path.parent.name == "worklogs" or "worklog" in name:
            kind = "worklog"
        else:
            kind = "other"
        rows.append({"date": date, "title": title, "type": kind})
    return sorted(rows, key=lambda row: (row["date"], row["title"]), reverse=True)


def _daily_activity(commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-day 'what was done' items from commit subjects, codes scrubbed."""
    days: dict[str, list[str]] = {}
    for commit in commits:
        subject = commit["subject"]
        label = ""
        match = re.match(r"^(\w+)(\([\w./-]+\))?!?:\s*(.+)$", subject)
        if match:
            label = _TYPE_LABELS.get(match.group(1).lower(), "")
            subject = match.group(3)
        item = scrub_codes(subject)
        if not item:
            continue
        text = f"[{label}] {item}" if label else item
        bucket = days.setdefault(commit["date"][:10], [])
        if text not in bucket:
            bucket.append(text)
    return [
        {"date": date, "items": items}
        for date, items in sorted(days.items(), reverse=True)
    ]


def _merge_history(
    fresh: dict[str, Any], previous_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep previously published days whose transcripts have since aged out."""
    daily = list(fresh.get("daily", []))
    sessions = list(fresh.get("sessions", []))
    if not previous_path.is_file():
        return daily, sessions
    try:
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return daily, sessions
    cutoff = (
        datetime.now(timezone.utc).date().toordinal() - HISTORY_CUTOFF_DAYS
    )
    is_old = lambda date: datetime.fromisoformat(date).toordinal() < cutoff  # noqa: E731
    fresh_dates = {row["date"] for row in daily}
    daily += [
        row
        for row in previous.get("daily", [])
        if is_old(row["date"]) and row["date"] not in fresh_dates
    ]
    session_keys = {(row["tool"], row["start"]) for row in sessions}
    sessions += [
        row
        for row in previous.get("sessions", [])
        if is_old(row["start"][:10]) and (row["tool"], row["start"]) not in session_keys
    ]
    daily.sort(key=lambda row: row["date"])
    sessions.sort(key=lambda row: row["start"])
    return daily, sessions


def publish_worklog(
    root: Path,
    out_dir: Path,
    *,
    sessions_data: dict[str, Any],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    daily, sessions = _merge_history(sessions_data, out_dir / "worklog.json")
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "daily_activity": _daily_activity(_git_commits(root)),
        "sessions": sessions,
        "daily": daily,
        "skipped_lines": sessions_data.get("skipped_lines", 0),
        "ai_outputs": _ai_outputs(root),
    }
    (out_dir / "worklog.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copyfile(root / "worklog_page" / "index.html", out_dir / "index.html")
    (out_dir / ".nojekyll").touch()
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT.parent / "quant_worklog")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--sessions-json",
        type=Path,
        default=Path(tempfile.gettempdir()) / "quant_worklog_sessions.json",
    )
    args = parser.parse_args(argv)
    if not args.sessions_json.is_file():
        raise SystemExit(f"sessions JSON not found: {args.sessions_json}")
    sessions = json.loads(args.sessions_json.read_text(encoding="utf-8"))
    if not isinstance(sessions, dict):
        raise SystemExit("sessions JSON must contain an object")
    payload = publish_worklog(args.repo_root, args.out_dir, sessions_data=sessions)
    print(
        f"Wrote {args.out_dir / 'worklog.json'} "
        f"({len(payload['daily_activity'])} activity days, "
        f"{len(payload['sessions'])} sessions)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
