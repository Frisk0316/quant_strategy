import json

import scripts.run_engine_consistency_smoke as smoke


def _summary(*, passed: bool = True) -> dict:
    signal_status = "PASS" if passed else "FAIL"
    mismatch_count = 0 if passed else 1
    return {
        "portable_validation_gate": {"passed": passed},
        "engines": {
            "vectorbt": {
                "comparison": {
                    "signal_logic": {
                        "status": "PASS",
                        "actionable_mismatch_count": 0,
                    },
                },
            },
            "backtrader": {
                "comparison": {
                    "signal_logic": {
                        "status": signal_status,
                        "actionable_mismatch_count": mismatch_count,
                    },
                },
            },
        },
    }


def _write_min_fixture(run_dir):
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps({"start": "2024-01-01T00:00:00Z", "end": "2024-01-01T02:00:00Z"}),
        encoding="utf-8",
    )
    (run_dir / "price_series.csv").write_text(
        "datetime,close\n2024-01-01T00:00:00Z,1\n2024-01-01T01:00:00Z,2\n",
        encoding="utf-8",
    )
    (run_dir / "signals.csv").write_text("side\nbuy\nsell\nbuy\n", encoding="utf-8")


def test_smoke_returns_nonzero_when_an_engine_signal_logic_fails(monkeypatch, tmp_path):
    fixture_root = tmp_path / "fixture"
    run_dir = fixture_root / "ma_crossover"
    _write_min_fixture(run_dir)

    monkeypatch.setattr(smoke, "FIXTURES", {"ma_crossover": "ma_crossover"})
    monkeypatch.setattr(smoke, "run_differential_validation", lambda **_: _summary(passed=False))

    assert smoke.main(["--fixture-root", str(fixture_root)]) == 1


def test_smoke_accepts_passing_engine_summaries(monkeypatch, tmp_path):
    fixture_root = tmp_path / "fixture"
    run_dir = fixture_root / "ma_crossover"
    _write_min_fixture(run_dir)

    monkeypatch.setattr(smoke, "FIXTURES", {"ma_crossover": "ma_crossover"})
    monkeypatch.setattr(smoke, "run_differential_validation", lambda **_: _summary())

    assert smoke.main(["--fixture-root", str(fixture_root)]) == 0
