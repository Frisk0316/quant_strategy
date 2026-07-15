---
status: current
type: task
owner: human
created: 2026-07-12
last_reviewed: 2026-07-15
expires: none
superseded_by: null
---

# Project Diagnosis Follow-up Tasks

## Goal

Restore a green, trustworthy development baseline; close the newly found trust
boundary and contract-metadata gaps; then resume research decisions without
changing strategy, risk, execution, or deployment policy by accident.

## Baseline and boundaries

- Audit-time HEAD: `7636dd9` on `codex/pipeline-batch1-stage3`; upstream branch was
  clean before this audit and is 96 commits ahead / 5 behind `origin/main`.
- No current strategy is promotion/demo/shadow/live ready.
- Truth sources remain `research/strategy_synthesis.md`, `config/`, accepted
  ADRs, and `docs/ai_collaboration.md` in the documented authority order.
- Forbidden unless a task below explicitly receives user approval:
  `research/`, existing `results/`, strategy/signal/risk/portfolio/execution
  behavior, differential-validation implementation, DB schema, and deployment
  gates.

## Closed by the 2026-07-12 audit repair

- [x] Standalone `scripts/run_server.py` serves `/api/manual`.
- [x] Manual responses hide lifecycle frontmatter.
- [x] Progress document links use a loopback-only, contained,
      config-allow-listed `.md` route; engine/non-loopback file serving is off.
- [x] Turtle fixed sweep input keeps its already-normalized fraction unit.
- [x] The stale OKX metadata integration test declares `primary_exchange=okx`.
- [x] `docs-impact` fails when Git cannot be inspected and implements A9/A10.
- [x] Current-state, handoff, Progress, known-issue, and review-entry docs were
      synchronized by this session.

## Ordered follow-up tasks

### P0.1 — Contain every artifact identifier

**Status:** [x] Implemented and Claude-review APPROVED 2026-07-12. Shared
reject-not-truncate validation plus resolved-root containment covers API,
library, sweep, artifact-writer and caller-facing CLI boundaries. See
`docs/change_manifests/2026-07-12-artifact-id-containment.md` and the
implementation-review section of `tasks/2026-07-12-claude-p0-review.md`.
Full unit `768 passed, 1 skipped` (Windows symlink privilege), integration
`38 passed`, Ruff and `docs-impact --strict` pass.

**Owner:** Codex implementation; Claude security/data-loss review; human scope
approval because the complete fix includes differential validation.

**Evidence:** F30 / I32. API `run_id` and validation `validation_id` can contain
path separators and reach outside their intended result directory.

**Permitted files (after approval):** the owning artifact-ID validators and
callers in `src/okx_quant/api/routes_backtest.py`,
`backtesting/differential_validation.py`, the smallest shared existing artifact
module if reuse is possible, targeted tests, `docs/FAILURE_MODES.md`,
`docs/INVARIANTS.md`, API/data-flow docs, and a required Change Manifest.

**Do:** locate every caller first; enforce one safe path-component rule at every
write/read entry; resolve and assert containment under the intended root; reject
`.`, `..`, absolute paths, separators, empty IDs, and overlong IDs.

**Acceptance:** API and CLI regressions prove traversal/absolute/unicode-separator
attempts fail before I/O; valid existing IDs still work; `docs-impact --strict`,
the Change Manifest, targeted API/validation tests, and full unit pass.

### P0.2 — Reconcile `ct_val` validation with venue multiplier contracts

**Status:** [x] Implemented and Claude-review APPROVED 2026-07-12. Uses the
approved finite-positive, `<=1e7` contract; PnL/position formulas were not
changed (Claude confirmed no sizing/PnL semantic drift). See
`docs/change_manifests/2026-07-12-ct-val-validation-contract.md`.

**Owner:** Claude plan/review, Codex implementation, explicit human approval.

**Evidence:** F32 / I34. `validate_ct_val()` rejects values above one, accepts
NaN, while accepted venue metadata contains legitimate multipliers from 100 to
1,000,000. ADR-0003's `<=1` wording conflicts with ADR-0007/config reality.

**Permitted files (only after approval):**
`src/okx_quant/portfolio/sizing.py`, exact callers/tests, ADR-0003/0007,
`docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, a Change
Manifest, and affected feature/data-flow docs.

**Do:** design-space review of metadata units; change validation to the approved
finite-positive contract (or a better venue-aware bound); add cases for `100`,
`1_000_000`, zero, negative, NaN, and infinity. Do not change PnL formulas.

**Acceptance:** approved ADR/rule text and tests agree; money-path suites and
`docs-impact --strict` pass; Claude confirms no sizing/PnL semantic drift.

### P0.3 — Reject unknown exchanges instead of defaulting to Binance

**Status:** [x] Implemented and Claude-review APPROVED 2026-07-12. Omitted/blank
uses the configured primary venue; explicit unknown values fail with HTTP 400
before queueing. See `docs/change_manifests/2026-07-12-venue-fail-closed.md`.

**Owner:** Codex; Claude data-provenance review.

**Evidence:** F31 / I33. `_normalize_exchange("typo-venue")` currently returns
`binance`, producing plausible data from the wrong venue.

**Permitted files:** request model/normalizer in
`src/okx_quant/api/routes_backtest.py`, targeted API tests, API/UI/data-flow docs,
`docs/DOMAIN_RULES.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, and a
required Change Manifest.

