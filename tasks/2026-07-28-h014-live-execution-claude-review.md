---
status: current
type: review
owner: claude
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# Claude review: H-014 live-execution layer (ADR-0017 Codex delivery)

Scope: staged 13-file delivery per `tasks/2026-07-28-h014-live-execution-codex-tasks.md`.
Method: independent code review (full staged diff + named source checks) plus a
fresh-context verifier that ran all commands. Reports summarized here.

## Verdict: APPROVE-WITH-FINDINGS

Money-path safety spine confirmed in actual code paths, not just tests:
- `enabled=false` structurally cannot construct the private client or emit a
  request; missing credentials fail at startup with a clear error.
- Entries are structurally post-only (`type=limit`, `post_only=not reduce_only`
  hardcoded); a plain taker order is unrepresentable in the client API.
- Live intents delegate to the frozen shadow builder (parity by single code
  path) with R8.3/unit-cap checks reused, not reimplemented; golden byte-match
  test guards future forking.
- Zero withdrawal/transfer surface (grep-clean). Testnet default committed in
  `config/risk.yaml` (`env: test`, `enabled: false`).
- Write-ahead append-only journal with the shadow lock pattern; persistent
  reduce-only flag survives restarts; panic dry-run verified side-effect-free.

Verifier facts: 23/23 new tests pass; full unit regression 955 passed /
1 skipped (pre-existing `test_backtest_visual_fallbacks` failure excluded as
known-unrelated); `validate_pipeline.py --check-config-only` PASS;
`config/risk.yaml` additions-only; no forbidden path touched; tests wrote no
`results/**` artifacts.

## Pre-activation blockers (Important — fix + re-review before activation)

1. **Fill-during-reprice divergence** (`adapter.py` `_execute_leg`): an order
   that fully fills during the reprice sleep makes the subsequent `cancel`
   error out → leg journaled `adapter_failure`, fill never recorded, venue
   position diverges from journal. Fix: add `get_order_state` to the client
   and reconcile `filled_amount` on cancel failure.
2. **Orphan order on transport failure**: HTTP timeout after Deribit accepts
   an order leaves a resting order with no captured order_id and no cancel;
   only panic recovers it. Fix: on transport error after send, label-scoped or
   currency-scoped cancel before re-raising.
3. **Final reprice attempt has zero resting time** (sleep gated by
   `attempt < max_reprices` before cancel): last order is placed and
   immediately cancelled — pure venue churn. Fix: sleep before cancel on every
   attempt or skip the final placement.

## Deferred minors (fold into pre-activation fix wave)

- Taker-unrepresentability test asserts annotations only — replace with a
  request-params invariant test over all flag combinations.
- OAuth secret in URL query params — move to POST body/basic auth before real
  keys exist.
- Live adapter imports underscore-private shadow internals
  (`_journal_cycle_lock`, `_open_units`) — export officially at activation.
- Reduce-only stop detected via string prefix match — use an exception class.
- Panic script/adapter paths are CWD-relative — anchor to repo root.
- `_default_notify` blocking `asyncio.run` per event; alerts silently skipped
  inside a running loop — tighten before activation.
- Missing test: fresh adapter with pre-existing `reduce_only.flag` rejects a
  clean-snapshot entry.

## Governance gap closed in this review

Delivery omitted `docs/DOMAIN_RULES.md`/`docs/INVARIANTS.md` registration
(`check_doc_impact.py --strict` would block; the task file's permitted list
omitted them — Claude authoring gap, not Codex scope violation). Closed by
adding R8.8/R8.9 and I56 alongside this review.

## Activation checklist addition

The three blockers above join the ADR-0017 activation review as mandatory
items, before any `enabled: true` discussion.

## Fix-wave outcome (2026-07-28, second review round)

Codex fix wave re-reviewed (scoped, most-capable model) + independently
verified: **clean — all 10 findings ADDRESSED** (F1.1-F1.3 blockers,
F2.1-F2.5 minors, F3 honest-blocked diff-validation entry), no new breakage.
Verifier: 100/100 focused tests, 969-passed full regression, diff confined to
the 12 permitted files, `client_secret` moved to POST body, paths repo-root
anchored, panic dry-run side-effect-free. Doc-impact strict closed by
registering F59 (order-lifecycle/journal divergence races) and reviewing
R8.8/R8.9/I56 against the post-fix behavior (no change needed) plus a
FEATURE_MAP note for the `h014_vol_regime_options` honest-blocked contract.

Remaining activation-wave items (from re-review minors, none blocking while
disabled): widen orphan sweep to ambiguous HTTPStatusError; journal the
original cancel-error text in sweep-resolved recoveries; anchor
`from_env`'s `.env` default; export shadow's private helpers officially;
tighten `_default_notify` async behavior; restate sequential-leg-execution
assumption as an invariant if concurrency is ever introduced. The
"shadow-bias-report satisfies the diff-validation gate row?" question stays
open for the activation review.
