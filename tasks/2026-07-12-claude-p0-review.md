---
status: current
type: review
owner: claude
created: 2026-07-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Claude Review: P0.1–P0.3 scopes and H-012/H-013 research decisions — 2026-07-12

Review of `tasks/2026-07-12-project-diagnosis-followup-tasks.md` per
`docs/REVIEW_QUESTIONS.md`, `docs/CRITIQUE_PROTOCOL.md`, `docs/INVARIANTS.md`,
and `docs/ai/TASK_TEMPLATES.md` §5. Evidence spot-checked in-session at the
cited lines. Verdicts here are Claude review positions; human approval is still
required where each task says so.

## P0.1 Artifact-ID containment — APPROVE scope, with binding amendments

Findings (severity / claim / evidence / resolution):

1. **blocker (confirmed)** — `validation_id` reaches a filesystem *write* path
   unsanitized: `src/okx_quant/api/routes_backtest.py:3332`
   (`output_dir = results_dir / clean_run_id / "validation" / validation_id`).
   A crafted ID writes outside the run dir and can overwrite existing result
   artifacts — data-loss class, not only disclosure. Fix at this entry.
2. **blocker (confirmed)** — same hole at library level:
   `backtesting/differential_validation.py:2811` and `:2996`
   (`... / "validation" / validation_id`). Both entrypoints must enforce the
   rule (the audit's own lesson: second entrypoints need their own guard).
3. **major (confirmed)** — CLI: `scripts/run_all_strategy_signal_validation.py:84`
   (`run_dir = results_dir / run_id`) uses raw `run_id`. Same shared rule.
4. **major (design)** — `Path(id).name` truncation is the wrong primitive and
   must NOT be the fix: on POSIX `Path("..\\evil").name` keeps the backslash;
   `Path("..").name == ""` and `root / ""` collapses to root; Windows
   drive-relative `C:evil` survives naive checks. Required rule: ONE shared
   validate-and-reject helper — allowlist regex (suggest
   `^[A-Za-z0-9._-]{1,128}$`), explicit rejection of `"."`/`".."`/empty, then a
   post-`resolve()` containment assert (`is_relative_to(root)`) at every
   write/read entry. Truncation-based "sanitizing" gets replaced, not extended.
5. **minor** — read helpers (`differential_validation.py:4096-4139`) currently
   sanitize-by-truncation: `../../x` silently becomes `x` and may serve the
   wrong artifact. Align to reject → 404/400.
6. **note** — confirm all generated IDs (`db_<hex>`, `diffval_<hex>`,
   timestamp-style run IDs) match the allowlist so existing artifacts stay
   readable (task acceptance already requires this).

Required tests: traversal `../`, `..\`, absolute path, drive-letter `C:x`,
empty, `.`, `..`, overlong, unicode-separator lookalikes — via API (POST run +
GET read) and CLI. No dedicated containment tests exist today (confirmed).

Cross-API/CLI boundary answer: enforce in the shared helper used by routes,
`differential_validation.py` functions, and scripts — library level is the
backstop so future entrypoints inherit containment.

## P0.2 ct_val contract — APPROVE with this concrete contract (needs human OK)

Confirmed facts: `validate_ct_val` (`src/okx_quant/portfolio/sizing.py:21-26`)
rejects `>1` but **accepts NaN** (NaN fails both comparisons). Accepted config
metadata contains legitimate `ct_val` 100 (XRP/ADA), 1000 (DOGE), 1e6 (SHIB) in
`config/instrument_specs.yaml`; ADR-0003 (accepted) says `0 < ct_val <= 1`;
ADR-0007 (accepted) legitimizes venue multipliers. The conflict is real: those
four OKX SWAP symbols cannot pass sizing today.

Recommended contract:

- Reject non-finite (`math.isfinite`) and `<= 0` — the NaN fix, uncontroversial.
- Accept any finite positive value, with a corruption sanity cap `<= 1e7`
  (largest legitimate known value 1e6, 10x headroom). No venue-aware per-row
  bound machinery — provenance rule R1.4 already forces the authoritative
  source; a dynamic bound is speculative complexity.
- No PnL formula change. ct_val enters linearly at every money-path site
  (positions.py:31/35/164, broker.py:207, replay_execution.py:102/235,
  portfolio_manager.py:129/277, replay.py:1663); widening the accepted domain
  changes nothing for previously accepted values. Previously-rejected symbols
  become usable under existing formulas — new capability, not drift.
- Docs: amend ADR-0003 "asserts 0 < ct_val ≤ 1" wording with a dated amendment;
  ADR-0007 unchanged; Change Manifest; final I34 wording: "rejects
  non-finite/non-positive and values above 1e7; accepts every
  venue-metadata-authorized value".
- Tests: 100, 1e6 accepted; 0, negative, NaN, +inf, >1e7 rejected; boundary 1e7.

Human decision needed: ratify the 1e7 cap (or choose no cap / another bound).

## P0.3 Venue fail-closed — APPROVE

Confirmed: `_normalize_exchange` (`routes_backtest.py:299-314`) silently falls
back to `primary_exchange`/`binance` for unknown values; the correct pattern
already exists in-repo at `routes_data.py:498-502` (`_normalize_fetch_exchange`
raises 400). Mirror it against `_ALLOWED_EXCHANGES`.

- Semantics to pin: omitted/None/empty → `cfg.storage.primary_exchange`
  (documented default); any other unknown string → 400, no fallback. Note the
  request models hard-default `exchange: str = "binance"` (`:347`, `:369`), so
  the config fallback is currently dead except for empty strings — recommend
  model default `None` → config primary, and document it. Empty string counts
  as omitted or is rejected; pick one and test it.
- Provenance framing (I33/R6.4): today's fallback swaps the user's declared
  venue silently; downstream artifacts are internally consistent (they honestly
  record the substituted venue) but user intent is silently replaced — exactly
  the "plausible data from the wrong venue" failure. Boundary rejection
  completes I33; downstream loaders are already strict (DATA_FLOW venue rules),
  no loader change needed.
- Minor scope addition: `scripts/backtest_daily_winner.py:43` `--exchange` has
  no `choices` constraint — add the same whitelist.
- 200→4xx for unknown venue is an API behavior change: Change Manifest (task
  already requires it) plus UI_MAP/DATA_FLOW rows; existing tests only cover
  default+known venues (`tests/unit/test_backtest_request_exchange.py:12-20`),
  add the unknown→4xx regression.

## H-012 / E-037 checkpoint — Claude verdict: SHELVE, no retry (user ratifies)

- DSR 0.7220 / PSR 0.8484 at family n_trials=4: the deflation penalty at n=4 is
  minimal, so the shortfall is signal weakness, not multiple-testing penalty;
  more trials can only lower DSR.
- Calibration against precedent: below H-002's refuted-level DSR 0.7823 / PSR
  0.8234, and nowhere near H-009's genuinely marginal 0.9346 KEEP.
- Standing H-002 constraint applies: no tuning `{lookback_days, z_min}` to
  chase 0.95. Any retry needs a new ex-ante mechanism-level rationale, consumes
  K, and adds its grid to family n_trials. None is on the table.
- Hygiene before recording the shelve (not expected to change the verdict):
  run the P1.3 leak-lag spot check on E-037 and close the family-minting
  `mechanism_novelty` human-review item. Mechanism novelty vs
  F-FUNDING-XS-DISPERSION looks real (max abs corr 0.0504) — MINT acceptable.
- On user ratification: ledger status `testing` → `shelved` (spec-correct
  baseline, enabled:false); E-037 stays the evidence record; no artifact edits.

## H-013 / F-VRP-TIMING Stage-1 — Claude verdict: APPROVE spec (user signs off)

- Spec is gate-compliant as written: pre-registered 4-combo grid, mandatory
  `published_at` as-of leak guard + t+1 execution (F26), costs and funding
  included, honest power disclosure, distinctness preflight required.
- Eyes-open caveat for the sign-off decision: 2 symbols, n_trials=4 →
  observed-Sharpe bar ≈1.7; ex-ante pass probability is low. Treat as a cheap,
  mechanism-novel probe; no post-hoc grid extension if it comes close.
- E-038 semantics (P1.3 open question): keep **reserved only**; do not create a
  planned zero-trial registry row — the registry records executed runs, a
  planned row is a double truth.
- Codex must not pre-run adapters or probes before the user sign-off is
  recorded (P1.3 rule).

## MUST-CATCH checklist (TASK_TEMPLATES §5)

- Scope violations: **clear** (task list keeps forbidden areas; P0.1's
  differential-validation carve-out is documented in AI_HANDOFF).
- Strategy drift / assumption changes: **clear**.
- PnL/ct_val errors: **found** — the P0.2 subject itself (NaN + >1 conflict).
- Funding sign: **n/a**.
- Lookahead/leakage/trial-count drift: **found-pending** — E-037 leak-lag spot
  check outstanding; H-013 leak guard specified; n_trials accounting honest.
- Orphan/partial-fill regressions: **n/a**.
- API schema breaks: **found (planned)** — P0.3 unknown-venue 200→4xx is an
  intentional contract change; Manifest + UI_MAP/DATA_FLOW required.
- Missing tests/docs/Manifest: **found** — no containment tests exist (P0.1),
  no unknown-venue rejection test (P0.3); both are in the acceptance criteria.
- Invariant regressions: **clear** — I32/I33/I34 are planned-blocker rows;
  I34's final wording lands with P0.2.
- Readiness claims: **clear** — nothing claims promotion/demo/shadow/live.

**Overall verdict: approve the P0.1→P0.2→P0.3 execution order with the
amendments above.** P0.4 branch integration remains a human decision; keep the
API unexposed to untrusted clients until P0.1 and P0.3 land.

## Ratification record

- 2026-07-12 (user): this review handed to Codex as the P0.1–P0.3 work order.
- 2026-07-12 (user): **P0.2 contract ratified as proposed** — finite positive
  (`math.isfinite` and `> 0`) with a `<= 1e7` corruption cap. Codex may
  implement with the ADR-0003 amendment and Change Manifest.
- 2026-07-12 (user): **H-013 Stage-1 spec approved as written.** E-038 Stage-2
  probe is authorized but queues behind the P0 blockers per the execution
  order; no post-hoc grid extension.
- 2026-07-12 (user): **H-012 SHELVE ratified** — recorded in the ledger with
  the leak-lag hygiene result (new finding F36: turnover cost charged on
  signal day t, not t+1; E-037 artifact untouched, non-promotion evidence).
- 2026-07-12 (user): **P0.4 = Option B** — single merge PR with documented
  integration exception after P0.1–P0.3 land; `verify-full` on the integration
  commit; merge the 5 main-only commits into the branch first; no force-push.
- 2026-07-12 (user): ADR-0001 local-task exception approved; ADR-0006 confirmed
  accepted; P1.4 operations decided — see "Human decisions recorded 2026-07-12"
  in `tasks/2026-07-12-project-diagnosis-followup-tasks.md`.

## Implementation review — 2026-07-12 (Claude): P0.1/P0.2/P0.3 APPROVED

Reviewed the Codex working-tree diff (~1,000 insertions, 36 files) against the
three Change Manifests and this review's amendments. Verification that Codex's
execution quota blocked was completed by this review session.

**Verdict: approve all three P0s.** Every binding amendment was implemented:

- P0.1: one shared reject-not-truncate helper (`validate_artifact_id` +
  `resolve_artifact_path` in `backtesting/artifact_rows.py`) — ASCII allowlist
  1–128 chars, explicit `.`/`..`/empty/trailing-dot/Windows-device rejection,
  post-`resolve()` `is_relative_to` containment. All four flagged sites fixed
  plus writer backstops (`artifacts.py`, `parameter_sweep.py`,
  `turtle_backtest.py`) and five CLI boundaries. Read helpers now reject
  instead of truncating. Zero `Path(id).name` sanitizing remains in
  src/backtesting/scripts (grep-verified). Derived names (`_strategy_fill`,
  `_execution_comparison.json`, finalist ranks) are pre-validated at request
  time so background jobs cannot fail late. `delete_run` validates before
  rmtree/DB delete. Execution-comparison reads dropped payload-provided paths.
- P0.2: `validate_ct_val` is exactly the ratified contract
  (`math.isfinite`, `0 < v <= 1e7`); formulas untouched (diff is validator +
  docstring only); tests cover 100/1e6/1e7 accept and 0/neg/NaN/inf/1e7+ε
  reject. ADR-0003 amendment is dated and states formulas unchanged. No
  sizing/PnL semantic drift confirmed.
- P0.3: `_normalize_exchange` mirrors the `routes_data.py` pattern — explicit
  unknown → HTTP 400 before queueing (jobs-list unchanged asserted in tests),
  omitted/blank → `cfg.storage.primary_exchange` (a five-venue `Literal`, so
  the fallback cannot yield an unknown venue; model default changed to `None`
  as recommended); `backtest_daily_winner.py` got argparse `choices`.

**Verification run by this review:** full unit `768 passed, 1 skipped`;
integration `38 passed`; Ruff pass; `docs-impact --strict` pass (67 files);
docs metadata + feature-map links pass.

**Findings (none blocking):**

1. minor — `routes_backtest.py:3264` over-indented statement inside
   `delete_run`'s try block; valid Python, Ruff-clean, fix on next touch.
2. minor — the symlink-escape regression skips on Windows without symlink
   privilege (WinError 1314), so the `resolve()` containment backstop is only
   exercised on environments that can create symlinks. Primary component
   validation is fully tested; keep the test for CI/Linux.
3. note — `backfill_backtest_artifact_rows.py --all` now raises on a legacy
   nonconforming on-disk run-dir name instead of skipping it (fail-loud,
   documented as a manifest risk).

**Codex closure note — 2026-07-12:** finding 1's indentation was corrected and
targeted Ruff passed. Finding 2 remains an honest environment skip with the
test active on symlink-capable CI/Linux; finding 3 is the documented fail-loud
contract. No blocking review item remains.

MUST-CATCH: scope/strategy-drift/funding/lookahead/orphan-fills/readiness all
clear or n/a; PnL-ct_val, API-contract, tests/docs/manifest, and invariant
items all found-and-satisfied (I32/I33/I34 now test-enforced; I35–I37 added).
