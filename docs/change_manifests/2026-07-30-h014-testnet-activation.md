---
status: current
type: manifest
owner: codex
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Change Manifest: Paper-trade testnet connectivity Phase 1

## Summary

Implement the pre-activation safety and manual connectivity surfaces for
Deribit, Binance, and OKX paper environments. H-014 remains disabled because
the authenticated Phase 1 evidence and Claude's explicit Phase 2 go are absent.

## Business rule(s) affected

- R8.9 / ADR-0018: an H-014 private client and any enabled exception path are
  hard-locked to Deribit testnet.
- R8.8 is unchanged; no signal intent, sizing, fill, or accounting rule changed.
- Binance and OKX additions are connectivity-only and introduce no strategy
  business rule.

## Trigger area(s) (DOC_IMPACT_MATRIX)

- A2 portfolio/execution.

## Files changed

- `src/okx_quant/execution/deribit_live/private_client.py` — remove the live
  host path while ADR-0018's exception is in effect.
- `src/okx_quant/execution/deribit_live/adapter.py` — reject an enabled
  non-test configuration before client construction.
- `tests/unit/test_deribit_private_client.py`,
  `tests/unit/test_h014_live_adapter.py` — verify the lock and one mocked
  auth/place/check/cancel lifecycle.
- `src/okx_quant/execution/binance_testnet/` — fixed-host signed Spot and USD-M
  test clients.
- `scripts/run_binance_testnet_smoke.py` — manual bounded connectivity smoke;
  futures orders can only reduce a pre-existing one-way position.
- `tests/unit/test_binance_testnet_client.py` — signing, credential,
  place/cancel, and exposure-safety checks.
- `scripts/run_okx_demo_smoke.py` — manual shared-credential demo balance and
  place/cancel smoke through `OKXBroker(demo=True)`.
- `.env.example` — blank testnet-only credential names, no secrets.
- `docs/FEATURE_MAP.md` and session state/handoff documents — ownership,
  current gate, verification, and rollback context.

## Behavior delta

- Before: the Deribit private client could be constructed with `env="live"`;
  Binance had no authenticated test client; OKX had only the long-running demo
  engine entrypoint.
- After: Deribit private construction is test-only and the committed H-014
  enable flag remains false; Binance and OKX have manual, unscheduled,
  non-strategy smoke entrypoints that fail closed without credentials.
- Money/risk impact: no real-capital path, strategy, sizing, PnL, fee, funding,
  risk limit, deployment gate, or committed enable flag changed.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — research is frozen and out of scope.
- `config/`: no runtime/risk setting changed; only the hand-maintained
  workstream status is synchronized.
- ADR: ADR-0018 was already accepted and R8.9 already recorded its narrow
  testnet exception; this implementation does not broaden it.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` R8.8/R8.9 — reviewed; the existing ADR-0018
  exception is sufficient and unchanged by this implementation.
- [x] `docs/INVARIANTS.md` I56 — reviewed; its fail-closed contract is
  strengthened by the targeted tests, with no text change required.
- [x] `docs/FAILURE_MODES.md` F59 — reviewed; ambiguous-order cleanup is covered
  by deterministic client order IDs and cancellation attempts, with no new bug
  class added.
- [x] `docs/FEATURE_MAP.md` — updated for the Deribit hard lock and Binance
  connectivity ownership.

## Invariants / golden cases

- Invariants checked: I56.
- Golden cases affected: none.

## Tests / checks run

- `pytest tests/unit/test_deribit_private_client.py tests/unit/test_h014_live_adapter.py -q`
  — 38 passed.
- `pytest tests/unit/test_binance_testnet_client.py -q` — 11 passed; combined
  targeted run — 49 passed.
- Targeted Ruff check — passed; new Binance/OKX files pass Ruff format check.
- OKX fail-closed invocation — blocked before network; H-014 panic dry-run —
  passed with no network or state write.
- Config, docs metadata/links/ledger, and doc-impact strict checks — passed
  (metadata retained two unrelated pre-existing warnings).

## Risks and rollback

- Risks: real authenticated venue behavior remains unverified until the user
  supplies paper-environment keys. Testnet liquidity is non-evidentiary.
- Rollback: revert only the files listed above; no DB, result artifact,
  scheduler, strategy, signal, risk, or portfolio state needs restoration.

## Approval

- Human approval required: ADR-0018 acceptance is recorded. Phase 2 still
  requires Claude review of real Phase 1 evidence and an explicit go; neither
  condition is satisfied in this session.
