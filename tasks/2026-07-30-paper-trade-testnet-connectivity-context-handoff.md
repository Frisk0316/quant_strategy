---
status: current
type: handoff
owner: codex
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Context Handoff: Paper-trade testnet connectivity — 2026-07-30

## Goal (one sentence)

Provide fail-closed manual connectivity for Deribit, Binance, and OKX paper
environments without crossing the H-014 Phase 2 gate or wiring a strategy to
Binance/OKX.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good commit / state: `3648702`; this task is an uncommitted,
  verified working-tree change layered over unrelated pre-existing edits.
- In-progress edits (files): the Deribit live client/adapter and tests; new
  Binance testnet package, smoke, and tests; new OKX demo smoke; `.env.example`;
  Feature Map, manifest, current/AI handoffs, workstream status, and this
  handoff pair.
- What works right now: all mocked order/signing/safety tests pass; missing
  credentials block before HTTP construction; H-014 panic dry-run remains
  no-network; config and documentation checks pass.
- What does not work / unfinished: no real authenticated venue smoke has run.
  H-014 remains disabled and Phase 2 is not authorized. OKX issue `60005`
  remains open.

## Decisions made (and why)

- Keep `h014_live.enabled: false` and do not add `run_h014_live.py` — real
  Phase 1 output and Claude's explicit go are both absent.
- Make `DeribitPrivateClient` test-only while ADR-0018 is active — one shared
  guard eliminates every accidental live-host caller.
- Use `https://demo-fapi.binance.com` for USD-M — it is Binance's current
  official test environment; the task's `testnet.binancefuture.com` host is
  stale.
- Use separate Spot and Futures Binance variables — the test environments
  issue distinct credentials and either venue can report independently.
- Never seed a futures position — the smoke blocks unless an existing
  non-zero one-way `BOTH` position can be reduced.
- Reuse the existing three OKX variables — `OKXBroker` has no demo-specific
  aliases and `demo=True` supplies the simulated-trading flag.

## Open questions / unverified assumptions

- Whether Claude accepts the current official Binance USD-M host deviation
  from the stale task text.
- Whether a follow-up should add these manual commands to `docs/RUNBOOK.md`
  and add ADR-0018 to `docs/ADR/README.md`; both were outside the task's
  permitted file list.
- Real credentials, venue permissions, account modes, and exchange responses
  remain unverified.

## Rules in play (preserve verbatim)

- Invariants touched: I56 — H-014 fails closed while disabled/uncredentialed;
  live intents must match frozen shadow intents; order/risk events remain
  journaled and risk-stop state persistent.
- Domain rules touched: R8.8 and R8.9, including the accepted ADR-0018
  testnet-only exception.
- Do-not-touch: `research/`, Deribit shadow intent code, strategy/signal/risk/
  portfolio code, existing result artifacts, schedulers, `config/risk.yaml`,
  and every live/mainnet host.

## Context to load next (the reading list)

- Source of truth: `research/strategy_synthesis.md`,
  `docs/ADR/0017-h014-live-execution-layer.md`,
  `docs/ADR/0018-h014-testnet-signal-driven-execution-exception.md`,
  `docs/DOMAIN_RULES.md` R8.8/R8.9, and `config/risk.yaml`.
- Owning files / MODULE_BRIEFS: `docs/FEATURE_MAP.md`,
  `src/okx_quant/execution/deribit_live/`,
  `src/okx_quant/execution/binance_testnet/`, and the three smoke scripts.
- Context Pack: none; `docs/CONTEXT_PACKS/README.md` has no deployment pack,
  so use the ADR/RUNBOOK/Feature Map reading list above.

## Checks run

- Targeted Deribit + Binance pytest — 49 passed.
- Targeted Ruff check — passed; new Binance/OKX files pass Ruff format check.
- `scripts/validate_pipeline.py --check-config-only` — passed.
- Doc metadata, Feature Map links, ledger consistency, and doc impact
  (`--strict`) — passed; metadata retained two unrelated pre-existing warnings.
- Deribit credential preflight — blocked before network.
- Binance CLI credential preflight — both venues reported
  `blocked-pending-user-key`.
- OKX CLI credential preflight — reported `blocked-pending-user-key`.
- `scripts/h014_live_panic.py --dry-run` — passed with `dry_run: true` and
  `reduce_only: false`.

## Approvals

- ADR-0018 frontmatter says `status: accepted`.
- Claude Phase 1 to Phase 2 approval: not found / not obtained. Phase 2 is
  therefore a hard no-go.

## Next action (single, concrete)

- After the user supplies trade-scoped Deribit testnet credentials, run the
  existing RUNBOOK read-only auth/account-summary/option-position plumbing
  check and give its redacted output to Claude for Phase 1 review.

## Human Learning Notes

Binance's current USD-M test host differs from the hostname frozen in the task,
and a normal flat futures account cannot safely prove a real reduce-only order.
The smoke therefore reports Spot and Futures independently and never creates a
futures position merely to test connectivity. A client order ID must be chosen
before POST so a lost response can still trigger a bounded cancellation attempt.
