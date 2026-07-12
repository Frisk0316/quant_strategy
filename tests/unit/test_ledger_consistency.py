"""Guard tests for scripts/docs/check_ledger_consistency.py (A11)."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "docs" / "check_ledger_consistency.py"

spec = importlib.util.spec_from_file_location("check_ledger_consistency", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

LEDGER_OK = """
| H-001 | F-A | 4 | hyp | src | testing | E-001; E-002 (reserved, probe) | notes |
"""
REGISTRY_OK = """
| E-001 | 2026-07-01 | H-001 | F-A | setup | 4 | artifact | outcome | notes |
| F-A | 1 | 2 | one retry |
"""


def _run(monkeypatch, tmp_path, ledger, registry):
    ledger_path = tmp_path / "HYPOTHESIS_LEDGER.md"
    registry_path = tmp_path / "EXPERIMENT_REGISTRY.md"
    ledger_path.write_text(ledger, encoding="utf-8")
    registry_path.write_text(registry, encoding="utf-8")
    monkeypatch.setattr(mod, "LEDGER", ledger_path)
    monkeypatch.setattr(mod, "REGISTRY", registry_path)
    return mod.main()


def test_consistent_pair_passes(monkeypatch, tmp_path, capsys):
    assert _run(monkeypatch, tmp_path, LEDGER_OK, REGISTRY_OK) == 0
    assert "passed" in capsys.readouterr().out


def test_reserved_experiment_may_be_absent(monkeypatch, tmp_path):
    # E-002 is annotated reserved and absent from the registry: allowed.
    assert _run(monkeypatch, tmp_path, LEDGER_OK, REGISTRY_OK) == 0


def test_missing_experiment_fails(monkeypatch, tmp_path, capsys):
    ledger = LEDGER_OK.replace("E-002 (reserved, probe)", "E-003")
    assert _run(monkeypatch, tmp_path, ledger, REGISTRY_OK) == 1
    assert "E-003" in capsys.readouterr().out


def test_unknown_hypothesis_fails(monkeypatch, tmp_path, capsys):
    registry = REGISTRY_OK.replace("H-001 | F-A", "H-999 | F-A")
    assert _run(monkeypatch, tmp_path, LEDGER_OK, registry) == 1
    assert "H-999" in capsys.readouterr().out


def test_family_disagreement_fails(monkeypatch, tmp_path, capsys):
    registry = REGISTRY_OK.replace("| E-001 | 2026-07-01 | H-001 | F-A |", "| E-001 | 2026-07-01 | H-001 | F-B |")
    assert _run(monkeypatch, tmp_path, LEDGER_OK, registry) == 1
    assert "disagrees" in capsys.readouterr().out


def test_missing_k_budget_family_fails(monkeypatch, tmp_path, capsys):
    registry = REGISTRY_OK.replace("| F-A | 1 | 2 | one retry |", "")
    assert _run(monkeypatch, tmp_path, LEDGER_OK, registry) == 1
    assert "K-budget" in capsys.readouterr().out


def test_k_over_limit_fails(monkeypatch, tmp_path, capsys):
    registry = REGISTRY_OK.replace("| F-A | 1 | 2 |", "| F-A | 3 | 2 |")
    assert _run(monkeypatch, tmp_path, LEDGER_OK, registry) == 1
    assert "exceeds" in capsys.readouterr().out


def test_real_repo_ledgers_are_consistent():
    assert mod.main() == 0
