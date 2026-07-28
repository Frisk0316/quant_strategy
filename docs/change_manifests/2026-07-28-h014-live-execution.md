---
status: current
type: manifest
owner: codex
created: 2026-07-28
last_reviewed: 2026-07-28
expires: none
superseded_by: null
---

# Change Manifest: H-014 live-execution layer (inactive)

## Summary

Implement accepted ADR-0017's reviewable, testnet-default private-client,
execution-adapter, risk-stop, journal, and panic surfaces while retaining
`h014_live.enabled: false` and making no activation change.

## Business rule(s) affected

R2.1 (maker/taker distinction), R4.2-R4.3 (reduce-only and exposure caps),
R5.1-R5.2 (post-only lifecycle and partial-fill state), R7.2 (no readiness
claim), and R8.3 (bounded H-014 option structure and 1.0-unit cap).

## Trigger area(s) (DOC_IMPACT_MATRIX)

A2 execution and A3 risk/config.

## Files changed

- `src/okx_quant/execution/deribit_live/` - new private client and thin adapter.
- `tests/unit/test_deribit_private_client.py` - mocked auth/order lifecycle.
- `tests/unit/test_h014_live_adapter.py` - parity, risk, journal, and panic tests.
- `config/risk.yaml` - additive disabled `h014_live` block only.
- `scripts/h014_live_panic.py` - cancel both currencies and persist reduce-only.
- `docs/FEATURE_MAP.md`, `docs/RUNBOOK.md`, `docs/AI_HANDOFF.md`,
  `docs/CHANGELOG_AI.md`, `config/workstreams.yaml` - ownership, operation,
  current state, history, and review status.
- `docs/change_manifests/2026-07-28-h014-live-execution.md` - this manifest.

## Behavior delta

- Before: no Deribit private endpoint or H-014 live execution code existed.
- After: an explicitly enabled adapter can consume the same shadow intents,
  validate them before private calls, place bounded post-only maker orders,
  enter persistent reduce-only on risk stops, and journal the lifecycle.
  Disabled startup constructs no private client and still appends supplied
  shadow evidence.
- Money/risk impact: none in this delivery because enabled remains false and no
  authenticated call/order ran. If separately activated, V1 notional is
  `tranche_units * signal spot` in USD, daily loss is USD, and drawdown is a
  fraction supplied by the activation runner.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A - frozen strategy assumptions are
  imported unchanged and research files are outside the permitted scope.
- `config/`: additive `h014_live` block in `config/risk.yaml`; no existing key,
  settings mode, or shadow config changed.
- ADR: accepted ADR-0017 is the implementation authority; unchanged.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/FEATURE_MAP.md` - new disabled feature ownership row.
- [x] `docs/RUNBOOK.md` - mocked/testnet plumbing, panic, rollback state, gates.
- [x] `docs/AI_HANDOFF.md`, `docs/CHANGELOG_AI.md`,
  `config/workstreams.yaml` - current review state and durable history.
- [x] `docs/DOMAIN_RULES.md` - reviewed, unchanged because ADR-0017 already
  records the new policy and the task's exhaustive permitted list excludes it.
- [x] `docs/INVARIANTS.md` - reviewed; I3/I6/I7/I15/I39 remain applicable and
  are covered by focused tests; the task does not permit editing this file.
- [x] `docs/FAILURE_MODES.md` - reviewed; no newly discovered bug class, and
  the task does not permit editing this file.
- [x] `docs/ai_collaboration.md` - reviewed; R7.2/gate policy is unchanged and
  the task does not permit editing this file.

## Invariants / golden cases

- Invariants checked: I3, I6, I7, I15, I39, and I40.
- Golden cases affected: no existing golden case changed; the new byte-parity
  and protection-first unit cases are implementation checks.

## Tests / checks run

- `python -m pytest tests/unit/test_deribit_private_client.py
  tests/unit/test_h014_live_adapter.py -v` - 23 passed.
- The same command plus `tests/unit/test_h014_shadow.py` - 37 passed.
- Targeted Ruff for new package/script/tests - passed.
- `python scripts/h014_live_panic.py --dry-run` - passed; BTC and ETH planned,
  no network or state write.
- `python scripts/validate_pipeline.py --check-config-only` - passed.
- Docs metadata/feature-map/ledger checks - passed; metadata emitted two
  pre-existing warnings for unrelated 2026-07-26/27 docs.
- `python scripts/docs/check_doc_impact.py` - exited 0 with two expected
  advisory A2/A3 notices because the task forbids editing the registry docs;
  the reviewed/unchanged disposition is recorded above. No blocking finding.
- `git diff --check`, private-client endpoint grep, additive risk-config diff,
  and the explicit permitted-file whitelist - passed (13 changed files).

## Risks and rollback

- Risks: sequential multi-leg partial fills, stale caller risk snapshots,
  operator-supplied cap units, private API drift, or accidental future enable.
  Protection-first ordering, caller-visible partial/missed journals, persistent
  reduce-only state, disabled default, and separate activation review bound
  those risks.
- Rollback: remove the new package/script/tests/manifest and documentation
  additions, then remove only the additive `h014_live` block. No DB migration,
  scheduler, existing result rewrite, or live rollback is required.

## Approval

- Human approval required: yes - obtained 2026-07-28 through explicit acceptance
  of ADR-0017 and assignment of the Codex task. This approves implementation
  only, not credentials, scheduling, config enablement, or trading.

## Human Learning Notes

- An accepted live-execution ADR authorizes reviewable code, not activation;
  disabled config, shadow evidence, promotion gates, and the later capital
  approval remain separate controls.
- The adapter delegates intent construction and bounded-structure checks to the
  shadow implementation, so parity is a code-path property rather than a second
  hand-maintained strategy definition.
- Panic state is persistent by design: cancellation handles resting orders,
  while the reduce-only flag prevents the next process from recreating risk.
