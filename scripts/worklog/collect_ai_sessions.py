"""Collect timestamp-only Claude Code and Codex work sessions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SESSION_GAP_MINUTES = 30
_DECODER = json.JSONDecoder()
_FIELDS = {
    name: re.compile(rf'(?<!\\)"{name}"\s*:\s*') for name in ("timestamp", "cwd")
}


def _json_string_field(line: str, name: str) -> str | None:
    for match in _FIELDS[name].finditer(line):
        try:
            value, _ = _DECODER.raw_decode(line[match.end() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, str):
            return value
    return None


def _timestamp(line: str) -> datetime | None:
    raw = _json_string_field(line, "timestamp")
    if raw is None:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _windows_path(value: str | Path) -> str:
    return str(PureWindowsPath(str(value).replace("/", "\\"))).casefold()


def _read_events(
    directory: Path,
    pattern: str,
    *,
    project_root: Path | None = None,
) -> tuple[list[datetime], int]:
    events: list[datetime] = []
    skipped = 0
    target = _windows_path(project_root) if project_root else None

    if not directory.is_dir():
        return events, skipped

    for path in sorted(directory.rglob(pattern)):
        known_cwd: str | None = None
        for line in path.open(encoding="utf-8", errors="replace"):
            if not line.strip():
                continue
            cwd = _json_string_field(line, "cwd")
            if cwd is not None:
                known_cwd = _windows_path(cwd)
            timestamp = _timestamp(line)
            if timestamp is None:
                skipped += 1
                continue
            if target is None or known_cwd == target:
                events.append(timestamp)
    return events, skipped


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sessions(tool: str, events: list[datetime]) -> list[dict[str, Any]]:
    if not events:
        return []
    groups: list[list[datetime]] = [[events[0]]]
    for event in sorted(events)[1:]:
        gap = (event - groups[-1][-1]).total_seconds() / 60
        if gap > SESSION_GAP_MINUTES:
            groups.append([event])
        else:
            groups[-1].append(event)
    return [
        {
            "tool": tool,
            "start_dt": group[0],
            "end_dt": group[-1],
            "event_count": len(group),
        }
        for group in groups
    ]


def _union_minutes(intervals: list[tuple[datetime, datetime]]) -> float:
    total = 0.0
    current: tuple[datetime, datetime] | None = None
    for start, end in sorted(intervals):
        if current and start <= current[1]:
            current = (current[0], max(current[1], end))
        else:
            if current:
                total += (current[1] - current[0]).total_seconds()
            current = (start, end)
    if current:
        total += (current[1] - current[0]).total_seconds()
    return total / 60


def collect_sessions(
    claude_dir: Path,
    codex_dir: Path,
    *,
    project_root: Path = ROOT,
) -> dict[str, Any]:
    claude_events, claude_skipped = _read_events(claude_dir, "*.jsonl")
    codex_events, codex_skipped = _read_events(
        codex_dir,
        "rollout-*.jsonl",
        project_root=project_root,
    )
    raw_sessions = sorted(
        _sessions("claude", sorted(claude_events))
        + _sessions("codex", sorted(codex_events)),
        key=lambda row: row["start_dt"],
    )
    sessions = [
        {
            "tool": row["tool"],
            "start": _iso(row["start_dt"]),
            "end": _iso(row["end_dt"]),
            "duration_minutes": round(
                (row["end_dt"] - row["start_dt"]).total_seconds() / 60, 2
            ),
            "event_count": row["event_count"],
        }
        for row in raw_sessions
    ]
    # Bucket by the generator's local date; total_minutes is the cross-tool
    # interval UNION so concurrent claude+codex time is never double-counted.
    daily: dict[str, list[dict[str, Any]]] = {}
    for row in raw_sessions:
        daily.setdefault(
            row["start_dt"].astimezone().date().isoformat(), []
        ).append(row)
    daily_rows = []
    for date, rows in sorted(daily.items()):
        minutes = {"claude": 0.0, "codex": 0.0}
        for row in rows:
            minutes[row["tool"]] += (
                row["end_dt"] - row["start_dt"]
            ).total_seconds() / 60
        union = _union_minutes([(row["start_dt"], row["end_dt"]) for row in rows])
        daily_rows.append(
            {
                "date": date,
                "claude_minutes": round(minutes["claude"], 2),
                "codex_minutes": round(minutes["codex"], 2),
                "overlap_minutes": round(
                    max(0.0, minutes["claude"] + minutes["codex"] - union), 2
                ),
                "total_minutes": round(union, 2),
            }
        )
    return {
        "sessions": sessions,
        "daily": daily_rows,
        "skipped_lines": claude_skipped + codex_skipped,
    }


def main(argv: list[str] | None = None) -> int:
    profile = Path(os.environ.get("USERPROFILE", Path.home()))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--claude-dir",
        type=Path,
        default=profile / ".claude" / "projects" / "c--quant-strategy",
    )
    parser.add_argument(
        "--codex-dir", type=Path, default=profile / ".codex" / "sessions"
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(tempfile.gettempdir()) / "quant_worklog_sessions.json",
    )
    args = parser.parse_args(argv)
    payload = collect_sessions(
        args.claude_dir, args.codex_dir, project_root=args.project_root
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["daily"], ensure_ascii=False))
    print(f"Skipped lines: {payload['skipped_lines']}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
