---
status: current
type: handoff
owner: codex
created: 2026-07-26
last_reviewed: 2026-07-26
expires: none
superseded_by: null
---

# Session Handoff: H-022/E-059 taker-flow Stage 2 — 2026-07-26

## Implementation summary

Formally verified the human ETHUSDT repair, confirmed the retained non-ETH
snapshot hash, and completed the ordered E-059 delivery. Registration
`592b757` precedes execution `049d136`; the only probe behavior change consumes
the accepted Binance universe alias after PIT top-30 selection without refill.
E-059 passes data, distinctness, and cost but fails statistical power, so H-022
is shelved with no retune or Stage 3.

## Diff scope

- Files added: the E-059 `stage2_feasibility.json` artifact and this paired
  context/session handoff.
- Files changed: `backtesting/taker_flow_probe.py`,
  `tests/unit/test_taker_flow_probe.py`, H-022/E-059 ledgers, alias manifest,
  Feature/Data/Known Issues, current state/handoff, and F-TAKER workstream
  metadata.
- Files deleted: none.

## Business-rule change?

- The rule was already accepted as R6.7/I50 in T2. T3 activates its first
  opted-in consumer; Change Manifest
  `docs/change_manifests/2026-07-24-consumer-time-universe-aliases.md` is
  updated. DOC_IMPACT_MATRIX strict check passes.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A; Claude-owned research was not
  modified.
- `config/`: only `config/workstreams.yaml` progress metadata changed; no
  runtime, risk, strategy, or deployment configuration changed.
- ADR: ADR-0015 remains accepted and unchanged.

## Experiments

- HYPOTHESIS_LEDGER entries: H-022 → `shelved`, trials 0.
- EXPERIMENT_REGISTRY entries: E-059 final result; F-TAKER-FLOW K remains 0/2.

## Tests / checks run

- Targeted alias/probe/registry tests — 29 passed.
- Full unit suite — 956 passed, 1 skipped, 1,273 existing numerical warnings.
- Repository-wide Ruff — passed.
- Docs metadata, feature-map links, ledger consistency, and
  `check_doc_impact.py --strict` — passed.
- Config validation and backtest smoke — passed; smoke is idealized-fill and
  not promotion evidence.

## Docs updated

- `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/KNOWN_ISSUES.md`,
  `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, the alias Change Manifest,
  `config/workstreams.yaml`, and the paired handoffs.

## Known limitations / risks

- The execution harness accidentally launched two identical read-only
  invocations. The detached one wrote the artifact; the second stopped at the
  immutable no-overwrite guard. No second artifact or byte change exists.
- H-002 correlation is advisory and is not an exact E-005 reproduction.
- H-022 remains research-only and shelved; no promotion evidence exists.

## Rollback plan

- Revert the outcome-sync commit, then `049d136`, then `592b757`. This removes
  only E-059 docs/code/test/artifact changes. Do not remove the user-completed
  ETH raw repair or rewrite the immutable membership/E-058 artifacts.

## Context Handoff

- See `tasks/2026-07-26-e059-taker-flow-context-handoff.md`.

## Questions for human review

- Claude: confirm the power-fail shelf, E-058 versus E-059 metric deltas,
  registration ordering, and no-refill alias semantics.
- Claude: assess the non-gating H-002 advisory correlation; it cannot reopen
  E-059 or authorize retuning.

## Next recommended task

- Claude review only. No H-022 reprobe, Stage 3, promotion, or deployment task
  is authorized.

## Human Learning Notes (required)

For long DB probes, use the tool's yielded execution cell. Detached host
processes can outlive the shell even when their PID is not visible; the
immutable artifact guard prevented overwrite here, but explicit single-process
monitoring is the safer operational pattern.
