---
status: accepted
type: adr
owner: claude
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# ADR-0017: H-014 Live-Execution Layer (parallel-track)

## Status

Accepted — 2026-07-28, explicit user acceptance in-session ("接受") after
review of the draft. Drafting had been user-authorized the same day in
parallel with the ADR-0011 shadow accumulation ("同時開始寫 live-execution
ADR"), compressing the serial wait without weakening any gate. **This ADR
being accepted does NOT enable live trading.** Activation stays behind, in
order: (1) ADR-0011 exit criteria (≥8 valid shadow weeks + bias report),
(2) Claude + human review of that bias report, (3) every deployment gate in
`docs/ai_collaboration.md` (R7.2), (4) a separate explicit user approval to
switch on, with a stated capital cap.

## Context

H-014 (RICH-regime covered call + put spread, coin-denominated, frozen
`ivp_min=85` / `z_min=0.5`) is `supported` on E-051/E-052 double-passed
evidence. ADR-0011's shadow layer journals hypothetical fills against the
live Deribit book with zero order capability. Its exit unlocks the
live-execution discussion; this document IS that discussion, started early by
user authorization so implementation review does not serialize behind the
8-week clock. The platform currently has no Deribit private-endpoint surface
of any kind.

## Decision (v1 scope)

1. **Venue + instrument scope:** Deribit only; BTC and ETH options already
   traded by the shadow layer (nearest-30d expiry, ~25Δ call, 25Δ/10Δ put
   spread). No perps, no other venues, no spot.
2. **Credentials:** Deribit API key with `trade` scope, stored ONLY in `.env`
   (`DERIBIT_API_KEY` / `DERIBIT_API_SECRET`), never committed (existing
   secrets check). Key created by the user; read-only + trade scopes, no
   withdrawal scope, IP-bound if the user's network allows.
3. **Order path:** a new `DeribitPrivateClient` (auth, place, cancel, cancel-
   all, positions, account summary) plus a thin execution adapter that
   consumes the SAME intent records the shadow layer emits. One code path
   generates intents (frozen ADR-0011 logic, incl. R8.3 naked-put rejection
   and 1.0 unit/symbol cap); live mode only changes what happens to an
   accepted intent: post as **maker (post-only) limit at our side of the
   book**, reprice at a bounded cadence, taker allowed ONLY for risk-reducing
   exits (matches the ai_collaboration execution rule).
4. **Risk enforcement (config-gated, wired to `config/risk.yaml` by Codex at
   implementation time):** max option notional per symbol and aggregate, max
   coin-denominated drawdown stop that flattens to reduce-only, daily
   loss stop, and a hard instrument allowlist (BTC/ETH options only).
5. **Kill switches (all three):** (a) config flag `h014_live.enabled=false`
   fails closed at process start; (b) removing the scheduled task stops the
   loop; (c) a `cancel-all + reduce-only` panic command documented in
   RUNBOOK, runnable without reading code.
6. **Mode staging:** `shadow` (today) → `live_small` (user-approved capital
   cap, e.g. one 1/30 tranche unit) → scale only per the ai_collaboration
   escalation row. `config/settings.yaml` must show the mode explicitly; mode
   changes are user-approval events (deployment checklist row "Mode").
7. **Observability:** every order/fill/reject appended to the same journal
   family as shadow (append-only JSONL, then DB schema per ADR-0011's
   graduation note); Telegram (or equivalent) alert on order placement,
   rejection, risk-stop trigger, and task failure — reusing the toast/alert
   pattern added to the shadow task on 2026-07-28.
8. **Rollback:** documented single step back to shadow mode (flip
   `h014_live.enabled` + cancel-all); the shadow journal keeps running in
   live mode so the bias measurement never stops.
9. **Parity requirement:** live intents must byte-match shadow intents on the
   same inputs (golden test) — the live layer may not fork strategy logic.

## Gates this ADR does NOT move

- ADR-0011 exit (≥8 valid weeks + bias report) — unchanged, still stalled
  pending the machine-availability fix (see KNOWN_ISSUES 2026-07-28 entry).
- R7.2 and the full `docs/ai_collaboration.md` deployment table — unchanged.
- Differential-validation portable gate for H-014 — must pass before
  `live_small`; verified at activation review, not by this ADR.
- OKX demo-key blocker is unrelated to this Deribit path and stays tracked
  separately.

## Consequences

- Codex can implement and unit-test the private client, risk wiring, and
  execution adapter against Deribit test fixtures during the shadow window;
  the activation review then has running, reviewed code instead of a design
  sketch.
- New attack/loss surface (private key, real orders) appears in the codebase
  before activation — mitigated by fail-closed `enabled=false`, no-withdrawal
  scope, and the secrets checklist.
- If the shadow bias report later shows the fill model was too optimistic,
  the execution adapter's maker-first ladder is the tunable layer; strategy
  logic stays frozen (any signal change is a new hypothesis, not a tune).

## Alternatives considered

- Wait for the 8-week clock before designing (status quo): rejected by user
  2026-07-28 — pure serial delay with no added evidence.
- Deribit testnet demo stage instead of `live_small`: kept OPTIONAL — testnet
  liquidity differs materially (same reasoning as ADR-0011); the deployment
  table's "demo" row is satisfied by testnet only for plumbing verification
  (auth, order lifecycle), never as fill-realism evidence.
- Reusing an existing exchange-client abstraction (OKX engine): rejected for
  v1 — Deribit options semantics (coin-denominated, option Greeks, expiries)
  do not fit the perp-shaped interfaces; a thin dedicated client is smaller
  than a forced abstraction.

## Implementation ownership

Codex implements after user accepts this ADR (AGENTS.md role split); Claude
reviews. Frozen strategy parameters and R8 accounting rules are consumed, not
modified. A Change Manifest accompanies implementation (execution/risk paths
are Manifest-relevant); this ADR is the major-rule-change record.
