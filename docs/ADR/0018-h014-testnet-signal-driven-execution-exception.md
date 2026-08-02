---
status: accepted
type: adr
owner: claude
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# ADR-0018: H-014 Testnet Signal-Driven Execution Exception

## Status

Accepted — 2026-07-30, explicit user acceptance in-session ("接受") after
review of the draft. Drafted at user request in-session ("啟動 H-014 在
Deribit testnet 跑實際訊號"), mirroring the ADR-0017 acceptance pattern
(drafted by Claude, accepted in-session by the user, then implemented by
Codex). T1 of
`tasks/2026-07-30-paper-trade-testnet-connectivity-codex-tasks.md` may now
proceed, subject to its own Phase 1 → Phase 2 review checkpoint.

## Context

ADR-0017 built (but did not activate) `execution/deribit_live/`: a private
client + adapter that consumes byte-identical ADR-0011 shadow intents and can
place real orders, fail-closed behind `h014_live.enabled: false`. ADR-0017
explicitly scoped testnet to **plumbing verification only** ("auth, order
lifecycle... never as fill-realism evidence"), and `docs/RUNBOOK.md:993-997`
implements exactly that narrower check: authenticated read-only calls (auth,
account-summary, position query) with no order placed and `enabled` left
false.

`docs/DOMAIN_RULES.md` **R8.9** fixes the activation order: ADR-0011 shadow
exit (≥8 valid weeks + bias report) → bias-report review → every R7.2 gate →
explicit user capital approval with a stated cap. As of 2026-07-30 the shadow
clock restarted 2026-07-29 (`docs/AI_HANDOFF.md` item 17) after a scheduling
bug fix — it is far from the 8-week exit condition. **R7.2** requires every
deployment-table gate to pass AND explicit human approval; it does not permit
substituting approval for an unmet gate on real/live capital.

The user now explicitly asked to go beyond plumbing verification: run the
live-execution adapter's real signal-driven order loop against Deribit
**testnet** (`test.deribit.com`), ahead of the R8.9 sequence, understanding
that this pre-empts the shadow-exit gate. This ADR is the mechanism AGENTS.md
requires for that kind of policy deviation ("every major rule/policy change
adds an ADR").

## Decision

A narrow, testnet-only exception to R8.9's activation order:

1. **Scope lock:** this exception applies only while
   `h014_live.env == "test"`. The adapter must hard-assert `env == "test"`
   before honoring this exception's enable path; any config attempt to set
   `env: live` while unaccompanied by full R8.9 completion must fail closed
   at process start, not just default to testnet.
2. **What this grants:** permission to set `h014_live.enabled: true` and run
   the signal-driven adapter loop (previously blocked entirely by R8.9) while
   `env: test`. Nothing else changes: R8.8 byte-parity with shadow intents,
   R8.3 naked-put rejection and the 1.0-unit cap, post-only-maker/reduce-only-
   taker execution rule, the three kill switches, and persistent reduce-only
   risk state all remain fully enforced exactly as ADR-0017 specified.
3. **What this does NOT grant:** it does not satisfy R7.2 or the ADR-0011
   shadow-exit condition. Testnet fills/journal records produced under this
   exception are **non-evidentiary** — they must not be cited in
   `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, or any bias
   report as shadow or live evidence, and must not advance the 8-week clock.
   ADR-0017's own caveat stands: testnet liquidity differs materially from
   live, so fills here prove connectivity/operational readiness, not edge.
4. **Real capital is untouched:** `env: live` / `live_small` activation still
   requires the complete, unmoved R8.9 sequence — ADR-0011 shadow exit,
   bias-report review, every R7.2 gate, and a separate explicit user capital
   approval with a stated cap. This ADR grants zero progress toward that.
5. **Sunset:** this exception is retired automatically once the real
   ADR-0011 shadow gate exits and activation review begins — at that point
   normal R8.9 sequencing resumes and supersedes it. No separate action is
   needed to turn it off going forward; turning `env` to `live` always needs
   fresh R8.9 approval regardless of this ADR.
6. **Observability unchanged** from ADR-0017: append-only journal, alert on
   order placement/rejection/risk-stop/task failure.
7. **Binance and OKX are out of scope for this ADR.** No strategy is
   validated on either venue, so no signal-driven order loop is authorized
   there under any exception. Work on those venues in this round is
   connectivity-only (authenticate, place+cancel a test order, read
   account/position) and must never be wired to a strategy signal.

## Gates this ADR does NOT move

- R7.2 and the full `docs/ai_collaboration.md` deployment table for real
  capital — unchanged.
- ADR-0011's ≥8-week shadow exit and bias-report requirement — unchanged;
  testnet order flow under this ADR does not count toward it.
- H-014's differential-validation portable gate — must still pass before
  `live_small`, unaffected by this ADR.
- OKX demo-key blocker (`60005 Invalid apiKey`) — unrelated, still requires
  the user to create a valid OKX Demo Trading API key.

## Consequences

- A real (testnet) order-placing loop runs in production code earlier than
  R8.9 would otherwise allow. Mitigated by: hard `env=="test"` assertion,
  every ADR-0017 control unchanged, and explicit non-evidentiary labeling so
  the testnet run cannot be mistaken for shadow/live proof later.
- If the testnet run surfaces adapter bugs (repricing, cancel races, journal
  correctness), those fixes benefit the eventual real activation review at
  no cost to the frozen strategy logic.

## Alternatives considered

- Status quo, plumbing-only per ADR-0017 (rejected by user 2026-07-30 — they
  want the signal-driven loop actually running, not just an auth check).
- Wait for the real ADR-0011 shadow exit before any order-capable run
  (rejected by user — that is the serial delay this exception buys back for
  zero-capital-risk operational proof).
- Extending this exception to `live_small` real capital (out of scope /
  rejected — R8.9's real-capital sequence is explicitly untouched).

## Implementation ownership

Codex implements the `env=="test"` hard-lock and the enable path per the
Change Manifest accompanying this ADR; Claude reviews before the final
`h014_live.enabled: true` commit. Frozen strategy parameters and R8
accounting rules are consumed, not modified.