**Acceptance:** omitted exchange retains the documented default; every unknown
explicit exchange returns 4xx; supported venues remain unchanged; no silent
substitution path remains; the Change Manifest and `docs-impact --strict` pass.

### P0.4 — Integrate or split the long-running feature branch

**Status:** [x] EXECUTED 2026-07-12 by Claude under explicit user authorization
and merged through PR #9 at `b378e16` from PR head `00c7a51`. P0 work committed
(`c84f5a1`); `origin/main` merged with
zero content delta and no conflicts (main's PR #1–#8 content was already in
branch history); integration commit `a950025` pushed; PR #9 used the
documented integration exception. verify-full equivalent on `a950025`: unit
768 passed/1 skipped, integration 38 passed, Ruff/docs/frontend/config/
backtest-smoke pass; api-smoke SKIP (no server); validate-data FAIL is the
pre-existing thin local parquet mirror, not merge-caused. No force-push.

**Owner:** human; Codex supplies evidence only unless asked to perform Git actions.

**Evidence:** at audit time the branch was 96 commits ahead and 5 behind
`origin/main`, far beyond the one-issue/short-lived branch policy.

**Do:** inspect the five main-only commits; inventory the branch by workstream;
split reviewable PRs or approve a documented integration exception; run full CI
against the chosen integration commit. Never force-push or rewrite user history.

**Acceptance:** human records the merge strategy; every included workstream has
review/test evidence; `main` is not changed by this task without explicit user
instruction.

### P1.1 — Finish governance-harness enforcement

**Status:** [x] Completed in the merged P1 batch; post-merge parser and exact
template-exemption hardening is part of the current follow-up repair.

**Owner:** Codex tooling; Claude governance review.

- Add the separate crypto-alpha-lab test target required by the original M1
  acceptance criteria and wire it into `verify` without mixing package imports.
- Build an honest A11 ledger consistency validator (H↔E IDs, family and K-budget
  relations); do not pretend a Git diff can detect ignored experiment artifacts.
- Require lifecycle metadata for every new Markdown file under `tasks/`
  recursively. Exempt only the frozen legacy filename allowlist and the four
  exact task templates; backdated and template-like filenames remain enforced.
- Add Human Review Overview coverage checks or a documented manual review step;
  the current checker validates format only.

**Acceptance:** parent and lab suites run separately; A11 failures are
machine-visible; lifecycle scope is unambiguous; docs checks stay green.

### P1.2 — Remove remaining documentation double truths

**Status:** [x] Completed in the merged P1 batch; stale PR/lifecycle state is
being corrected in the current follow-up repair.

**Owner:** Claude narrative/review; Codex checks links and commands; human decides
policy changes.

- Slim `README.md` to onboarding plus an explicit research/not-live-ready status;
  route operational detail to `docs/RUNBOOK.md`.
- Reconcile ADR-0006 metadata (`accepted`) with its body (`Proposed`) without
  inventing human approval.
- Decide whether ADR-0001's mandatory GitHub issue rule remains binding or needs
  a new accepted local-task exception; update workflow docs only after that
  human decision.
- Supersede/archive completed manual/pipeline plans and refresh their stale Human
  Review Overviews instead of treating them as current implementation state.
- Move compressed 2026-07-04→12 history to `CHANGELOG_AI`; keep handoff/current
  state present-tense.

### P1.3 — Make the next research decisions before more computation

**Owner:** Claude + human. Codex must not run retries or adapters first.

1. [x] H-012 / E-037: SHELVE/no-retry ratified; mechanism novelty closed as
   MINT; portable block remains honest; leak-lag hygiene recorded F36 without
   editing E-037.
2. [x] H-013 / F-VRP-TIMING: Stage-1 approved; E-038 remains reserved-only and
   absent from the registry until a separately scoped Stage-2 probe runs.
3. H-009: no chase-the-gate retry; any retry needs an ex-ante rationale, consumes
   K, and accumulates family trials.
4. H-010: remain blocked until OKX BTC/ETH 1m candles are backfilled and Stage-2
   is reprobed without cross-venue substitution.

### P1.4 — Decide forward-ingestion operations

**Owner:** human operations; Codex implements only the approved option.

