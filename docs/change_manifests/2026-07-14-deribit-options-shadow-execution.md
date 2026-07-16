---
status: current
type: manifest
owner: codex
created: 2026-07-14
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Change Manifest: Deribit options shadow execution (ADR-0011 v1)

## Summary

Add the credential-free H-014 shadow layer authorized by ADR-0011: DB-backed
research-parity signals, bounded intents, public-book hypothetical fills,
append-only JSONL accounting, and the exit-criteria bias report.

## Design-space expansion

**Problem:** measure live-book execution and mark bias without adding any order
or credential capability.

**Constraints:** frozen `ivp=85/z=0.5`, R8/I39, exact research sequence, public
endpoints only, no schema/risk/scheduler/research changes, append-only evidence.

- **A — existing engine shadow:** reuse the broker/event pipeline. Strongest
  benefit is future same-code execution; rejected because that surface includes
  credential/broker capability and exceeds ADR-0011 v1.
- **B — dedicated thin shadow path:** import the research signal/strike/accounting
  functions, allow-list four public methods, and append JSONL. Smallest blast
  radius; wrong if a future live ADR requires engine event parity immediately.
- **C — extend the research runner:** fewest new modules, but it would let the
  research implementation grade itself and mix immutable artifacts with forward
  operation.

**Axis:** executable power versus reversibility/isolation. **Decision:** B,
because zero order capability is the defining v1 safety property. **Would
change if:** a future user-approved live ADR opens the engine integration gate.

## Business rule(s) affected

R8.3 (bounded intents and 1.0-unit cap), R8.4 (sell bid/buy ask shadow fills),
R8.5–R8.6 (marks/provenance), and new R8.7 (public-only JSONL/exit boundary).

## Trigger area(s) (DOC_IMPACT_MATRIX)

A2 execution and A12 options research/shadow accounting and safety.

## Files changed

- `src/okx_quant/execution/deribit_shadow/` — signal, intent, public quote,
  shadow fill/accounting, journal, report.
- `scripts/run_h014_shadow.py` — one-cycle/manual report CLI.
- `config/h014_shadow.yaml` — approved frozen constants only.
- `tests/unit/test_h014_shadow.py` — I39/I40/F39 regression coverage.
- `tests/fixtures/h014_shadow_db_signal.json` — recorded SQL-return rows and
  immutable E-039 expectations for five BTC/ETH signal days.
- `docs/ADR/README.md`, `docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`,
  `docs/FAILURE_MODES.md`, `docs/GOLDEN_CASES.md`,
  `docs/DOC_IMPACT_MATRIX.md` — decision/rule/invariant registry sync.
- `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`,
  `docs/MODULE_BRIEFS/` — owning files, flow, operations, navigation.
- `docs/CURRENT_STATE.md`, `docs/KNOWN_ISSUES.md`, `docs/CHANGELOG_AI.md`,
  human overview/index, and task handoffs — current evidence and review entry.

## Behavior delta

- Before: no Deribit option shadow surface or in-code R8.3 intent rejection.
- After: a manual process can append what H-014 would do against public books;
  all three legs must be fillable, naked puts/over-cap intents reject, and stale
  DB dates reject before journaling. The Claude-review follow-up replaces the
  self-delegation signal test with recorded DB-shape parity and journals sparse
  chain failures as `missed_entry` or R8.3 failures as `rejected` without
  aborting the sibling currency.
- Money/risk impact: no capital or order path. Shadow PnL uses imported R8
  accounting and is evidence only.

## Source-of-truth updates

- `research/strategy_synthesis.md`: N/A — research assumptions unchanged;
  current user authorization and accepted ADR-0011 govern this shadow task.
- `config/`: new `config/h014_shadow.yaml`; no existing config or gate changed.
- ADR: ADR-0011 already accepted by the user; index synchronized.

## Docs updated (from DOC_IMPACT_MATRIX row)

- [x] `docs/DOMAIN_RULES.md` — R8 shadow scope.
- [x] `docs/INVARIANTS.md` — I39 strengthened, I40 added.
- [x] `docs/FAILURE_MODES.md` — F39 guards stale/day-boundary drift; F40 guards
  unjournaled intent-chain aborts.
- [x] ADR-0011 — accepted source unchanged; index updated.
- [x] `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/RUNBOOK.md` — flow/ops.
- [x] `docs/backtest_live_parity_plan.md` — reviewed, unchanged: this path is
  independent shadow evidence and does not modify the replay engine.

## Invariants / golden cases

- Invariants checked: I39 and I40.
- Golden cases affected: G-004; existing six-case R8 accounting file remains green.

## Tests / checks run

- Targeted shadow + R8 golden tests: 17 passed.
- Full parent unit suite: 861 passed, 1 skipped; only existing numerical
  precision/empty-slice warnings were emitted.
- Targeted Ruff: passed.
- Real DB parity: five BTC/ETH days, IVP delta 0 and absolute z delta 0.036–0.041.
- Public Deribit smoke: 838 BTC options; sampled book exposed bid/ask/mark.
- First valid real-DB cycle: BTC/ETH both `not_rich`; append-only valid records
  written with `order_capability=false` and `credentials_used=false`.
- Report smoke: one valid day in one distinct week (0.14-week span), two
  ignored stale audit records, all exit/live gates false as expected.
- Claude-review follow-up: recorded BTC/ETH DB-shape fixture matches five E-039
  days within `|Δivp| < 0.5` and `|Δz| < 0.05`, including RICH and not-rich;
  one-line DVOL as-of and 08:00 boundary mutations each fail the fixture test.
  Sparse-chain and R8.3 rejection regressions journal and continue to ETH.

## Risks and rollback

- Risks: source-day drift, stale canonical inputs, thin books, incomplete VWAP
  follow-up, or accidental future endpoint expansion. Exact-day rejection,
  atomic three-leg fills, method allow-list, JSONL dedupe, and tests guard them.
- Initial pre-F39 manual smoke appended two stale `not_rich` records. They remain
  as append-only audit history, but the report explicitly excludes/counts them;
  they do not count toward eight weeks.
- Rollback: remove the new package/CLI/config/test and revert this change's doc
  additions. No DB/schema/config migration or existing result rewrite is needed.

## Approval

- Human approval required: yes — obtained 2026-07-14 via accepted ADR-0011 and
  the explicit task request. This does not approve scheduling or live trading.
