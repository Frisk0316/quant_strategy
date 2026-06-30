"""Deterministic idea-batch front end for the research pipeline."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from backtesting.pipeline_checkpoint1 import family_registry_from_text
from backtesting.pipeline_family_minting import decide_family_minting

SCHEMA_VERSION = 1
DEFAULT_CAP = 15


def _cells(line: str) -> list[str]:
    return [cell.strip().strip("*`") for cell in line.strip().strip("|").split("|")]


def _rows(markdown: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header: list[str] = []
    for line in markdown.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells if cell):
            continue
        if not header:
            header = cells
            continue
        row = {header[idx] if idx < len(header) else f"col{idx}": cell for idx, cell in enumerate(cells)}
        if (row.get("Family ID") or "").startswith("F-"):
            rows.append(row)
    return rows


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "idea"


def _rank_from_text(value: str, *, default: int = 1) -> int:
    text = value.lower()
    if "available" in text and "partial" not in text:
        return 0
    if "partial" in text:
        return 1
    if "blocked" in text:
        return 9
    return default


def _is_data_blocked(row: Mapping[str, str]) -> bool:
    text = " ".join(row.values()).lower()
    return "blocked" in text or "無 options" in text or "on-chain" in text


def enumerate_gaps(
    taxonomy_text: str,
    ledger_text: str,
    data_availability_probe: Any | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return taxonomy families that are feasible enough to draft."""

    registry = family_registry_from_text(ledger_text)
    del data_availability_probe
    eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in _rows(taxonomy_text):
        family_id = row.get("Family ID", "").strip()
        text = " ".join(row.values()).lower()
        ledger_status = (registry.get(family_id).status if registry.get(family_id) else "").lower()
        if "refuted" in text or "shelved" in text or "refuted" in ledger_status or "shelved" in ledger_status:
            skipped.append({"family_id": family_id, "reason": "refuted_no_twist"})
            continue
        if _is_data_blocked(row):
            skipped.append({"family_id": family_id, "reason": "data_blocked"})
            continue
        mechanism = row.get("機制") or row.get("mechanism") or row.get("col1") or family_id
        data_text = row.get("資料") or text
        eligible.append(
            {
                "source": "B_taxonomy",
                "provisional_candidate_id": f"B-{_slug(family_id)}",
                "family_id": family_id,
                "family_id_or_NEW": family_id,
                "mechanism": mechanism,
                "data_feasible": True,
                "data_rank": _rank_from_text(data_text),
                "crowding_rank": 1 if "高" in text else 0,
                "planned_grid_size": 4,
                "draft_status": "pending_llm",
                "feedback_spawned": False,
            }
        )
    return {"eligible": eligible, "skipped": skipped}


def rank_and_cap(gaps: Sequence[Mapping[str, Any]], cap: int = DEFAULT_CAP) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministically rank eligible gaps and cap the batch."""

    # ponytail: simple tuple sort is enough until the first real batch proves weights matter.
    ranked = sorted(
        (dict(gap) for gap in gaps),
        key=lambda row: (
            int(row.get("data_rank", 1)),
            int(row.get("crowding_rank", 1)),
            int(row.get("planned_grid_size", 999)),
            str(row.get("family_id") or row.get("family_id_or_NEW") or ""),
        ),
    )
    selected: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked, start=1):
        if idx <= cap:
            row["prior_rank"] = idx
            selected.append(row)
        else:
            overflow.append(
                {
                    "family_id": row.get("family_id") or row.get("family_id_or_NEW", ""),
                    "reason": "cap_overflow",
                }
            )
    return selected, overflow


def _ledger_draft(candidates: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Hypothesis Ledger Draft",
        "",
        "| Candidate | Source | Family | Mechanism | Draft status | Family decision |",
        "|---|---|---|---|---|---|",
    ]
    for candidate in candidates:
        lines.append(
            "| {candidate} | {source} | {family} | {mechanism} | {status} | {decision} |".format(
                candidate=candidate.get("provisional_candidate_id", ""),
                source=candidate.get("source", ""),
                family=candidate.get("family_id_or_NEW", ""),
                mechanism=candidate.get("mechanism", ""),
                status=candidate.get("draft_status", ""),
                decision=candidate.get("family_minting_decision", ""),
            )
        )
    return "\n".join(lines) + "\n"


def _with_family_decision(candidate: Mapping[str, Any], batch_id: str, ledger_path: str | Path) -> dict[str, Any]:
    row = dict(candidate)
    if row.get("draft_status") != "drafted":
        return row
    decision = decide_family_minting(
        row.get("representative_signal", []),
        row.get("reference_signals", {}),
        str(row.get("family_id_or_NEW", "NEW")),
        str(row.get("mechanism", "")),
        ledger_path,
        batch_id=batch_id,
        candidate_id=str(row.get("provisional_candidate_id", "")),
    )
    row["family_minting"] = decision
    row["family_minting_decision"] = decision["decision"]
    return row


def register_batch(
    candidates: Sequence[Mapping[str, Any]],
    batch_id: str,
    ledger_path: str | Path,
    *,
    output_root: str | Path = "results",
    a_half_drafts: Sequence[Mapping[str, Any]] | None = None,
    skipped: Sequence[Mapping[str, Any]] | None = None,
    n_eligible_before_cap: int | None = None,
) -> dict[str, Any]:
    b_rows = [dict(row, source=row.get("source", "B_taxonomy")) for row in candidates]
    a_rows = [dict(row, source=row.get("source", "A_literature")) for row in (a_half_drafts or [])]
    merged = b_rows + a_rows
    decided = [_with_family_decision(row, batch_id, ledger_path) for row in merged]
    source = "mixed" if a_half_drafts is not None else (decided[0].get("source", "B_taxonomy") if decided else "mixed")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "n_eligible_before_cap": len(candidates) if n_eligible_before_cap is None else n_eligible_before_cap,
        "n_selected": len(decided),
        "skipped": list(skipped or []),
        "candidates": decided,
    }
    batch_dir = Path(output_root) / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "idea_batch.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (batch_dir / "hypothesis_ledger_draft.md").write_text(_ledger_draft(decided), encoding="utf-8")
    return payload


def generate_batch(
    taxonomy_path: str | Path,
    ledger_path: str | Path,
    batch_id: str,
    *,
    output_root: str | Path = "results",
    cap: int = DEFAULT_CAP,
) -> dict[str, Any]:
    taxonomy_text = Path(taxonomy_path).read_text(encoding="utf-8")
    ledger_text = Path(ledger_path).read_text(encoding="utf-8")
    enumerated = enumerate_gaps(taxonomy_text, ledger_text)
    selected, overflow = rank_and_cap(enumerated["eligible"], cap=cap)
    return register_batch(
        selected,
        batch_id,
        ledger_path,
        output_root=output_root,
        skipped=[*enumerated["skipped"], *overflow],
        n_eligible_before_cap=len(enumerated["eligible"]),
    )
