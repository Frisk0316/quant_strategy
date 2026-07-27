---
status: current
type: task
owner: claude
created: 2026-07-21
last_reviewed: 2026-07-21
expires: 2026-10-21
superseded_by: null
---

# Codex Task: B1-code distinctness feasibility guard

User-authorized 2026-07-21 (ruling recorded in
`tasks/2026-07-18-strategy-history-h010-claude-review.md`). Implements in code
what R6.6/I49 currently promise only in prose: a Stage-2 distinctness contract
whose structural infeasibility is detected and refused BEFORE probe execution.

## Filled Implementation template

```text
Task: Add a pre-execution distinctness-feasibility guard to the H-010/xvenue
Stage-2 path so a structurally impossible reference intersection is refused
as a contract defect before any probe runs.

Strategy/spec source: docs/DOMAIN_RULES.md R6.6; docs/INVARIANTS.md I49;
  docs/superpowers/specs/2026-07-18-f-xvenue-leadlag-hypothesis.md
  "Future-round distinctness amendment — 2026-07-21";
  tasks/2026-07-18-strategy-history-h010-claude-review.md (B1 finding +
  2026-07-21 follow-up verification).

Required behavior:
- New function (suggest backtesting/xvenue_leadlag_probe.py, or a small
  shared helper if genuinely reusable — no speculative generality):
  `check_distinctness_feasibility(candidate_window, reference_ranges,
  min_common_days=MIN_COMMON_DAYS)` that, given the candidate formal window
  and each gating reference's DECLARED available date range, computes the
  maximum achievable common-day intersection per reference and overall.
- Refusal semantics: if the achievable intersection < min_common_days, raise
  an explicit contract-defect error (message naming each reference, its
  range, the achievable common days, and the required minimum) — mirroring
  the B2 frozen-evidence refusal style. This must run BEFORE probe/candidate
  simulation on BOTH entry paths (run_data_probe and
  STAGE2_PROBES["F-XVENUE-LEADLAG"]), and before any artifact is written.
- Declaration source: reference_ranges must be passed in explicitly by the
  caller (ex-ante declaration), not inferred silently from whatever data
  happens to load. A missing/empty declaration is itself a refusal (fail
  closed), consistent with the calibration_evidence contract.
- The E-057 configuration (91-day window, references from 2022+,
  min 365) must be exactly reproducible as a refusal in a test: the guard
  must reject it before probe execution.
- A feasible configuration test must also exist (e.g. multi-year candidate
  window intersecting the declared ranges >= 365 days) proving PASS is now
  structurally reachable and the probe proceeds to the existing checks.
- E-057's recorded artifacts, registry/ledger rows, and outcome are
  IMMUTABLE — this guard governs future rounds only. No reprobe, retry, or
  Stage-2 execution of any kind is authorized by this task; the guard ships
  with tests only.

PERMITTED FILES (only edit these):
- backtesting/xvenue_leadlag_probe.py
- backtesting/pipeline_stage2_registry.py   (wire the guard into both paths)
- tests/unit/test_xvenue_leadlag_probe.py
- tests/unit/test_pipeline_stage2_registry.py
- docs/DOMAIN_RULES.md                       (R6.6: note the rule is now
  code-enforced, one line)
- docs/INVARIANTS.md                         (I49: reference the guarding test)

FORBIDDEN (do not touch):
- results/** (E-057 artifacts immutable — paste hash check proving untouched)
- docs/EXPERIMENT_REGISTRY.md, docs/HYPOTHESIS_LEDGER.md
- src/okx_quant/{strategies,signals,risk,portfolio,execution}/, config/risk.yaml
- Any probe execution, reprobe, or new experiment record

SCOPE LIMIT: guard + tests + two one-line doc notes. No threshold changes
(MIN_COMMON_DAYS stays 365), no window widening decision (that belongs to a
future user-authorized round), no orchestrator behavior change beyond the
guard firing on its existing path.

ACCEPTANCE CRITERIA (binary):
- [ ] E-057's exact configuration reproduces a pre-execution refusal in a test.
- [ ] A structurally feasible configuration passes the guard and proceeds.
- [ ] Missing/empty reference declaration refuses (fail closed) with a test.
- [ ] Guard fires on BOTH entry paths before any artifact write (tests on both).
- [ ] E-057 artifact SHA-256 unchanged (pasted before/after).
- [ ] Full unit suite green; Ruff, ledger consistency, doc checks PASS (tails).
- [ ] Diff contains only permitted files.

REPORT: changed files, test tails, hash check, assumptions, anything
UNCONFIRMED. 完成後交 Claude 審；審過後 reprobe 禁令才解除（解除 ≠ 授權
reprobe——reprobe 仍需獨立的使用者授權與 ex-ante rationale + K 計數）。
```
