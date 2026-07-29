---
status: current
type: task
owner: claude
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# H-014 testnet plumbing verification — checklist (waits on user testnet key)

Purpose: verify the ADR-0017 live layer's auth/order/cancel/panic plumbing
against test.deribit.com with a REAL (testnet) counterparty. Per ADR-0017
"Alternatives", testnet verifies plumbing ONLY — it is never fill-realism or
readiness evidence (R7.2 untouched). `h014_live.enabled` stays `false` in
config; the verification run enables it via an explicit local override that
is never committed.

## Prerequisites (user)

- [ ] test.deribit.com account created; API key with `trade` scope, NO
      withdrawal scope. Put `DERIBIT_API_KEY` / `DERIBIT_API_SECRET` in `.env`
      (never committed — pre-existing secrets check applies).
- [ ] Confirm `config/risk.yaml` still has `h014_live.env: test`.

## Verification steps (Claude/Codex session, ~30 min, testnet only)

1. **Auth round-trip:** construct `DeribitPrivateClient` from env; call
   `get_account_summary` for BTC. Expect: token obtained via POST body auth,
   summary returns. Then force a 401 (corrupt token in-memory) and confirm
   single refresh + retry works.
2. **Post-only order lifecycle:** place a far-from-market post-only limit BUY
   on a liquid BTC option (e.g. bid far below best bid so it rests), confirm
   `order_id` returned and order visible via `get_order_state`; cancel it;
   confirm state `cancelled`. Journal events appear in
   `results/live_h014/orders.jsonl` (this IS a real artifact write —
   acceptable: testnet events are journaled like any events; note run date).
3. **Post-only crossing rejection:** place a post-only limit that would cross
   the spread; expect venue rejection (order_state rejected / error), adapter
   journals the rejection, no position.
4. **Label sweep:** place two far resting orders with the `h014:` label, run
   `cancel_by_label`, confirm both gone.
5. **Panic script (real mode, testnet):** with one resting order open, run
   `python scripts/h014_live_panic.py` (no --dry-run). Expect: cancel-all both
   currencies succeeds, `reduce_only.flag` written. Then confirm a fresh
   adapter refuses a clean entry (ReduceOnlyError). Remove the flag afterward
   and record that removal in the run notes.
6. **Fail-closed re-check:** unset the env credentials, restart, confirm
   enabled+missing-credentials raises the startup error; restore.

## Recording

- Append results (date, each step PASS/FAIL, order ids) to this file under a
  "Run log" section; update `docs/AI_HANDOFF.md` one line. Any FAIL → new
  finding in `tasks/2026-07-28-h014-live-execution-claude-review.md` scope,
  fix wave before activation review.
- This checklist satisfies only the "plumbing verification" clause of
  ADR-0017's demo row. Fill realism remains ADR-0011 shadow evidence.
