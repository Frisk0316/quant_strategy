from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess

import scripts.worklog.snapshot_strategies as snapshot_strategies
from scripts.worklog.collect_ai_sessions import collect_sessions
from scripts.worklog.publish_worklog_page import publish_worklog, scrub_codes
from scripts.worklog.snapshot_portfolio import MAX_EQUITY_POINTS, build_snapshot


def _line(timestamp: str, **fields: object) -> str:
    return json.dumps({"timestamp": timestamp, **fields})


def test_session_split_daily_totals_skips_and_codex_cwd_filter(tmp_path: Path):
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir()
    (codex / "2026" / "08" / "04").mkdir(parents=True)
    (claude / "session.jsonl").write_text(
        "\n".join(
            [
                _line("2026-08-04T10:00:00Z"),
                _line("2026-08-04T10:15:00Z"),
                "not-json",
                _line("2026-08-04T11:00:00Z"),
            ]
        ),
        encoding="utf-8",
    )
    rollout_dir = codex / "2026" / "08" / "04"
    (rollout_dir / "rollout-other.jsonl").write_text(
        "\n".join(
            [
                _line("2026-08-04T12:00:00Z", cwd="C:/another_project"),
                _line("2026-08-04T12:10:00Z"),
            ]
        ),
        encoding="utf-8",
    )
    (rollout_dir / "rollout-target.jsonl").write_text(
        "\n".join(
            [
                _line("2026-08-04T13:00:00Z", cwd="c:\\QUANT_STRATEGY"),
                _line("2026-08-04T13:20:00Z"),
            ]
        ),
        encoding="utf-8",
    )

    result = collect_sessions(claude, codex, project_root=Path("C:/quant_strategy"))

    assert [(row["tool"], row["event_count"]) for row in result["sessions"]] == [
        ("claude", 2),
        ("claude", 1),
        ("codex", 2),
    ]
    assert result["daily"] == [
        {
            "date": "2026-08-04",
            "claude_minutes": 15.0,
            "codex_minutes": 20.0,
            "overlap_minutes": 0.0,
            "total_minutes": 35.0,
        }
    ]
    assert result["skipped_lines"] == 1


def test_daily_total_is_interval_union_not_double_counted(tmp_path: Path):
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir()
    codex.mkdir()
    (claude / "session.jsonl").write_text(
        "\n".join([_line("2026-08-04T10:10:00Z"), _line("2026-08-04T10:30:00Z")]),
        encoding="utf-8",
    )
    (codex / "rollout-a.jsonl").write_text(
        "\n".join(
            [
                _line("2026-08-04T10:20:00Z", cwd="C:/quant_strategy"),
                _line("2026-08-04T10:40:00Z"),
            ]
        ),
        encoding="utf-8",
    )

    result = collect_sessions(claude, codex, project_root=Path("C:/quant_strategy"))

    day = result["daily"][0]
    assert day["claude_minutes"] == 20.0
    assert day["codex_minutes"] == 20.0
    assert day["overlap_minutes"] == 10.0
    assert day["total_minutes"] == 30.0


def test_transcript_content_and_secret_canaries_never_reach_output(tmp_path: Path):
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir()
    codex.mkdir()
    (claude / "session.jsonl").write_text(
        _line(
            "2026-08-04T10:00:00Z",
            content="SECRET_CANARY_XYZ",
            apiKey="sk-test",
        ),
        encoding="utf-8",
    )

    serialized = json.dumps(collect_sessions(claude, codex))

    assert "SECRET_CANARY_XYZ" not in serialized
    assert "sk-" not in serialized
    assert '"content"' not in serialized


def _run_fixture(run_dir: Path, *, metrics: bool = True) -> None:
    run_dir.mkdir()
    if metrics:
        (run_dir / "metrics.json").write_text(
            json.dumps({"total_return": 0.12, "sharpe": 1.5}), encoding="utf-8"
        )
    (run_dir / "config.json").write_text(
        json.dumps({"cli_args": {"strategy": ["ma_crossover", "funding_carry"]}}),
        encoding="utf-8",
    )
    with (run_dir / "equity_curve.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ts", "equity", "drawdown"])
        writer.writeheader()
        for index in range(1001):
            writer.writerow(
                {"ts": index, "equity": 1000 + index, "drawdown": -index / 10000}
            )


