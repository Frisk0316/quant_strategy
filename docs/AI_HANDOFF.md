---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# AI Handoff

Cross-session current state for Claude and Codex. Read `docs/CURRENT_STATE.md`
first; use `docs/CHANGELOG_AI.md` for history and `docs/KNOWN_ISSUES.md` for the
durable backlog.

## Current goal

Close out the completed H-024..H-027 limited probe for Claude review. E-025's
frozen selected combo now has a faithful 898-day dated reference; whole-batch
I49 passed, and all four candidates executed in the authorized order. Every
candidate stopped at Stage 2, so no grid, Stage 3, new trial, or K consumption
occurred.

## Branch and working tree

- Current branch: `feature/deribit-moneyness-hypotheses`. Registration is
  `4c84a18`; dated E-025 regeneration is `094742e`; ordered H-024/H-025/H-027/
  H-026 outcome commits are `8f053bb`, `0f572dd`, `084df47`, and `5ac02a8`.
  H-025 merged into F-OPT-HEDGE-DEMAND; all four Stage-2 artifacts are
  immutable and no Stage-3 artifact exists.
- Pushed 2026-07-14: `origin/codex/pipeline-batch1-stage3` through `d046978`,
  F-VOL research delivery `d66f08a`, and Taxonomy_003 research delivery
  `821f761`; the final shared-state commit is on the Taxonomy_003 branch.
- PR #9 merged to `main` at `b378e16`; its PR head was `00c7a51`. Commits
  `6129f94` through `037b15f` and the current repairs were not in PR #9 and
  require a separate follow-up PR. No force-push or history rewrite.

## Current implementation state

- Turtle: accepted research-only standalone runner; real-data golden parity,
  API/UI, and resumable large sweeps exist. Audit fix restores the documented
  fraction-unit sweep behavior.
- Deribit: D1-D5 and review fixes accepted. Native `hv_deribit_*` remains
  limited to Deribit's recent rolling response; separate derived
  `rv30_deribit_{btc,eth}_1h` now has 48,792 unique hourly rows per symbol from
  2021-01-01 through 2026-07-26, sourced from contiguous venue perpetual
  closes. The Market Data Coverage fetch form can queue BTC/ETH DVOL, native
  HV, RV30, and current full option-surface refreshes. Forward schedulers are
  not registered; option-surface history remains snapshot-only.
- Manual/Progress: all manual chapters exist. The standalone server now wires
  `/api/manual`, chapter frontmatter is removed, and configured Progress markdown
  links are served through a contained allow-list route only on loopback binds.
  Engine and non-loopback views render those paths without a file endpoint.
- Runtime: the pre-existing listener on 127.0.0.1:8080 (PID 23696 during audit)
  timed out and was left untouched; temporary 8081 smoke was healthy and cleaned
  up. Demo engine login still needs a valid key. P1.4 repo support now pins the
  liquidation task's Python executable and documents least-privilege S4U task
  registration/run/removal; the host task still reports `Interactive` until the
  user runs the Administrator PowerShell registration and verifies result `0`.
- Runtime/data reliability: external coverage now uses one grouped observation
  scan; the current real DB returned 137 combined coverage rows in 1.704 seconds
  after the old query exceeded a 12-second cold timeout. Compose waits for DB
  health, runtime `DATABASE_URL` overrides the YAML candle DSN, and run-list /
  result-summary DB outages without file fallback return 503 instead of empty or
  missing data. F52 browser authentication and remaining per-artifact/pool work
  stay explicit follow-ups; no schema or API payload shape changed.
- P0 hardening: artifact-ID containment and venue fail-closed behavior remain
  closed. The accepted finite-positive `ct_val <=1e7` rule now fails closed at
  DB/registry/caller-spec boundaries, and rejected fills leave ledger state
  unchanged. No PnL formula or existing result changed.
