"""A11: cross-check HYPOTHESIS_LEDGER and EXPERIMENT_REGISTRY consistency.

Validates H<->E ID links, family relations, and K-budget bounds from the
markdown tables. It deliberately does NOT claim to verify experiment artifacts
on disk (they may be gitignored or external) — that remains a human review
step per docs/DOC_IMPACT_MATRIX.md A11.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / "docs" / "HYPOTHESIS_LEDGER.md"
REGISTRY = REPO_ROOT / "docs" / "EXPERIMENT_REGISTRY.md"

TEMPLATE_IDS = {"H-000", "E-000", "F-000"}
E_ID_RE = re.compile(r"E-\d{3}")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _rows(path: Path, prefix: str) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {prefix}"):
            rows.append(_cells(line))
    return rows


def main() -> int:
    errors: list[str] = []

    # Ledger: | ID | Family ID | n_trials | hypothesis | source | status | Experiment(s) | notes |
    hypotheses: dict[str, dict] = {}
    for row in _rows(LEDGER, "H-"):
        if len(row) < 8:
            errors.append(f"ledger {row[0]}: expected 8 columns, got {len(row)}")
            continue
        h_id, family, n_trials = row[0], row[1], row[2]
        if h_id in hypotheses:
            errors.append(f"ledger {h_id}: duplicate hypothesis ID")
        hypotheses[h_id] = {"family": family, "experiments_text": row[6]}
        if h_id not in TEMPLATE_IDS and not re.fullmatch(r"\d+", n_trials):
            errors.append(f"ledger {h_id}: n_trials {n_trials!r} is not a non-negative integer")

    # Registry: | ID | Date | Hypothesis | Family ID | setup | trials | artifact | outcome | notes |
    experiments: dict[str, dict] = {}
    for row in _rows(REGISTRY, "E-"):
        if len(row) < 9:
            errors.append(f"registry {row[0]}: expected 9 columns, got {len(row)}")
            continue
        e_id, h_ref, family = row[0], row[2], row[3]
        if e_id in experiments:
            errors.append(f"registry {e_id}: duplicate experiment ID")
        experiments[e_id] = {"hypothesis": h_ref, "family": family}

    # K-budget: | Family ID | K_used | K_limit | basis |
    k_budget: dict[str, tuple[int, int]] = {}
    for row in _rows(REGISTRY, "F-"):
        if len(row) < 4:
            errors.append(f"k-budget {row[0]}: expected 4 columns, got {len(row)}")
            continue
        family, used, limit = row[0], row[1], row[2]
        if family in k_budget:
            errors.append(f"k-budget {family}: duplicate family row")
        try:
            k_budget[family] = (int(used), int(limit))
        except ValueError:
            errors.append(f"k-budget {family}: non-integer K values {used!r}/{limit!r}")

    # Empty tables must fail loud: an unreadable/reformatted ledger silently
    # passing would defeat the whole check.
    real_hypotheses = {h for h in hypotheses if h not in TEMPLATE_IDS}
    real_experiments = {e for e in experiments if e not in TEMPLATE_IDS}
    if not real_hypotheses:
        errors.append("ledger: no non-template hypothesis rows parsed")
    if not real_experiments:
        errors.append("registry: no non-template experiment rows parsed")

    # H -> E links. "reserved" experiments are intentionally absent from the
    # registry until their probe runs (e.g. E-038 per the 2026-07-12 decision).
    # The reserved annotation only covers the ID it directly follows: it is
    # searched between this E-ID and the next E-ID (or end of cell), so it can
    # never leak onto a neighboring experiment ID.
    for h_id, h in hypotheses.items():
        if h_id in TEMPLATE_IDS:
            continue
        text = h["experiments_text"]
        matches = list(E_ID_RE.finditer(text))
        for idx, match in enumerate(matches):
            e_id = match.group(0)
            if e_id in experiments:
                continue
            tail_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            annotation = text[match.end():tail_end].lower()
            if "reserved" in annotation:
                continue
            errors.append(f"ledger {h_id}: references {e_id} not present in registry")

    # E -> H links, family agreement, and the reverse listing requirement:
    # every registry experiment must be listed on its hypothesis row.
    for e_id, e in experiments.items():
        if e_id in TEMPLATE_IDS:
            continue
        h_ref = e["hypothesis"]
        if h_ref not in hypotheses:
            errors.append(f"registry {e_id}: hypothesis {h_ref!r} not present in ledger")
            continue
        if e["family"] != hypotheses[h_ref]["family"]:
            errors.append(
                f"registry {e_id}: family {e['family']!r} disagrees with "
                f"ledger {h_ref} family {hypotheses[h_ref]['family']!r}"
            )
        if e_id not in E_ID_RE.findall(hypotheses[h_ref]["experiments_text"]):
            errors.append(
                f"registry {e_id}: not listed in ledger {h_ref} Experiment(s) column"
            )

    # Family coverage and K bounds.
    families_seen = {h["family"] for h_id, h in hypotheses.items() if h_id not in TEMPLATE_IDS}
    families_seen |= {e["family"] for e_id, e in experiments.items() if e_id not in TEMPLATE_IDS}
    for family in sorted(families_seen - set(k_budget) - TEMPLATE_IDS):
        errors.append(f"family {family}: missing from the K-budget table")
    # K_limit = 2 is the documented pipeline stop condition; the pipeline
    # consumes these values, so a relaxed or negative row is an error.
    for family, (used, limit) in sorted(k_budget.items()):
        if used < 0:
            errors.append(f"k-budget {family}: K_used {used} is negative")
        if limit != 2:
            errors.append(f"k-budget {family}: K_limit {limit} differs from the documented limit 2")
        if used > limit:
            errors.append(f"k-budget {family}: K_used {used} exceeds K_limit {limit}")

    for error in errors:
        print(f"ERROR {error}")
    if errors:
        print(f"ledger consistency check failed: {len(errors)} error(s)")
        return 1
    print(
        f"ledger consistency check passed: {len(hypotheses)} hypotheses, "
        f"{len(experiments)} experiments, {len(k_budget)} K-budget families "
        "(artifact existence is NOT checked; see DOC_IMPACT_MATRIX A11)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
