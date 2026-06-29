# Codex Task — CPCV raw-path-return retention + honest n_trials provenance

Plan source: Claude review of `833de14` (DSR recheck) — see
`tasks/2026-06-24-dsr-allstrategy-recheck-task.md` and the
`docs/results_validation_manifest.md` "2026-06-24 DSR Recheck" section.

Two halves of one problem — **DSR-gate credibility**:
1. We cannot independently recompute any CPCV DSR offline because artifacts store
   only summary DSR/PSR + `path_sharpes`, not the raw path returns. The 2026-06-24
   audit could only invariant-check (`DSR <= PSR(0)`), not recompute.
2. CPCV `n_trials` is silently `len(final grid)` (= 8 in the XS runs). That
   **understates** the true research trial budget, which inflates DSR (weaker
   deflation). The same hypothesis H-002 was searched across E-003/E-004/E-005,
   and a 5-dimension grid with only 8 points is itself suspect.

This is forward-looking only. **Do not** rewrite or recompute existing artifacts;
this changes the writer + the trial-count contract for future runs.

---

## Task

### Part 1 — Retain raw CPCV path returns (artifact schema change)
Emit the raw per-path OOS return series in the CPCV output so DSR is
independently auditable offline.

- `backtesting/cpcv.py` already builds `path_returns_list` (~line 292). Add it to
  the returned dict (e.g. `"path_returns": [list(s.values) for s in path_returns_list]`,
  plus the matching timestamps if cheap, or at least `periods` + length so the
  PSR/DSR denominator skew/kurtosis is reproducible). Keep the existing
  `path_sharpes` / `n_paths` / `n_combinations` fields.
- The `else` branch (no path returns, line ~311) should likewise emit the
  `combined_returns` it uses, so that path too is auditable.
- This is a **result-artifact schema change (ADR-0002 area)** → create a Change
  Manifest from `docs/CHANGE_MANIFEST_TEMPLATE.md` and check
  `docs/DOC_IMPACT_MATRIX.md`. Add/strengthen an `docs/INVARIANTS.md` entry:
  *future CPCV artifacts MUST carry raw path (or combined) returns for DSR
  audit*.
- Extend `scripts/recheck_dsr.py`: when an artifact carries raw path returns,
  **recompute** DSR via the fixed `deflated_sharpe`/`psr` and report old→new,
  instead of only the invariant check. (Closes the loop the whole audit was for.)

> Size note (ponytail): raw returns for N=6 paths over ~2yr 1H is a few MB of
> JSON per artifact. Just store the arrays. Do NOT build a compression/columnar
> scheme unless a real artifact measurably hurts — name the ceiling in a
> `ponytail:` comment if you take a shortcut.

### Part 2 — Make n_trials honest + explicit (mechanism only)
Stop letting `n_trials` silently equal the final grid size.

- `backtesting/xs_momentum_backtest.py:113,115` set `n_trials = len(combos)`.
  Change the runner so the trial count fed to CPCV is an **explicit, provenance-
  tagged** value, not an implicit `len(combos)`:
  - Accept a caller-supplied `researched_n_trials` (the honest total across the
    whole search) and record where it came from in
    `validation.n_trials_provenance` (e.g. `"caller_declared"` vs
    `"grid_size_floor"`).
  - If the caller does not supply one, fall back to `len(combos)` **but tag it
    `grid_size_floor` and set `validation.n_trials_is_floor = true`** so a reader
    knows it is a lower bound, not the researched count. The existing
    `n_trials_missing` flag in `cpcv.py` stays as-is for the `<=0` case.
- Do **not** invent a "true" trial number. The actual honest value (does it
  include cross-run E-003/E-004/E-005 iteration? the full grid dimensionality?)
  is a **Claude/user research decision** — surface the floor + provenance and
  stop there. Leave a `Questions for Claude` line proposing a number; do not bake
  one in.

---

## PERMITTED FILES (only edit these)
- `backtesting/cpcv.py`
- `backtesting/xs_momentum_backtest.py`
- `scripts/recheck_dsr.py`
- `tests/unit/test_cpcv.py`, `tests/unit/test_xs_momentum_backtest.py` (add coverage)
- `docs/change_manifests/` (new manifest), `docs/INVARIANTS.md`,
  `docs/DOC_IMPACT_MATRIX.md` (rows), `docs/KNOWN_ISSUES.md`,
  `docs/EXPERIMENT_REGISTRY.md` (note schema change), `docs/AI_HANDOFF.md`,
  `docs/CURRENT_STATE.md`

## FORBIDDEN (do not touch)
- `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`
- `src/okx_quant/analytics/dsr.py` (the DSR/PSR math is correct — do not re-edit)
- Existing result artifacts' numeric payloads (no rewrite, no recompute-in-place)
- Deployment / shadow / demo / live gates; `config/risk.yaml`, `config/strategies.yaml`

## SCOPE LIMIT
Only the retention field + the n_trials provenance mechanism. Do **not** rerun XS
validation, do not change sizing/leverage, do not touch the leak fix, do not
re-derive a trial count. No adjacent refactors.

---

## REQUIRED ON COMPLETION
- List changed files.
- Run:
  - `python -m pytest tests/unit/test_cpcv.py tests/unit/test_dsr.py tests/unit/test_xs_momentum_backtest.py -q`
  - `python scripts/recheck_dsr.py` (must still run clean against current results)
  - `python scripts/docs/check_doc_impact.py`
- Create the Change Manifest + update `docs/DOC_IMPACT_MATRIX.md`, `INVARIANTS.md`,
  `KNOWN_ISSUES.md`, handoff docs.
- Commit with `AI-Origin: Codex` trailer.

## ACCEPTANCE CRITERIA
- [ ] New CPCV output carries raw path (or combined) returns; a unit test
      recomputes DSR from the emitted returns and matches the stored `dsr` within
      tolerance.
- [ ] `recheck_dsr.py` recomputes (not just invariant-checks) when raw returns
      are present, and prints old→new DSR.
- [ ] CPCV output records `n_trials` provenance; when the runner does not get an
      explicit researched count, the artifact is tagged as a floor
      (`n_trials_is_floor = true` / `n_trials_provenance = "grid_size_floor"`),
      not presented as the researched trial count.
- [ ] Change Manifest exists; `INVARIANTS.md` has the path-return-retention
      invariant; doc-impact passes.
- [ ] No strategy/risk/portfolio/execution/gate/`dsr.py` changes; no existing
      artifact payload rewritten.

## Questions for Claude (answer in the handback, do not decide unilaterally)
- What is the honest `researched_n_trials` for XS momentum H-002 — does it span
  the E-003/E-004/E-005 iteration, and what is the full grid dimensionality? (This
  number, once set by Claude/user, is what will actually re-test the XS DSR.)

## Note
Both halves serve the same end: until a CPCV DSR is **recomputable from saved
returns** AND deflated by an **honest trial count**, no XS DSR (even the
"invariant-passing" 0.78 portfolio-vol value) should be treated as a real
promotion gate. XS momentum stays BLOCKED regardless of this task.
