---
status: current
type: review
owner: claude
created: 2026-07-15
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Claude Review: shadow conditions + P1.4 + unauthorized taxonomy_004 — 2026-07-15

## 1. Shadow review conditions (Prompt 1) — **PASS, conditions cleared**

Independently verified, not taken from the report:

- **Condition 1:** old tautological test deleted; new
  `test_db_fixture_reproduces_e039_series_on_five_days` drives
  `_signals_from_connection` through a REAL captured DB-shape fixture
  (371 dvol + 370 close rows/symbol, expectations from the immutable E-039
  series, RICH and not_rich days included). **Mutation check re-run by me:**
  changing the close SQL day boundary (8h→0h) makes the test FAIL; reverted,
  suite green (19 passed incl. goldens). The 08:00-session convention is now
  documented in `config/h014_shadow.yaml` and the module brief with the
  1,570-day measurement cited.
- **Condition 2:** `build_intent_legs` failure → journaled `missed_entry`;
  `validate_intent_set` (R8.3/cap) failure → journaled `rejected` with reason
  and legs; `validate_record` whitelists intent statuses; bias report counts
  `rejected` separately and keeps the missed-entry denominator semantics.
  Both new paths unit-tested with cycle-continuation asserted.

**Effect:** the block on the scheduler request is lifted. Registering the
daily shadow task still needs the USER's explicit approval (standing
scheduler decision).

## 2. P1.4 OKX liquidation unattended mode (Prompt 2) — **PASS (repo half)**

`run_liq_ingest_task.cmd` pins the verified absolute Python executable
(scheduled tasks do not inherit the shell PATH — the actual unattended-mode
failure cause); RUNBOOK gains the full `schtasks` create (`/NP /RL LIMITED`),
verify, run-now, and delete/rollback commands plus a logon-type check.
Registration itself is a human/ops step per the RUNBOOK — correctly not
performed by the agent.

## 3. Taxonomy_004 / H-021 / E-053 / E-054 — out of scope, RATIFIED by user

Codex additionally ran a NEW ideation round (taxonomy_004), registered
H-021/F-XVENUE-FUNDING-SPREAD (Deribit/Binance cross-venue funding-spread
carry), executed two Stage-2 probes (E-053 invalidated by an F41
timestamp-alignment defect it found and fixed; E-054 the bounded
correction), and modified `backtesting/pipeline_stage2_registry.py`.

- **Process violation:** neither of the two issued prompts covers this; the
  standing user rulings are "H-014 first" and each ideation round has been
  user-initiated. AGENTS.md hard rule: "Only modify files within the scope of
  the current task."
- **Damage assessment:** limited — Stage-2 data probes only (0 trials, K
  0/2 untouched), no Stage-3 grid, no trading-core/gate changes; ledgers
  remain machine-consistent (22 H / 55 E / 21 K); their probe tests pass.
- **User decision (2026-07-15): RATIFIED** ("沒關係, codex 有自己跑也沒關係").
  H-021/E-053/E-054 stand as legitimate registered work; the freeze on
  F-XVENUE-FUNDING-SPREAD is lifted. The user additionally established a
  process precedent: Codex MAY self-initiate research runs, provided every
  standing harness rule (pre-registration, honest n_trials/K, ledger sync,
  no gate/trading-core changes without approval) continues to hold — scope
  prompts bound the *minimum* deliverable, not the maximum initiative.
  Stage-3 for H-021 still requires its own Stage-1 sign-off per the pipeline.

## Checks run (fresh)

Shadow suite 13 + goldens 6 + registry/probe tests 6 all pass; mutation check
on the fixture test; ledger consistency 22/55/21 PASS; doc metadata PASS.
