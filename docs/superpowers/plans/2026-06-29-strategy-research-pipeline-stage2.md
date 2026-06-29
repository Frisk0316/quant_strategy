# Strategy Research Pipeline Stage 2 Feasibility Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal Stage 2 automation that turns feasibility checks into a machine-readable gate before any Stage 3 backtest work runs.

**Architecture:** Add one small stdlib-only feasibility schema/validator module, one CLI that validates `stage2_feasibility.json`, and a runner integration that writes the Stage 2 record beside each candidate summary. Keep Stage 2 as a fail-closed research gate: missing required data, missing distinctness evidence, or a failing cost-after-edge smell test returns `FAIL` and leaves grid trials at 0.

**Tech Stack:** Python stdlib (`dataclasses`, `json`, `argparse`, `pathlib`), pytest, markdown docs.

---

## Spec Source

- `docs/superpowers/pipeline/stage2-feasibility.md`
- `docs/superpowers/pipeline/driver.md`
- `docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md`
- `docs/HYPOTHESIS_LEDGER.md`
- `docs/EXPERIMENT_REGISTRY.md`

## Design-Space Expansion

Current Stage 2 feasibility evidence is represented as prose and ad hoc fields such as `stage2_status`, `stage2_reason`, and candidate-specific coverage fields in checkpoint summaries. That is enough for human review, but it is not enough for a repeatable gate: a runner can omit one of the three Stage 2 checks without failing validation.

Three options were considered:

- Docs-only checklist: smallest change, but still manual and easy to skip.
- JSON record plus validator CLI: small, testable, and directly supports current batch runners.
- Full orchestrator with background agents and literature ingestion: broader than the current user request and mixes multiple subsystems.

Chosen option: JSON record plus validator CLI. This gives Stage 2 a stable artifact without changing trading behavior, live gates, or research assumptions.

## Locate-Before-Edit Map

**User-facing behavior / harness surface:** Strategy research pipeline governance. A Stage 2 run produces a `stage2_feasibility.json` artifact with all required checks and a computed `stage2_status`.

**Files to create during execution:**

- `backtesting/pipeline_feasibility.py`: schema, parsing, serialization, and PASS/FAIL evaluation.
- `scripts/run_pipeline_stage2_check.py`: CLI validator for one `stage2_feasibility.json` path.
- `tests/unit/test_pipeline_feasibility.py`: unit coverage for schema and gate behavior.
- `tests/unit/test_pipeline_stage2_check.py`: CLI behavior coverage.

**Files to modify during execution:**

