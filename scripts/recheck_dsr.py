"""Audit saved result artifacts for pre-fix CPCV DSR values."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from okx_quant.api.routes_backtest import _daily_winner_cpcv, _daily_winner_return_series


FIX_COMMIT = "fecdd98"


@dataclass
class DsrRow:
    path: str
    kind: str
    generated_before_fix: str
    old_dsr: float | None
    new_dsr: float | None
    psr: float | None
    sanity: str
    status: str
    note: str


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _format_number(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        ts = datetime.fromisoformat(text)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _fix_commit_time(commit: str) -> datetime | None:
    proc = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT.as_posix()}",
            "show",
            "-s",
            "--format=%cI",
            commit,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return _parse_time(proc.stdout.strip())


def _artifact_time(path: Path, payload: Any) -> datetime | None:
    declared = None
    if isinstance(payload, dict):
        declared = (
            payload.get("created_at")
            or payload.get("generated_at")
            or payload.get("timestamp")
            or payload.get("run_started_at")
        )
    return _parse_time(declared) or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _is_before_fix(path: Path, payload: Any, fix_time: datetime | None) -> str:
    if fix_time is None:
        return "unknown"
    artifact_time = _artifact_time(path, payload)
    if artifact_time is None:
        return "unknown"
    return "yes" if artifact_time < fix_time else "no"


def _is_daily_winner(payload: dict[str, Any]) -> bool:
    strategies = payload.get("strategies") or [payload.get("strategy")]
    return "daily_winner" in {str(item) for item in strategies if item}


def _recompute_daily_winner(payload: dict[str, Any]) -> tuple[float | None, float | None] | None:
    returns_rows = payload.get("returns")
    if not isinstance(returns_rows, list):
        return None
    returns = _daily_winner_return_series(returns_rows)
    cpcv = _daily_winner_cpcv(returns)
    if not cpcv:
        return None
    return _number(cpcv.get("dsr")), _number(cpcv.get("psr"))


def _sanity(old_dsr: float | None, psr: float | None) -> str:
    if old_dsr is None or psr is None:
        return "unknown"
    return "pass" if old_dsr <= psr + 1e-12 else "FAIL"


def _cpcv_row(path: Path, payload: dict[str, Any], cpcv: dict[str, Any], fix_time: datetime | None) -> DsrRow:
    old_dsr = _number(cpcv.get("dsr"))
    psr = _number(cpcv.get("psr"))
    before_fix = _is_before_fix(path, payload, fix_time)
    sanity = _sanity(old_dsr, psr)
    new_dsr = None
    note = ""

    if _is_daily_winner(payload):
        recomputed = _recompute_daily_winner(payload)
        if recomputed:
            new_dsr, new_psr = recomputed
            psr = new_psr
            status = "recomputed"
            note = "recomputed from saved daily_winner returns"
        else:
            status = "untrusted"
            note = "daily_winner returns unavailable"
    elif sanity == "FAIL":
        status = "untrusted"
        note = "DSR exceeds PSR(0); old harness output cannot be cited"
    elif old_dsr is not None and old_dsr >= 0.95 and before_fix == "yes":
        status = "untrusted"
        note = "pre-fix passing DSR without saved raw path returns"
    else:
        status = "summary_only"
        note = "raw path returns not saved; invariant passes and DSR is not promotion-passing"

    return DsrRow(
        path=path.relative_to(ROOT).as_posix(),
        kind="cpcv",
        generated_before_fix=before_fix,
        old_dsr=old_dsr,
        new_dsr=new_dsr,
        psr=psr,
        sanity=sanity,
        status=status,
        note=note,
    )


def _single_run_row(path: Path, payload: dict[str, Any], fix_time: datetime | None) -> DsrRow | None:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    if not isinstance(metrics, dict) or "dsr" not in metrics:
        return None
    old_dsr = _number(metrics.get("dsr"))
    psr = _number(metrics.get("psr"))
    note = "replay-level diagnostic; not CPCV multiple-trial DSR"
    return DsrRow(
        path=path.relative_to(ROOT).as_posix(),
        kind="single_run_diagnostic",
        generated_before_fix=_is_before_fix(path, payload, fix_time),
        old_dsr=old_dsr,
        new_dsr=None,
        psr=psr,
        sanity=_sanity(old_dsr, psr),
        status="not_affected",
        note=note,
    )


def _rows(results_dir: Path, fix_time: datetime | None) -> list[DsrRow]:
    out: list[DsrRow] = []
    for path in sorted(results_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        cpcv = payload.get("cpcv")
        if isinstance(cpcv, dict) and "dsr" in cpcv:
            out.append(_cpcv_row(path, payload, cpcv, fix_time))
            continue

        if "dsr" in payload and ("n_combinations" in payload or "path_sharpes" in payload):
            out.append(_cpcv_row(path, payload, payload, fix_time))
            continue

        single = _single_run_row(path, payload, fix_time)
        if single:
            out.append(single)
    return out


def _print_table(rows: list[DsrRow], *, kind: str) -> None:
    selected = [row for row in rows if row.kind == kind]
    if not selected:
        return
    print(f"\n## {kind}\n")
    print("| Path | Before fecdd98 | Old DSR | New DSR | PSR | DSR<=PSR | Status | Note |")
    print("|---|---:|---:|---:|---:|---|---|---|")
    for row in selected:
        print(
            "| "
            + " | ".join(
                [
                    f"`{row.path}`",
                    row.generated_before_fix,
                    _format_number(row.old_dsr),
                    _format_number(row.new_dsr),
                    _format_number(row.psr),
                    row.sanity,
                    row.status,
                    row.note,
                ]
            )
            + " |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default=str(ROOT / "results"))
    parser.add_argument("--fix-commit", default=FIX_COMMIT)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_absolute():
        results_dir = ROOT / results_dir
    fix_time = _fix_commit_time(args.fix_commit)
    rows = _rows(results_dir, fix_time)

    print(f"# DSR Recheck Audit")
    print(f"\nFix commit: `{args.fix_commit}`")
    print(f"Fix commit time: `{fix_time.isoformat() if fix_time else 'unknown'}`")
    print(f"Scanned JSON files under: `{results_dir.relative_to(ROOT).as_posix()}`")
    print(f"Rows with DSR: {len(rows)}")
    print(f"CPCV rows: {sum(1 for row in rows if row.kind == 'cpcv')}")
    print(f"Single-run diagnostic rows: {sum(1 for row in rows if row.kind == 'single_run_diagnostic')}")
    print("\nSanity invariant: CPCV DSR must be <= PSR(0) for the same return series.")

    _print_table(rows, kind="cpcv")
    _print_table(rows, kind="single_run_diagnostic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