- Research pipeline: H-009 is now shelved after the pre-registered E-063
  breadth-restored retry failed checkpoint 1 (31 unique assets; WF 1.4778,
  CPCV 0.9092, DSR 0.8305, PSR 0.9166; family `n_trials=8`, K 1/2).
  H-023/F-XS-IDIOVOL stopped at E-062 Stage 2 because plausible net Sharpe
  0.5961 was below the 0.7134 power floor; zero grid trials and K 0/2.
  User correction 2026-07-27: that batch contained only one genuinely new
  family (H-023) and one existing-family iteration (H-009), so it is a limited
  two-candidate probe rather than a completed strategy-finding round. Future
  full rounds follow ADR-0016/R6.8/I53: seal and deterministically evaluate
  10–15 execution-ready strategies before results, including at least eight
  verified-paper-backed new mechanisms and two eligible ex-ante
  existing-strategy iterations.
  Current automation does not meet that contract: the generators have no
  minimum/mix validator or unified command, literature drafts normally remain
  `pending_llm`, and new families without registered runners stop before
  execution. Until the manifest, candidate-specific runner path, and
  reconciled report ship, output is advisory/limited rather than a completed
  round.
  H-012 is user-shelved with no retry and E-037 remains immutable
  non-promotion evidence. H-010/E-057
  is now shelved at Stage 2: full source-aware candles pass, exact OKX funding is
  absent, and the fixed zero-trial anchor's median gross capture is 1.3636 bps
  versus 8.0 bps cost across 7,376 episodes. Stage 3 did not run. H-013/E-050 is
  shelved after statistical failure.
  H-024..H-027 limited probe is complete at E-064..E-067. The reference-only
  E-025 regeneration reproduced its full-sample runner Sharpe exactly and
  added 898 dated daily returns without changing H-006, trials, or K. H-024
  stopped on data/power; H-025 failed all four checks and merged into
  F-OPT-HEDGE-DEMAND at signal corr 0.749580; H-027 passed data/distinctness
  (E-025 corr 0.027930 over 898 days) but failed cost/power; H-026 passed
  data/distinctness but failed cost/power. H-026's screen used prospective
  family `n_trials=8`, while actual trials remain 4 and K remains 0/2 because
  no Stage 3 ran. No retune is authorized.
  Taxonomy_003 E-044..E-049 completed and all six candidates failed their
  statistical gates. H-014/E-051/E-052 is supported but promotion-blocked;
  ADR-0011's >=8-week manual shadow gate is next. Taxonomy_004 H-021/E-056 is
  refuted after its separately authorized first Stage-3 full-PnL validation:
  WF -0.2158, CPCV -0.0375, DSR 0.2357, PSR 0.4818, family-cumulative
  `n_trials=12`, K 0/2. Stop with no retry, retune, promotion, or deployment
  claim.
- F-TAKER-FLOW H-022 is `shelved` after E-059 completed the authorized
  data-gap repair reprobe. T1 verifies ETH at 898/898 complete member-days and
  1,293,120/1,293,120 exact raw/taker rows; the retained non-ETH snapshot hash
  remains `c2b7bf0313b30ae203548e718d91621d33f98c6c6c3475970a05ffc597146858`.
  ADR-0015 alias consumption yields 24,745/24,745 member-days. Data,
  distinctness, and cost pass; power fails at plausible net Sharpe 0.448466
  versus the recomputed 0.754896 floor. Family trials remain 0, K remains 0/2,
  and no retune or Stage 3 is authorized.
- Research Ops UI: the loopback standalone server now exposes H-014 bias/journal
  status plus one existing public-data shadow cycle, and an H-009 full-sample
  lookback/quantile screen. Mutations are disabled in the engine app and on
  non-loopback binds and require the frontend's local-action header. H-014 cycles
  share a cross-process journal lock with CLI/scheduler runs. H-009 combinations
  accumulate an explicitly labeled known trial lower bound; the registry remains
  authoritative. Neither surface changes a verdict, mode, credential boundary,
  or live gate.
- H-014 live implementation: ADR-0017's new `deribit_live` package is complete
  but inactive. The review-fix wave now reconciles fills after cancel races,
  performs journaled label-first orphan sweeps on ambiguous transport sends,
  rests every placed order before cancellation, keeps OAuth secrets out of the
  URL, uses a dedicated reduce-only exception, and anchors runtime defaults to
  the repo root. `h014_vol_regime_options` is now explicitly declared in the
  differential-validation contract with all candidate engines
  `adapter_required`; its portable gate is honestly blocked, not passed.
  No runner, scheduler, settings mode flip, credential, network order, or
  `results/**` artifact was created. Activation remains shadow exit -> bias
  review -> R7.2 -> explicit user capital approval.
