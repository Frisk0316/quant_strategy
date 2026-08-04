from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.publish_public_status import build_public_status


FORBIDDEN = ("dvol", "ivp", "vrp", "rv", "z", "px", "signal", "legs", "intent")


def _fixture(root: Path, *, missing: str | None = None) -> dict[str, str]:
    config = root / "config"
    shadow = root / "results" / "shadow_h014"
    frontend = root / "frontend"
    config.mkdir(parents=True)
    shadow.mkdir(parents=True)
    frontend.mkdir(parents=True)

    if missing != "workstreams.yaml":
        (config / "workstreams.yaml").write_text(
            """workstreams:
  - name: Public status
    status: active
    milestones: [scope, publish]
    current: publish
    state: implementation complete
    next: enable Pages
    links: [tasks/public-status.md]
""",
            encoding="utf-8",
        )
    if missing != "bias_report.json":
        (shadow / "bias_report.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-08-04T00:00:00Z",
                    "exit_criteria": {
                        "journal_weeks": 3.0,
                        "distinct_journal_weeks": 3,
                        "minimum_weeks": 8,
                        "eight_week_journal_met": False,
                        "private_metric": 99,
                    },
                }
            ),
            encoding="utf-8",
        )
    canaries = {key: f"SECRET_{key.upper()}" for key in FORBIDDEN}
    if missing != "journal.jsonl":
        events = [
            {"event_date": "2026-08-03", "status": "not_rich", **canaries},
            {"event_date": "2026-08-04", "status": "not_rich"},
        ]
        (shadow / "journal.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
    if missing != "research_funnel.json":
        (frontend / "research_funnel.json").write_text(
            json.dumps(
                {
                    "families": [
                        {
                            "family_id": "F-TEST",
                            "status": "refuted",
                            "hypothesis_id": "H-001",
                            "experiments": [
                                {"id": "E-001", "outcome": "stage2_fail"},
                                {"id": "E-002", "outcome": "refuted"},
                            ],
                            "dsr": 0.1,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
    return canaries


def test_complete_inputs_publish_only_the_four_status_sections(tmp_path: Path):
    _fixture(tmp_path)

    status = build_public_status(tmp_path)

    assert status["schema_version"] == 1
    assert set(status) == {
        "schema_version",
        "generated_at",
        "workstreams",
        "shadow_h014",
        "research_funnel",
    }
    assert status["workstreams"][0]["links"] == ["public-status.md"]
    assert status["shadow_h014"]["event_counts"] == {
        "total": 2,
        "by_status": {"not_rich": 2},
        "last_event_date": "2026-08-04",
    }
    assert status["research_funnel"] == [
        {
            "family": "F-TEST",
            "status": "refuted",
            "hypothesis_id": "H-001",
            "experiment_count": 2,
            "outcome": "refuted",
        }
    ]


def test_journal_signal_canaries_never_reach_serialized_output(tmp_path: Path):
    canaries = _fixture(tmp_path)

    serialized = json.dumps(build_public_status(tmp_path))

    for key, value in canaries.items():
        assert f'"{key}"' not in serialized
        assert value not in serialized


@pytest.mark.parametrize(
    ("missing", "section"),
    [
        ("workstreams.yaml", "workstreams"),
        ("bias_report.json", "shadow_h014"),
        ("journal.jsonl", "shadow_h014"),
        ("research_funnel.json", "research_funnel"),
    ],
)
def test_missing_input_marks_its_section_unavailable(
    tmp_path: Path, missing: str, section: str
):
    _fixture(tmp_path, missing=missing)

    unavailable = build_public_status(tmp_path)[section]

    assert unavailable == {"available": False, "reason": f"{missing} not found"}
