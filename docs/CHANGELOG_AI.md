---
status: current
type: handoff
owner: human
created: 2026-06-12
last_reviewed: 2026-07-17
expires: none
superseded_by: null
---

# AI Changelog

Durable history for AI-assisted sessions. `docs/AI_HANDOFF.md` should stay focused
on current state, current goal, do-not-touch constraints, and next actions.

## 2026-07-17 - Stage-2 caller repair and OKX source-aware promotion (Codex)

- Recorded the user's ratification of ADR-0013's five-line evaluator scope and
  computed `1.7206` reference case. Active registry CLI, funding backfill, and
  orchestrator callers now require candidate-specific power inputs before DB
  access, probes, artifacts, or terminal status mutation; no breadth/Sharpe
  defaults were invented.
- Funnel schema v3 reports malformed Stage-2 files under
  `stage2_artifact_errors` and continues valid-family aggregation. This closes
  F45/F46 without changing Stage-3, ledgers, results, or deployment gates.
- Accepted ADR-0014 and added an additive source-aware canonical hypertable/view
  while keeping the existing priority-resolved canonical identity and CAGGs
  unchanged. Future raw canonicalization dual-writes the source-aware layer and
  pair purge paths remove it.
- Applied the fixed OKX BTC/ETH 1m promotion for
  `[2024-01-01, 2026-06-17)`: 1,293,120 venue rows per symbol. The read-only
  verifier reports raw/venue counts equal, OHLCV mismatches 0,
  coverage/alignment 1.0, and resolved OKX rows 0. A second promotion changed 0
  rows.
- No network ingest, H-010 retry/Stage-1/verdict, experiment/ledger update,
  backtest, strategy/result change, promotion, demo, shadow, or live work ran.

## 2026-07-16 - Stage-2 power triage, history audit, and Ledger view (Codex)

- Added ADR-0013 and a registry-scoped Stage-2 statistical-power check that inverts the
  current PSR/DSR definitions, uses family-cumulative `n_trials`, and fails
  closed on missing inputs. It is triage only; Stage-3 and deployment gates are
  unchanged. Existing immutable artifacts remain readable and are not migrated.
- Added a ledger/registry-derived funnel report and a read-only 研究總表 / Ledger
  frontend projection. The optional static JSON is disposable; the Markdown
  ledgers remain authoritative, and their links retain the existing loopback-only
  allow-list boundary.
- Added a read-only canonical/external history audit, ranked P1-P3 backfill list,
  exact human-run OKX 1m command, and fail-closed H-010 verifier. The real audit
  found 68 canonical plus 46 external datasets. H-010 still fails at 0% canonical
  OKX coverage: the raw/multi-venue tables already hold the rows, but the current
  canonical identity/source priority cannot expose both venues simultaneously.
- No network ingest, retry, Stage-3 run, result mutation, trading-core change,
  gate relaxation, or live/demo/shadow action was performed.

## 2026-07-15 - Deribit perpetual candles and H-021 E-055 reprobe (Codex)

- Added a credential-free, throttled Deribit TradingView-chart client and the
  existing checkpointed candle-ingest path for native `BTC-PERPETUAL` and
  `ETH-PERPETUAL` 1m bars. The canonical rows retain exact
  `source_primary='deribit'` provenance; no index or cross-venue substitution
  is allowed.
- Backfilled 2024-01-01 through the current closed minute, then ran the same
  command as a forward top-up. Both instruments are continuous through
  2026-07-15 08:04Z at 1,333,925 rows, with zero missing minutes, null OHLC,
  or suspect rows. Six fixed API/DB OHLC spot checks matched exactly.
- Registered E-055 after rerunning the frozen H-021 Stage-2 probe without a
  retune. Gate 1 flipped to PASS at 1,314,720/1,314,720 Deribit price rows per
  leg and distinctness remained PASS; the robust cost gate remained FAIL
  because no cell passed the conservative scenario on both BTC and ETH.
  Family trials remain 8 and K remains 0/2. The stop condition was applied:
  no Stage 3, basis/inverse-collateral PnL, gate, strategy, risk, shadow, or
  deployment work ran.

## 2026-07-15 - Taxonomy_004 cross-venue funding Stage 2 (Codex)

- The strategy ideator selected the only new research-authorized frontier:
  C4/F-XVENUE-FUNDING-SPREAD, after H-013 and H-015 satisfied its activation
  condition. The Stage-1 contract froze four BTC/ETH funding-proxy cells and
  counted every inspected cell.
- E-053 exposed F41: exact timestamp equality retained only 1,782/2,739
  settlement events. Its artifact is retained as invalid evidence. E-054 used
  the orchestrator reprobe with <=1 second boundary canonicalization and
  restored 2,739/2,739 aligned events per symbol; family proxy trials total 8,
  K remains 0/2 because both rows stopped at Stage 2.
- E-054 remains `stage2_fail`: provisional feature distinctness passes (max
  abs corr 0.292), but Deribit venue-scoped perpetual 1m price coverage is 0%,
  and no frozen cell is positive on both symbols under both repo-default and
  conservative two-leg costs. No Stage 3, full price/basis PnL, CPCV,
  checkpoint, config, strategy, shadow/live, or promotion work ran.
- Added F41-I41 settlement-boundary, F42-I42 undefined-correlation, and
  F43-I43 missing-interval guards with focused unit tests. The corrected E-054
  advisory is preserved as an immutable SHA-256-addressed snapshot.

## 2026-07-15 - P1.4 OKX liquidation unattended-mode support (Codex)

- Kept the existing `quant_liq_okx_ingest` action and two-hour cadence; the
  wrapper now uses the verified Python 3.12 executable so non-interactive runs
  do not depend on a logged-on user's PATH.
- Documented a least-privilege `woody` S4U (`/NP`) task with `LIMITED` run level,
  including create, verification, manual run, status, rollback, and removal.
  SYSTEM was deliberately rejected because the repository is user-writable.
- Host activation remains pending: the existing task still reports
  `Interactive`; Task Scheduler updates from this session returned Access
  Denied without Administrator rights. No ingestion schema/data semantics,
  strategy, risk, execution, H-014/shadow file, or gate changed.

## 2026-07-14 - ADR-0011 H-014 shadow-only implementation (Codex)

- Implemented manual, public-only Deribit shadow execution for the frozen
  H-014 combination (`ivp=85`, `z=0.5`): DB as-of signals reuse the research
  sequence builder and strike selector, hypothetical sells hit bid and buys
  lift ask, and R8 accounting functions are imported from the accepted
  research implementation. There is no broker, private endpoint, credential,
  order submission, scheduler, DB write, schema change, or `risk.yaml` change.
- Added fail-closed R8.3 intent validation: any naked short-put intent is
  rejected and each coin is capped at 1.0 unit. The append-only JSONL journal
  has deterministic event IDs; the report covers fill bias, missed-entry rate,
  mark tracking error, weekly coverage, and keeps both discussion and live
  approval gates closed until at least 8 valid weeks and later approvals.
- A real DB smoke exposed F39: selecting the latest common date can silently
  reuse stale candles, and its same-day ID can block the corrected append-only
  rerun. The runner now requires the exact prior research day, uses the research
  08:00 UTC boundary, and qualifies intent IDs by signal day. The two pre-fix
  records are retained but ignored. After bounded refreshes through the existing
  public ingestion paths, the first valid cycle recorded BTC/ETH as `not_rich`.
- Verification includes the existing R8 golden tests, new signal/intent/fill/
  report tests, five-day DB parity within the task tolerances, and a successful
  credentials-free Deribit public order-book smoke. The current report has one
  valid day in one distinct week, no RICH opportunity, and both live gates closed. This is shadow
  evidence, not live-trading or deployment approval. Final parent unit result:
  861 passed, 1 skipped; config/docs/strict impact checks passed.

## 2026-07-14 - H-014 E-052 extended-window pass + shadow layer authorized (Claude)

- Checkpoint-① RATIFIED by the user → H-014 `supported`; governance commit
  `22bdf48` pushed the E-051/ADR-0010 record with evidence-chain scripts.
- E-052 (user-authorized K-consuming retry, spec pre-registered): pre-DVOL IV
  proxy from the 2019-04+ trade tape — v1 (tenor 20-40d) honestly FAILED
  CLOSED on the staleness rule (monthly-expiry gaps, runs 16/24d; archived);
  v2 (tenor 10-60d, ±15% moneyness, spec-amended first) gave BTC 0% / ETH
  3.8% carry; splice corr 0.964/0.984, bias −10.1/−11.5 pts, sensitivity
  artifact shows RICH-day Jaccard 0.972–1.000 under ±3 pts. **Extended
  window (2020-05→2026-02, three stress episodes) PASSED the gate**:
  WF 0.8818, CPCV 1.0098, DSR 0.9746 < PSR 0.9904 (real penalty — fold
  selections varied), n_trials=8, K 1/2. Adversarial verifier's one MAJOR
  (in-session-only sensitivity check) resolved by persisting the artifact;
  both E-051 caveats (degenerate penalty, single bear) are closed.
- ADR-0011 accepted (user: "先授權 deribit 執行層"): shadow-only execution
  layer — live public data, hypothetical fills, R8.3 naked-put rejection in
  code, JSONL journal, zero order capability; Codex task file issued
  (`tasks/2026-07-14-deribit-shadow-execution-codex-tasks.md`), exit =
  ≥8 weeks journal + bias report before any live-execution ADR.
- Ledgers: 21 H / 53 E / 20 K consistent; E-052 registered with K 1/2.

## 2026-07-14 - H-014 E-051: first statistical-gate pass (Claude solo, user-signed-off)

- User signed off the package in one decision: ADR-0010 accepted (coin-margined
  options research accounting → DOMAIN_RULES R8.1–R8.6, invariant I39, matrix
  row A12, manifest `2026-07-14-inverse-options-research-accounting.md`),
  Stage-3 spec accepted, E-051 authorized; long leg OFF and naked short puts
  prohibited confirmed.
- Data extension collected free from official sources: 786 t+1 entries,
  11,121 instrument-day trade-VWAP marks, 4,930 official delivery prices
  (`results/h014_stage3_data_20260714/`). Golden-cycle accounting tests 6/6
  (`tests/unit/test_h014_options_accounting.py`).
- **E-051 PASSED the DSR/PSR ≥ 0.95 gate — first in project history**:
  WF OOS Sharpe 1.3049, CPCV 1.1326, DSR = PSR 0.9845, minting MINT (0.074),
  124–261 tranches/combo, BS-fallback marks 4.0–4.5%, window 2022-05→2026-02.
  Adversarial fresh-verifier verdict PASS-STANDS (786/786 entries t+1,
  hand-recomputed tranche PnL matches, no lookahead/double-count). Recorded
  caveats: 0.9845 margin is thin and its DSR multiple-testing penalty
  degenerates to zero because every CPCV fold selected the same combo; the
  window holds one deep bear. H-014 → `testing`, checkpoint-① human review
  pending; `promotion_gate_passed:false` per R7.2.
- Security note: the verifier agent reported and ignored a prompt-injection
  attempt (fake system-reminder urging information suppression and unsafe git
  operations) during its run; flagged to the user.

## 2026-07-14 - H-013 full run (shelved) + H-014 entry-leg data collected (Claude solo)

- User authorized running H-013 and collecting H-014's data; nothing was
  required from the user (free official sources only).
- H-013/F-VRP-TIMING: E-038 feasibility probe PASS (zero-Δ daily DVOL ≈ 0,
  complete candles). E-050 ran the pre-registered 4-combo grid exactly per
  the 2026-07-12 spec (hourly-DVOL as-of minus 1m realized vol, z90,
  long/flat, fold-refit WF/CPCV, minting MINT 0.051): WF OOS Sharpe 0.0543,
  CPCV 0.5588, DSR 0.5999, PSR 0.7845 — statistical fail, SHELVED, no retry.
- H-014 data: `research/probes/h014_collect_leg_marks.py` collected real
  traded premiums for all pre-registered entry legs (25Δc/25Δp/10Δp/ATM c+p,
  ~30d expiry) on the union of grid RICH days from the official
  history.deribit.com trade tape: 1,306/1,310 leg-days with trades
  (261-262/262 per leg), median 36 trades/leg-day
  (`results/h014_leg_marks_20260714/leg_marks.csv`). Two collector bugs found
  and fixed en route: missing `include_old`, and expiry selection must filter
  instruments by `creation_timestamp` ≤ signal day (D+30 otherwise lands on
  daily/weekly instruments created later). Vendor chain purchase is now
  optional robustness, not a Stage-3 blocker.

