---
status: current
type: handoff
owner: codex
created: 2026-07-13
last_reviewed: 2026-07-13
expires: none
superseded_by: null
---

# Context Handoff: F-VOL-REGIME-OPT Stage 2 / E-040 — 2026-07-13

## Goal (one sentence)

Determine whether real Deribit short-premium quotes support the E-039 synthetic
pricing result, or leave a reproducible fail-closed acquisition record.

## Current state

- Branch: `codex/pipeline-batch1-stage3`.
- Last known state: `d046978`; the working tree already contained Claude's
  uncommitted H-014/E-039 files and unrelated PR #9 follow-up edits before this task.
- In-progress edits: none; E-040 implementation, artifacts, report, ledgers, and
  handoffs are written.
- What works: deterministic 6-date-per-symbol sampling; single-timestamp as-of
  chain extraction; nearest-30d leg matching; BS-on-DVOL comparison; unit test;
  fail-closed output; vendor comparison.
- What does not work / unfinished: the full 12-pair sample did not complete.
  Four dates yielded 7 day×symbol pairs, then the 2024-03-01 Tardis gzip was
  3,053,462,495 bytes versus the fixed 2 GiB limit. `verdict.evaluated=false`.

## Decisions made (and why)

- Select the three lowest and three highest IVP classified month-first dates per
  symbol, ties by date — deterministic extremes satisfy the approved
  stratification without discretionary sampling; would change only via a new
  approved task rule.
- Build the chain as of the global `local_timestamp` nearest 08:00 UTC — every
  retained quote is available at or before that snapshot; would change if the
  vendor supplies an authoritative atomic chain-snapshot dataset.
- Stop above 2 GiB per daily gzip — bounded acquisition was required and the
  task explicitly permits fail-closed size handling; would change only with
  user approval for a larger local download budget or purchased bulk delivery.
- Treat partial ratios as diagnostic, not a verdict — the ≥6-per-symbol sample
  gate was not met.

## Open questions / unverified assumptions

- Whether the remaining five unique free sample files can be processed safely
  with a larger local resource budget is unverified.
- Whether a one-off Tardis BTC/ETH-only history purchase is cheaper than the
  public $3,000/month Business Options plan requires a vendor quote; no quote
  was requested.

## Rules in play (preserve verbatim)

- I13 / R6.3: trial count is recorded; no hidden trials in selection. E-040 has
  0 trials and no K use.
- I8 / R5.3 and R6.1: a quote used by the 08:00 snapshot has
  `quote_local_timestamp <= snapshot_timestamp`; artifact QA passed for all 35 rows.
- I15 / R7.2: no live/shadow/demo claim without all gates passed + human approval.
- Do-not-touch: existing E-039 result artifacts; `research/*.md`; strategy,
  signal, risk, portfolio, execution, backtesting engine, config gates, and the
  other session's PR #9 repair edits. Stage 3 remains unauthorized.

## Context to load next (the reading list)

- Source of truth: `tasks/2026-07-13-f-vol-regime-opt-stage2-codex-tasks.md`,
  `docs/superpowers/specs/2026-07-13-f-vol-regime-opt-hypothesis.md`, and
  `results/stage2_probe_20260713_f_vol_regime_opt/stage2_feasibility.json`.
- Owning files: `research/probes/f_vol_regime_opt_stage2.py`,
  `tests/unit/test_f_vol_regime_opt_stage2.py`, `docs/FEATURE_MAP.md`, and
  `docs/DATA_FLOW.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` (no dedicated
  F-VOL context pack exists).

## Checks run

- `...Python312\python.exe -m pytest tests\unit\test_f_vol_regime_opt_stage2.py -q -p no:cacheprovider` — 1 passed.
- `...Python312\python.exe -m ruff check research\probes\f_vol_regime_opt_stage2.py tests\unit\test_f_vol_regime_opt_stage2.py` — passed.
- `...Python312\python.exe scripts\docs\check_doc_metadata.py` — passed, 0 warnings.
- `...Python312\python.exe scripts\docs\check_feature_map_links.py` — passed, 214 paths.
- `...Python312\python.exe scripts\docs\check_ledger_consistency.py` — passed,
  15 hypotheses / 40 experiments / 14 K-budget families.
- PowerShell artifact QA — 35 rows, BTC=3 pairs, ETH=4 pairs; all quote local
  timestamps are at or before the snapshot.
- A separate `py_compile` attempt could not write
  `tests/unit/__pycache__` due workspace permissions; pytest import/execution passed.

## Approvals

- Human approval obtained: Stage 2 T1/T2 only.
- Not obtained: larger/unbounded data acquisition, purchase, Stage 3, options
  engine/adapter/accounting, or any deployment/promotion work.

## Next action (single, concrete)

- Claude reviews E-040 for I13/F26 compliance and confirms the fail-closed
  verdict before the user decides whether to fund/authorize another data path.

## Human Learning Notes

Free does not mean small: the four processed Tardis daily gzips were 0.71–1.96
GB, and reaching 08:00 consumed 0.24–0.69 GB compressed per date. The first
blocked file alone was 3.05 GB. Partial quotes looked plausible but cannot answer
the hypothesis because the registered sample gate failed; preserving that
distinction prevents an attractive partial result from becoming hidden selection.