**Status:** Repo support implemented 2026-07-15: the OKX liquidation wrapper
pins the verified Python executable and the RUNBOOK documents least-privilege
S4U create/verify/run/rollback/remove commands. Host activation remains pending
because this session could not obtain Administrator Task Scheduler rights; the
existing task still reports `Interactive`.

- Register the documented Deribit D3 snapshot and forward-ingest scheduled tasks,
  or explicitly accept stale series.
- Ingest or retire the empty daily `dvol_deribit_*` config datasets.
- Decide whether OKX liquidation collection needs unattended/service mode; the
  current Interactive-only task loses hours-scale retention during logouts.
- Inspect/restart the pre-existing hung `127.0.0.1:8080` process before relying
  on that port; do not terminate an unverified user process blindly.
- Create a valid OKX Demo key before restarting engine mode; never switch to live
  as a workaround.

### P2.1 — Add the smallest browser interaction gate

**Owner:** Codex.

Cover only the flows static syntax cannot: standalone Manual opens all written
chapters without frontmatter, Progress opens one allow-listed doc and rejects an
unlisted path, and progressive chart selection still works. Reuse Playwright;
do not add a frontend framework or duplicate unit suite.

### P2.2 — Reduce noisy numerical warnings after correctness blockers

**Owner:** Codex.

Profile the 1,195 constant-row z-score precision warnings from the unit suite;
handle zero-variance inputs at their shared source if behavior is defined. Add
one regression, not warning filters. This is lower priority because current
results are deterministic and the warnings did not cause the two baseline test
failures.

## Human decisions recorded 2026-07-12

- **P0.1–P0.3:** scopes ratified per `tasks/2026-07-12-claude-p0-review.md`
  (P0.2 contract: finite positive via `math.isfinite`, `> 0`, cap `<= 1e7`).
- **P0.4:** Option B — single merge PR with a documented integration exception,
  executed after P0.1–P0.3 land, `verify-full` on the integration commit, no
  force-push/history rewrite. The 5 main-only commits are merged into the
  branch first to resolve conflicts before the PR.
- **P1.2 ADR-0001:** local `tasks/` files are an accepted substitute for GitHub
  issues (amendment added to the ADR).
- **P1.2 ADR-0006:** user confirmed it was approved; body status corrected to
  Accepted.
- **P1.1 tasks/ lifecycle metadata (Claude judgment, delegated by user):** every
  new Markdown file under `tasks/` requires lifecycle frontmatter recursively.
  Only the frozen legacy filename allowlist and four exact task templates are
  exempt; backdated, nested, undated, and template-like new files are enforced.
- **P1.3 H-012:** SHELVE ratified; recorded in `docs/HYPOTHESIS_LEDGER.md`
  (including the F36 turnover-cost-timing finding from the leak-lag check).
- **P1.3 H-013:** Stage-1 approved as written; E-038 probe queues behind P0s.
- **P1.4 operations:**
  1. Deribit forward schedulers: NOT registered; stale series accepted as long
     as the RUNBOOK manual-update path keeps working.
  2. Empty daily `dvol_deribit_*` datasets: verified 2026-07-12 — the data IS
     obtainable (Deribit `get_volatility_index_data` supports `1D`, confirmed
     by 2026-07-11 live probes in `research/deribit_data_strategy_research.md`;
     `deribit_dvol.py` and `config/external_data.yaml` already support it; it
     was simply never backfilled). Retirement condition not met: KEPT, and the
     one-time backfill is DONE 2026-07-12 — 1,936 gap-free daily rows per
     symbol (2021-03-24→2026-07-11), close values match the hourly series.
     Manual-update command (requires both `--start` and `--end`) is recorded
     in `docs/RUNBOOK.md`.
  3. OKX liquidation collection: approved to move to unattended/service mode
     (repo implementation done; Administrator host activation pending).
  4. The hung `127.0.0.1:8080` listener/port is abandoned; use another port,
     do not kill the user process.
  5. User will create a valid OKX Demo key later; engine mode stays blocked
     until then.

## Execution order

1. [x] Complete, verify, and obtain Claude approval for P0.1 → P0.2 → P0.3;
   keep external API exposure conservative until the diff is integrated.
2. [x] Execute approved P0.4 Option B as a separate Git task before adding
   another large workstream; PR #9 merged at `b378e16`.
3. [x] Run P1.1/P1.2 to make governance evidence trustworthy; remaining
   post-merge findings are now a separate repair/verification task and PR.
4. Run H-013/E-038 Stage-2 only as a separate task; Stage 3 is not authorized.
5. [ ] Apply and verify the recorded P1.4 S4U host task; repo support is done,
   but the task remains Interactive until the Administrator RUNBOOK command runs.
6. Add P2 browser/noise coverage only after the green baseline is stable.

No step above authorizes promotion, demo, shadow, live, a gate relaxation, or
mutation of existing result artifacts.
