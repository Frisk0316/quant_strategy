from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from backtesting.pipeline_feasibility import FeasibilityCheck
from scripts.run_strategy_finding_20260726 import (
    _alias_adjusted_membership,
    _create_output_root,
    _distinctness_check,
    _h009_data_check,
    _validate_preregistration,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preregistration_receipt_is_verified_and_output_root_cannot_be_reused(tmp_path):
    spec = tmp_path / "docs/superpowers/specs/2026-07-26-strategy-finding-round.md"
    ledger = tmp_path / "docs/HYPOTHESIS_LEDGER.md"
    registry = tmp_path / "docs/EXPERIMENT_REGISTRY.md"
    receipt = tmp_path / "tasks/receipt.md"
    for path in (spec, ledger, registry, receipt):
        path.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        "H-023 F-XS-IDIOVOL H-009 family-cumulative trial count",
        encoding="utf-8",
    )
    ledger.write_text("| H-023 |\n| H-009 |\n", encoding="utf-8")
    registry.write_text("| E-060 |\n| E-061 |\n", encoding="utf-8")
    receipt.write_text(
        "\n".join(
            f"| `{path.relative_to(tmp_path).as_posix()}` | `{_hash(path)}` |"
            for path in (spec, ledger, registry)
        ),
        encoding="utf-8",
    )

    assert _validate_preregistration(project_root=tmp_path, receipt_path=receipt)["validated"]
    ledger.write_text("| H-023 |\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        _validate_preregistration(project_root=tmp_path, receipt_path=receipt)

    output = tmp_path / "output"
    _create_output_root(output)
    with pytest.raises(FileExistsError):
        _create_output_root(output)


def test_alias_collapse_happens_after_pit_selection_without_refill(tmp_path):
    universe = tmp_path / "membership.parquet"
    pd.DataFrame(
        [
            {"date": "2024-01-01", "symbol": "1000SHIB-USDT-SWAP", "eligible": True},
            {"date": "2024-01-01", "symbol": "SHIB-USDT-SWAP", "eligible": True},
            {"date": "2024-01-01", "symbol": "NEXT-USDT-SWAP", "eligible": False},
        ]
    ).to_parquet(universe)

    membership, evidence = _alias_adjusted_membership(
        universe,
        start="2024-01-01",
        end="2024-01-02",
    )

    assert membership["symbol"].tolist() == ["1000SHIB-USDT-SWAP"]
    assert evidence["duplicate_economic_asset_rows_removed"] == 1
    assert evidence["rank_refill"] is False


def test_h009_restoration_is_exactly_28_to_31_unique_assets():
    old = [f"S{index}" for index in range(28)]
    good = [*old, "CC-USDT-SWAP", "FIL-USDT-SWAP", "M-USDT-SWAP"]
    shared = FeasibilityCheck("data_availability", "PASS", "ok", {})

    check = _h009_data_check(shared, good, old)

    assert check.status == "PASS"
    assert check.details["breadth_restoration"]["retry_unique_assets"] == 31
    assert check.details["breadth_restoration"]["shib_alias_double_counted"] is False


def test_distinctness_fails_if_any_declared_reference_column_collides():
    index = pd.date_range("2024-01-01", periods=430, freq="D")
    candidate = pd.Series([(-1.0) ** day * (day + 1) / 10_000 for day in range(430)], index=index)
    references = {
        "funding": pd.Series(range(430), index=index, dtype=float),
        "illiquidity:w14q20": candidate.copy(),
        "illiquidity:w14q30": pd.Series(range(430, 0, -1), index=index, dtype=float),
        "illiquidity:w28q20": pd.Series([(day % 11) / 100 for day in range(430)], index=index),
        "illiquidity:w28q30": pd.Series([(day % 7) / 100 for day in range(430)], index=index),
    }

    check = _distinctness_check(candidate, references)

    assert check.status == "FAIL"
    assert len(check.details["comparisons"]) == 5
    assert check.details["max_abs_corr"] == pytest.approx(1.0)
