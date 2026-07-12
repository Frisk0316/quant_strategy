import subprocess

from scripts.docs import check_doc_impact


def test_git_failure_cannot_look_like_clean_changeset(monkeypatch, capsys):
    monkeypatch.setattr(
        check_doc_impact.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=128, stdout="", stderr="fatal: dubious ownership"
        ),
    )

    assert check_doc_impact.main(["--strict"]) == 1
    assert "could not inspect changed files" in capsys.readouterr().out


def test_executable_matrix_includes_validation_and_governance_rules():
    rules = {rule.rule_id: rule for rule in check_doc_impact.RULES}

    assert check_doc_impact._matches_any("backtesting/cpcv.py", rules["A9"].triggers)
    assert check_doc_impact._matches_any("docs/DOC_IMPACT_MATRIX.md", rules["A10"].triggers)