- Pipeline observability/triage: under ADR-0013, new registry-written Stage-2
  artifacts fail closed on a fourth `statistical_power` check using
  registry-cumulative trials. `docs/STRATEGY_HISTORY.md` consolidates H-000–H-021
  and E-000–E-057 without inventing unrecorded metrics. The disposable funnel is
  now schema v2 and the read-only 研究總表 / Ledger view exposes each family's
  source, hypothesis, and full iteration timeline; schema v1 degrades to a
  regeneration hint. The Markdown ledgers remain authoritative and generated
  JSON is not checked in. This does not alter Stage-3 or deployment gates.
- Stage-2 follow-up: the five-line evaluator scope and computed `1.7206`
  reference case were ratified. Active CLI/backfill/orchestrator callers reject
  missing candidate-specific power inputs before probes/artifacts/status
  changes. H-010's generic orchestrator path additionally refuses missing or
  mismatched frozen calibration evidence before the venue probe. Funnel schema
  v3 isolates malformed and identity-less files under
  `stage2_artifact_errors`; no research inputs are inferred.
- History/data boundary: the read-only scan completed over 68 canonical and 46
  external datasets. Under separately approved ADR-0014, the existing complete
  raw OKX BTC/ETH 1m window was promoted to an additive source-aware canonical
  layer. Each symbol has 1,293,120 rows, raw mismatches 0,
  coverage/alignment 1.0, resolved OKX rows 0, and an idempotent rerun changed 0
  rows. The later E-057 research task is separate from that promotion: full
  candle alignment passes, but I48 correctly rejects missing OKX funding.
- Shelved/refuted: XS Momentum and Batch 2 C1/C2/C3. No gate may be chased by
  unregistered retries.

## Audit closures and remaining blockers

1. **Closed - artifact containment (F30/I32):** one reject-not-truncate
   helper and resolved-root containment cover read/write API, library, sweep,
   artifact-writer and caller-facing CLI boundaries.
2. **Closed - `ct_val` enforcement (F32/F37/I34):** DB, registry, caller-spec,
   fill, and existing-position fallback values share the finite-positive
   `<=1e7` validator before provenance or ledger mutation.
3. **Closed - venue fail closed (F31/I33):** omitted/blank uses config
   primary; any explicit unknown venue returns 400 before the job queue.
4. **Closed - integration (P0.4):** Option B executed 2026-07-12; PR #9 merged
   to `main` at `b378e16` with PR head `00c7a51`. verify-full equivalent on
   `a950025`: unit 768/1
   skip, integration 38, Ruff/docs/frontend/config/backtest-smoke pass;
   api-smoke SKIP (no server); validate-data FAIL is the pre-existing thin
   parquet mirror, not merge-caused.
5. **Closed - follow-up governance checks (F38/I38):** H↔E ownership, explicit
   reservation, malformed/compact rows, exact template exemptions, and populated
   lifecycle metadata now fail closed under adversarial tests.
6. **Open - F36:** the shelved OI runner posts turnover cost on signal day even
   though positions/funding start t+1. Do not reuse E-037 as promotion evidence.
7. **Closed - F47/I48:** H-010 refuses to substitute Binance funding for a
   position executed on OKX; missing execution-venue settlements fail closed.

Full evidence and binary acceptance criteria are in the follow-up task file;
durable gaps are in `docs/KNOWN_ISSUES.md`.

## Do not touch without explicit approval

