---
status: current
type: handoff
owner: codex
created: 2026-06-24
last_reviewed: 2026-06-24
expires: none
superseded_by: null
---

# Context Handoff: DSR All-Strategy Recheck - 2026-06-24

## Goal (one sentence)
Recheck saved DSR-bearing artifacts after the CPCV DSR harness fix and make sure
pre-fix DSR values are not cited as promotion evidence.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`.
- Last known committed state before this session: `b34ef47` (`chore(results):
  delete pre-6/18 artifacts + reconcile doc references`).
- DSR fix boundary: `fecdd98` (`fix(backtest): correct XS momentum lookahead +
  DSR computation; portfolio-vol sizing`).
- In-progress edits: `scripts/recheck_dsr.py`, docs audit notes, and this handoff
  pair.
- What works right now: `scripts/recheck_dsr.py` scans current
  `results/**/*.json`, classifies CPCV vs single-run DSR rows, recomputes Daily
  Winner CPCV from saved returns, and reports `DSR <= PSR(0)` sanity status.
- What does not work / unfinished: XS momentum CPCV artifacts do not save raw
  path returns, so the audit cannot independently recompute their DSR without a
  DB-backed rerun.

## Decisions made (and why)
- Treat replay `metrics.dsr == metrics.psr` rows as `single_run_diagnostic`,
  not affected CPCV DSR, because `backtesting/replay.py` documents them as PSR-like
  single-run diagnostics.
- Mark `xs_momentum_validation_20260623` and
  `xs_momentum_validation_20260624_leakfix` CPCV DSR as untrusted because saved
  `DSR > PSR(0)`.
- Leave result JSON payloads untouched because the task forbids modifying existing
  artifacts; all corrections are doc annotations and audit output.

## Open questions / unverified assumptions
- Future CPCV artifacts should save raw path returns or a recompute bundle; current
  XS summary/path-Sharpe-only artifacts are not enough for independent DSR recompute.

## Rules in play (preserve verbatim)
- Invariants touched: I21 - DSR is computed on the same per-observation return
  basis as PSR(0), and `DSR <= PSR(0)` for the same series when `n_trials > 1`.
- Domain rules touched: R7.4 - DSR uses non-overlapping OOS observations and
  honest `n_trials`; DSR must not exceed PSR(0).
- Do-not-touch: `src/okx_quant/strategies/`, `signals/`, `risk/`,
  `portfolio/`, `execution/`, `src/okx_quant/analytics/dsr.py`,
  `backtesting/cpcv.py`, existing result artifact payloads, deployment gates,
  `research/`.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`,
  `tasks/2026-06-24-dsr-allstrategy-recheck-task.md`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md` -> Validation / Promotion
  Gates and Result Artifacts.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run
- `python scripts/recheck_dsr.py` - passed; 45 DSR-bearing JSON rows, 7 CPCV rows,
  38 single-run diagnostic rows.
- `python -m pytest tests/unit/test_dsr.py tests/unit/test_cpcv.py -q` - 3 passed;
  pytest emitted a `.pytest_cache` permission warning.
- `python scripts/docs/check_doc_impact.py` with one-shot `safe.directory` env -
  passed; 8 changed files, no impact-matrix violations.
- `make docs-check PYTHON=...` - not run because `make` is unavailable in this
  Windows environment.
- `python scripts/docs/check_doc_metadata.py` - passed with 14 pre-existing
  metadata warnings outside this task.
- `python scripts/docs/check_feature_map_links.py` - passed.

## Approvals
- Human approval needed / obtained: current user explicitly requested the DSR
  recheck task. No approval was requested or needed to modify result payloads
  because none were modified.

## Next action (single, concrete)
- Review and commit the audit/docs changes, then ask Claude to review the
  DSR recheck classifications if a second opinion is needed.

## Human Learning Notes
The saved artifact shape matters as much as the metric: summary Sharpe fields are
not enough to recompute DSR. Future CPCV evidence should preserve raw path returns
or a compact recompute bundle, otherwise every audit needs a costly DB rerun.
