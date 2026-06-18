import json
import os

import scripts.run_all_strategy_signal_validation as runner


def test_main_passes_selected_engines_to_strategy_validation(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_builder(results_dir, batch_id, *, force=False):
        run_dir = results_dir / f"{batch_id}_ma_crossover"
        run_dir.mkdir(parents=True)
        return run_dir

    def fake_validate(results_dir, strategy, engines, fixture_run_id, validation_id):
        calls.append({
            "results_dir": results_dir,
            "strategy": strategy,
            "engines": engines,
            "fixture_run_id": fixture_run_id,
            "validation_id": validation_id,
        })
        return {
            "status": "PASS",
            "validation_conclusion": {"status": "REFERENCE_PASS"},
            "source_data_validation": {"status": "PASS"},
            "portable_validation_gate": {"passed": True},
            "signal_point_correctness": {"passed": True},
            "nautilus_order_fill_parity": {"status": "SKIP"},
            "evidence_path": str(tmp_path / "validation_result.json"),
        }

    monkeypatch.setattr(runner, "BUILDERS", {"ma_crossover": fake_builder})
    monkeypatch.setattr(runner.dv, "run_strategy_differential_validation", fake_validate)

    runner.main([
        "--results-dir", str(tmp_path),
        "--strategies", "ma_crossover",
        "--batch-id", "unit_batch",
        "--engines", "vectorbt,backtrader",
    ])

    assert calls[0]["engines"] == ["vectorbt", "backtrader"]
    assert calls[0]["fixture_run_id"] == "unit_batch_ma_crossover"
    report = json.loads(capsys.readouterr().out)
    assert report["engines"] == ["vectorbt", "backtrader"]
    assert report["scope"] == "signal_point_indicator"


def test_main_disables_numba_jit_by_default_for_vectorbt(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("NUMBA_DISABLE_JIT", raising=False)

    def fake_builder(results_dir, batch_id, *, force=False):
        run_dir = results_dir / f"{batch_id}_ma_crossover"
        run_dir.mkdir(parents=True)
        return run_dir

    def fake_validate(results_dir, strategy, engines, fixture_run_id, validation_id):
        return {
            "status": "PASS",
            "validation_conclusion": {"status": "REFERENCE_PASS"},
            "source_data_validation": {"status": "PASS"},
            "portable_validation_gate": {"passed": True},
            "signal_point_correctness": {"passed": True},
            "nautilus_order_fill_parity": {"status": "SKIP"},
            "evidence_path": str(tmp_path / "validation_result.json"),
        }

    monkeypatch.setattr(runner, "BUILDERS", {"ma_crossover": fake_builder})
    monkeypatch.setattr(runner.dv, "run_strategy_differential_validation", fake_validate)

    runner.main([
        "--results-dir", str(tmp_path),
        "--strategies", "ma_crossover",
        "--batch-id", "unit_batch",
        "--engines", "vectorbt",
    ])

    assert os.environ["NUMBA_DISABLE_JIT"] == "1"
    capsys.readouterr()
