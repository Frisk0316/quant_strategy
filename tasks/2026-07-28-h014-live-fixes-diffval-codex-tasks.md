---
status: current
type: task
owner: claude
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# H-014 live-layer fix wave + differential-validation declaration — Codex tasks

Sources: `tasks/2026-07-28-h014-live-execution-claude-review.md` (findings being
fixed — read first), `docs/ADR/0017-h014-live-execution-layer.md`,
`docs/ai_collaboration.md` deployment-gate table "Differential validation" row.

**Authorization:** user directed both items 2026-07-28 ("兩項一起排"), within
the accepted ADR-0017 scope. Same narrow opening as the original task: only
the files listed under PERMITTED may change.

**Hard rules (unchanged):** `h014_live.enabled` stays false-default and
fail-closed; no activation, scheduler, settings/mode change, credential, or
readiness claim; `src/okx_quant/execution/deribit_shadow/` stays untouched;
strategy logic frozen; tests mock all HTTP.

## F1 — Fix the three pre-activation blockers (review Important #1-#3)

1. **Fill-during-reprice reconciliation.** Add `get_order_state(order_id)` to
   `DeribitPrivateClient` (`/private/get_order_state`). In
   `adapter._execute_leg`, when `cancel` fails, query order state and
   reconcile `filled_amount` before classifying: fully/partially filled →
   record the fill (journal `fill` event with reconciled amount), continue;
   genuinely unknown → journal `adapter_failure` as today.
2. **Orphan-order recovery on transport failure.** If `buy`/`sell` raises a
   transport error (timeout/connection) AFTER the request may have reached the
   venue, attempt a scoped cancel before re-raising: prefer label-scoped
   (Deribit `/private/cancel_by_label` with the `h014:` label already
   attached) else `cancel_all_by_currency` for that currency; journal a
   `cancel_sweep` event either way. The sweep itself failing must not mask the
   original error.
3. **Reprice loop resting time.** Every placed order must rest for
   `reprice_interval_seconds` before being cancelled — including the final
   attempt (sleep before cancel on every attempt, or do not place an order
   that will be immediately cancelled). Update
   `test_bounded_reprices...` accordingly: with `max_reprices=1`, the last
   order either rests or is never placed-and-instantly-cancelled.

Acceptance (binary):
- [ ] Unit test: order fills during reprice sleep → cancel error → state
      queried → `fill` journaled with reconciled amount, no `adapter_failure`,
      sibling legs proceed.
- [ ] Unit test: transport error after send → scoped cancel attempted →
      `cancel_sweep` journaled → original error re-raised.
- [ ] Unit test: no order is ever cancelled with zero configured resting time.
- [ ] All pre-existing 23 tests still pass (amended only where behavior
      legitimately changed; list any amended test with one-line justification).

## F2 — Selected minors from the review (same files, same wave)

1. Replace the annotations-only taker test with a request-params invariant
   test: for `buy` and `sell` × `reduce_only` in {absent, False, True}, assert
   the outgoing params always contain `type=limit` and
   `post_only == (not reduce_only)`.
2. Move OAuth `client_secret` out of the URL query string (POST body or HTTP
   basic auth — Deribit supports both).
3. Reduce-only stop signaling: dedicated exception class instead of string
   prefix matching in `execute_intent`.
4. Anchor adapter/panic default paths (`results/live_h014/…`,
   `config/risk.yaml`) to the repo root (pattern already in
   `scripts/h014_live_panic.py::ROOT`), not CWD.
5. New test: a fresh adapter constructed with a pre-existing
   `reduce_only.flag` rejects a clean-snapshot entry intent.

Deferred (do NOT do now, note in report): exporting shadow's private helpers
officially; `_default_notify` async tightening — both are activation-wave
items.

Acceptance (binary):
- [ ] Each of 1-5 implemented with its test; no behavior change beyond the
      review's fix direction.

## F3 — Differential-validation declaration for H-014 (honest-blocked entry)

Add an ADDITIVE entry to
`backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS`
keyed `h014_vol_regime_options` (match the dict's existing shape exactly):
- `strategy_class`: options / vol-regime (follow existing naming style),
- `portable_validation_required: True`, `minimum_reference_engines: 1`,
- `engines`: declare the candidate engines honestly as NOT implemented —
  no external reference engine (vectorbt/backtrader/nautilus) can replay
  coin-denominated Deribit options today. Use the contract's existing
  vocabulary for an unimplemented adapter (e.g. `status: "adapter_required"`)
  so `portable_validation_gate.passed` evaluates `false` with
  `adapter_required_engines`/`blocked_reason` populated, per the
  ai_collaboration row: "若完整 reference adapter 尚未實作，
  `portable_validation_gate.passed` 必須為 `false`" — declaring the gap
  explicitly is the deliverable; do NOT fabricate a passing path.
- `limitation`: state that ADR-0011's shadow-vs-research bias report is the
  designated portability evidence for this options strategy, and whether it
  can satisfy this gate row is an activation-review decision for Claude + the
  user (record the open question, do not decide it).

NO other change to differential_validation.py — the dict entry only. If the
consistency test `test_reference_validation_contract_covers_all_declared_strategies`
or any schema test requires the new entry to be registered elsewhere, make the
minimal additive registration and name it in the report.

Acceptance (binary):
- [ ] New contract entry present; `python -m pytest
      tests/unit/test_differential_validation.py -v` all pass (including any
      new/updated consistency assertions).
- [ ] A focused new test asserts the H-014 entry yields
      `portable_validation_gate.passed == false` with a populated
      blocked/adapter-required marker (honest-blocked, not silent-absent).
- [ ] `git diff` for differential_validation.py shows the dict addition only.

## PERMITTED FILES (only these)

- `src/okx_quant/execution/deribit_live/` (existing package files)
- `tests/unit/test_deribit_private_client.py`,
  `tests/unit/test_h014_live_adapter.py`
- `backtesting/differential_validation.py` (F3 dict entry ONLY),
  `tests/unit/test_differential_validation.py` (additive tests)
- `scripts/h014_live_panic.py` (path anchoring only)
- `docs/change_manifests/2026-07-28-h014-live-execution.md` (append fix-wave
  section), `docs/RUNBOOK.md` (only if panic usage text changes),
  `docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`

## FORBIDDEN

- `src/okx_quant/execution/deribit_shadow/`, all other existing execution files
- `src/okx_quant/{strategies,signals,risk,portfolio}/`, `config/risk.yaml`,
  `config/settings.yaml`, `config/h014_shadow.yaml`
- Any differential_validation.py change outside the F3 dict entry
- Scheduler registration; `results/**`

SCOPE LIMIT: fix exactly the listed findings; no adjacent refactoring; any
deviation returns as a question, not a silent design change.

REQUIRED ON COMPLETION: standard AGENTS.md report; run
`python -m pytest tests/unit/test_deribit_private_client.py
tests/unit/test_h014_live_adapter.py tests/unit/test_differential_validation.py -v`
plus `python scripts/docs/check_doc_impact.py`, paste output tails.
Deployment readiness line: "not deployable; activation gated per
ADR-0017/R7.2".
