---
status: current
type: handoff
owner: human
created: 2026-05-11
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# AI Handoff

Cross-session current state for Claude and Codex. Read `docs/CURRENT_STATE.md`
first; use `docs/CHANGELOG_AI.md` for history and `docs/KNOWN_ISSUES.md` for the
durable backlog.

## Current goal

H-038/E-095 is complete and F-S5 is terminal at K 2/2. E-095 passed the
authorized 0.95 data gate, measured breadth from actual positions, and failed
closed at distinctness because E-014 has no dated returns. Public/private
status publication and the H-014 shadow/parity path remain separate work.

## Branch and working tree

- PR #21 merged `feature/deribit-moneyness-hypotheses` into `main` at `c887a9f`
  (2026-08-05), so H-038/E-094/E-095, WS-C C3/C5/C10, the worklog generators,
  and the public-status implementation are all on `origin/main`. Verified
  in-main: the audit's ungated work is fully landed — F1 + WS-A A1-A5 + B1
  (`181f82b`), A6 (`8dd88ab`), B2-B5 (`081451b`, completed by `c9fa77b` for the
  two research/probe DSNs outside Codex's ownership), and E1-E2 (`5bf2c42`).
- Current branch: `feature/deribit-moneyness-hypotheses`. Registration is
  `4c84a18`; dated E-025 regeneration is `094742e`; ordered H-024/H-025/H-027/
  H-026 outcome commits are `8f053bb`, `0f572dd`, `084df47`, and `5ac02a8`.
  H-025 merged into F-OPT-HEDGE-DEMAND; all four Stage-2 artifacts are
  immutable and no Stage-3 artifact exists.
- H-030..H-037 implementation/outcome slices are `69fae10`, `1f5f8df`,
  `d482a17`, and `9f3023d`; the registry/docs wrap-up is the following ordered
  commit. Eight SHA-bound Stage-2 artifacts exist under
  `results/slate_stage2_20260729/`; no Stage-3 artifact exists.
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
  not registered; option-surface history remains snapshot-only. New option-flow
  ingests retain every inverse trade and its `trade_id`. Historical full-tape
  enrichment is partial only: 2,304 BTC hours and 744 ETH hours were enriched
  before the hard stop. Total hourly row counts remain 22,403/22,402, but BTC
  aggregate `trade_count` now sums to 12,724,092 versus the pre-task
  12,724,097 baseline; do not resume or treat H-031/H-035 as unblocked until
  Claude/user resolves restoration or source-revision policy.
- H-039/F-XVENUE-OPT-IV Stage 0 now has six forward-only hourly
  `xvenue_opt_iv_{okx,bybit,deribit}_{btc,eth}` datasets. The collector brackets
  30 days, interpolates ATM/25-delta legs in total variance with nearest-expiry
  fallback, retains the full normalized chain, isolates source failures, and
  alerts on gaps over 1.5 hours. All six official public source normalizations
  pass. Accumulation has not started: the configured TimescaleDB connection is
  refused and no scheduler is registered. Trials stay 0 and K stays 0/2. Start
  the DB, run one manual six-dataset snapshot, then have the user register and
  verify the hourly task; do not start Stage 2 before at least 270 persisted
  daily observations.
- CFTC COT and Cboe adapters/config/tests are complete. Official-source
  validation returned 433/277 crypto COT rows, 1,050 rows for each of ES,
  UST10Y, USD Index, and Gold, plus 3,915/9,240/4,241/4,673 rows for
  VIX9D/VIX/VIX3M/VIX6M. These are source counts only; DB backfill remains
  blocked. Cboe's official total put/call CSV has 3,253 rows through
  2019-10-04 and is discontinued, so it must not be scheduled as a current
  feed or replaced with a scraped source.
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
- Security hardening: the 2026-08-03 F1 + WS-A Codex task (A1-A5) + B1 batch
  is implemented. Telegram commands require the configured chat and
  `/reset confirm`; API pair deletion is contained; engine/standalone remote
  binds fail closed without an API key; standalone destructive routers share
  auth; job status no longer carries DSNs and the OHLCV rotation child consumes
  them from `DATABASE_URL`; Compose is loopback-bound with required secrets;
  and the OKX smoke reads only `OKX_DEMO_*`. WS-A A6 and WS-B B2-B5 are also
  landed and in `main` (see "Branch and working tree"). Targeted safety
  tests and Compose fail/pass validation are green. Claude reviewed and
  APPROVED the batch (`tasks/2026-08-03-security-batch-claude-review.md`); it
  is committed and pushed at `181f82b`. The review caught and Codex closed one
  regression (the rotation child needed a `DATABASE_URL` fallback once `--dsn`
  left argv). WS-C's remaining items and F2 remain authorization-gated.
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
  ADR-0016 slice 1 now supplies deterministic joined-input filtering,
  10–15/8/2 executable validation, manifest sealing/hash-bound resume, and
  terminal-artifact reconciliation. No real round ran. Complete-round
  automation remains blocked on enough registered candidate-specific runners
  and the one-command execution path; output remains advisory/limited until
  those later slices ship.
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
  H-030..H-037 limited slate execution is complete at E-069..E-076. H-030
  passed data and decisive E-059 distinctness, then failed cost/power
  (-97.306114 net Sharpe after 8 bps/event). H-032 and H-034 passed data but
  failed their decisive mint-apart checks (0.561490 vs E-067; 0.494810 vs
  E-062), cost, and power. H-031/H-035 remain blocked because historical
  option-flow full-tape retention is partial and aggregate immutability is
  unresolved. H-033's DGS2 and two H-036 macro inputs (VIXCLS/DTWEXBGS) are
  now ingested; H-036's gold leg is an explicitly research-only Yahoo `GC=F`
  futures proxy and still needs Claude/user acceptance before any rerun. H-037
  lacks official CME settlements. All family trials/K
  remain zero and no retune or Stage 3 is authorized.
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
  layer. The historical extension was already executed by `b40f15b` on
  2026-07-18 and reverified 2026-08-06: each symbol has 3,396,960 rows over
  `[2020-01-01, 2026-06-17)`, raw mismatches 0, coverage/alignment 1.0, no raw
  gaps, resolved OKX rows 0, and two idempotent reruns changed 0 rows. The later
  E-057 research task is separate from that promotion: full candle alignment
  passes, but I48 correctly rejects missing OKX funding.
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
- 2026-07-30 data unblock: FRED API smoke and 2020+ ingest passed with 1,682
  VIXCLS, 1,640 DTWEXBGS, 1,643 DGS2, and 1,653 research-only GC=F rows; every
  FRED row has `published_at > observed_at` and no dataset has a gap over seven
  days. Deribit six-hour pre-flight passed exact aggregate equality, but the
  wider archive changed the BTC aggregate total by -5. Workers were stopped;
  only 2,304 BTC and 744 ETH hours are enriched. Targeted ingestion tests pass;
  full unit reported 1,036 passed, 1 skipped, and 1 unrelated pre-existing
  frontend contract failure.
- `make` is unavailable in this Windows environment. Use the absolute Python
  executable and Makefile-equivalent commands; report API smoke SKIP unless a
  healthy server is explicitly provided.

## Next steps

New (2026-08-06): F78 root-caused and fixed — the three DB-writing scheduled
wrappers never sourced `.env`, so `DATABASE_URL` was absent and every run
2026-08-03→08-06 failed with only `Last Result 1` recorded. 65 xvenue hours
are permanently lost and the shadow journal stalled at 08-03 again.
`scripts/_load_dotenv.cmd` + 5 tests landed; xvenue/liq re-verified Last
Result 0 via Task Scheduler; confirm the 16:10 shadow run writes 2026-08-06.
Weekly DB backup registered (`quant_db_backup_weekly`, SUN 03:00, S4U,
`C:\quant_backups`, `market_klines` excluded; first 11.6 GB archive verified).
Data inventory + the first two admission packets delivered and CLOSED (001 no
predictive literature; 002 user data-gate + its literature belongs to refuted
H-044). Public-status page live and scheduled. PR #22 (all seven commits)
MERGED 2026-08-06 as `7cc7eb1`. The OKX 2020+ raw→canonical promotion was
already complete and is now
reverified; the dated ADR-0014 amendment was Claude-reviewed and ACCEPTED
2026-08-06 (evidence relayed from the verifier run, not re-queried). The
recurring external-ingest question is CLOSED by user ruling: schedule nothing,
because every unconsumed family is a re-downloadable archive (Binance Vision OI
zips re-probed 2026-08-06); only unreproducible snapshots would earn a timer and
`optsurf_deribit_*` is deferred. Next: open a PR for `5261de0`; supply the
Deribit testnet key.

New (2026-08-04, updated 2026-08-05): worklog page implementation is complete
but not published; Claude review APPROVED. It collects timestamp-only local
Claude Code/Codex sessions with cwd filtering and a privacy canary, indexes
commit/task headings, creates daily portfolio replay snapshots (user ruling
2026-08-05: `--end` rolls to the previous day), and renders a self-contained
page for a NEW separate PUBLIC repo `quant_worklog` (user ruling 2026-08-05:
public repo, PnL/work-time exposure accepted, no GitHub Pro needed).
The additive E-063 holdings replay now emits 129 scheduled weekly rows from the
frozen parameters with a USD 10,000 display notional; strategy snapshot
ingestion passes. Browser rendering is not yet claimed because the existing
page calls `.map()` on the schema object rather than its `rebalances` list, and
that page/snapshot fix was outside the holdings task's permitted files.
User prerequisites: merge, create the repo, follow RUNBOOK.
No repo, push, Pages setting, or scheduled task was created; `public_status/**`
remains untouched.

Immediate (2026-08-03): the Deribit immutability conflict is RESOLVED — the
count-invariant pagination + payload-only contract landed in `5920380` and the
root cause was pagination, not an archive revision. All 17 new external
datasets (FRED, COT, Cboe, six xvenue IV) are DB-verified; the H-039 hourly
collector and the Sunday worklog generator are registered scheduled tasks.
Keep Docker Desktop + TimescaleDB up or collector hours are permanently lost.
All three then-pending user decisions are now RESOLVED: (a) H-033/H-036 need no
action, closed by H-045/H-046; (b) H-038 was authorized and is terminal at
E-095; (c) `feature/deribit-moneyness-hypotheses` merged via PR #21 (`c887a9f`).
No H-031/H-035 rerun is possible (Deribit first-20 history gap persists for
pre-2024 ranges).

CLOSED 2026-08-05: the ADR-0017 H-014 review-fix wave re-review is DONE — the
second round was recorded clean (all 10 findings addressed) in
`tasks/2026-07-28-h014-live-execution-claude-review.md`, and the later
ADR-0018 delta in `659a930` was reviewed 2026-08-05 as strictly narrowing
(`LiveConfig.__post_init__` plus the private client's hard-pinned
`test.deribit.com` base URL reject `enabled` + non-test before any client is
constructed). Verified live state: `h014_live.enabled` is false, the only
importer of `deribit_live` is `scripts/h014_live_panic.py`, and no H-014
execution task is registered — Phase 2 has NOT occurred and there is nothing
to give a go/no-go on. Phase 2 needs, in order: a trade-scoped no-withdrawal
Deribit testnet key from the user, a Codex-built runner with real Phase 1
outputs, then an explicit Claude go/no-go. Continue the independent H-014
shadow cycle; do not enable the live block, register a live scheduler, or
perform an authenticated order test before the remaining gate sequence and
separate user capital approval.

Also open (2026-08-03): a two-round whole-repo optimization audit produced
`tasks/2026-08-03-project-optimization-codex-plan.md` (11 areas, 24 agents, all
findings adversarially verified; Codex-ready). F1, WS-A's A1-A5 Codex task, and
B1 were committed and pushed at `181f82b`. WS-A A6, WS-B B2-B5, and WS-E E1-E2
have since landed too, so the remaining audit scope is WS-D, WS-E's unlanded
items, F3-F8, and the authorization-gated work. WS-C
trading-safety and F2 (rate limiter) touch
execution/risk/portfolio and each need explicit per-item authorization + a
Change Manifest before Codex acts. Round 2 cleared five previously unaudited
areas: git history holds no real credentials (`.env` never tracked), no
notebooks exist, tests make no real network/DB calls, the frontend has one
latent (non-exploitable) markdown sink, and no untrusted deserialization exists.

Before executing another full strategy-finding round:

1. Wire the slice-1 manifest helper into the one-command orchestrator after
   schema-valid GenAI drafts are available.
2. Extend verified provenance identity from the current family/provenance key
   to normalized DOI/arXiv/title identity at the literature adapter boundary.
3. Reuse the drafted `signal_ref` registry contract so every counted strategy
   has a deterministic Stage-2 screening backtest; keep Stage 3 pass-only.
4. Emit the slice-1 reconciled report from the real sequential execution path.

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
    COMPLETED 2026-07-29: H-029/E-068 Stage 2 passed data and distinctness
    but failed cost and power (net Sharpe -0.471876 vs 0.880629 floor);
    zero trials/K and no Stage 3. ADR-0016 slice 1 passed synthetic validation;
    no real complete round ran.

17. DONE 2026-07-29 (Claude): (a) H-014 shadow clock ROOT-CAUSED and REPAIRED —
    the two-week stall was Task Scheduler power conditions (refused on battery,
    no catch-up), not user downtime; settings flipped with user approval, the
    wrapper's exit-code masking fixed, and a second blocker cleared
    (`canonical_candles` ran 14 days behind raw because the daily ops script
    never promoted). Scheduled 16:10 run now completes unattended (Last Result
    0) and the journal carries 2026-07-29 — the ≥8-week clock restarts there.
    (b) Literature slate built for ADR-0016: H-030…H-037 registered as eight
    verified-paper-backed new mechanisms, each with its decisive distinctness
    gate and honest power/data limits ex ante; H-038 registered as the ONLY
    eligible existing-strategy iteration after auditing every K-remaining
    family. **The 8/2/10 contract still cannot be met honestly** (9 of 10–15;
    a second iteration would be gate-chasing) — specs
    `docs/superpowers/specs/2026-07-29-literature-slate-h03{0,2}-*.md`.
    Next: Stage-2 probe modules per candidate (ADR-0016 phase 3).

18. COMPLETE AT STAGE 2, 2026-07-29 (user-authorized): H-030..H-037 now have
    deterministic registered runners and E-069..E-076 SHA-bound artifacts.
    Whole-slate I49 ran before DB access. H-030, H-032, and H-034 reached
    measurable returns but failed cost/power; H-032/H-034 also failed decisive
    distinctness. The other five are honestly data-blocked. No Stage 3,
    parameter grid, trial/K consumption, ingestion, proxy substitution,
    promotion, or deployment ran. The 8/2/10 complete-round contract remains
    blocked because H-038 is still unauthorized and only one eligible
    iteration exists.

19. AUTHORIZED 2026-07-30 (user, "接受" on ADR-0018): paper-trade testnet
    connectivity handed to Codex —
    `tasks/2026-07-30-paper-trade-testnet-connectivity-codex-tasks.md`. T1
    activates H-014's disabled live-execution adapter to run its real
    signal-driven order loop on Deribit **testnet only**
    (`docs/ADR/0018-h014-testnet-signal-driven-execution-exception.md`,
    accepted; `docs/DOMAIN_RULES.md` R8.9 now cross-references the
    exception). Testnet fills are explicitly non-evidentiary — they do not
    advance the ADR-0011 8-week shadow clock or R7.2/live gates, which
    remain unmoved for real capital. T1 has an internal Phase 1 (build/
    verify, `enabled` stays false) → Phase 2 (activate) checkpoint requiring
    Claude's go-ahead. T2 (new Binance spot+futures testnet clients) and T3
    (verify existing OKX demo connectivity, still blocked on the user
    creating a Demo API key) are connectivity-only, no gate, no strategy
    wiring. Next: Codex executes; Claude reviews Phase 1 before Phase 2.

20. PHASE 1 IMPLEMENTED / AUTHENTICATED RUNS BLOCKED 2026-07-30: Deribit
    private execution now rejects every non-test host and the mocked
    auth/place/check/cancel lifecycle passes; `h014_live.enabled` remains
    false and `config/risk.yaml` is unchanged. New Binance Spot and USD-M
    clients are fixed to their test/demo hosts, use separate blank credential
    names, and have a manual no-strategy smoke; the futures API can express
    only `reduceOnly=true` one-way reductions. A bounded OKX demo smoke reuses
    `OKX_API_KEY` / `OKX_SECRET` / `OKX_PASSPHRASE` through
    `OKXBroker(demo=True)`. No valid Deribit, Binance, or OKX paper key is
    available, so no authenticated venue request or real test order was made.
    Next: the user supplies scoped paper keys; Codex captures the real Phase 1
    outputs; Claude then gives an explicit Phase 2 go or no-go. Until then, no
    H-014 signal drives even a testnet order and `KNOWN_ISSUES` 60005 stays
    open.

21. BINANCE/OKX DEMO AUTHENTICATED 2026-08-02 (user-authorized): Binance Spot
    now uses the official unified Demo endpoint `demo-api.binance.com`, syncs
    venue time before signing, and completed a real Demo place/cancel round
    trip with no open orders. The same Demo key authenticated against USD-M
    `demo-fapi.binance.com`; the flat account correctly blocked the reduce-only
    smoke instead of creating exposure. OKX Demo REST completed balance,
    place, and cancel, and private WS authenticated plus subscribed to
    `orders:ANY` and `positions:SWAP`. Shared OKX execution now sanitizes the
    venue tag, checks nested `sCode`, aligns directional prices to tick size,
    uses `cash` for Spot, and observes Spot fills. The current BTC funding rate
    annualized to about 0.229%, below the configured 12% gate, so the real-time
    funding strategy correctly emitted no order; targeted synthetic/replay
    tests verify the dual-leg path. This is paper connectivity and strategy
    plumbing evidence only. Cross-leg execution is not atomic, no promotion
    gate moved, and Deribit H-014 Phase 2 remains separately gated.

22. OKX PUBLIC DATA ACCUMULATION ACTIVE 2026-08-02 (user-authorized): the
    `quant_okx_market_data` Windows task starts at boot as
    `woody`/S4U/Limited and continuously writes chunked BTC/ETH Spot and
    SWAP books, public trades, and funding-rate Parquet files. The path loads no
    credentials, broker, strategy, or order method. A real four-symbol smoke
    persisted all three data kinds; the task stores no password, is battery-safe, start-when-
    available, unlimited-duration, and configured for one-minute failure
    restart. A 10 GiB free-space guard stops safely; retention is manual.

23. IMPLEMENTED, NOT PUBLISHED 2026-08-04 (Claude-planned, Codex-implemented):
    public research-progress
    page for GitHub Pages —
    `tasks/2026-08-04-public-status-page-codex-tasks.md`. User chose "research
    progress + shadow observability", daily refresh. Publish boundary is an
    orphan `public-status` branch containing only `index.html`, `status.json`,
    and `.nojekyll`; no Actions workflow, no DB access, no `frontend/**` change.
    The generator reads only `config/workstreams.yaml`, the shadow
    bias/journal files, and the funnel projection, and a required leak-canary
    test asserts no signal key or value (`dvol`/`ivp`/`vrp`/`rv`/`z`/`px`/
    `signal`/`legs`/`intent`) reaches the output. The page must state plainly
    that there is no live and no paper-trading performance and that no gate has
    been passed. The local-only generator, self-contained page, daily wrapper,
    leak-canary tests, feature map, and runbook are complete. No branch was
    created, no push occurred, Pages remains disabled, and no scheduler was
    registered. Not a business-rule change, so no Change Manifest. Next: the
    user reviews/merges, then creates the orphan branch, enables Pages, verifies
    the first page, and registers the daily task. `docs/CURRENT_STATE.md`
    next-actions were reordered on the same date at the user's request.

24. DECISION BATCH 2026-08-04 (user): (a) merge — PR #19 is open/MERGEABLE and
    `origin/main` already holds PRs #9/#14/#16/#18, so nothing is pushed to
    `main` directly; (b) H-033/H-036 — no action, closed by H-045/H-046;
    (c) H-038 AUTHORIZED, `tasks/2026-08-04-h038-residual-meanrev-stage2-codex-tasks.md`,
    terminal for F-S5 at K 2/2, breadth must be derived not declared;
    (d) WS-C partially authorized for C3/C5/C10 only,
    `tasks/2026-08-04-wsc-c3-c5-c10-codex-tasks.md`, one commit and one Change
    Manifest each — C1/C2/C4/C6/C7/C8/C9/C11 and F2 stay ungated;
    (e) ADR-0016 deferred. The deferral reason is now invariant I68: R6.8/I53
    used "execution-ready" without defining it, so candidates counted with
    unverified data, a declared breadth, and no gross-edge estimate. Evidence
    is the `docs/ai/LESSONS.md` 2026-08-04 sweep of 38 Stage-2 artifacts.
    I68 enforcement is REVIEW until the ADR-0016 manifest validator ships.

25. CODEX DELIVERY 2026-08-04: (a) H-038/E-094 failed the strict Stage-2 data
    gate at 17,271/17,272 PIT member-days because `SOL-USDT-SWAP` had 1,439 of
    1,440 Binance 1m rows on 2026-01-01. No admissible backtest positions were
    produced; breadth failed closed to 1 with n_obs=0 and family-cumulative
    n_trials=72. The user later ruled the unprovenanced 100% threshold a
    contract error, so E-094 did not consume K. The SHA-bound artifact is
    `results/h038_stage2_20260804/stage2_feasibility.json` at
    `fec068c6c37445dd44df3759a8a87873174141c7c7581caeafda5d2d422113c8`;
    its separate immutable breadth provenance records the absent position input.
    (b) Authorized WS-C C5/C3/C10 are implemented with separate manifests:
    complete venue instrument specs fail closed before broker construction,
    reduce-only plus the caller's `posSide` reaches OKX, and runtime/replay mark
    consumers use the maintained `OkxBook`. No mode, gate, or live state changed.

26. CODEX DELIVERY 2026-08-04: H-038/E-095 changed only the authorized
    experiment-specific data threshold to named `MIN_MEMBER_DAY_COVERAGE=0.95`,
    recorded taker-flow/I11/user-ruling provenance, and wrote a new immutable
    artifact. Data passed at 17,271/17,272 member-days; actual positions yielded
    breadth 5.743875 over 898 daily observations. Distinctness failed closed
    because E-014 has no dated return series; cost and power were not evaluated.
    Artifact SHA-256 is `40c815834fdbe1f5caadcb1e3a06282eea4b678925dc78cb0bf21e8e4fe9c78f`.
    F-S5 is terminal at K 2/2 with n_trials=72 and no E-096, retune, Stage 3,
    promotion, or deployment claim. E-094 remains byte-identical.

27. CODEX DELIVERY 2026-08-04: the private worklog page task is implemented
    and locally testable, but not published. Three standard-library Python
    scripts collect timestamp-only AI sessions, snapshot existing replay
    artifacts, and assemble git/task indexes; one self-contained page renders
    work-time, commits, AI outputs, metrics, equity/drawdown, and snapshot
    history. The daily wrapper uses the supported fixed `run_replay_backtest.py`
    command because deprecated `run_backtest.py` emits no artifacts, and it
    still publishes work-time/commits after a replay failure. Privacy/cwd/
    downsampling/site tests pass. No business rule, existing artifact,
    public-status file, remote repo, Pages setting, push, or scheduler changed.

28. CODEX DELIVERY 2026-08-05: E-063's frozen funding-XS replay now has an
    opt-in holdings log and an additive `holdings.json` with 129 scheduled
    weekly rows, USD 10,000 display notionals, and period returns. Default-off
    output is byte-identical in the regression test; existing funding tests and
    targeted Ruff pass; the strategy snapshot consumes the file without a
    forbidden-key error. This is reporting replay only: no experiment, retry/K
    use, parameter/grid change, existing result-artifact modification, formal
    business-rule change, or Change Manifest. The plan's every-leg `0.5`
    acceptance statement conflicts with E-063 final weights: volatility
    targeting, the 0.1 cap, PIT breadth, and flat regimes produce equal legs in
    `[0, 0.465897]`, so the artifact preserves actual weights rather than
    fabricating 0.5. The pre-existing page/schema `.map()` mismatch remains an
    out-of-scope browser-rendering blocker.

29. CLAUDE SESSION 2026-08-05: (a) reconciled three stale handoff items that
    were re-advertising completed work (H-014 fix-wave re-review, H-032/H-034
    family ruling, WS-A A6 / WS-B B2-B5 / PR #9 follow-up), each verified
    against the artifact that closed it. (b) Delivered the requested
    input-quality review, `tasks/2026-08-05-candidate-input-quality-review.md`,
    with a Candidate Admission Form; Codex ran a validation pass whose four
    corrections were independently re-verified and accepted. User ruled the B3
    bar at gross/cost >= 2.0. (c) Ruled the E-043 artifact mislabel and added
    artifact-identity reconciliation (I72/F77) to
    `check_ledger_consistency.py`; the artifact is unmodified. Commits
    `79c87fb`, `1faac25`, `294cb98` on
    `claude/state-reconcile-input-quality-review`. No experiment ran, no trial
    or K consumed, no `results/**` file changed, no gate moved.

## Open decisions

- CLOSED 2026-08-05: the PR #9 follow-up is merged — `6129f94`, `037b15f`, and
  `d046978` are all ancestors of `origin/main`. ADR-0001 local-task exception is
  approved; ADR-0006 accepted; E-038 stays reserved-only; H-012 shelved; P1.4
  operations decided.
- H-014 pre-2024 hourly-DVOL backfill and E-043 are complete. Any chain-history
  purchase or Stage-3 engine/accounting work still needs explicit human approval.
- CLOSED 2026-07-29 (recorded in `docs/HYPOTHESIS_LEDGER.md`, re-confirmed
  2026-08-05): Claude's I27 ASSIGN ruling reassigned H-032 to F-VRP-TIMING
  (inheriting n_trials=4, K 0/2; F-VOL-OF-VOL dissolved) and H-034 to
  F-XS-IDIOVOL (n_trials=0, K 0/2; F-VARIANCE-DECOMP dissolved). No family
  decision is outstanding.