- `research/` and existing `results/**` artifacts.
- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`.
- `config/risk.yaml`, strategy assumptions, or demo/shadow/live gates.
- Differential-validation implementation beyond the completed P0.1 containment
  boundary.

## Verification baseline

- Audit baseline before repair: full unit `661 passed, 1 failed` (Turtle static
  contract); integration `37 passed, 1 failed` (stale ADR-0007 test). After the
  repair: full unit `666 passed`; integration `38 passed`.
- Final P0 checks: targeted `306 passed, 1 skipped`; full unit `768 passed,
  1 skipped`; integration `38 passed`; full Ruff, docs metadata/links/overview,
  `docs-impact --strict`, config and backtest smoke pass. The skip is the Windows
  no-symlink-privilege containment case.
- Audit-scope Ruff, frontend syntax, docs metadata/links/overview/impact, config,
  backtest smoke, live API smoke, and Playwright Manual/Progress checks pass.
- 2026-07-16 delivery checks: 99 targeted cross-module tests pass; targeted Ruff,
  all frontend syntax (including `view-ledger.js`), docs metadata/links/ledger/
  strict impact, config, backtest smoke, funnel CLI, and loopback HTTP contract
  pass. The real H-010 verifier correctly exits 1 at 0% coverage. Playwright is
  an environment SKIP because no local package exists and third-party npm
  download/execution was rejected; no browser-render claim is made.
- 2026-07-17 delivery checks: funnel and route tests pass (`3 + 10`), targeted
  Ruff and every frontend syntax check pass, and docs metadata/links/ledger plus
  config validation pass. A real disposable projection produced schema 2 with
  22 families and the expected F-FUNDING-CARRY timeline. Playwright against
  Edge verified both schema-v2 expansion and schema-v1 graceful fallback; the
  only console error was the unrelated missing favicon. Temporary JSON,
  screenshots, logs, server, and browser processes were removed.
- 2026-07-17 authorized follow-up: focused Stage-2 caller/funnel tests passed
  (31), source-aware data tests passed (45), real fixed-scope promotion inserted
  1,293,120 rows per symbol, verifier PASSed exact raw parity and 1.0
  coverage/alignment, and the second promotion changed zero rows. No H-010
  experiment command ran.
- 2026-07-18 H-010 E-057: full candles 3,396,960/leg with 1.0 alignment;
  calibration 7,376 episodes, median gross/cost 1.3636/8.0 bps; all four Stage-2
  checks FAIL, grid trials 0. Focused H-010 + registry tests pass.
- 2026-07-21 review repair: B2 red-first regression reproduced the orchestrator
  bypass, then passed after the guard. Targeted matrix `80 passed`; full unit
  `921 passed, 1 skipped`; full Ruff, frontend syntax, config, backtest smoke,
  docs metadata/links/ledger, and strict doc impact pass. E-057 file hashes are
  byte-identical before/after.
- 2026-07-21 DB/UI reliability repair: six focused API/data files pass
  (`119 passed`); targeted Ruff, config validation, Compose dependency parsing,
  docs metadata/links/ledger, advisory doc impact, and `git diff --check` pass.
  Real coverage returned HTTP 200 with 137 rows in 1.704 seconds. Docker and a
  running browser/API server were unavailable, so those integration smokes were
  not claimed.
- 2026-07-24 E-058: targeted tests `27 passed`; full unit `954 passed, 1
  skipped`; full Ruff, config, backtest smoke, docs metadata/links/ledger,
  strict doc impact, and diff checks pass. The real read-only probe completed
  all bounded symbol-year queries without a probe timeout and wrote the
  immutable four-check artifact with SHA-256
  `a61f58c0c2ea8b539b6cb0896abde6cd50e1154a7bbd59794db11f3b7a275a10`.
- 2026-07-24 T2 alias rule/helper: targeted `1 passed`; full unit `955 passed,
  1 skipped`; full Ruff, config, backtest smoke, docs metadata/links/ledger,
  strict doc impact, and diff checks pass. Membership and E-058 hashes are
  byte-identical; no taker-flow probe code or result artifact changed.
- 2026-07-26 E-059: targeted alias/probe/registry tests `29 passed`; full unit
  `956 passed, 1 skipped`; full Ruff, docs metadata/feature-map/ledger, strict
  doc impact, config, backtest smoke, and diff checks pass. Data 24,745/24,745
  PASS, distinctness 0.043660/0.093939 PASS, cost 42.7529 versus 9.9160 bps
  PASS, power 0.448466 versus 0.754896 FAIL. Artifact SHA-256 is
  `0eefc5531d075202aa688ae052e9d159c6b7f2d494b76ccd0080dea9c352acee`.
- 2026-07-28 H-014 live implementation + review-fix wave: the two live unit
  files pass (`36 passed`), and the required live plus differential-validation
  matrix passes (`100 passed`). Targeted Ruff and panic `--dry-run` pass.
  Config, docs, and final scope checks are recorded in the associated Change
  Manifest. This is implementation evidence only, not activation or deployment
  evidence; portable validation remains blocked on missing adapters.
- 2026-07-29 H-024..H-027: E-025 regeneration reproduced the recorded runner
  Sharpe exactly over 898 dated rows; whole-batch I49 passed. Probe tests,
  aggregate four-check/SHA validation, ledger consistency, and the
  F-PAIRS-OU/H-006 no-drift guard pass. All four candidates stopped at Stage 2.
- `make` is unavailable in this Windows environment. Use the absolute Python
  executable and Makefile-equivalent commands; report API smoke SKIP unless a
  healthy server is explicitly provided.

## Next steps

Immediate: Claude reviews `094742e`, `8f053bb`, `0f572dd`, `084df47`,
`5ac02a8`, and the wrap-up commit. Confirm E-025 regeneration is
reference-only, H-025's family merge is correct, every Stage-2 stop is honest,
and H-026 retained actual family trials=4 and K=0/2. Do not retune or rerun any
of H-024..H-027; the E-059 review remains separate.

In parallel, Claude re-reviews the ADR-0017 H-014 review-fix wave and its
honest-blocked differential-validation declaration. Continue the independent
H-014 shadow cycle; do not enable the live block, register a live scheduler, or
perform an authenticated order test before the remaining gate sequence and
separate user capital approval.

Before executing another full strategy-finding round:

1. Add the ADR-0016 manifest validator at the orchestrator boundary and reject
   fewer than eight `new_research`, two `existing_iteration`, or ten executable
   candidates before DB/backtest access.
2. Join verified literature candidates and history-led iteration candidates,
   deduplicate DOI/arXiv/title identity, and have GenAI emit schema-valid specs
   only.
3. Reuse the drafted `signal_ref` registry contract so every counted strategy
   has a deterministic Stage-2 screening backtest; keep Stage 3 pass-only.
4. Reconcile one manifest/state/report and bind resume to the manifest hash.

Keep the first implementation sequential. Add bounded concurrency only after
runtime/DB profiling shows it is needed. A smaller user-approved batch remains
a limited probe, not a completed round.

First review the five ordered commits plus the 2026-07-21 context/session
handoffs. Confirm A1-A3/B1-B4 are scoped, E-057 is byte-identical, and each
commit stat contains only its named delivery/shared-sync files.

Claude review (`tasks/2026-07-12-claude-p0-review.md`) is user-ratified and
implemented for P0.1-P0.3, H-012, and H-013.

All 2026-07-12 audit decisions are now recorded — see "Human decisions
recorded 2026-07-12" in `tasks/2026-07-12-project-diagnosis-followup-tasks.md`.

1. DONE 2026-07-12: Claude reviewed the P0 diff and APPROVED all three P0s
   (implementation-review section of `tasks/2026-07-12-claude-p0-review.md`)
   and reran the blocked verification: full unit `768 passed, 1 skipped`
   (Windows symlink privilege), integration `38 passed`, Ruff pass,
   `docs-impact --strict` pass. Two minor findings, none blocking.
2. DONE: P0.4 Option B was executed at integration commit `a950025`; PR #9
   merged to `main` at `b378e16` from PR head `00c7a51`.
3. DONE 2026-07-13: repaired the remaining review findings. Final verification:
   unit `841 passed, 1 skipped`, integration `38 passed`, lab `18 passed`, full
   Ruff/docs/config/backtest smoke PASS, and strict doc impact from `00c7a51`
   PASS across 131 changed files. Repair commit `df53f73` and handoff commit
   `d046978` were pushed 2026-07-14. Next: open a separate follow-up PR for
   commits `6129f94` through `d046978`.
4. DONE 2026-07-12 (Claude, user-authorized): P1.1 — `make test-lab` wired into `verify`,
   A11 validator `check_ledger_consistency.py` in `docs-check` (+8 unit tests,
   fixed missing F-VRP-TIMING K-budget row), lifecycle frontmatter enforced for
   every new Markdown file under `tasks/` recursively, with only the frozen
   legacy filename allowlist and four exact templates exempt. Overview coverage
   remains a documented manual review step. P1.2 — README 897→101 lines with
   operational detail moved verbatim to
   RUNBOOK, two completed 2026-06-25 plans archived, CHANGELOG backfilled
   07-05/07-07/07-11.
   P1.4 repo implementation is complete; host S4U activation remains an
   Administrator PowerShell operation.
5. E-038 Stage-2 is a separate task; Stage 3 remains unauthorized.
6. P1.4 repo support DONE 2026-07-15: the OKX liquidation wrapper uses the
   verified Python 3.12 executable, and RUNBOOK documents S4U/Limited create,
   verify, run, rollback, and removal. Host activation is not yet done because
   non-elevated Task Scheduler updates returned Access Denied; the current task
   remains Interactive.
7. Daily `dvol_deribit_*` backfill DONE 2026-07-12: 1,936 gap-free rows per
   symbol, 2021-03-24→2026-07-11, values cross-checked against the hourly
   series; manual-update command recorded in `docs/RUNBOOK.md` (must pass
   `--start` AND `--end`). User creates the OKX Demo key later.
8. Taxonomy_003 CLOSED 2026-07-14 (user-authorized Stage-3 sweep, Claude
   solo, E-044..E-049, verifier clean): all six MINT, all six FAIL the
   DSR/PSR ≥ 0.95 gate — H-015 refuted, H-016 shelved (best 0.70/0.80),
   H-017 inconclusive, H-018 refuted, H-019 shelved, H-020 refuted. See
   `tasks/2026-07-14-taxonomy003-stage3-handoff.md`; no retries without
   ex-ante rationale + K.
9. H-014/E-039 done 2026-07-13 (`tasks/2026-07-13-vol-regime-opt-handoff.md`).
   Stage-2 handed to Codex: `tasks/2026-07-13-f-vol-regime-opt-stage2-codex-tasks.md`
   (T1 Tardis calibration/E-040, T2 vendor report; T3 NOT authorized). Claude
   is the reviewer for this workstream from 2026-07-13 on (user ruling).
   E-040 ran and FAILED CLOSED (2 GiB guard at 2024-03-01); Claude review
   ACCEPTED it (`tasks/2026-07-13-e040-stage2-claude-review.md`) — Stage 2 not
   passed at that point. UPDATE 2026-07-14: after the user-authorized
   hourly-DVOL backfill (2021→2024, 46,440 rows/symbol), E-043 completed all
   12 pairs — **Stage 2 PASS**, real/synthetic RICH-leg ratios 0.88–1.03 ≥
   the ex-ante 0.8 bar. Next gate is the user's: chain-history purchase and
   Stage-3/engine authorization (coin-accounting manifest + ADR first).

10. DONE 2026-07-17: Codex completed
    `tasks/2026-07-16-strategy-history-doc-frontend-codex-tasks.md` — Task A
    `docs/STRATEGY_HISTORY.md` records H-000–H-021 and E-000–E-056; Task B upgrades
    the disposable funnel to schema v2 with per-family source, hypothesis text,
    and dated experiments; Task C adds expandable Ledger iteration detail and
    schema-v1 fallback. Ledgers stayed read-only; no new route, checked-in JSON,
    strategy/gate change, or fabricated metric was introduced.

11. DONE 2026-07-18 (Claude review, two independent agents):
    `tasks/2026-07-18-strategy-history-h010-claude-review.md`. A/B/C delivery
    APPROVE-WITH-FINDINGS (no blockers; minor A1-A3). H-010 Stage-1/E-057
    APPROVE-WITH-FINDINGS: recorded stage2_fail/shelved outcome accepted as
    honest and fail-closed; majors B1 (structurally unpassable distinctness
    gate presented as data-conditional) and B2 (`_run_xvenue_probe` skips
    frozen-calibration checks when the orchestrator omits
    `calibration_evidence`) block any reuse of this Stage-2 path, not the
    recorded outcome. Codex applies A1-A3/B1-B5, then commits per-delivery.

12. DONE 2026-07-21 (Codex): A1-A3/B1-B4 repaired and the working tree split
    into five ordered commits. The distinctness amendment is future-only;
    E-057 artifacts/outcome are unchanged. B2 fails closed before probe, the
    full unit suite is green, and the next action is Claude diff review.

13. DONE 2026-07-27 (Claude, subagent-driven, user-directed): Deribit vol
    backfill + moneyness buckets on `feature/deribit-vol-backfill-moneyness`
    (e60cb05..2f6ab9e, final review clean). DVOL 1h backfilled to 2021-03-24;
    RV30 to 2018-09-14 (BTC) / 2019-04-14 (ETH); calibration corr 0.745/0.766
    user-accepted. Surface + flow adapters emit ATM/ITM/OTM buckets; optflow
    re-ingested with buckets from 2024-01-01. Ingest CLI now selects the
    Deribit history vs www endpoint by start age (archive lags ~7 d, www ~24 h;
    newest ~day keeps pre-bucket schema until archive catch-up re-ingest).
    Next: human merge decision, then a one-off optflow re-ingest ~9 days back.

14. COMPLETE AT STAGE 2, 2026-07-29 (user-authorized 2026-07-28):
    execute the H-024..H-027 Deribit
    moneyness/vol limited probe per
    `docs/superpowers/specs/2026-07-28-deribit-moneyness-vol-probe-hypotheses.md`
    (order H-024→H-025→H-027→H-026; H-026 = F-VRP-TIMING K retry 1/2,
    explicitly included). Commit `094742e` regenerated the missing E-025 dated
    reference without changing its outcome/accounting; I49 then passed with
    898 H-027/E-025 common days. E-064..E-067 record the ordered Stage-2 runs:
    H-024 data/power fail; H-025 duplicate/data/cost/power fail and family
    merge; H-027 cost/power fail; H-026 cost/power fail. No grid, trial/K
    consumption, retune, Stage 3, promotion, or deployment occurred.

15. IMPLEMENTED, NOT ACTIVATED 2026-07-28 (user-approved ADR-0017): H-014
    live-execution layer is implemented in the new `execution/deribit_live/`
    package with additive `h014_live:` risk keys, enabled=false fail-closed,
    testnet default, bounded post-only repricing, shared shadow intents/checks,
    cancel-race fill reconciliation, transport-error cancel sweeps, append-only
    live journal, and panic command. The review-fix wave is ready for Claude
    re-review; `h014_vol_regime_options` remains portable-validation blocked
    with three `adapter_required` engines. No authenticated network call,
    scheduler, settings mode flip, or activation occurred. Activation order
    remains shadow exit -> bias review -> R7.2 -> separate explicit user
    capital approval. The shadow task's desktop toasts remain independent; its
    8-week clock is still stalled, see KNOWN_ISSUES.

16. AUTHORIZED 2026-07-29 (user, "照你的方向做"): next-batch direction —
    H-029/F-FUNDING-SETTLEMENT-DRIFT Stage-2 probe (event design; spec
    `docs/superpowers/specs/2026-07-29-event-probe-hypotheses.md`, task
    `tasks/2026-07-29-funding-settlement-probe-codex-tasks.md`);
    H-028/F-LIQUIDATION-REVERSAL registered data-blocked (liq_okx_* has only
    ~26 days, forward-only — keep quant_liq_okx_ingest healthy, earliest
    probe ~2027-07); ADR-0016 round-infra slice 1 in parallel
    (`tasks/2026-07-29-adr0016-round-infra-slice1-codex-tasks.md`).
    Note: binance funding stale since 2026-07-02 and 1m candles since
    2026-07-14 (candle top-up rode the stalled H-014 shadow task); H-029's
    frozen window (ends 2026-07-02) is unaffected.

## Open decisions

- Human review/merge decision for the separate PR #9 follow-up remains pending.
  ADR-0001 local-task exception is approved; ADR-0006 accepted; E-038 stays
  reserved-only; H-012 shelved; P1.4 operations decided.
- H-014 pre-2024 hourly-DVOL backfill and E-043 are complete. Any chain-history
  purchase or Stage-3 engine/accounting work still needs explicit human approval.
