---
status: current
type: review
owner: claude
created: 2026-08-07
last_reviewed: 2026-08-07
expires: none
superseded_by: null
---

# Claude review — ADR-0016 slice 2 (I68 validator + one-command round path)

Scope reviewed: uncommitted working-tree diff on `claude/ops-dsn-fix-and-db-backup`
vs `df4e75d` — `backtesting/pipeline_round.py` (+381), `backtesting/
pipeline_orchestrator.py` (+145), `scripts/run_pipeline_orchestrator.py`,
both test modules, I68 row, change-manifest/CHANGELOG/handoff updates.
Task: `tasks/2026-08-07-adr0016-slice2-i68-validator-codex-tasks.md`.

## Verdict: APPROVE-WITH-FINDINGS (no blockers)

All binary acceptance criteria verified met by a fresh-context verifier:
23/23 targeted tests pass, Ruff clean, doc metadata + ledger consistency
pass, doc-impact advisory shows only the A5 WARN (FEATURE_MAP spot-checked
by reviewer: `run_pipeline_orchestrator.py` already owned by the pipeline
feature row; no update needed). No forbidden path touched. I68 diff is
exactly the verification column. `reconcile_round` call site compatible.
Sealing without DSN refuses (`dsn_required`); dataset count mismatch,
missing gross/cost/provenance, breadth coercion-to-1, ordered execution,
interruption resume, and mutated-manifest refusal all have passing tests.
No real round ran; runner registry deliberately empty until phase 3.

## Findings

1. MINOR — real-path range check is count-only. Claim: `query_dataset_claim`
   returns the claim's own parsed start/end, so `dataset_range_mismatch`
   (`pipeline_round.py` validate loop) is unreachable via the live DB path;
   range confirmation reduces to row-count equality inside the claimed
   half-open window. Evidence: `query_dataset_claim` returns
   `{"row_count", "start": start, "end": end}` from the claim itself; the
   mismatch test only fires with an injected `dataset_query`. Resolution:
   acceptable for this slice (count-in-window equality is a real DB
   confirmation); when a phase-3 slice touches this file, have the live
   query also return DB `min/max(ts)` in-window so the range branch bites.
2. MINOR (known gap to record) — breadth is reference-verified, not
   recomputed. Claim: the validator verifies containment + existence +
   SHA-256 of the referenced realized-position artifact but accepts the
   declared breadth number; a candidate could pair any positive breadth
   with any hash-matching file. Evidence: `_prepare_i68_fields` sets
   `row["breadth"] = declared` once the reference verifies. This matches
   the task's letter; I68's "derived, never declared" is fully automated
   only for the fail-closed side. Resolution: carried as a known gap —
   phase 3 runners must recompute breadth from the referenced artifact and
   refuse a declared value that disagrees; noted for the phase-3 task spec.
3. NIT — resume re-validates against the live DB before consulting the
   stored manifest, so a post-seal backfill into a claimed window surfaces
   as `dataset_row_count_mismatch` rather than a resume-specific message.
   Fail-closed and correct; only the diagnostics are indirect. No action
   required this slice.

## Review incidents (not Codex findings)

- `config/workstreams.yaml` encoding corruption (BOM + `—`→`??` in three
  name lines) was introduced by a Claude ops one-liner earlier on
  2026-08-07 (PS5.1 `Get-Content|Set-Content` ANSI misread), predating the
  Codex edit. Repaired during review from HEAD; the working diff now holds
  only the intended 4-line roadmap-row update. Lesson queued for
  `docs/ai/LESSONS.md`: never round-trip UTF-8 repo files through PS5.1
  cmdlets; use the Edit tool or Python.
- Commit hygiene: the working tree mixes this delivery with the same-day
  ops changes (`scripts/backup_db.ps1`, state-doc updates). Commit as
  separate commits: (a) ops/backup + state, (b) slice-2 delivery + its
  docs, so the PR #23 history stays reviewable.

## Checklist disposition

Scope: permitted files only, locate-before-edit honored. Money/risk: no
PnL/fee/funding/sizing/fill code touched — N/A. Data/evidence: no
experiment, trial, K, or artifact change. Schema/contracts: additive CLI
round mode; no API/backtest schema change; DATA_FLOW/UI_MAP unaffected.
Tests/docs: new behavior fully tested; manifest + I68 + CHANGELOG updated.
Readiness: no readiness claim made — correct.
