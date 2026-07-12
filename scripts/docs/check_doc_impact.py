"""Check that business-rule changes carry the required doc updates and manifest.

This is the executable mirror of ``docs/DOC_IMPACT_MATRIX.md``. For each rule, if
any changed file matches a trigger glob, the rule requires that:

* at least one of the rule's ``docs`` is also in the changeset, and
* if the rule is ``manifest`` (a business-rule area), a Change Manifest is
  present in the changeset.

Changed files are gathered from the working tree relative to ``HEAD`` plus
untracked files, and optionally relative to a base ref via ``DOC_IMPACT_BASE``.

Default mode is advisory: violations are printed as warnings and the script
exits 0, so it never blocks an unrelated ``make`` run. Pass ``--strict`` (used
for merge gating) to turn violations into errors and exit 1.
Failure to inspect Git state is always an error; it must not look like a clean
changeset.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Location where Change Manifests are stored (see CHANGE_MANIFEST_TEMPLATE.md).
MANIFEST_GLOB = "docs/change_manifests/*.md"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    triggers: tuple[str, ...]
    docs: tuple[str, ...]
    manifest: bool
    note: str = ""
    extra_manifest_paths: tuple[str, ...] = field(default_factory=tuple)


class GitInspectionError(RuntimeError):
    """Git state could not be inspected reliably."""


# Keep in sync with docs/DOC_IMPACT_MATRIX.md.
RULES: tuple[Rule, ...] = (
    Rule(
        "A1",
        ("src/okx_quant/strategies/*", "src/okx_quant/signals/*"),
        (
            "research/strategy_synthesis.md",
            "docs/DOMAIN_RULES.md",
            "docs/FEATURE_MAP.md",
            "docs/INVARIANTS.md",
            "docs/FAILURE_MODES.md",
        ),
        manifest=True,
        note="strategy/signal logic",
    ),
    Rule(
        "A2",
        ("src/okx_quant/portfolio/*", "src/okx_quant/execution/*"),
        ("docs/DOMAIN_RULES.md", "docs/INVARIANTS.md", "docs/FAILURE_MODES.md"),
        manifest=True,
        note="portfolio/execution accounting",
    ),
    Rule(
        "A3",
        ("src/okx_quant/risk/*", "config/risk.yaml"),
        ("docs/DOMAIN_RULES.md", "docs/INVARIANTS.md", "docs/ai_collaboration.md"),
        manifest=True,
        note="risk/sizing",
    ),
    Rule(
        "A4",
        ("config/strategies.yaml", "config/settings.yaml", "config/universe.yaml"),
        (
            "docs/DOMAIN_RULES.md",
            "docs/FEATURE_MAP.md",
            "docs/DATA_FLOW.md",
            "research/strategy_synthesis.md",
        ),
        manifest=True,
        note="strategy/runtime config",
    ),
    Rule(
        "A5",
        (
            "backtesting/*",
            "scripts/run_backtest.py",
            "scripts/run_replay_backtest.py",
        ),
        ("docs/DATA_FLOW.md", "docs/FEATURE_MAP.md", "docs/GOLDEN_CASES.md"),
        manifest=True,
        note="backtesting workflow",
    ),
    Rule(
        "A6",
        ("sql/*",),
        ("docs/DATA_FLOW.md", "docs/KNOWN_ISSUES.md"),
        manifest=True,
        note="DB schema",
    ),
    Rule(
        "A7",
        ("src/okx_quant/api/*",),
        ("docs/UI_MAP.md", "docs/DATA_FLOW.md", "docs/FEATURE_MAP.md"),
        manifest=False,
        note="API routes",
    ),
    Rule(
        "A8",
        ("frontend/*",),
        ("docs/UI_MAP.md", "docs/FEATURE_MAP.md"),
        manifest=False,
        note="frontend",
    ),
    Rule(
        "A9",
        (
            "backtesting/cpcv.py",
            "backtesting/differential_validation.py",
            "backtesting/pipeline_checkpoint1.py",
            "backtesting/replay.py",
            "backtesting/research_controls.py",
            "backtesting/walk_forward.py",
            "src/okx_quant/analytics/dsr.py",
            "scripts/recheck_dsr.py",
            "scripts/run_differential_validation.py",
            "scripts/run_pipeline_checkpoint1_check.py",
            "scripts/run_source_provenance_validation.py",
        ),
        (
            "docs/DOMAIN_RULES.md",
            "docs/ai_collaboration.md",
            "docs/ADR/0005-replay-validation-gates.md",
            "docs/INVARIANTS.md",
        ),
        manifest=True,
        note="validation / promotion gates",
    ),
    Rule(
        "A10",
        (
            "AGENTS.md",
            "CLAUDE.md",
            "AI_CONTEXT.md",
            "docs/AI_OUTPUT_CONTRACT.md",
            "docs/AI_WORKFLOW.md",
            "docs/BRANCH_VERSIONING.md",
            "docs/DOC_IMPACT_MATRIX.md",
            "docs/DOC_LIFECYCLE.md",
            "docs/ai_collaboration.md",
            "scripts/docs/check_doc_impact.py",
        ),
        ("docs/README.md", "docs/DOC_LIFECYCLE.md", "docs/DOC_IMPACT_MATRIX.md"),
        manifest=False,
        note="AI governance",
    ),
)


def _git_lines(args: list[str]) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-c", f"safe.directory={REPO_ROOT.as_posix()}", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitInspectionError("git executable not found") from exc
    if out.returncode != 0:
        detail = out.stderr.strip() or f"exit code {out.returncode}"
        raise GitInspectionError(f"git {' '.join(args)} failed: {detail}")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def changed_files() -> list[str]:
    files: set[str] = set()
    files.update(_git_lines(["diff", "--name-only", "HEAD"]))
    files.update(_git_lines(["ls-files", "--others", "--exclude-standard"]))
    base = os.environ.get("DOC_IMPACT_BASE")
    if base:
        files.update(_git_lines(["diff", "--name-only", f"{base}...HEAD"]))
    # Normalize to posix repo-relative paths.
    return sorted(f.replace("\\", "/") for f in files)


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    for pat in patterns:
        if pat.endswith("/*"):
            prefix = pat[:-1]  # keep trailing slash
            if path.startswith(prefix):
                return True
        elif fnmatch.fnmatch(path, pat) or path == pat:
            return True
    return False


def _has_manifest(changed: list[str], extra: tuple[str, ...]) -> bool:
    for path in changed:
        if fnmatch.fnmatch(path, MANIFEST_GLOB):
            return True
        if extra and _matches_any(path, extra):
            return True
    return False


def evaluate(changed: list[str]) -> list[str]:
    violations: list[str] = []
    for rule in RULES:
        triggered = [p for p in changed if _matches_any(p, rule.triggers)]
        if not triggered:
            continue

        docs_touched = [d for d in rule.docs if d in changed]
        if not docs_touched:
            violations.append(
                f"{rule.rule_id} ({rule.note}): changed "
                f"{triggered[0]} but none of the required docs were updated "
                f"({', '.join(rule.docs)})"
            )

        if rule.manifest and not _has_manifest(changed, rule.extra_manifest_paths):
            violations.append(
                f"{rule.rule_id} ({rule.note}): business-rule change to "
                f"{triggered[0]} but no Change Manifest in changeset "
                f"(expected a file under {MANIFEST_GLOB})"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat violations as errors and exit 1 (use for merge gating)",
    )
    args = parser.parse_args(argv)

    try:
        changed = changed_files()
    except GitInspectionError as exc:
        print(f"ERROR doc impact check could not inspect changed files: {exc}")
        return 1
    if not changed:
        print("doc impact check: no changed files detected; nothing to verify")
        return 0

    violations = evaluate(changed)
    label = "ERROR" if args.strict else "WARN "
    for v in violations:
        print(f"{label} {v}")

    if not violations:
        print(
            f"doc impact check passed: {len(changed)} changed file(s), "
            f"no impact-matrix violations"
        )
        return 0

    summary = (
        f"doc impact check found {len(violations)} violation(s) across "
        f"{len(changed)} changed file(s)"
    )
    if args.strict:
        print(f"{summary} (strict: blocking)")
        return 1
    print(f"{summary} (advisory: not blocking; run with --strict to enforce)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