## 2026-07-14 - Uncommitted work split and pushed by workstream (Codex)

- Pushed the verified PR #9 follow-up branch from `037b15f` through `d046978`.
- Split the mixed working tree into stacked, reviewable deliveries without
  rewriting history: F-VOL specs/probes/tests/artifacts at `d66f08a`, followed
  by Taxonomy_003 specs/probes/data/results at `821f761`; shared ledgers, state,
  Progress mirror, and session handoffs remain a separate final commit on the
  Taxonomy_003 branch.
- Pre-commit checks: F-VOL target pytest `3 passed`; Ruff, docs metadata,
  feature-map links, ledger consistency (21 H / 49 E / 20 K), docs impact, and
  config validation passed. No `.env`, secret, strategy/risk/execution, DB
  schema, deployment-gate, or existing tracked result file was staged.

## 2026-07-14 - Taxonomy_003 Stage-3 sweep + H-014 Stage-2 PASS (Claude solo)

- User authorized: (a) pre-2024 hourly-DVOL backfill (done, adding 24,312
  rows/symbol; both series now 46,440 gap-free 2021-03-24→2026-07-10); (b) performance
  backtests for all six taxonomy_003 candidates, Claude end-to-end.
- Pre-registered `docs/superpowers/specs/2026-07-14-taxonomy003-stage3-specs.md`
  (grids/directions frozen before first run), registered H-016..H-020, fetched
  DefiLlama/Coinbase/blockchain.info data, then ran E-044..E-049 through the
  repo fold-refit WF/CPCV harness (921 daily bars, t+1, 2+2 bps, funding,
  vol-target). Family minting: all six MINT (max abs corr ≤ 0.099).
  **All six FAIL the DSR/PSR ≥ 0.95 gate**: H-015 optflow refuted
  (WF −1.12); H-016 XS-illiquidity shelved (best: WF 0.97/DSR 0.70/PSR 0.80);
  H-017 stablecoin inconclusive (one-regime window); H-018 coinbase refuted;
  H-019 hash-ribbon shelved (breadth-1); H-020 calendar refuted. Fresh-verifier
  pass: no leakage; minor cap-binding + double-lag conservatisms annotated.
- E-043 (H-014 calibration rerun with hourly DVOL): probe COMPLETE 12/12,
  verdict **PASS** (RICH-leg real/synthetic ratios 0.88–1.03 ≥ 0.8 bar) —
  Stage 2 passed; E-040's low call ratio was the daily-close-DVOL mismatch.
  Checkers pass (21 H / 49 E / 20 K).

## 2026-07-13 - Idea batch taxonomy_003 + H-015 F-OPTFLOW-POSITIONING (Claude solo)

- User instructed Claude to run a new ideation round end-to-end without Codex,
  downloading any needed data itself. Output:
  `results/idea_batch_20260713_taxonomy_003/` (schema-conforming, 6 selected /
  4 skipped, cap 15) with `feasibility.json` availability probes — DB optflow
  coverage 0.9999 with 100% bucket-end `published_at` and zero frozen-feed;
  Amihud breadth 29–33 complete symbols; DefiLlama stablecoins daily since
  2017-11; Coinbase candles and blockchain.info hashrate reachable.
- Top pick registered: H-015/F-OPTFLOW-POSITIONING — Deribit put/call
  taker-buy premium imbalance (D4 data, mechanism reserved by the Deribit
  research doc §3 C2) as a BTC/ETH long/flat risk-off book; direction fixed
  ex-ante (follow put-flow extremes, Pan-Poteshman); grid {L ∈ [1,3],
  z_cut ∈ [1.0,1.5]} = 4 pre-registered; E-042 Stage-2 data probe PASS
  (0 trials, no K). Skipped as blocked: liquidation cascade, DVOL skew,
  ETF flow, DVOL momentum.
- Stage 3 gated on user ratification of the ranking; per the user ruling
  Claude (not Codex) implements the runner when authorized. Checkers pass
  (16 H / 42 E / 15 K families).

## 2026-07-13 - H-014 Stage 2 E-040/E-041 calibration (Codex)

- E-040 implemented the deterministic 12-pair Tardis real-premium calibration
  and failed closed after 7 pairs at the fixed 2 GiB `Content-Length` guard;
  Claude accepted the fail-closed record. The three-vendor purchase report
  recommends Tardis Business at the published $3,000/month, with no purchase.
- The user-authorized E-041 bounded rerun changed only the guard to compressed
  bytes read, the denominator to DB hourly DVOL published as-of 08:00 UTC, and
  completion/pricing status separation. It failed closed before download: the
  fixed sample starts 2022-04-01, but DB hourly DVOL starts 2024-01-01.
- E-041 has 0 trials, no K, no fallback, no pricing verdict, and no promotion
  evidence. Stage 3 remains unauthorized and blocked.

## 2026-07-13 - H-014 F-VOL-REGIME-OPT Stage 1 + E-039 probe (Claude)

- User request: Deribit BTC/ETH coin-margined options vol-regime strategy
  (covered call; sell premium when vol is "super high", buy when "super low").
  User rulings: new family vs F-VRP-TIMING; probe approved; final target is
  the two-sided switch (Option C) with the put side as a spread.
- Registered H-014 with a 4-combo grid pre-registered BEFORE the probe
  (`docs/superpowers/specs/2026-07-13-f-vol-regime-opt-hypothesis.md`, with
  the literature/data survey). E-039 synthetic-pricing probe (BS on DVOL,
  Deribit public API, 2021-03→2026-07, 0 trials, no K): RICH-regime short
  premium strongly positive vs ≈0 unfiltered (covered call BTC +2.35%/30d
  coin vs −0.09%); CHEAP-bucket long ATM straddle negative on both symbols,
  so the long leg stays OFF by default. Mechanism support only, not edge
  evidence (RICH bucket ≈2–4 non-overlapping cycles).
- Stage 3 blocked on: option-chain history (Tardis/Amberdata), an options
  backtest engine, a Deribit trade adapter, and a coin-accounting
  DOMAIN_RULES Change Manifest + ADR. Ledger/metadata checkers pass.

## 2026-07-13 - PR #9 follow-up repair closure

- Re-reviewed the already-merged PR #9 head (`00c7a51`) plus its five
  post-merge repair commits and closed the remaining `ct_val` boundary gaps:
  DB, registry, caller overrides, and ledger fallbacks now share the same
  finite `0 < ct_val <= 1e7` validator before authoritative provenance or
  position state is written. Invalid fills are atomic and leave no ghost
  position. No PnL formula, strategy assumption, or promotion gate changed.
- Hardened governance checks so H↔E evidence links must agree in both
  directions, only explicit per-ID reservation is exempt, valid Markdown table
  spacing cannot hide ledger rows, lifecycle metadata must be non-empty, and
  only the four exact task templates are exempt.
- Corrected collaboration state: PR #9 is merged at `b378e16`; this closure is
  delivered from `codex/pipeline-batch1-stage3` as a separate follow-up change
  for human review and merge.
- Synchronized R1.5, I34/I38, F32/F37/F38, the data flow, Change Manifest,
  current-state/handoff records, review index, and workstream status. No
  research file or existing result artifact changed.
- Final verification: unit `841 passed, 1 skipped`; integration `38 passed`;
  lab `18 passed`; full Ruff, docs metadata/links/ledger/overview, config,
  backtest smoke, and strict doc impact from `00c7a51` passed.
- Repair committed locally as `df53f73`. Push did not occur: the sandbox could
  not reach GitHub, and escalation was rejected by the tool usage limit.

## 2026-07-13 - Codex review fixes for PR #9/#10

- Closed the P0.2 enforcement gap Codex found: `PositionLedger._fill_ct_val`
  now routes every explicitly provided multiplier through the shared
  `validate_ct_val()` (inf/>1e7 no longer enter positions/PnL; NaN no longer
  silently becomes 1.0; the fallback applies only to truly absent values), and
  replay caller-supplied `instrument_specs` are validated before receiving the
  authoritative `config_override` provenance label. Regressions added; ct_val
  Change Manifest addendum, R1.5/I34 updated. No PnL formula changed.
- RUNBOOK corrections: demo/live gate text now defers to
  `docs/ai_collaboration.md` (DSR and PSR >= 0.95, idealized-fill exclusion,
  differential validation); the deprecated bar-proxy backtest removed from the
  live-gate table; the stale `ctVal > 1` note replaced with the finite
  `<= 1e7` contract.
- Historical `tasks/` handoffs/plans (June and July) demoted from `current`
  to `archived`; only the active follow-up backlog and the two latest session
  handoffs remain `current`.
- A11 validator hardened against fail-open: registry experiments must be
  listed on their hypothesis row, `reserved` exemption is scoped to the ID it
  annotates, empty ledgers fail, `K_used >= 0` and `K_limit == 2` enforced
  (14 unit tests).
- Task metadata checker now scans `tasks/` recursively with a frozen 65-name
  legacy exemption list — undated, backdated, and nested new files are all
  enforced (8 unit tests).
- Doc sync: new Human Review Overview for the whole batch, review_index row,
  workstream 8080-abandoned wording, CHANGELOG commit dates corrected.

## 2026-07-12 - P0.4 integration executed; P1.1 governance tooling; P1.2 docs cleanup