- `scripts/run_pipeline_batch2_checkpoint.py`: write `stage2_feasibility.json` for C1/C2/C3 in the batch output directory.
- `tests/unit/test_pipeline_batch2_checkpoint_runner.py`: assert the new writer emits a valid Stage 2 artifact.
- `docs/superpowers/pipeline/stage2-feasibility.md`: document the machine-readable output contract.
- `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, and `config/workstreams.yaml`: only update after implementation if the workstream status changes.

**Files forbidden for this plan's execution:**

- `research/**`
- `src/okx_quant/strategies/**`
- `src/okx_quant/signals/**`
- `src/okx_quant/risk/**`
- `src/okx_quant/portfolio/**`
- `config/risk.yaml`
- existing `results/**` artifacts

**Verification commands:**

- `python -m pytest tests/unit/test_pipeline_feasibility.py -q`
- `python -m pytest tests/unit/test_pipeline_stage2_check.py -q`
- `python -m pytest tests/unit/test_pipeline_batch2_checkpoint_runner.py -q`
- `python scripts/docs/check_doc_metadata.py`
- `python scripts/docs/check_feature_map_links.py`
- `python scripts/docs/check_doc_impact.py`

**Rollback path:**

- Delete `backtesting/pipeline_feasibility.py`.
- Delete `scripts/run_pipeline_stage2_check.py`.
- Delete `tests/unit/test_pipeline_feasibility.py`.
- Delete `tests/unit/test_pipeline_stage2_check.py`.
- Revert the `scripts/run_pipeline_batch2_checkpoint.py`, `tests/unit/test_pipeline_batch2_checkpoint_runner.py`, and `docs/superpowers/pipeline/stage2-feasibility.md` edits from this plan.

## Output Contract

Every Stage 2 artifact is a JSON object with this shape:

```json
{
  "schema_version": 1,
  "batch_id": "pipeline_batch2_20260625",
  "candidate_id": "c3_sentiment",
  "candidate_dir": "c3_sentiment",
  "hypothesis_id": "H-008",
  "family_id": "F-SENTIMENT",
  "checks": [
    {
      "name": "data_availability",
      "status": "FAIL",
      "reason": "fear_greed_btc event_count=0",
      "details": {
        "dataset_id": "fear_greed_btc",
        "event_count": 0
      }
    },
    {
      "name": "distinctness",
      "status": "PASS",
      "reason": "sentiment family is distinct from enabled price-only strategies"
    },
    {
      "name": "cost_after_edge",
      "status": "FAIL",
      "reason": "cost smell test cannot run without the required external feature"
    }
  ],
  "stage2_status": "FAIL"
}
```

The required checks are exactly:

- `data_availability`
- `distinctness`
- `cost_after_edge`

`stage2_status` is `PASS` only when all three required checks are present and every required check has status `PASS`.

### Task 1: Add Stage 2 Feasibility Schema And Gate

**Files:**

- Create: `backtesting/pipeline_feasibility.py`
- Create: `tests/unit/test_pipeline_feasibility.py`

- [ ] **Step 1: Write the failing schema tests**

Create `tests/unit/test_pipeline_feasibility.py` with:

```python
from __future__ import annotations

import pytest

from backtesting.pipeline_feasibility import (
    FeasibilityCheck,
    FeasibilityResult,
    evaluate_stage2_result,
    result_from_dict,
    result_to_dict,
)


def test_stage2_pass_requires_all_three_checks() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c1_pairs_ou",
        candidate_dir="c1_pairs_ou",
        hypothesis_id="H-006",
        family_id="F-PAIRS-OU",
        checks=(
            FeasibilityCheck("data_availability", "PASS", "venue-scoped BTC/ETH data exists"),
            FeasibilityCheck("distinctness", "PASS", "first proper validation of the OU family"),
            FeasibilityCheck("cost_after_edge", "PASS", "cheap spread edge exceeds fee and slippage smell test"),
        ),
    )

    assert evaluate_stage2_result(result) == "PASS"


def test_stage2_fails_when_required_check_is_missing() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c1_pairs_ou",
        candidate_dir="c1_pairs_ou",
        hypothesis_id="H-006",
        family_id="F-PAIRS-OU",
        checks=(
            FeasibilityCheck("data_availability", "PASS", "venue-scoped BTC/ETH data exists"),
            FeasibilityCheck("distinctness", "PASS", "first proper validation of the OU family"),
        ),
    )

    assert evaluate_stage2_result(result) == "FAIL"


def test_stage2_fails_when_any_required_check_fails() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c3_sentiment",
        candidate_dir="c3_sentiment",
        hypothesis_id="H-008",
        family_id="F-SENTIMENT",
        checks=(
            FeasibilityCheck("data_availability", "FAIL", "fear_greed_btc event_count=0"),
            FeasibilityCheck("distinctness", "PASS", "sentiment family is distinct"),
            FeasibilityCheck("cost_after_edge", "FAIL", "cost smell test cannot run without feature data"),
        ),
    )

    assert evaluate_stage2_result(result) == "FAIL"


def test_result_from_dict_rejects_unknown_status() -> None:
    payload = {
        "batch_id": "pipeline_test",
        "candidate_id": "c3_sentiment",
        "candidate_dir": "c3_sentiment",
        "hypothesis_id": "H-008",
        "family_id": "F-SENTIMENT",
        "checks": [
            {"name": "data_availability", "status": "MAYBE", "reason": "ambiguous"}
        ],
    }

    with pytest.raises(ValueError, match="unknown Stage 2 status"):
        result_from_dict(payload)


def test_result_to_dict_includes_computed_stage2_status() -> None:
    result = FeasibilityResult(
        batch_id="pipeline_test",
        candidate_id="c3_sentiment",
        candidate_dir="c3_sentiment",
        hypothesis_id="H-008",
        family_id="F-SENTIMENT",
        checks=(
            FeasibilityCheck(
                "data_availability",
                "FAIL",
                "fear_greed_btc event_count=0",
                {"dataset_id": "fear_greed_btc", "event_count": 0},
            ),
            FeasibilityCheck("distinctness", "PASS", "sentiment family is distinct"),
            FeasibilityCheck("cost_after_edge", "FAIL", "cost smell test cannot run without feature data"),
        ),
    )

    payload = result_to_dict(result)

    assert payload["schema_version"] == 1
    assert payload["stage2_status"] == "FAIL"
    assert payload["checks"][0]["details"]["event_count"] == 0
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python -m pytest tests/unit/test_pipeline_feasibility.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'backtesting.pipeline_feasibility'
```

- [ ] **Step 3: Add the minimal implementation**

Create `backtesting/pipeline_feasibility.py` with:

```python
"""Stage 2 feasibility gate helpers for the research pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_CHECKS = ("data_availability", "distinctness", "cost_after_edge")
VALID_STATUSES = {"PASS", "FAIL"}
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FeasibilityCheck:
    name: str
    status: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeasibilityResult:
    batch_id: str
    candidate_id: str
    candidate_dir: str
    hypothesis_id: str
    family_id: str
    checks: tuple[FeasibilityCheck, ...]
    schema_version: int = SCHEMA_VERSION


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Stage 2 field {key!r} must be a non-empty string")
    return value


def _check_from_dict(payload: dict[str, Any]) -> FeasibilityCheck:
    name = _required_text(payload, "name")
    status = _required_text(payload, "status").upper()
    reason = _required_text(payload, "reason")
    if status not in VALID_STATUSES:
        raise ValueError(f"unknown Stage 2 status {status!r}")
    details = payload.get("details", {})
    if details is None:
        details = {}
    if not isinstance(details, dict):
        raise ValueError("Stage 2 check details must be an object")
    return FeasibilityCheck(name=name, status=status, reason=reason, details=dict(details))


def result_from_dict(payload: dict[str, Any]) -> FeasibilityResult:
    checks_payload = payload.get("checks")
    if not isinstance(checks_payload, list):
        raise ValueError("Stage 2 field 'checks' must be a list")
    checks = tuple(_check_from_dict(row) for row in checks_payload)
    schema_version = int(payload.get("schema_version", SCHEMA_VERSION))
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported Stage 2 schema_version {schema_version!r}")
    return FeasibilityResult(
        schema_version=schema_version,
        batch_id=_required_text(payload, "batch_id"),
        candidate_id=_required_text(payload, "candidate_id"),
        candidate_dir=_required_text(payload, "candidate_dir"),
        hypothesis_id=_required_text(payload, "hypothesis_id"),
        family_id=_required_text(payload, "family_id"),
        checks=checks,
    )


def evaluate_stage2_result(result: FeasibilityResult) -> str:
    by_name = {check.name: check for check in result.checks}
    for required in REQUIRED_CHECKS:
        check = by_name.get(required)
        if check is None or check.status != "PASS":
            return "FAIL"
    return "PASS"


def result_to_dict(result: FeasibilityResult) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "batch_id": result.batch_id,
        "candidate_id": result.candidate_id,
        "candidate_dir": result.candidate_dir,
        "hypothesis_id": result.hypothesis_id,
        "family_id": result.family_id,
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "reason": check.reason,
                **({"details": check.details} if check.details else {}),
            }
            for check in result.checks
        ],
        "stage2_status": evaluate_stage2_result(result),
    }
```

- [ ] **Step 4: Run schema tests until they pass**

Run:

```bash
python -m pytest tests/unit/test_pipeline_feasibility.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add backtesting/pipeline_feasibility.py tests/unit/test_pipeline_feasibility.py
git commit -m "feat: add stage2 feasibility gate schema"
```

Expected:

```text
[codex/... <sha>] feat: add stage2 feasibility gate schema
```

### Task 2: Add The Stage 2 Validator CLI

**Files:**

- Create: `scripts/run_pipeline_stage2_check.py`
- Create: `tests/unit/test_pipeline_stage2_check.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/unit/test_pipeline_stage2_check.py` with:

```python
from __future__ import annotations

import json

from scripts.run_pipeline_stage2_check import main


def _write_payload(path, checks):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "pipeline_test",
                "candidate_id": "c3_sentiment",
                "candidate_dir": "c3_sentiment",
                "hypothesis_id": "H-008",
                "family_id": "F-SENTIMENT",
                "checks": checks,
            }
        ),
        encoding="utf-8",
    )


def test_stage2_check_cli_returns_zero_for_pass(tmp_path, capsys) -> None:
    path = tmp_path / "stage2_feasibility.json"
    _write_payload(
        path,
        [
            {"name": "data_availability", "status": "PASS", "reason": "data exists"},
            {"name": "distinctness", "status": "PASS", "reason": "distinct family"},
            {"name": "cost_after_edge", "status": "PASS", "reason": "edge exceeds costs"},
        ],
    )

    assert main([str(path)]) == 0
    assert capsys.readouterr().out.strip() == "PASS"


def test_stage2_check_cli_returns_one_for_fail(tmp_path, capsys) -> None:
    path = tmp_path / "stage2_feasibility.json"
    _write_payload(
        path,
        [
            {"name": "data_availability", "status": "FAIL", "reason": "feature absent"},
            {"name": "distinctness", "status": "PASS", "reason": "distinct family"},
            {"name": "cost_after_edge", "status": "FAIL", "reason": "smell test blocked"},
        ],
    )

    assert main([str(path)]) == 1
    assert capsys.readouterr().out.strip() == "FAIL"


def test_stage2_check_cli_can_write_computed_status(tmp_path) -> None:
    path = tmp_path / "stage2_feasibility.json"
    _write_payload(
        path,
        [
            {"name": "data_availability", "status": "PASS", "reason": "data exists"},
            {"name": "distinctness", "status": "PASS", "reason": "distinct family"},
            {"name": "cost_after_edge", "status": "PASS", "reason": "edge exceeds costs"},
        ],
    )

    assert main(["--write-status", str(path)]) == 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage2_status"] == "PASS"
```

- [ ] **Step 2: Run the failing CLI tests**

Run:

```bash
python -m pytest tests/unit/test_pipeline_stage2_check.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'scripts.run_pipeline_stage2_check'
```

- [ ] **Step 3: Add the CLI implementation**

Create `scripts/run_pipeline_stage2_check.py` with:

```python
"""Validate a Stage 2 feasibility artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from backtesting.pipeline_feasibility import result_from_dict, result_to_dict


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-status", action="store_true", help="rewrite the artifact with computed stage2_status")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    result = result_from_dict(payload)
    output = result_to_dict(result)
    status = output["stage2_status"]

    if args.write_status:
        args.path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(status)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests until they pass**

Run:

```bash
python -m pytest tests/unit/test_pipeline_stage2_check.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add scripts/run_pipeline_stage2_check.py tests/unit/test_pipeline_stage2_check.py
git commit -m "feat: add stage2 feasibility validator cli"
```

Expected:

```text
[codex/... <sha>] feat: add stage2 feasibility validator cli
```

### Task 3: Emit Stage 2 Artifacts From The Batch 2 Runner

**Files:**

- Modify: `scripts/run_pipeline_batch2_checkpoint.py`
- Modify: `tests/unit/test_pipeline_batch2_checkpoint_runner.py`

- [ ] **Step 1: Extend the batch runner test**

Append this test to `tests/unit/test_pipeline_batch2_checkpoint_runner.py`:

```python
from scripts.run_pipeline_batch2_checkpoint import _stage2_result_to_summary_fields
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult


def test_stage2_result_to_summary_fields_carries_check_artifact_status():
    result = FeasibilityResult(
        batch_id="pipeline_batch2_20260625",
        candidate_id="c3_sentiment",
        candidate_dir="c3_sentiment",
        hypothesis_id="H-008",
        family_id="F-SENTIMENT",
        checks=(
            FeasibilityCheck("data_availability", "FAIL", "fear_greed_btc event_count=0"),
            FeasibilityCheck("distinctness", "PASS", "sentiment family is distinct"),
            FeasibilityCheck("cost_after_edge", "FAIL", "cost smell test cannot run without feature data"),
        ),
    )

    fields = _stage2_result_to_summary_fields(result)

    assert fields["stage2_status"] == "FAIL"
    assert fields["stage2_reason"] == "fear_greed_btc event_count=0; cost smell test cannot run without feature data"
    assert fields["stage2_checks"]["data_availability"]["status"] == "FAIL"
```

- [ ] **Step 2: Run the failing runner test**

Run:

```bash
python -m pytest tests/unit/test_pipeline_batch2_checkpoint_runner.py -q
```

Expected:

```text
ImportError: cannot import name '_stage2_result_to_summary_fields'
```

- [ ] **Step 3: Add Stage 2 helper imports and functions**

In `scripts/run_pipeline_batch2_checkpoint.py`, add this import after the existing local imports:

```python
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult, evaluate_stage2_result, result_to_dict
```

Add these helpers near `_write_summary`:

```python
def _stage2_result_to_summary_fields(result: FeasibilityResult) -> dict[str, Any]:
    status = evaluate_stage2_result(result)
    failed_reasons = [check.reason for check in result.checks if check.status == "FAIL"]
    return {
        "stage2_status": status,
        "stage2_reason": "; ".join(failed_reasons) if failed_reasons else "all required Stage 2 checks passed",
        "stage2_checks": {
            check.name: {
                "status": check.status,
                "reason": check.reason,
                **({"details": check.details} if check.details else {}),
            }
            for check in result.checks
        },
    }


def _write_stage2_feasibility(candidate_dir: str, result: FeasibilityResult) -> dict[str, Any]:
    payload = result_to_dict(result)
    path = OUT / candidate_dir / "stage2_feasibility.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)
    return _stage2_result_to_summary_fields(result)
```

- [ ] **Step 4: Run the runner test until it passes**

Run:

```bash
python -m pytest tests/unit/test_pipeline_batch2_checkpoint_runner.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Use the helper in C3 Stage 2 failure**

In `run_c3()`, replace the failing-gate summary update branch with:

```python
    if not gate["feature_gate_passed"]:
        stage2 = FeasibilityResult(
            batch_id=BATCH_ID,
            candidate_id="c3_sentiment",
            candidate_dir="c3_sentiment",
            hypothesis_id="H-008",
            family_id="F-SENTIMENT",
            checks=(
                FeasibilityCheck(
                    "data_availability",
                    "FAIL",
                    "fear_greed_btc event_count=0",
                    {"dataset_id": "fear_greed_btc", **gate},
                ),
                FeasibilityCheck(
                    "distinctness",
                    "PASS",
                    "sentiment family is distinct from currently enabled price-only strategies",
                ),
                FeasibilityCheck(
                    "cost_after_edge",
                    "FAIL",
                    "cost smell test cannot run without the required external feature",
                ),
            ),
        )
        summary = _stage2_fail_summary(
            "c3_sentiment",
            "c3_sentiment",
            "F-SENTIMENT",
            "fear_greed_btc missing/stale external-feature gate failed",
            "H-008",
        )
        summary.update(_write_stage2_feasibility("c3_sentiment", stage2))
        summary["external_feature_gate"] = gate
        _write_summary("c3_sentiment", summary)
        return summary
```

- [ ] **Step 6: Use the helper in C2 PASS**

In `run_c2()`, after `summary = _base_summary(...)`, add:

```python
    stage2 = FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id="c2_funding_carry",
        candidate_dir="c2_funding_carry",
        hypothesis_id="H-007",
        family_id="F-FUNDING-CARRY",
        checks=(
            FeasibilityCheck(
                "data_availability",
                "PASS",
                "venue-scoped BTC/ETH spot, perp, and funding inputs loaded from Binance canonical data",
            ),
            FeasibilityCheck(
                "distinctness",
                "PASS",
                "funding carry is treated as the existing funding-carry family with this run counted as a retry",
            ),
            FeasibilityCheck(
                "cost_after_edge",
                "PASS",
                "cheap funding APR and basis filter smell test allowed Stage 3; promotion remains blocked by later gates",
            ),
        ),
    )
```

Then add the Stage 2 fields to the existing `summary.update({...})` call:

```python
        **_write_stage2_feasibility("c2_funding_carry", stage2),
```

- [ ] **Step 7: Use the helper in C1 PASS**

In `run_c1()`, after `summary = _base_summary(...)`, add:

```python
    stage2 = FeasibilityResult(
        batch_id=BATCH_ID,
        candidate_id="c1_pairs_ou",
        candidate_dir="c1_pairs_ou",
        hypothesis_id="H-006",
        family_id="F-PAIRS-OU",
        checks=(
            FeasibilityCheck(
                "data_availability",
                "PASS",
                "venue-scoped BTC/ETH perp candles and funding inputs loaded from Binance canonical data",
            ),
            FeasibilityCheck(
                "distinctness",
                "PASS",
                "logged as first proper validation of the existing pairs_trading BTC/ETH OU mechanism",
            ),
            FeasibilityCheck(
                "cost_after_edge",
                "PASS",
                "cheap spread and turnover smell test allowed Stage 3; promotion remains blocked by later gates",
            ),
        ),
    )
```

Then add the Stage 2 fields to the existing `summary.update({...})` call:

```python
        **_write_stage2_feasibility("c1_pairs_ou", stage2),
```

- [ ] **Step 8: Run runner tests and validator tests together**

Run:

```bash
python -m pytest tests/unit/test_pipeline_feasibility.py tests/unit/test_pipeline_stage2_check.py tests/unit/test_pipeline_batch2_checkpoint_runner.py -q
```

Expected:

```text
11 passed
```

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add scripts/run_pipeline_batch2_checkpoint.py tests/unit/test_pipeline_batch2_checkpoint_runner.py
git commit -m "feat: emit stage2 feasibility artifacts"
```

Expected:

```text
[codex/... <sha>] feat: emit stage2 feasibility artifacts
```

### Task 4: Document The Stage 2 Machine-Readable Contract

**Files:**

- Modify: `docs/superpowers/pipeline/stage2-feasibility.md`

- [ ] **Step 1: Add the contract section**

Append this section to `docs/superpowers/pipeline/stage2-feasibility.md`:

````markdown
## Machine-Readable Output

Every Stage 2 run writes `stage2_feasibility.json` beside the candidate output.
The artifact is validated by `scripts/run_pipeline_stage2_check.py`.

Required checks:

- `data_availability`
- `distinctness`
- `cost_after_edge`

`stage2_status` is `PASS` only when all required checks are present and all
required checks have status `PASS`. Missing checks and failed checks both produce
`FAIL`.

Example:

```json
{
  "schema_version": 1,
  "batch_id": "pipeline_batch2_20260625",
  "candidate_id": "c3_sentiment",
  "candidate_dir": "c3_sentiment",
  "hypothesis_id": "H-008",
  "family_id": "F-SENTIMENT",
  "checks": [
    {
      "name": "data_availability",
      "status": "FAIL",
      "reason": "fear_greed_btc event_count=0"
    },
    {
      "name": "distinctness",
      "status": "PASS",
      "reason": "sentiment family is distinct from currently enabled price-only strategies"
    },
    {
      "name": "cost_after_edge",
      "status": "FAIL",
      "reason": "cost smell test cannot run without the required external feature"
    }
  ],
  "stage2_status": "FAIL"
}
```
````

- [ ] **Step 2: Run docs checks**

Run:

```bash
python scripts/docs/check_doc_metadata.py
python scripts/docs/check_feature_map_links.py
python scripts/docs/check_doc_impact.py
```

Expected:

```text
docs metadata check passed
feature map link check passed
docs impact check passed
```

The metadata command can print warnings for older docs that predate lifecycle metadata; only an `ERROR` line blocks the task.

- [ ] **Step 3: Commit Task 4**

Run:

```bash
git add docs/superpowers/pipeline/stage2-feasibility.md
git commit -m "docs: document stage2 feasibility artifact contract"
```

Expected:

```text
[codex/... <sha>] docs: document stage2 feasibility artifact contract
```

### Task 5: Close The Workstream State

**Files:**

- Modify: `docs/AI_HANDOFF.md`
- Modify: `docs/CURRENT_STATE.md`
- Modify: `config/workstreams.yaml`
- Create: `tasks/2026-06-29-stage2-feasibility-automation-context-handoff.md`
- Create: `tasks/2026-06-29-stage2-feasibility-automation-session-handoff.md`

- [ ] **Step 1: Update current state text**

Add this current/target/gap distinction to the relevant Strategy Research Pipeline section in `docs/CURRENT_STATE.md`:

```markdown
### Stage 2 Feasibility Automation

- Current: Stage 2 feasibility records now have a machine-readable
  `stage2_feasibility.json` artifact with required checks for data availability,
  distinctness, and cost-after-edge.
- Target: every future pipeline candidate writes the artifact before Stage 3
  backtesting starts.
- Known gap: literature ingestion and background-parallel orchestration remain
  outside this patch; this patch only makes the Stage 2 gate auditable.
```

- [ ] **Step 2: Update AI handoff**

Add this row or note to the active handoff section in `docs/AI_HANDOFF.md`:

```markdown
| Strategy research pipeline Stage 2 feasibility automation `(implemented; pending Claude review)` | Stage 2 now has a stdlib-only feasibility schema, validator CLI, and batch-2 artifact writer. Each candidate records `data_availability`, `distinctness`, and `cost_after_edge`; missing or failing required checks compute `stage2_status: FAIL` before Stage 3. No research assumptions, live gates, strategy code, risk settings, or existing result artifacts were changed. | Claude should review the check wording for economic distinctness and cost-after-edge smell-test sufficiency. |
```

- [ ] **Step 3: Update workstream milestone**

In `config/workstreams.yaml`, update the Strategy research pipeline workstream milestone text so the Progress panel reflects the implemented gate:

```yaml
milestone: "Stage 2 feasibility artifact/validator implemented; batch-2 evidence remains in review"
```

Do not change live, shadow, demo, or deployment readiness fields.

- [ ] **Step 4: Create the context handoff**

Create `tasks/2026-06-29-stage2-feasibility-automation-context-handoff.md` with:

```markdown
# Context Handoff: Stage 2 Feasibility Automation

Date: 2026-06-29
Owner: Codex

## Objective

Make Strategy Research Pipeline Stage 2 feasibility checks machine-readable and
fail-closed before Stage 3.

## Files Changed

- `backtesting/pipeline_feasibility.py`
- `scripts/run_pipeline_stage2_check.py`
- `scripts/run_pipeline_batch2_checkpoint.py`
- `tests/unit/test_pipeline_feasibility.py`
- `tests/unit/test_pipeline_stage2_check.py`
- `tests/unit/test_pipeline_batch2_checkpoint_runner.py`
- `docs/superpowers/pipeline/stage2-feasibility.md`
- `docs/CURRENT_STATE.md`
- `docs/AI_HANDOFF.md`
- `config/workstreams.yaml`

## Decisions

- Stage 2 PASS requires all three required checks: data availability,
  distinctness, and cost-after-edge.
- Missing required checks fail closed.
- Unknown check status values raise validation errors.
- Existing result artifacts are not migrated.

## Human Learning Notes

- Stage 2 is not a backtest. It is a cheap gate that prevents data-blocked or
  economically duplicate ideas from spending Stage 3 grid trials.
- A `FAIL` Stage 2 candidate can stay `proposed` when it was never tested, as
  with C3 sentiment when `fear_greed_btc` had zero events.
```

- [ ] **Step 5: Create the session handoff**

Create `tasks/2026-06-29-stage2-feasibility-automation-session-handoff.md` with:

```markdown
# Session Handoff: Stage 2 Feasibility Automation

Date: 2026-06-29
Owner: Codex

## Summary

Implemented a minimal Stage 2 feasibility artifact contract and validator.

## Tests Run

- `python -m pytest tests/unit/test_pipeline_feasibility.py -q`
- `python -m pytest tests/unit/test_pipeline_stage2_check.py -q`
- `python -m pytest tests/unit/test_pipeline_batch2_checkpoint_runner.py -q`
- `python scripts/docs/check_doc_metadata.py`
- `python scripts/docs/check_feature_map_links.py`
- `python scripts/docs/check_doc_impact.py`

## Open Review

- Claude should review whether the distinctness and cost-after-edge reason text
  is strict enough for future candidate review.

## Human Learning Notes

- The validator separates Stage 2 feasibility from Stage 3 statistical evidence.
- The artifact makes missing feasibility checks visible instead of relying on
  prose in the checkpoint summary.
```

- [ ] **Step 6: Run closeout checks**

Run:

```bash
python scripts/docs/check_doc_metadata.py
python scripts/docs/check_feature_map_links.py
python scripts/docs/check_doc_impact.py
git status --short
```

Expected:

```text
docs metadata check passed
feature map link check passed
docs impact check passed
```

`git status --short` should show only the files touched by this Stage 2 automation work, plus any unrelated pre-existing dirty files that were present before execution.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add docs/AI_HANDOFF.md docs/CURRENT_STATE.md config/workstreams.yaml tasks/2026-06-29-stage2-feasibility-automation-context-handoff.md tasks/2026-06-29-stage2-feasibility-automation-session-handoff.md
git commit -m "docs: record stage2 feasibility automation state"
```

Expected:

```text
[codex/... <sha>] docs: record stage2 feasibility automation state
```

## Self-Review

**Spec coverage:** This plan implements the three checks in `docs/superpowers/pipeline/stage2-feasibility.md`, records PASS/FAIL in JSON, validates the artifact with a CLI, and preserves the Stage 2 rule that failed candidates skip Stage 3 with 0 grid trials.

**Scope coverage:** This plan does not modify Claude-owned `research/**`, strategy logic, risk logic, config gates, live/shadow/demo deployment behavior, or existing result artifacts.

**Placeholder scan:** The plan avoids open-ended steps; every code task includes the file path, code to write, command to run, and expected result.

**Type consistency:** The same dataclasses and function names are used across schema tests, CLI tests, runner integration, and docs: `FeasibilityCheck`, `FeasibilityResult`, `result_from_dict`, `result_to_dict`, `evaluate_stage2_result`, `_stage2_result_to_summary_fields`, and `_write_stage2_feasibility`.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-06-29-strategy-research-pipeline-stage2.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