def test_snapshot_keeps_metrics_and_exact_downsample_endpoints(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    _run_fixture(run_dir)

    snapshot = build_snapshot(run_dir, date="2026-08-04")

    assert snapshot["metrics"]["sharpe"] == 1.5
    assert snapshot["strategies"] == ["ma_crossover", "funding_carry"]
    assert len(snapshot["equity"]) == MAX_EQUITY_POINTS
    assert snapshot["equity"][0]["ts"] == "0"
    assert snapshot["equity"][-1]["ts"] == "1000"

    (run_dir / "metrics.json").unlink()
    assert build_snapshot(run_dir)["metrics"] == {
        "available": False,
        "reason": "metrics.json not found",
    }


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _repo_fixture(root: Path, commit_subject: str) -> None:
    (root / "tasks").mkdir(parents=True)
    (root / "docs" / "worklogs").mkdir(parents=True)
    (root / "worklog_page").mkdir()
    (root / "tasks" / "2026-08-04-test-codex-tasks.md").write_text(
        "# H-038 E-095 rerun task\nprivate body", encoding="utf-8"
    )
    (root / "worklog_page" / "index.html").write_text("<h1>page</h1>", encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.name", "Unit Test")
    _git(root, "config", "user.email", "unit@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-m", commit_subject)


def test_publisher_emits_scrubbed_daily_activity_without_commit_details(tmp_path: Path):
    root = tmp_path / "repo"
    out = tmp_path / "site"
    _repo_fixture(root, "feat(backtesting): complete H-038 E-095 terminal rerun")
    sessions = {"sessions": [], "daily": [], "skipped_lines": 2}

    payload = publish_worklog(root, out, sessions_data=sessions)
    serialized = (out / "worklog.json").read_text(encoding="utf-8")

    assert payload["schema_version"] == 2
    assert "commits" not in payload
    assert payload["daily_activity"][0]["items"] == [
        "[功能] complete terminal rerun"
    ]
    assert payload["ai_outputs"][0]["title"] == "rerun task"
    assert "filename" not in payload["ai_outputs"][0]
    assert "E-095" not in serialized
    assert "H-038" not in serialized
    assert (out / "index.html").is_file()
    assert (out / ".nojekyll").is_file()


def test_scrub_codes_removes_internal_identifiers():
    assert scrub_codes("H-038 E-095 rerun per ADR-0016 WS-C C3/C5 PR #17") == "rerun per"
    assert scrub_codes("PR #19/#20 merged, F-S5 restored to K 1/2 (C3 fix)") == (
        "merged, restored to (fix)"
    )
    assert scrub_codes("plain subject stays") == "plain subject stays"


def test_publisher_merges_previously_published_history(tmp_path: Path):
    root = tmp_path / "repo"
    out = tmp_path / "site"
    out.mkdir()
    _repo_fixture(root, "chore: keep")
    old_daily = {
        "date": "2026-05-04",
        "claude_minutes": 50.0,
        "codex_minutes": 0.0,
        "overlap_minutes": 0.0,
        "total_minutes": 50.0,
    }
    old_session = {
        "tool": "claude",
        "start": "2026-05-04T02:00:00Z",
        "end": "2026-05-04T02:50:00Z",
        "duration_minutes": 50.0,
        "event_count": 9,
    }
    (out / "worklog.json").write_text(
        json.dumps({"daily": [old_daily], "sessions": [old_session]}),
        encoding="utf-8",
    )
    fresh_daily = {
        "date": "2026-08-05",
        "claude_minutes": 10.0,
        "codex_minutes": 0.0,
        "overlap_minutes": 0.0,
        "total_minutes": 10.0,
    }
    sessions = {"sessions": [], "daily": [fresh_daily], "skipped_lines": 0}

    payload = publish_worklog(root, out, sessions_data=sessions)

    assert payload["daily"] == [old_daily, fresh_daily]
    assert payload["sessions"] == [old_session]


def test_strategies_snapshot_counts_shadow_without_signal_values(
    tmp_path: Path, monkeypatch
):
    vol = tmp_path / "vol"
    funding = tmp_path / "funding"
    shadow = tmp_path / "shadow"
    for directory in (vol, funding, shadow):
        directory.mkdir()
    (vol / "summary.json").write_text(
        json.dumps(
            {
                "window": ["2020-05-11", "2026-02-27"],
                "statistical_gate_passed": True,
                "default_combo_for_minting": "combo_a",
                "combo_meta": {"combo_a": {"tranches": 357}},
                "validation": {"dsr": 0.9746, "psr": 0.9904, "wf_oos_sharpe": 0.88},
            }
        ),
        encoding="utf-8",
    )
    (vol / "combo_daily_returns.csv").write_text(
        "day,combo_a\n2020-05-11,0.01\n2020-05-12,0.02\n", encoding="utf-8"
    )
    (funding / "summary.json").write_text(
        json.dumps(
            {
                "statistical_gate_passed": False,
                "dsr": 0.83,
                "psr": 0.92,
                "full_sample_best_params": {"lookback_days": 7, "quantile": 0.2},
            }
        ),
        encoding="utf-8",
    )
    (funding / "combo_daily_returns.csv").write_text(
        "day,lookback_days=7|quantile=0.2\n2024-01-01,0.0\n2024-01-02,0.005\n",
        encoding="utf-8",
    )
    (shadow / "journal.jsonl").write_text(
        json.dumps(
            {
                "event_date": "2026-08-04",
                "status": "not_rich",
                "signal": {"dvol": 43.2, "px": 61000.5, "z": -0.4},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (funding / "holdings.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "notional_base_usd": 10000,
                "notional_note": "amounts are weights on a nominal base",
                "rebalances": [
                    {
                        "date": "2024-01-01",
                        "long": {"ADA": 1000.0},
                        "short": {"ALGO": 1000.0},
                        "period_return": 0.0186,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(snapshot_strategies, "VOL_DIR", vol)
    monkeypatch.setattr(snapshot_strategies, "FUNDING_DIR", funding)
    monkeypatch.setattr(snapshot_strategies, "SHADOW_DIR", shadow)

    payload = snapshot_strategies.build_snapshot()
    serialized = json.dumps(payload, ensure_ascii=False)

    vol_row, funding_row = payload["strategies"]
    assert vol_row["passed_statistical_gate"] is True
    assert vol_row["equity"][-1]["cum"] == 0.03
    assert vol_row["shadow"]["status_counts"] == {"not_rich": 1}
    assert funding_row["rebalances"][0]["long"] == {"ADA": 1000.0}
    assert funding_row["rebalance_notional_note"]
    for banned in ("dvol", "61000.5", '"z"', '"px"'):
        assert banned not in serialized
    monkeypatch.setattr(snapshot_strategies, "VOL_DIR", tmp_path / "gone")
    assert (
        snapshot_strategies.build_snapshot()["strategies"][0]["metrics"]["available"]
        is False
    )