- P0.4 Option B executed by Claude under explicit user authorization: the P0
  hardening plus audit repair committed as `c84f5a1`; `origin/main` merged with
  zero content delta (main's PR #1–#8 content was already in branch history);
  integration commit `a950025` verified (unit 768/1 skip, integration 38, Ruff/
  docs/frontend/config/backtest-smoke pass; api-smoke SKIP; validate-data FAIL
  is the pre-existing thin local parquet mirror); PR #9 opened with the
  documented integration exception. No force-push.
- P1.1 (branch `claude/p1-governance-docs`): `make test-lab` runs
  `research/crypto-alpha-lab/tests` separately and is part of `verify`;
  `scripts/docs/check_ledger_consistency.py` (A11: H↔E links, family
  agreement, K-budget bounds) added to `docs-check` with 8 unit tests — it
  immediately caught the missing F-VRP-TIMING K-budget row, now added;
  lifecycle frontmatter enforced for dated `tasks/` files ≥2026-07-01 (28 July
  files migrated, 4 templates updated, pre-July legacy exempt); Human Review
  Overview coverage documented as a manual review step.
- P1.2: README slimmed 897→101 lines; all operational commands/gates moved
  verbatim into `docs/RUNBOOK.md`; completed 2026-06-25 pipeline/manual plans
  archived; CHANGELOG backfilled with 07-05/07-07/07-11 entries.

## 2026-07-12 - P0 artifact, ct_val, and venue hardening

- Implemented the user-ratified Claude P0 review. One shared validate-and-reject
  path contract now covers caller-controlled artifact IDs across API, library,
  writers/readers, sweeps, differential/strategy validation, and CLIs; fixed
  namespace and final derived paths are resolved against their true root.
- Changed the numeric `ct_val` guard to finite `0 < value <= 1e7`, preserving all
  sizing/PnL/funding formulas. Numeric acceptance remains separate from
  promotion-grade provenance under R1.4/I16.
- Changed run/sweep venue requests so omitted/blank resolves to configured
  primary and any explicit unknown venue returns HTTP 400 before queue mutation;
  the daily-winner CLI uses the same supported venue allow-list.
- Recorded H-012 as shelved/no-retry after hygiene found F36 (turnover cost on
  signal day while position/funding begin t+1); E-037 remains immutable
  non-promotion evidence. Accepted H-013 Stage-1; E-038 stays reserved-only and
  no probe/grid/adapter ran.
- Added three Change Manifests and synchronized rules, invariants, failure modes,
  maps, current state, Progress, task plan, ledger/spec, and Human Review
  Overview. No research file, existing result, schema, deployment gate, commit,
  push, or merge changed.
- Final verification: P0 target suite `306 passed, 1 skipped`; full unit
  `768 passed, 1 skipped`; integration `38 passed`; full Ruff, docs metadata/
  links/overview, `docs-impact --strict`, config, backtest smoke and 12 frontend
  syntax checks passed. API smoke explicitly skipped without `API_BASE_URL`;
  optional local `validate-data` remained advisory-fail because its legacy
  parquet fixture is absent. Claude implementation review approved all P0s.

## 2026-07-12 - Whole-project audit and baseline repair

- Rebuilt project status from collaboration docs, accepted ADRs, maps, Git, and
  executable checks. Replaced stale uncommitted-work claims, deprecated the old
  branch board, corrected XS Momentum to shelved, and added a current Progress
  hardening stream plus a human review entry.
- Fixed the RUNBOOK standalone server's missing Manual router, hid lifecycle
  frontmatter from rendered chapters, and replaced broken Progress repo links
  with a read-only route limited to configured, repo-contained markdown files.
  File serving is enabled only for loopback standalone binds; the engine and
  non-loopback views expose no repository-file endpoint.
- Removed the reintroduced Turtle fixed-input unit guess and corrected the stale
  integration test to exercise unknown OKX metadata instead of valid Binance
  base-unit contracts.
- Made `docs-impact` fail closed on Git inspection errors, supplied invocation-
  scoped safe-directory handling, added A9/A10 executable rules, and documented
  why A11 needs a dedicated ledger validator rather than a diff heuristic.
- Recorded new blockers F30-F32/I32-I34 (artifact path containment, invalid-
  venue fallback, `ct_val` metadata validation) without changing their protected
  code paths. Full scope/order is in
  `tasks/2026-07-12-project-diagnosis-followup-tasks.md`.
- Verification: 666 unit passed; 38 integration passed; Ruff, all frontend Node
  syntax checks, docs metadata/links/overview/doc-impact, config validation,
  backtest smoke, live API smoke on temporary port 8081, and Playwright Manual /
  Progress allow-list checks passed. No backtest result artifact was changed.

## 2026-07-11 - Deribit D2-D5 ingestion, R1-R5 review fixes, D4 backfill

- Implemented the signed-off Deribit plan: hourly DVOL, funding, option-surface
  snapshot, option-flow hourly aggregates, and a frontend/API read path for
  external derivative context (`routes_data.py`, `config/external_data.yaml`).
- Applied Claude review fixes R1-R5: PIT `published_at` labels for hourly DVOL
  and option-flow, checkpoint preservation on failed chunks, hour-aligned
  option-flow bounds, DVOL throttling/retry, minor surface/snapshot/API/frontend
  fixes. D4 option-flow history backfilled through 2026-07-10 23:00Z.
- No business-rule change; `check_doc_impact.py --strict` passed. Source
  handoffs: `tasks/2026-07-11-deribit-*-handoff.md`.

## 2026-07-07 - F-OI-POSITIONING Stage-3 runner and E-037 checkpoint

- Implemented the research-only H-012 Stage-3 runner
  (`backtesting/oi_positioning_backtest.py`, checkpoint CLI, unit coverage,
  Stage-3 registry entry), Change Manifest
  `docs/change_manifests/2026-07-07-oi-positioning-stage3.md`.
- E-037 4-combo fold-refit checkpoint failed the statistical gate (WF 0.6034,
  CPCV 0.7240, DSR 0.7220, PSR 0.8484); later user-ratified SHELVE/no-retry
  with hygiene finding F36 (turnover cost on signal day) recorded 2026-07-12.

## 2026-07-11/12 - Turtle sweep scale-up and UI polish (commits)

- Turtle UI polish: warmup hint, invest_pct units, heatmap hover (`61f04e2`,
  2026-07-11); batched resumable turtle sweeps with raised caps (`4ac9a41`,
  2026-07-12); Deribit feed groundwork and research checkpoints (`b9ec041`,
  2026-07-12).

## 2026-07-05 - Weekly worklog (2026-06-29→07-05)

- Compressed weekly history lives in `tasks/2026-07-05-work-log.md`: pipeline
  automation (idea generation → literature scoring → orchestration → Stage-3
  checkpoint), batch-2 closure, governance framework landing, turtle platform
  acceptance, OI/DVOL data-source hookup.

## 2026-07-04 - Turtle Manual Pass + F-FUNDING-XS-DISPERSION Checkpoint Verdict

User directives executed: keep F-FUNDING-XS-DISPERSION, and put the turtle
through a real manual pass (it is a usable strategy, not a rejected one).

- **F-FUNDING-XS-DISPERSION (H-009/E-031) reviewed and verdict recorded:**
  Codex's Stage-3 checkpoint ran the family-minting distinctness checker
  FIRST against the real C2 funding-carry reference signal (max abs corr
  0.138 -> provisional MINT, quantitatively confirming the Stage-1 spec's
  mechanism argument), then the pre-registered 4-combo grid through
  fold-refit WF/CPCV: WF OOS Sharpe 1.1812, CPCV OOS Sharpe 0.9553,
  DSR = PSR = 0.9346 - a genuinely marginal miss of the 0.95 gate, unlike
  the clean refutations of H-006/007/008. Claude verdict (user-ratified
  2026-07-04): **KEEP as `testing`, MINT accepted, do not refute** - and do
  not tune to chase the gate (H-002 lesson); any retry needs an ex-ante
  rationale, burns K (0/2 used), and accumulates n_trials. DSR==PSR is
  explained by all 5 CPCV paths selecting the same combo (small-grid
  stability), not a computation defect.
- **Turtle golden parity now passes on REAL data:** the earlier 600-day
  synthetic fixture was replaced per spec with 898 real BTC-USDT-SWAP UTC
  daily bars exported from canonical DB (all days have the full 1440
  minute-bars). The verbatim reference `turtle_trading_system_full` was
  re-run in a polars scratch venv on the real fixture (default + cash-gate
  stress param sets; the stress run emitted hundreds of reference cash-skip
  prints, exercising exactly the intended path). The pandas port matches
  both expected CSVs exactly - 17 columns, ints exact, floats rtol 1e-9,
  898 rows (final equities 50578.081905 / 12307.892184). Fixture provenance
  and regeneration steps: `tests/fixtures/turtle/README.md`.
- **DB-backed end-to-end API smoke (no mocks, in-process TestClient against
  the real router + real DB):** single run with a manually adjusted
  `invest_pct=0.05` completed (75 orders, full ADR-0002 artifact set incl.
  `equity_curve.csv`); 2-free-window-param sweep (6 combos) produced
  rows.csv + surface.html + working result/artifact endpoints; the
  invest_pct-axis sweep produced equity_curves.csv for the slider scrub UI.
  The smoke caught one real bug - `run_turtle_sweep` equity-curve rows
  carried pandas Timestamps and crashed the sweep job's `summary.json`
  serialization - fixed at source (ISO date strings) with a regression test.
- Full unit suite: **599 passed** (includes the RF1 contract regression and
  the real-data parity tests). Turtle is accepted as a usable,
  manually-tunable frontend strategy; research-only, no live/demo/shadow
  claim.

## 2026-07-03 Codex (Turtle research runner platform integration)

Implemented the user-requested Turtle S1/S2 platform integration from
`tasks/2026-07-03-turtle-strategy-platform-tasks.md`: a research-only pandas
reference port in `backtesting/turtle_backtest.py`, FastAPI single-run and
sweep branches in `routes_backtest.py`, frontend 1D controls with `invest_pct`
percent slider, Turtle sweep heatmaps, and vendored Plotly 2.35.2 for
`surface.html`. Added focused unit tests for reference quirks, grid constraints,
API artifacts, and sweep artifact readers. Follow-up RF1-RF3 fixed the
full-suite contract regression with one declarative `turtle` validation
contract entry, added the `invest_pct` sweep scrub UI and 5-metric heatmaps,
and wired the checked-in 600-day golden fixture into parity tests. No replay
strategy, config strategy, strategy/risk/live/deployment gate,
differential-validation implementation, or existing result artifact was changed.
DB-backed manual run/sweep smoke passed on a temporary current-code 8081 server
with local 1D candles.

## 2026-07-03/04 - Pipeline P1-P9 Full Cycle + First Stage-1 Spec From Taxonomy

Full-cycle Claude review + user-authorized execution of the pipeline
improvement plan (`tasks/2026-07-03-pipeline-improvement-tasks.md`), ending in
the first taxonomy-sourced candidate to clear Stage-2 data availability.

- **P1-P8 review (Claude):** approved with one required fix — `liq_okx_eth`
  in `scripts/market_data/ingest_external.py` hardcoded `contract_value:
  0.01`, but OKX `ETH-USDT-SWAP` ct_val is 0.1 (ADR-0007,
  `sql/seed_venue_instrument_specs.sql`); OKX liquidation details carry only
  `sz`/`bkPx`, so the computed-notional path always applies and would have
  understated ETH liquidation notional 10x. Fixed 0.01->0.1 with a
  seed-SQL-pinned regression test. Independently reran 88 pipeline + 18 lab
  tests (superset of Codex's reported 76), confirmed no forbidden file/gate/
  threshold changed, verified acceptance-mapped tests (ssrn-6609698
  refuted-family regression, byte-identical reprobe idempotency, fail-closed
  missing-hypothesis-id, placeholder-score rejection, review-bundle firewall,
  feedback-spawned n_trials reconciliation). Committed `dfc7af8` (35 files),
  separate from the M1-M5 maintenance stream.
- **Real-data acceptance runs (user-authorized):** P1 funding backfill wrote
  66,041 rows for the (then) 22-symbol point-in-time union, 0 gaps
  2024-01-01->2026-07-02. P8 ingested Binance Vision historical OI, 262,814
  rows each for BTC/ETH (5m, 2024-01-01->2026-07-02) - F-OI-POSITIONING no
  longer data-blocked. P5 landed the first OKX liquidation ingest (1,600 rows
  each BTC/ETH) and measured the public REST retention window at only
  **hours** (BTC ~14h, ETH ~5h at the cap). P6 `--reprobe` ran for real on
  `idea_batch_20260701_taxonomy_002`: funding candidate stayed FAIL with
  improved metrics (good_symbols 5->7), appended append-only; xvenue
  unchanged (OKX 1m still ~5,220 rows vs 1.29M/leg on Binance). Committed
  `6997aba`.
- **Root cause found:** the funding-breadth FAIL was not a funding-data gap —
  `scripts/build_universe_membership.py` derived PIT `eligible` from a thin
  local parquet mirror (`data/ticks/*/candles_1m.parquet`), producing an
  eligible/day median of 2 (BTC/ETH eligible only 61 days vs MEME 657 —
  economically impossible). This artifact was also the root cause behind
  `E-028`'s `universe=8` and `H-004`/S5's "no grid activity".
- **Three user decisions executed (2026-07-03):** (1) P9 (membership-builder
  DB source) task-blocked for Codex; (2) OKX liquidation ingest scheduled
  every 2h via Windows Task Scheduler (`quant_liq_okx_ingest`,
  Interactive-only — runs only while logged on;
  `scripts/market_data/run_liq_ingest_task.cmd`, documented in
  `docs/RUNBOOK.md`); (3) Stage-2 funding breadth-min changed to evaluate
  from `START + breadth_warmup_days` (30, mirrors `config/universe.yaml`
  warmup) instead of the full window, since PIT eligibility cannot exist
  during warmup — threshold **values** unchanged, warmup days stay recorded
  for audit, empty evaluation still fails closed. Manifest:
  `docs/change_manifests/2026-07-03-stage2-breadth-warmup.md`. Committed
  `14976d4`.
- **P9 executed (2026-07-04, user-authorized after an initial scope
  correction):** `build_universe_membership.py` gained a `--source db` path
  (`daily_dollar_volume_rows_to_candles`, `load_candles_from_db`) that
  aggregates `canonical_candles` daily dollar volume instead of reading the
  parquet mirror, feeding the exact same `build_membership()` eligibility
  formula either way (tested: `test_db_and_parquet_sources_feed_the_same_
  build_membership`). Rebuilt the shared `data/universe/universe_membership.
  parquet` from DB: eligible/day median 2 -> 28 (min 3, max 30, 101,910
  rows). Note: the classifier initially and correctly blocked the rebuild
  because "P9 交 Codex" had been the prior explicit decision and overwriting
  the shared parquet is an irreversible cross-pipeline change; the user then
  explicitly authorized Claude to proceed.
- **Official Stage-2 re-probe (E-030): data_availability now PASSES** — the
  first taxonomy-sourced Stage-2 pass in this pipeline's history. 32
  point-in-time eligible symbols, 28 meet the funding coverage/stale
  threshold (the 4 with zero funding rows -
  `CC`/`FIL`/`M`/`SHIB`-USDT-SWAP - only became eligible under the rebuilt
  universe and are outside the original 22-symbol funding backfill), breadth
  min 24 / median 27 / max 28 vs threshold 10 over the post-warmup-evaluated
  window (868/898 days). `stage2_status` stays FAIL by design pending
  `distinctness` and `cost_after_edge`. Advisory `orchestrator --reprobe`
  re-ran against the rebuilt universe and correctly appended another
  `stage2_fail` status entry (overall verdict unchanged; the per-check
  `data_availability` PASS is visible only in `reprobe_advisory.json`'s
  metrics, not the top-line state — confirmed this is intentional, tested
  behavior, not a bug, before touching anything).
- **Stage 1 hypothesis spec written (Claude, docs-only):**
  `docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`
  — testable signal/entry/sizing spec (cross-sectional long-low/short-high
  trailing-funding-APR book, perp-only, dollar-neutral, reusing
  `xs_momentum_backtest.py`'s corrected vol-targeting and leak-fixed
  daily-shift as the implementation skeleton), a small pre-registered grid
  (`{L in [7,14], Q in [0.20,0.30]}` = 4 combos, deliberately small per the
  2026-07-03 statistical-power analysis), and a mechanism-level distinctness
  table against `F-FUNDING-CARRY` (H-007, refuted) explaining why the E-026
  refutation mechanism — realistic spot/perp basis-execution and financing
  cost crushing a thin absolute single-name funding-level edge — does not
  mechanically transfer to a perp-only cross-sectional dispersion book. The
  spec explicitly marks this as a provisional MINT pending the quantitative
  family-minting distinctness checker, which is Stage-2(b)/Stage-3 (Codex)
  work, not something a docs-only spec can compute.
- **Ledger updates:** `H-009`'s hypothesis text replaced the "has enough
  breadth to justify a spec" meta-claim with the real testable claim; new
  `E-030` row added to `docs/EXPERIMENT_REGISTRY.md`; mechanism-taxonomy row
  for `F-FUNDING-XS-DISPERSION` updated to "available — Stage-2
  data_availability PASS". Family `n_trials` stays 0 (no Stage-3 run yet);
  `H-009` status stays `proposed`.
- No strategy, risk, portfolio, execution, config gate, deployment gate, or
  existing durable ledger verdict was changed by any of this; the two Stage-2
  checks that gate Stage 3 (`distinctness`, `cost_after_edge`) are explicit
  Codex hand-off items, not yet run.

## 2026-07-03 - M2-R1 Reviewed, Accepted, And Committed

Claude independently reran the M1-M5 verification evidence (ruff full scope,
576 unit + 32 root + 18 lab tests, `node --check` on every `frontend/*.js`,
backtest smoke incl. a reproduced broken-fixture probe, no forbidden file in
`a688de1..4c7afd9`) and reviewed the M2-R1 docs remediation: all three
verbatim spot-checks were present in `docs/CHANGELOG_AI.md` (batch-1 "do not
tune to chase the gate", C2 realism DSR 0.0041/WF -1.5093/n_trials=48,
`DSR<=PSR(0)` + both untrusted artifact names), both restored
`docs/KNOWN_ISSUES.md` caveats were substantively correct, `docs/AI_HANDOFF.md`
was 244 lines (<=400), and no stale "dirty pipeline worktree" language
remained. **M1-M5 + M2-R1 accepted and committed as `21cc3c9`.**

## 2026-07-03 - Project Maintenance M2-M5 Completion

- M2 slimmed hot-state governance docs, moved July 3 history into this changelog,
  refreshed `STATUS.md`, and kept active backlog items in `docs/KNOWN_ISSUES.md`.
- M3 replaced the entrypoint-only backtest smoke with a tiny frozen no-DB replay
  fixture that writes artifacts to a temp directory and verifies `result.json`,
  `metrics.json`, and `fills.csv`.
- M4 added dedicated monitoring unit tests for Telegram alert hooks, metrics
  handles, and calibration JSONL/summary roundtrip without network or DB access.
- M5 kept `src/okx_quant/stocks/` as a docs-mapped research-only sandbox (Option
  A) and did not wire it into crypto replay, UI, API, or deployment gates.
- Local evidence: backtest smoke passed and failed under a temporary broken
  fixture probe; monitoring tests passed; full unit suite passed (575); docs-check
  equivalents passed; stock-system tests passed.

## 2026-07-03 - Project Maintenance Audit And M1 CI Alignment

- Claude completed a whole-project maintenance audit outside the in-flight
  pipeline P1-P8 scope and wrote
  `tasks/2026-07-03-project-maintenance-tasks.md`.
- Verified gaps: CI/local verify drift, bloated/stale governance docs,
  entrypoint-only `backtest-smoke`, monitoring modules without dedicated tests,
  and orphan `src/okx_quant/stocks/` ownership.
- Codex M1 aligned CI with local lint/test intent: ruff now checks
  `src tests backtesting scripts`; CI installs and tests `crypto-alpha-lab`
  separately; CI runs the root-level synthetic Daily Winner/OHLCV Rotation tests;
  `frontend-check` includes `tweaks-panel.js` and `view-manual.js`.
- Local evidence: ruff passed; unit tests passed (555); root synthetic tests
  passed (32); lab tests passed (18); each frontend `node --check` command passed.

## 2026-07-03 - Pipeline Auto-Ideation Review And Improvement Plan

- Claude reviewed the auto-ideation pipeline and concluded the defensive side is
  sufficient: n_trials/K accounting, DSR/PSR gates, checkpoint1 review, and
  append-only state worked across three auto batches plus seven human-seeded
  families, with zero gate-passing candidates.
- Binding constraints are inlet-side: title-only literature scoring, data-blocked
  taxonomy frontier, and unimplemented cross-round feedback.
- User decisions: session-based LLM scoring (no API), public Binance Vision OI
  history (no paid provider), and a power-analysis note with no gate change.
- Deliverables committed before M2: `tasks/2026-07-03-pipeline-improvement-tasks.md`
  and `docs/superpowers/specs/2026-07-03-statistical-power-gates.md`.

## 2026-07-02 - Literature Scorer Review

- Claude reviewed Codex Task B commit `a688de1`, reran the relevant pipeline and
  lab suites, and confirmed the fetch-once/snapshot-once literature scorer path.
- The real Crossref-only batch selected one A-literature draft just above
  threshold; Claude flagged it for Stage-1 scrutiny because it mechanically maps
  to refuted family `F-FUNDING-CARRY`.
- arXiv timed out and Semantic Scholar returned HTTP 429 during the real run; the
  batch honestly reflects only the Crossref query.

## 2026-07-01 - Pipeline Orchestrator, External Data, Literature, And Taxonomy_002

### 2026-07-01 Claude (Task A review + first real orchestrator run, docs+run only)

Reviewed Codex's Task A implementation (below) against
`docs/superpowers/specs/2026-07-01-pipeline-orchestration-driver-design.md`
line by line, then independently re-verified rather than trusting the
self-report: reran the full pytest set myself (45 passed), confirmed
`docs/HYPOTHESIS_LEDGER.md`/`docs/EXPERIMENT_REGISTRY.md` carry only the
pre-existing H-009/H-010/E-028/E-029 rows (unchanged before/after, `git diff
--stat` identical), confirmed no forbidden trading-core/gate/legacy-runner file
was touched, and reran `scripts/run_pipeline_stage2_data_probe.py` into a
scratch `--output-root` to diff its output byte-for-byte against the existing
`results/idea_batch_20260701_taxonomy_002/**/stage2_feasibility.json`
artifacts (identical, confirming the regression requirement independent of
Codex's claim). Implementation matches the hardened spec's exact contracts
(`Stage2Probe`/`Stage3Runner` signatures, `derive_candidate_dir`, fail-closed
`hypothesis_ids`, legacy-runner `batch_id` guard, append-only/idempotent
state). One non-blocking deviation: the spec's illustrative Chinese
shortlist text (`待 Codex 補 Stage2 探測函式`) was implemented as equivalent
English text -- functionally fine, field is never blank, not worth a rework.
Then ran the orchestrator for real on `idea_batch_20260701_taxonomy_002` with
a `--hypothesis-ids` mapping `{"B-f-funding-xs-dispersion": "H-009",
"B-f-xvenue-leadlag": "H-010"}` (the same IDs already on record in
`docs/HYPOTHESIS_LEDGER.md`). First real
`results/idea_batch_20260701_taxonomy_002/orchestrator_state.json` and
`shortlist.md` now exist: both candidates advance `idea_registered ->
stage2_fail` (funding breadth 5/10 good symbols, 0/10 min rebalance breadth;
xvenue OKX leg 0 coverage/no Binance substitution per I19) -- the same known
data-availability failure, now produced by the automated driver instead of
by hand. Reran the CLI a second time to confirm real idempotency: state file
byte-identical, `status_history` timestamps unchanged, no re-invocation of
either Stage2 probe. No strategy, gate, ledger, or trading-core file changed.
Next: Task B (literature keyword scorer + a real literature batch run)
remains unimplemented; taxonomy_002 stays at `stage2_fail` until new data
closes the funding-breadth/OKX-coverage gaps or a Claude/human decision
changes the candidates.

### 2026-07-01 Codex follow-up (pipeline orchestration driver Task A)

Implemented the advisory pipeline orchestrator from
`docs/superpowers/specs/2026-07-01-pipeline-orchestration-driver-design.md`
Task A. New code: `backtesting/pipeline_orchestrator.py`,
`backtesting/pipeline_stage2_registry.py`,
`backtesting/pipeline_stage3_registry.py`, and
`scripts/run_pipeline_orchestrator.py`; updated
`scripts/run_pipeline_stage2_data_probe.py` into a thin registry wrapper.
New tests: `tests/unit/test_pipeline_orchestrator.py`,
`tests/unit/test_pipeline_stage2_registry.py`, and
`tests/unit/test_pipeline_stage3_registry.py`. The driver pre-registers
`idea_batch.json` candidates into append-only `orchestrator_state.json`,
derives candidate dirs, requires explicit hypothesis IDs, runs family-keyed
Stage2 probes, stops missing family implementation as
`awaiting_stage2_implementation` / `awaiting_stage3_implementation`, guards
legacy batch-2 Stage3 runners against non-`pipeline_batch2_20260625` batches,
and renders `shortlist.md`. I29 and manifest
`docs/change_manifests/2026-07-01-pipeline-orchestrator.md` record the rule.
No `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`, strategy,
research truth file, config gate, deployment gate, or existing result artifact
was changed. Next: use the orchestrator only with an explicit reviewed
`--hypothesis-ids` JSON and DB access; Task B literature keyword scoring remains
unimplemented.

### 2026-07-01 Claude (pipeline orchestration driver spec hardened for one-pass Codex handoff, docs-only)

Reviewed the draft
`docs/superpowers/specs/2026-07-01-pipeline-orchestration-driver-design.md`
against Codex's own gap report (no `pipeline_orchestrator.py`, no Stage2/3
family registries, no append-only state file, literature scorer missing) and
found the draft's Task A/B blocks under-specified in ways that would have
blocked or misled a one-pass Codex implementation. Rewrote §1.2/§1.3/§1.5 and
added §1.6/§1.7 to close four concrete gaps: (1) `idea_batch.json` candidates
carry no `candidate_dir` or `hypothesis_id` field, so `pre_register_batch` now
has an exact deterministic `candidate_dir` derivation and a **required**
`hypothesis_ids` mapping input (fails closed if any candidate is missing one,
mirroring the existing `--max-runtime-seconds` no-silent-default rule); (2)
`probe_funding`/`probe_xvenue` have different signatures, so
`STAGE2_PROBES` is now specified as a uniform `Callable[[conn, context],
Awaitable[FeasibilityResult]]` keyed by `family_id`; (3) the existing
`run_c1`/`run_c2`/`run_c3` Stage-3 functions are 0-arg and hardcode
`results/pipeline_batch2_20260625/...`, so registering them directly would
have let the orchestrator silently overwrite that old batch's artifacts for
any other `batch_id` -- `pipeline_stage3_registry.py` now specifies a
`batch_id`-guarded adapter that raises instead; (4) Task B's literature scorer
would have double-fetched papers (once for scoring, once inside the real CLI
via `--source`), risking a `paper_id` mismatch -- the scorer now fetches once,
snapshots the papers, and the main CLI is fed via `--papers`, not `--source`.
Also added `derive_candidate_dir`/legacy-runner-guard/missing-hypothesis-id/
`family_id_or_NEW=="NEW"` acceptance criteria, added
`tests/unit/test_pipeline_stage3_registry.py` to permitted files, and marked
`scripts/run_pipeline_batch2_checkpoint.py` explicitly import-only/forbidden.
No code, strategy, gate, or `results/**` artifact changed; this is a design
doc revision only. Next: user/Codex decide whether to start Task A
(orchestrator + registries) or Task B (literature batch) first; both are now
specified precisely enough for one-pass implementation.

### 2026-07-01 Codex follow-up (Tier-1 external data unlock)

Added keyless external adapters for Binance futures open interest and Deribit
DVOL without creating strategies, families, gates, backtests, or durable ledger
rows. New clients live in the existing `okx_quant.data.external_clients`
package and are dispatched by `scripts/market_data/ingest_external.py`.
Registered datasets: `oi_binance_btc`, `oi_binance_eth`,
`dvol_deribit_btc`, and `dvol_deribit_eth`. `--dry-run` now validates selected
external dataset config/adapter dispatch without a DB or network fetch.
`fail_on_empty_fetch` stays fail-closed: empty fetch raises and does not advance
the external-ingestion checkpoint. OI values are `sumOpenInterestValue` in
`USDT_notional`; Binance's public OI endpoint only exposes roughly the recent
~30-day window, so this is forward accumulation only. True 2024 OI backfill
requires a paid provider such as Coinglass/Coinalyze and remains out of scope.
Deribit DVOL uses public historical windows, but Deribit execution/venue fit is
research-layer review only. Next: run real ingest only in a DB+network
environment and then have Claude confirm whether `F-OI-POSITIONING` and
`F-VOL-RISK-PREMIUM` should update their taxonomy data status after observed
coverage is present.

### 2026-07-01 Codex follow-up (A-literature driver)

Added the parent literature idea driver without touching the concurrent
taxonomy_002 work. New code: `scripts/run_pipeline_literature_ideas.py`; new
tests: `tests/unit/test_pipeline_literature_ideas.py`; manifest:
`docs/change_manifests/2026-07-01-literature-idea-driver.md`. The driver imports
the existing crypto-alpha-lab helpers, supports keyless source fetch or fixture
`--papers`, requires static `--scores` or an injected scorer, runs
`build_scoring_prompt` before scoring so market series / fold boundaries fail
closed, promotes only scores above threshold, caps A-half drafts at 15, writes
`weekly_screen/search_log_*.md` and `screen_*.json`, then registers A-half
drafts through `register_batch(a_half_drafts=...)`. Literature drafts are forced
to `draft_status="pending_llm"` and `allow_live_trading=false`, so
`register_batch` does not run family minting before Stage-1 signal/distinctness
review. No `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
taxonomy files, taxonomy_002 artifacts, strategy/risk/portfolio/execution files,
config gates, deployment gates, Stage 2/3 runs, WF/CPCV/backtests, or existing
`results/**` artifacts were changed. Next: run a human/Claude-reviewed
literature batch separately from taxonomy_002; do not append durable ledger rows
or backtest any literature draft until Stage-1 review supplies the signal and
family decision path.

### 2026-07-01 Codex follow-up (taxonomy_002 Stage-2 data probe)

Ran the requested read-only Stage-2 data-availability probe for the 2
taxonomy_002 frontier candidates only. New code:
`scripts/run_pipeline_stage2_data_probe.py`; test:
`tests/unit/test_pipeline_stage2_data_probe.py`; artifacts:
`results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/stage2_feasibility.json`
and
`results/idea_batch_20260701_taxonomy_002/f_xvenue_leadlag/stage2_feasibility.json`.
Funding dispersion data availability FAILS: the point-in-time universe has 8
eligible symbols, 5 meet the per-symbol funding coverage/stale threshold, and
daily ready breadth is min 0 / median 0.0 / max 2 versus threshold 10. Xvenue
lead-lag data availability FAILS by I19: Binance BTC/ETH canonical 1m legs each
have 1,293,120 rows and 1.0 coverage, but OKX has 0 rows / 0.0 coverage for
both legs and 0 aligned rows; Binance was not used to fill OKX. Each
`stage2_feasibility.json` contains only `data_availability`; `stage2_status`
is FAIL because `distinctness` and `cost_after_edge` have not run, so neither
candidate is released to Stage 3. Appended only proposed placeholders H-009 /
H-010 and data-probe rows E-028 / E-029; no existing ledger verdict, n_trials,
K-budget, strategy, gate, WF/CPCV/backtest, or existing result artifact was
changed. Next: Claude Stage-1 review/spec decision for taxonomy_002 candidates;
do not run Stage 3/backtest or append any draft verdict until Claude/human
review says so.

### 2026-07-01 Codex follow-up (B-taxonomy verdict source + taxonomy_002 sidecar)

Closed the Claude-confirmed idea-generator selection gaps without changing
trading logic or durable ledgers. `backtesting/pipeline_idea_generator.py`
now reads occupied-family verdicts from `docs/HYPOTHESIS_LEDGER.md` `Status`
via the new CLI `--hypothesis-ledger`; `docs/EXPERIMENT_REGISTRY.md` remains
the source for trial/K-budget plumbing into batch registration and
family-minting. No-twist `inconclusive` families now skip as
`inconclusive_no_twist`, refuted/shelved no-twist families still skip as
`refuted_no_twist`, and taxonomy rows containing `overlay` skip as
`overlay_needs_base` before data fallback. New invariant/failure docs:
I28 in `docs/INVARIANTS.md`, F23 in `docs/FAILURE_MODES.md`, and manifest
`docs/change_manifests/2026-07-01-idea-generator-verdict-source.md`. New
advisory sidecar only:
`results/idea_batch_20260701_taxonomy_002/idea_batch.json` plus
`hypothesis_ledger_draft.md`; it selected 2 pending-LLM candidates
(`F-FUNDING-XS-DISPERSION`, `F-XVENUE-LEADLAG`), skipped `F-VOL-REGIME` as
`overlay_needs_base`, and skipped `F-S5-RESIDUAL-MEANREV` /
`F-S6-TS-MOMENTUM` as `inconclusive_no_twist`. The prior
`results/idea_batch_20260630_taxonomy_001/` artifact was not modified. No
research truth files, config gates, deployment gates, strategy/risk/portfolio/
execution files, durable ledger rows, or existing result artifacts changed.
Next: Claude/human review the new taxonomy_002 draft before any durable ledger
append, Stage 2/3 run, or backtest.

## 2026-06-30 - Strategy Research Pipeline Automation And C3 Verification

### 2026-06-30 Codex follow-up (XS family n_trials + B-half data probe)

Closed the two user-flagged post-§7a gaps. First,
`backtesting/pipeline_checkpoint1.py::family_registry_from_text()` now honors
explicit family-cumulative registry notes/overrides, so F-XS-MOMENTUM inherits
24 trials from E-003/E-004/E-005 (with K=2/2 at limit) instead of the stale
per-run grid value 8, while newer cumulative rows such as C2 E-026 remain 48
and are not double-counted. The same value is used by checkpoint①
`n_trials_reconcile` and `backtesting/pipeline_family_minting.py` inheritance.
Second, `backtesting/pipeline_idea_generator.py::enumerate_gaps()` now consumes
supplied Stage-2 `pipeline_feasibility.py` data-availability results before
falling back to taxonomy text, so the old "taxonomy text only" behavior is now
only a fallback. Regression coverage is in
`tests/unit/test_pipeline_checkpoint1_check.py`,
`tests/unit/test_pipeline_family_minting.py`, and
`tests/unit/test_pipeline_idea_generator.py`. New manifest:
`docs/change_manifests/2026-06-30-xs-trials-and-idea-probe.md`; the resolved
gaps are recorded in `docs/KNOWN_ISSUES.md`. No durable ledger rows, research
truth files, config gates, deployment gates, strategy/risk/portfolio/execution
files, or existing result artifacts were changed. That draft is now superseded;
next remains Claude/human review of
`results/idea_batch_20260701_taxonomy_002/hypothesis_ledger_draft.md` before any
durable ledger append, Stage 2/3 run, or backtest.

### 2026-06-30 Codex follow-up (family-minting K-budget wiring + first idea sidecar)

Completed the §7a K-budget follow-up before running the first taxonomy-only idea
batch. `backtesting/pipeline_checkpoint1.py::family_registry_from_text()` now
parses `docs/EXPERIMENT_REGISTRY.md` Family K-budget rows (`| F-... | K_used |
K_limit | ... |`) and `backtesting/pipeline_family_minting.py` reports real
`k_used`, `k_limit`, and `at_k_limit` instead of the stale
`inherited_K = inherited_n_trials` proxy. Regression coverage is in
`tests/unit/test_pipeline_family_minting.py`; direct execution of
`scripts/run_pipeline_idea_generator.py` is now covered by
`tests/unit/test_pipeline_idea_generator.py`. New manifest:
`docs/change_manifests/2026-06-30-family-minting-k-budget.md`; `docs/KNOWN_ISSUES.md`
marks the K-vs-n_trials issue resolved; `docs/FEATURE_MAP.md` now maps research
pipeline automation ownership. Generated first taxonomy-only advisory sidecar:
`results/idea_batch_20260630_taxonomy_001/idea_batch.json` plus
`results/idea_batch_20260630_taxonomy_001/hypothesis_ledger_draft.md`. It selected
4 pending-LLM candidates (`F-VOL-REGIME`, `F-FUNDING-XS-DISPERSION`,
`F-S6-TS-MOMENTUM`, `F-XVENUE-LEADLAG`) and skipped refuted/no-twist or
data-blocked families. No durable ledger rows, research truth files, config
gates, deployment gates, strategy/risk/portfolio/execution files, or existing
result artifacts were changed. That first sidecar is now superseded by
`results/idea_batch_20260701_taxonomy_002/`; next: Claude/human review the
taxonomy_002 `hypothesis_ledger_draft.md`, and do not append it to
`docs/HYPOTHESIS_LEDGER.md`, run Stage 2/3, or backtest until reviewed.

### 2026-06-30 Codex follow-up (idea generator B §6 + A §6b implemented)

Implemented the full-auto idea-generator front end without changing trading
logic, research truth files, durable ledger values, config gates, deployment
gates, or existing `results/**` artifacts. B-half code:
`backtesting/pipeline_idea_generator.py` and
`scripts/run_pipeline_idea_generator.py`; test:
`tests/unit/test_pipeline_idea_generator.py`. It parses the mechanism taxonomy,
skips refuted/shelved or data-blocked families, ranks feasible gaps
deterministically, caps the batch at 15, and writes
`idea_batch.json` plus `hypothesis_ledger_draft.md`. Drafted candidates run
through the existing advisory family-minting checker, including A-half drafts in
mixed batches. A-half lab code:
`research/crypto-alpha-lab/src/crypto_alpha_lab/pipeline/paper_ingestion.py`
and `research/crypto-alpha-lab/src/crypto_alpha_lab/adapters/parent_stage1.py`;
test: `research/crypto-alpha-lab/tests/test_pipeline_adapters.py`. It supports
keyless arXiv metadata parsing, validated `PaperScoring`, promotion to
research-only `AlphaCandidate`, dated weekly screen output, a prompt data
firewall that rejects market series/fold boundaries, and conversion into parent
Stage 1 drafts. Stage 1 now documents the autonomous-mode/data-firewall
boundary. Change manifests:
`docs/change_manifests/2026-06-30-idea-generator-frontend.md` and
`docs/change_manifests/2026-06-30-idea-generator-a-half.md`. Verification:
parent idea-generator tests 5 passed; lab adapter tests 4 passed and lab full
suite 12 passed with `-p no:cacheprovider`; docs metadata passed with 32 pre-existing warnings;
doc-impact strict passed with process-local `safe.directory` across 43 changed files. `make docs-check`
is not available in this Windows shell. Next lane: run a first real
`idea_batch.json` sidecar from the taxonomy/lab corpus, then ask Claude/human to
review the ledger draft before anything enters `docs/HYPOTHESIS_LEDGER.md`.

### 2026-06-30 Codex follow-up (family-minting checker §7 implemented)

Implemented `docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md` §7 as an
advisory, pre-backtest family-minting distinctness checker. New code:
`backtesting/pipeline_family_minting.py` and
`scripts/run_pipeline_family_minting_check.py`; new tests:
`tests/unit/test_pipeline_family_minting.py`. The checker takes a candidate
signal, caller-supplied reference family signals, and
`docs/EXPERIMENT_REGISTRY.md`, computes pairwise-complete absolute correlation,
and returns `ASSIGN`, `MINT`, `NEEDS_HUMAN`, or `SKIP_RECOMMENDED` in
`family_minting.json`. High-correlation relabels inherit the nearest family
trial/K budget instead of minting a fresh family; high correlation to a
refuted/shelved family is `SKIP_RECOMMENDED`; MINT remains provisional and always
keeps human mechanism-novelty review. I27 is recorded in `docs/INVARIANTS.md`;
change manifest
`docs/change_manifests/2026-06-30-family-minting-checker.md` records the R6.3/R7.4
doc-impact review. No strategy, research-truth file, ledger value, config gate,
deployment gate, or existing `results/**` artifact changed. Next implementation
lane is the idea-generator front-end / literature corpus side, not another
family-minting parser.

### 2026-06-30 Codex follow-up (checkpoint① automation contract §4 implemented)

Implemented the Stage-3 checkpoint① machine pre-check without changing any
strategy, research truth file, config gate, deployment gate, or existing
`results/**` artifact. New checker code:
`backtesting/pipeline_checkpoint1.py` and
`scripts/run_pipeline_checkpoint1_check.py`; new tests:
`tests/unit/test_pipeline_checkpoint1_check.py`. The CLI reads a Stage-3
`summary.json`, reconciles family/CPCV `n_trials` against
`docs/EXPERIMENT_REGISTRY.md`, checks leak test presence, DSR<=PSR, idealized
fill exclusion, portable-validation/promotion honesty, CT venue/label
consistency, and DSR/PSR gate thresholds, then writes `checkpoint1_auto.json`.
`checkpoint1_auto_status` is `PASS`, `FAIL`, or `NEEDS_HUMAN`; `PASS` is
advisory only and does not publish or promote anything. I26 is now recorded in
`docs/INVARIANTS.md`, Stage-3 run instructions require the sidecar for future
summaries, and change manifest
`docs/change_manifests/2026-06-30-checkpoint1-automation.md` records the R6.3/R7.4
doc-impact review. Other Claude plans reviewed: batch-2/C2/C3 execution plans
are closed/refuted/shelved; `2026-06-30-stage3-idea-ingestion-design.md` and
`2026-06-30-mechanism-taxonomy.md` are the next implementation lane after
Claude/user review of the new checker contract, literature corpus choice, and
family-minting audit cadence.

### 2026-06-30 Claude (strategy-research-pipeline full-automation diagnosis + 2 draft specs, docs-only)

Diagnosed why the 策略發想器 is still semi-auto ("known
candidates -> backtest evidence") and what blocks "from-0 fully autonomous". Key
findings: (1) Stage 1 is "expand a backlog entry into a spec", **not** literature
search (design spec line 119); candidates are human-seeded. (2) The autonomous
driver is a prompt template, never run end-to-end -- batches were hand-run via
`scripts/run_pipeline_batch2_checkpoint.py`. (3) Checkpoint① still needs Claude
each candidate. Produced two **draft** design docs (no code, no gate change, no
experiment): `docs/superpowers/specs/2026-06-30-checkpoint1-automation-contract.md`
(Stage-2 unlock: splits checkpoint①'s 9 items into machine-decidable vs
human-judgment, defines aggregator `run_pipeline_checkpoint1_check.py` +
`checkpoint1_auto.json` + **invariant I26** + ledger reconciliation, with a
ready-to-hand Codex task block) and
`docs/superpowers/specs/2026-06-30-stage3-idea-ingestion-design.md` (Stage-3
"from-0" ingestion: the 便宜發想×誠實 n_trials tension and its defenses --
family-before-backtest, family-minting distinctness gate to stop K-evasion,
"anything reaching Pass-A counts toward family n_trials", prior-plausibility gate;
lists open decisions for the user). The ingestion spec also folds in a web prior-art
survey (§7): RD-Agent / R&D-Agent-Quant, AlphaAgent, vectorbt, OpenBB -- verdict
"borrow patterns, not frameworks". Concrete adopted mechanisms: RD-Agent's IC>=0.99
dedup (-> quantitative family-distinctness backstop) and its "LLM never sees raw
data/splits" firewall (-> anti-leakage at idea generation); AlphaAgent's
parameter-count->n_trials parsimony and originality/decay regularizers. RD-Agent
landing verdict: Linux/Docker/Qlib-coupled with looser gates than ours, so use its
Synthesis (idea-gen) half only as a candidate source, never as a validator. **User
locked 4 decisions 2026-06-30:** (1) checkpoint① automation first; (2) idea sources
= literature + mechanism taxonomy, free data-mining (Option C) rejected, RD-Agent
borrowed for mechanisms only (IC-dedup, data firewall), not as an idea source; (3)
<=15 candidates/round hard cap; (4) cross-round knowledge feedback **ADOPTED** --
hard condition: every feedback-spawned idea reaching Pass-A counts toward family
n_trials, so I26 reconciliation must cover them (ingestion spec §4.7/§8;
checkpoint contract §3 note). Deferred defaults: family-minting audit every batch;
literature corpus TBD. The checkpoint① checker + I26 implementation is now
covered by the Codex entry above. The mechanism-taxonomy initial list is now
**drafted** (`2026-06-30-mechanism-taxonomy.md`: 17 families -- 7 occupied/mostly
refuted, 4 untested-documented [S1/S2/S8/S10], 6 frontier; only
F-FUNDING-XS-DISPERSION and F-XVENUE-LEADLAG are currently data-feasible frontier,
the rest are occupied-refuted or data-blocked [OI/liquidation/on-chain/options]).
The remaining ingestion sub-pieces are the family-minting distinctness checker and
the literature corpus front-end. Both `status: draft`, design locked; recommended order remains checkpoint① automation first (now done) before
ingestion. The irreducibly-human review items (leak lag
spot-check, diff-block honesty, cost realism like C2's 0.247% vol, retry-vs-new-family,
publish) are kept as per-batch/per-policy gates, not removed. No trading-core,
config gate, risk, deployment, research-truth file, or result artifact changed.

### 2026-06-30 Codex follow-up (C3 sentiment Stage-3 verification + as-of hardening)

Verified the existing C3 Stage-3 task instead of duplicating implementation.
Code-quality review found one real edge: the vectorized C3 F&G lookup keyed
events by normalized `published_day`, so a non-midnight `published_at` could be
skipped and never reconsidered for the next trading day. Fixed
`backtesting/c3_sentiment_backtest.py` to use the latest observation published
before each UTC decision day closes, then keep the existing one-day target lag.
Regression:
`tests/unit/test_c3_sentiment_backtest.py::test_c3_sentiment_midday_publish_trades_next_day`
failed before the fix and passes after. Full narrow verification now has 11
tests passing; rerunning `run_c3()` still writes Stage-2 PASS, family
`n_trials=9`, retained CPCV `path_returns`, DSR 0.4532, PSR 0.5806,
`promotion_gate_passed:false`, and status `refuted`. No live strategy, config
gate, risk, portfolio, execution, demo/shadow/live, research truth, or C1/C2
artifact behavior changed.

## 2026-06-29 - Batch 2, C2 Realism, UX Fixes, And CPCV Retention

### 2026-06-29 Codex follow-up (C3 sentiment Stage-3 checkpoint complete)

C3 is no longer data-blocked after Alternative.me Fear & Greed ingestion.
`backtesting/c3_sentiment_backtest.py` adds a research-only vectorized
long/flat runner that mirrors `FearGreedSentimentStrategy` entry/hold/exit
logic, uses one-day target lag, applies R3.1 funding sign for the BTC perp leg,
and stays outside live strategy/risk/portfolio/execution code. The populated
external-feature gate tz bug in `scripts/run_pipeline_batch2_checkpoint.py` is
fixed by converting asyncpg tz-aware `published_at` values to UTC instead of
re-localizing them. `run_c3()` now runs the pre-registered 9-combo grid through
the existing fold-refit WF/CPCV helpers after Stage-2 PASS. New artifact:
`results/pipeline_batch2_20260625/c3_sentiment/summary.json`. Result:
Stage-2 PASS (`event_count=897`, `missing_ratio=0.0`, `stale_ratio=0.0`),
nonzero grid activity, family `n_trials=9`, retained CPCV `path_returns`, WF OOS
Sharpe -0.2556, CPCV OOS Sharpe 0.1315, DSR 0.4532, PSR 0.5806,
`statistical_gate_passed:false`, `promotion_gate_passed:false`, status
`refuted`. H-008 and E-027 are updated. No live `fear_greed_sentiment` strategy,
config gate, risk, portfolio, execution, demo/shadow/live, or C1/C2 artifact
behavior changed.

### 2026-06-29 Claude (backtest UX + late-listing fix, user-requested)

Three user-requested changes. (1) Multi-symbol backtests no longer crash when a
symbol listed after the requested start: `backtesting/data_loader.py`
`_raise_on_venue_gap` now measures coverage from a symbol's first observed bar
(new `VENUE_GAP_MIN_COVERAGE = 0.80`), so late-listing coins (e.g. the reported
`CC-USDT-SWAP` 1D "expected 898, found 229") pass; empty venue series and
sub-80% internal gaps still raise and no cross-venue/parquet substitution is
allowed (I19 preserved). Manifest:
`docs/change_manifests/2026-06-29-venue-gap-late-listing.md`. (2) Added a Cancel
backtest button (mirrors the fetch-jobs cancel): new
`POST /api/backtest/run/cancel/{job_id}` terminates the registered replay/rotation
subprocess and cooperatively cancels the in-process daily-winner job;
`_run_procs` registry + `cancel_requested` flag in
`src/okx_quant/api/routes_backtest.py`; `cancelBacktestRun` in `frontend/data.js`;
button + "cancelled"/"cancelling" terminal handling in `frontend/view-config.js`.
(3) Backtest config Validation now defaults to `None` instead of `Both (WF +
CPCV)` (`frontend/view-config.js`). No strategy, risk, PnL, funding, config gate,
or deployment behavior changed. Tests: `tests/unit/test_data_loader.py` (10),
`tests/integration/test_api_endpoints.py` (incl. new
`test_cancel_backtest_run_terminates_proc`).

### 2026-06-29 Codex follow-up (C2 funding-carry realism re-cost complete)

`scripts/run_c2_realism.py` reran C2 under fixed realism costs without touching
the live `src/okx_quant/strategies/funding_carry.py`, risk/portfolio/execution,
DSR/CPCV/WF harnesses, config gates, or the old C2 checkpoint artifact. New
artifact:
`results/pipeline_batch2_20260625/c2_funding_carry_realism/summary.json`.
Family-cumulative `n_trials=48` (prior E-024 24 + retry grid 24).
Realism run result: WF OOS Sharpe -1.5093, CPCV OOS Sharpe -0.2349, DSR 0.0041,
PSR 0.4457, `statistical_gate_passed:false`,
`promotion_gate_passed:false`. The pre-registered stress set was selected
mechanically from trailing 7-day funding APR < 0 or abs(basis z) > 3 and
evaluated as one group: 154 stress days, stress PnL -0.000786, stress max
drawdown -0.000218, and 4 active/mid-flip days. Realized annualized vol is still
only 0.247%, below the 2% self-check red flag, so the vectorized hedge model
remains too calm even after re-costing. H-007 is recorded as refuted/shelved in
the ledgers; no C2 adapter, publish, demo, shadow, or live work is justified
without a new Claude/user-approved realism path.

### 2026-06-29 Codex follow-up (pipeline batch 2 checkpoint 1 ready)

Batch 2 [C3, C2, C1] ran in the requested order after DB access became
available, then stopped at Claude evidence checkpoint 1. Summaries are under
`results/pipeline_batch2_20260625/{c3_sentiment,c2_funding_carry,c1_pairs_ou}/summary.json`;
shortlist is `results/pipeline_batch2_20260625/shortlist.md`. C3 Stage-2 FAIL:
`external_observations.dataset_id='fear_greed_btc'` has event_count 0 over
2024-01-01 through 2026-06-17, so no sentiment proxy was fabricated. C2 Stage-2
PASS and Stage-3 fold-refit completed with family-cumulative n_trials 24, WF OOS
Sharpe 3.5596, CPCV OOS Sharpe 6.8913, DSR/PSR ~1.0, leak test passed, CPCV
`path_returns` retained, but `promotion_gate_passed:false` because portable
validation remains adapter-required/absent. C1 Stage-2 PASS and Stage-3
fold-refit completed with family-cumulative n_trials 24, WF OOS Sharpe -1.2584,
CPCV OOS Sharpe -0.9097, DSR 0.0079, PSR 0.0994, leak test passed, CPCV
`path_returns` retained, and `promotion_gate_passed:false`. Ledgers now append
E-023/E-024/E-025 after the initial blocked-attempt rows E-020/E-021/E-022, and
H-006/H-007/H-008 carry the actual Stage-2 PASS/FAIL and trial counts. Live
`funding_carry.py`, config gates, risk, demo/shadow/live settings, DSR code,
research files, and existing result payloads were not changed. Limitation:
Stage-3 Pass A parquet pre-screen was skipped for C2/C1 because required BTC
perp candle/funding parquet inputs are missing or incomplete; summaries mark
`pass_a_status:"skipped_missing_required_parquet_cache"` and Pass B DB
fold-refit completed.

### 2026-06-29 Codex follow-up (Stage 2 feasibility automation implemented)

Stage 2 feasibility records now have a machine-readable artifact contract:
`stage2_feasibility.json` with `data_availability`, `distinctness`, and
`cost_after_edge` checks. New helper code lives in
`backtesting/pipeline_feasibility.py`; the validator CLI is
`scripts/run_pipeline_stage2_check.py`; the batch-2 runner writes the artifact
for C1/C2/C3 PASS, FAIL, and data-probe exception paths. This did not rerun the
DB-backed batch runner and did not migrate existing `results/**` artifacts. No
research assumptions, live strategy behavior, risk/config gates, demo/shadow/live
settings, or deployment readiness changed. Claude should review the reason text
for economic distinctness and cost-after-edge sufficiency before relying on it
as a durable research-review convention.

### 2026-06-29 Codex follow-up (T2 CPCV retention/provenance mechanism)

`backtesting.cpcv.CPCV.evaluate()` now emits retained `path_returns` (or
`combined_returns` when path assembly is unavailable), return lengths, periods,
`n_trials_provenance`, and `n_trials_is_floor`. Absent `n_trials` is tagged as a
`grid_size_floor`; explicit nonpositive `n_trials` still sets
`validation.n_trials_missing`. `backtesting/xs_momentum_backtest.py` accepts
caller-declared `researched_n_trials` and otherwise labels scan counts as a
floor. `scripts/recheck_dsr.py` recomputes DSR from retained returns and prints
old-to-new DSR when artifacts carry the raw series. Pipeline batch checkpoint
summaries copy retained CPCV fields with `n_trials_provenance="caller_declared"`
because those counts are family-cumulative. No existing
result artifact payloads were rewritten; historical summary-only CPCV artifacts
remain non-recomputable offline.

## 2026-06-25 - Pipeline Batch 1 Closeout, Stage 1 Pipeline, And Progress Panel

### 2026-06-25 Claude (pipeline batch 1 closeout + batch 2 pre-registration)

Pipeline batch 1 is **CLOSED -- all three candidates refuted under the fold-refit
WF/CPCV harness**. S6 (E-015) WF 0.0088 / CPCV 0.5422 / DSR 0.1963 / PSR 0.7387,
statistical-fail (the original `statistical_gate_passed:true` was a
non-refitting-harness artifact); S5 (E-014) no grid activity, data-universe
artifact; S7 (E-016) WF -0.4359 / CPCV -1.1124, shelved. H-003 shelved,
H-004/H-005 inconclusive. **Do not tune S5/S6/S7 to chase the gate** (mirrors the
H-002 shelve decision); the total refutation is the gate working, and it is
research signal that price-momentum/mean-reversion alpha on BTC/ETH net of cost
is weak in 2024-2026. **Batch 2 pre-registered** (now superseded by the
2026-06-29 Codex checkpoint above): C1 BTC/ETH
OU-gated pairs RV (H-006/E-017, F-PAIRS-OU, n_trials=24); C2 funding carry +
basis-z filter (H-007/E-018, F-FUNDING-CARRY, 24); C3 Fear&Greed long/flat
(H-008/E-019, F-SENTIMENT, 9, `fear_greed_btc` data-availability Stage-2 check
pending). Run order [C3, C2, C1]; batch id `pipeline_batch2_20260625`. Next:
Claude writes Stage-1 hypothesis specs, then Codex runs Stage 2->3. The one open
Codex code task before any batch-2 DSR was trustworthy was **T2** (CPCV raw-path
retention + honest n_trials provenance), now implemented for future artifacts;
follow-up tasks tracked in
`tasks/2026-06-25-pipeline-batch1-followup-tasks.md` (T1 done, T3 done, T4 moot,
T2 done).

### 2026-06-26 Codex follow-up (Progress workstream milestone panel)

`/api/progress` no longer reads git metadata, `STATUS.md`, or linked-plan
checkboxes. The endpoint now reads the hand-maintained
`config/workstreams.yaml` registry and returns workstream cards with
done/current/pending milestone states. The frontend renders curated milestone
steppers, state/next lines, and doc links. Maintenance contract:
update `config/workstreams.yaml` whenever this file is updated so the panel
stays honest. This is read-only UI/API/config data; no DB, network, write
endpoint, strategy, risk, config gate, deployment, or result-artifact behavior
changed.

### 2026-06-25 Codex follow-up (manual completion + standalone Progress route)

`scripts/run_server.py` now includes `/api/progress` after Claude/user approval.
Manual chapters `docs/manual/00-architecture.md` through
`docs/manual/80-glossary.md` were rewritten into readable Traditional Chinese
summaries from existing project docs, and `docs/manual/manual.json` now marks all
chapters as `written`. Scope is documentation/read-only API surface only: no
research files, strategy behavior, config gates, risk rules, live/shadow/demo
behavior, or result artifacts changed.

### 2026-06-25 Codex follow-up (read-only Progress panel)

Added `/api/progress`
and the `進度 / Progress` Analysis nav panel. The route reads local git metadata,
`STATUS.md`, and linked plan checkboxes only; no DB, network, write endpoint,
strategy, risk, config gate, deployment, or result-artifact behavior changed.
`STATUS.md` seeds the branch board. Checks run: `tests/unit/test_routes_progress.py`
passed, frontend JS syntax checks passed via direct `node --check` commands
because `make` is unavailable in this Windows shell, `api_smoke.py` skipped
cleanly without `API_BASE_URL`, and docs metadata/feature-map link checks passed
with existing metadata warnings.

### 2026-06-25 Codex follow-up (pipeline batch 1 Stage 3/refit checkpoint after data repair)

Binance canonical data is complete for S6/S7 over `2024-01-01`
through `2026-06-16 23:59 UTC`: `BTC-USDT-SWAP`, `ETH-USDT-SWAP`,
`BTC-USDT`, and `ETH-USDT` each have 1,293,120 1m rows with 0 gaps, and
BTC/ETH perp funding each has 2,694 rows. ETH perp was loaded with
`scripts/download_binance_data.py`; ETH funding was loaded with
`scripts/market_data/ingest.py` after fixing Binance funding windowing and
legacy `funding_rates` mirroring. The old S5/S6 summaries are superseded because
they used a non-refitting WF/CPCV harness. New fold-refit artifacts are under
`results/pipeline_batch1_20260625_refit/`: S6 has WF OOS Sharpe 0.0088, CPCV
OOS Sharpe 0.5422, DSR 0.1963, PSR 0.7387, `statistical_gate_passed:false`, so
adapter/ct_val work should not start. S5 reran with ETH factor data but current
point-in-time membership plus venue-scoped candle coverage produces
`nonzero_grid_activity:false`, so it is a data-universe artifact, not support or
refutation. S7 (`results/pipeline_batch1_20260625/s7/summary.json`) reran with a
non-degenerate finite half-life grid and is `shelved_pending_research_review`
(WF -0.4359, CPCV -1.1124, DSR/PSR ~0), not refuted from the prior all-zero
no-trade artifact. No first-batch strategy is promotion evidence or
live/demo/shadow ready.

### 2026-06-25 Codex follow-up (Strategy Research Pipeline Stage 1)

Claude brainstormed
+ planned a semi-autonomous strategy-research pipeline so one kickoff runs backlog
candidates through 文獻->假設 -> 可行性 -> 實作+回測, stops at one Claude evidence
review, and emits a shortlist (publish stays the user's call). Spec
`docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md`, plan
`docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md`, driver +
stage templates under `docs/superpowers/pipeline/`. Decisions: backlog source,
single manual checkpoint, **per-family cumulative `n_trials`** (K=2 retry limit),
two-pass backtest (parquet pre-screen -> DB CPCV), publish = `enabled:false`
candidate (never touches demo/shadow/live gates). Codex completed Task 1
code/tests and Tasks 2-4 docs: `scan_xs_momentum` accepts
`prior_family_n_trials`, records family-cumulative `attrs["n_trials"]`, and the
Stage 3 template requires passing the family count into CPCV. The generic
validation runner already passes caller-provided `n_trials` into
`CPCV.evaluate()`. Family trial-accounting docs, invariant I23, Change Manifest
`docs/change_manifests/2026-06-25-family-cumulative-n-trials.md`, driver,
three stage templates, and shortlist template are in place. First batch when run
= [S7, S5, S6]. Nothing run yet; no strategy promotion, result artifact value,
config, or demo/shadow/live gate changed.

## 2026-06-24 - Results Cleanup, DSR Harness, And XS Momentum Leak Fix

### 2026-06-24 Results cleanup (user-approved)

All pre-6/18 `results/` artifacts were
deleted to declutter -- scratch runs (smoke/test/verify/sweep/old-UI + old PNGs)
and pre-6/18 cited evidence (`cme_gap_research*.json`,
`codex_2026061{2,6}_signal_*`, `results/strategy_validation/`,
`ui_funding_carry_ac454742`). 6/18 and later are kept, including the durable
adr0007 source-provenance PASS artifact. Consequence: on-disk
differential/signal-validation evidence is gone -- re-run
`make strategy-signal-validation` (CI regenerates it) before citing fresh
validation evidence. `docs/results_validation_manifest.md` rows for deleted files
are now historical-only.

### 2026-06-24 Codex follow-up (DSR harness + XS portfolio-vol correctness)

Fixed
DSR computation so `src/okx_quant/analytics/dsr.py` uses per-observation Sharpe
from the same return series that feeds `sqrt(T-1)`, and
`backtesting/cpcv.py` computes DSR over non-overlapping CPCV paths with honest
`n_trials`; the harness now enforces `DSR <= PSR(0)` by refusing
`DSR > PSR(0)` and emits `dsr=0.0` with
`validation.n_trials_missing` when callers omit researched trial count. Added
I21/F20. XS momentum sizing now targets estimated portfolio book vol with
`MAX_GROSS_LEVERAGE = 2.0` rather than median single-name vol capped at 1.0;
added I22/F21 and updated ADR-0009. Correctness-only rerun:
`results/xs_momentum_validation_20260624_portfoliovol/` with
`promotion_gate_passed:false`, `status:"review_required"`, WF OOS Sharpe 1.2412,
CPCV OOS Sharpe 0.6027, DSR 0.7823, PSR 0.8234, `n_trials=8`,
`n_combinations=15`. PSR remains below 0.95, so promotion remains **BLOCKED**.
`xs_momentum` stays disabled; no live/demo/shadow/deployment gates changed.

### 2026-06-24 Codex follow-up (DSR all-strategy recheck)

Added
`scripts/recheck_dsr.py` and ran it against current `results/**/*.json`.
The audit found 45 DSR-bearing JSON rows: 7 CPCV rows and 38 replay-level
single-run diagnostic rows. The single-run rows set `dsr == psr` and are not the
CPCV multiple-trial DSR defect. Daily Winner CPCV was recomputed from saved
returns (`old dsr=0.0`, recomputed `dsr=6.81623e-39`, `psr=0.658074`).
`results/xs_momentum_validation_20260623/{cpcv,summary}.json` and
`results/xs_momentum_validation_20260624_leakfix/{cpcv,summary}.json` are
**untrusted** for DSR because `DSR > PSR(0)`. The portfolio-vol artifact passes
the invariant (`0.7823 <= 0.8234`) and remains below gate, but it stores only
summary/path Sharpe fields, not raw path returns; the audit cannot independently
recompute it from artifacts alone. No result payloads were modified.

### 2026-06-24 Claude review note (XS momentum Phase C runner)

**BLOCK promotion -- look-ahead leak found.** `backtesting/xs_momentum_backtest.py` builds the day-D
target weight from day-D's own close (`_daily_close` bins at 00:00 but holds the
day's 23:00 close) and lags it by only one intraday bar (`positions =
target.shift(1)`), so every rebalance day is partially traded with same-day-close
hindsight. This inflates the committed WF/CPCV evidence
(`results/xs_momentum_validation_20260623/`: OOS Sharpe 2.4-5.1 at ~2-3% vol,
`dsr=1.0`, `psr=0.99`) -- that artifact is **INVALID / superseded, not promotion
evidence, do not cite.** It also carries `summary.json:"promotion_gate_passed":
true`, which must be retracted (no user approval, leaked numbers). Separately, the
vol-target sizes on median single-name vol capped at gross<=1.0 -> ~5x chronic
under-leverage (spec-conformance issue, not the leak). The D3-flagged fixes
(annualized vol-target, `market_close` wiring) did land and are tested. Funding
sign is R3.1-correct. Fix is daily-level lag + regression test + leak-free re-run:
Codex task `tasks/2026-06-24-xs-momentum-lookahead-fix-task.md`; full review
`tasks/2026-06-24-xs-momentum-phase-c-review.md`.

### 2026-06-24 Codex follow-up (XS momentum lookahead fix)

Fixed
`backtesting/xs_momentum_backtest.py` so daily targets are shifted one full day
before intraday expansion, while retaining the existing one-bar execution lag.
Regression coverage:
`tests/unit/test_xs_momentum_backtest.py::test_daily_close_target_is_not_traded_on_same_day`.
Leak-free validation rerun was written to
`results/xs_momentum_validation_20260624_leakfix/` with
`promotion_gate_passed:false`, `status:"review_required"`, 27 loaded symbols,
8 searched parameter trials, 15 CPCV combinations, WF combined OOS Sharpe
0.8825, CPCV overall OOS Sharpe 0.5577, pre-fix DSR 1.0 (**untrusted; DSR > PSR**),
and PSR 0.7961. Because PSR is below 0.95, this rerun does **not** support promotion. The leaked
`results/xs_momentum_validation_20260623/` artifact now has `SUPERSEDED.md` and
must not be cited. Vol-target quantity/sizing remains a separate Claude/user
decision; no `src/okx_quant/strategies/`, risk, portfolio, execution, config, or
deployment gate files were changed.

## 2026-06-23 - Engine Consistency Smoke And Binance 1H DB Parity Follow-Up

- Added `scripts/run_engine_consistency_smoke.py`, `make engine-consistency-smoke`,
  and frozen real Binance BTC-USDT-SWAP 1H fixtures under
  `tests/fixtures/engine_consistency/`.
- Verified the smoke locally: MA/EMA/MACD all passed vectorbt+backtrader
  signal-logic comparison in 27.581s. MA and EMA fixtures each cover 960 hourly
  bars with 5 signals; MACD covers 120 hourly bars with 5 signals. This is
  signal-logic-only `strategy_fill` evidence, not promotion/live evidence.
- Added `scripts/resample_binance_1h_canonical.py` and used it to seed 20,400
  Binance-sourced BTC-USDT-SWAP 1H canonical rows from existing Binance 1m
  canonical rows in local Postgres.
- Pre-repair MA source-provenance validation failed DB parity with
  `canonical_source_primary=binance`, `artifact_rows=20400`, `db_rows=20376`,
  `missing_in_db=24`, and `value_mismatches=0`.
- Follow-up filled the remaining 2024-04-29 Binance 1H gap with
  `download_binance_data.py --start 2024-04-29 --end 2024-04-30`. Local parquet
  and DB canonical rows now match for that day (24 rows, 0 close mismatches);
  pre-repair validation artifacts need regeneration before a DB-parity PASS can
  be cited.

## 2026-06-22 - Backtest Execution Profiles

- Added first-class `strategy_fill` and `dual_output` execution profile
  implementation path for replay backtests.
- Kept `strategy_fill` as the existing research-only fill-all mechanism, with
  explicit idealized-fill marking.
- Added submitted-fill metrics that exclude terminal liquidation from strategy
  order fill counts.
- Verified BTC-USDT-SWAP Binance 1H with `max_order_notional_usd=250` and
  `max_pos_pct_equity=1`: Strategy Fill produced MA 228/228/228, EMA
  252/252/252, and MACD 1558/1558/1558 signal/order/fill counts with zero
  rejections. Full-period MACD Dual Output confirmed the realistic path still
  has sparse submitted fills: 779 submitted orders, 3 submitted-order fills, and
  1 terminal liquidation fill.
- Added Run Detail execution-profile visibility plus a comparison JSON link for
  dual-output child runs.

## 2026-06-22 - Validation Lab Report Package

- Added `docs/validation_lab_report_zh.md`, a Chinese report explaining the
  Validation Lab architecture, vectorbt/backtrader/Nautilus roles, source-data
  validation boundaries, parameter interpretation, max-order-notional
  differences, limitations, and a beginner no-code strategy-builder plan.
- Updated `scripts/generate_backtest_external_validation_report.py` and
  regenerated `docs/backtest_external_validation_report_zh.pptx` with
  Validation Lab report slides.
- Added `scripts/run_validation_lab_signal_order_check.py` and generated
  `results/validation_lab_signal_order_check_20260622.json` for
  BTC-USDT-SWAP Binance 1H MA/EMA 10/200 and MACD 12/26/9 signal-to-order
  evidence. The long-window differential-validation attempts for those
  generated runs did not complete locally and remain follow-up work.
- Updated reduce-only risk semantics after user approval: bounded reduce-only
  close orders may bypass the single-order fat-finger cap up to current position
  notional. Added Change Manifest
  `docs/change_manifests/2026-06-22-reduce-only-fat-finger-bypass.md` and reran
  the 250 USD / 100% equity sensitivity check.

## 2026-06-22 - Fast Backtest Artifact Rows (ADR-0008)

- Added ADR-0008 and a Change Manifest for Option C: a derived
  `backtest_artifact_rows` table that accelerates saved-result reads without
  changing existing artifact payloads or trading semantics.
- Added row-first API reads for common chart/table endpoints plus a lightweight
  `/api/backtest/{run_id}/summary` endpoint for immediate UI selection.
- Added backfill and benchmark scripts so old runs can be indexed, verified by
  count/hash parity, and measured through the running API.

## 2026-06-12 - AI Context And Harness

- Added root `AI_CONTEXT.md` for project-wide AI onboarding context.
- Added feature, UI, data-flow, and runbook maps under `docs/`.
- Added docs-check scripts and Makefile harness targets.
- Added Codex prompt templates under `.codex/prompts/`.

## 2026-06-16 - Strategy Signal Validation Interface

- Added a selectable `--engines` CLI to `scripts/run_all_strategy_signal_validation.py`.
- Added `make strategy-signal-validation` and Runbook instructions for active-strategy
  portable signal-point validation.
- Added a default `NUMBA_DISABLE_JIT=1` guard for vectorbt fixture validation to
  avoid Windows import/JIT stalls on tiny fixtures.
- Generated batch `codex_20260616_signal_validation`, which produced PASS rows
  for all active strategies under `results/strategy_validation/`.

## 2026-06-17 - Strategy Signal Validation CI

- Added a CI `strategy-signal-validation` job that installs validation extras and
  runs the active-strategy fixture signal-validation batch.
- Added `VALIDATION_RESULTS_DIR` to `make strategy-signal-validation` so CI can
  keep generated validation artifacts in runner temp storage.
- Recorded the next validation priority as real-data/source-provenance evidence
  before full execution parity work.

## 2026-06-17 - Source Provenance Validation Gate

- Added `scripts/run_source_provenance_validation.py` to gate existing or freshly
  generated differential-validation evidence for real-data/source provenance.
- Added `make source-provenance-validation` as a thin wrapper around the script.
- Locked the rule that DB parity `SKIP` is not enough: the gate requires
  `source_data_validation`, `ct_val_provenance`, and `db_parity` to pass, with
  `ohlcv_source_validation == "db_parity_pass"`.

## 2026-06-17 - Multi-Venue Instrument Specs (ADR-0007) Design + Coordination

Claude session (planning/review/risk; ponytail full). Design + plan + review;
implementation by Codex.

- Diagnosed the open "which saved run for the first DB-backed source-provenance
  PASS" question: no existing run qualifies (fixtures -> `db_parity` SKIP; real
  BTC and `ui_sweep` MA/EMA/MACD runs -> ct_val from `registry`, non-authoritative
  -> FAIL). The gate reads ct_val from the artifact, not live DB.
- Established the key correctness fact: ct_val cancels in notional-sized backtest
  PnL (`n=notional/(ct_val*price)`, `pnl=n*dprice*ct_val` -> `notional*dprice/price`).
  The ct_val provenance gate is therefore a **live-readiness gate, not a
  backtest-correctness gate**.
- Authored ADR-0007 (multi-venue instrument specs): single venue per run; new
  `venue_instrument_specs (exchange, symbol)` table; canonical symbol + thin
  native mapping; venue-aware ct_val resolution (Binance/Bybit USDT-M = 1.0, OKX
  BTC 0.01 / ETH 0.1); provenance gate stays shape-compatible + gains a venue
  tag. Added Change Manifest skeleton and ADR index row.
- Wrote the P1 implementation plan
  (`docs/superpowers/plans/2026-06-17-multi-venue-instrument-specs-p1.md`) as the
  Codex task spec (6 TDD tasks).
- Added a workstream sequencing note to `AI_HANDOFF.md` (multi-venue P1 owns the
  ct_val provenance gate; validation parallelizes except that surface + the
  Binance DB-backed PASS milestone; price chart independent).
- Reviewed the price-chart fix (`76dcecc`, branch `codex/fix-price-chart-universal`):
  per-symbol loading/empty/error states and indicator-overlay gating scoping are
  correct. Pass; pending human sign-off + merge.
- Diagnosed a backtest crash (Binance run on unseeded swap): `venue_instrument_specs`
  not applied to DB + resolver raises for non-OKX unseeded swaps. Provided a seed
  stopgap (A) and the structural fix (B): Binance/Bybit USDT-M perps resolve to
  `exchange_base_unit` (authoritative 1.0); 1000x-multiplier symbols still need an
  explicit DB row.
- Codex implemented P1 on `codex/impl-multi-venue-instrument-specs`: table+seed
  (`171b3f4`), exchange-aware resolution (`1aa85e2`), provenance tag (`e7eb3ed`),
  gate venue-tag (`519385e`), API+frontend exchange selector (`7be7f65`),
  convergence golden case (`71cd90c`), and the structural base-unit fix
  (`9bef416`). Remaining: Task 6 docs/Manifest fill-in + end-to-end DB-backed
  Binance PASS verification.

## 2026-06-18 - DB Parity Close-Only Contract

- Confirmed the saved Binance ADR-0007 run has 192/192 artifact closes matching
  DB canonical Binance closes with zero close mismatches.
- Updated `db_parity` to compare timestamped `close` values only for
  `price_series.csv` provenance; close-flattened artifact O/H/L and quote-volume
  units are not treated as like-for-like DB candle fields.
- Added regression coverage for close-flattened artifacts with matching close
  values.
- Generated durable source-provenance PASS evidence under
  `results/adr0007_binance_btc_1h_db_pass_20260618/validation/codex_close_only_db_parity_pass_20260618/`.
