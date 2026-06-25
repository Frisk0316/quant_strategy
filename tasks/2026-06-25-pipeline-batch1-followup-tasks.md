---
status: current
type: task
owner: claude
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Pipeline Batch 1 — Follow-up Task Bundle (T1–T4)

Author: Claude (planning/review role). Implementer: Codex unless a task says
docs-only.

These four tasks are the agreed continuation **after** the current S5/S6/S7
rework (rerun S5/S6 on the fixed harness; re-run S7 with a wider half-life;
shelve-not-refute S7). They exist because the 2026-06-25 Stage 3 checkpoint
produced an S6 `statistical_gate_passed: true` that is **not credible**: the
WF/CPCV harness in `scripts/run_pipeline_batch1_checkpoint.py` never refits per
fold, so the "OOS" numbers are in-sample and the five CPCV `path_sharpes` are
byte-identical (`1.1324740507618738`), which neuters DSR (`dsr == psr == 0.9621`).

## Why this bundle (one-paragraph context)

`_wf_cpcv_from_daily` ([run_pipeline_batch1_checkpoint.py:50-61](../scripts/run_pipeline_batch1_checkpoint.py#L50-L61))
feeds WF/CPCV a single full-sample daily-return series whose parameters were
selected on the **whole** window ([:87-90](../scripts/run_pipeline_batch1_checkpoint.py#L87-L90)),
and its `returns_for(_train, test)` callback **discards `train`**
([:53-54](../scripts/run_pipeline_batch1_checkpoint.py#L53-L54)). CPCV then reassembles
the same fixed series into every path → identical path Sharpes → DSR deflation
does nothing. Until that is fixed, no S6/S5 statistical number is evidence, and
the downstream gates (portable validation, ct_val, realistic fill) are premature.

## Execution order & dependencies

```
T3 (docs honesty)  ──► can run immediately, independent, no code
T1 (refit harness) ──► rerun S6/S5; produces real OOS numbers
T2 (CPCV audit)    ──► depends on/extends T1; makes DSR recomputable
T4 (promotion ev.) ──► HARD-GATED: only if T1+T2 leave S6 with DSR≥0.95 & PSR≥0.95
```

Recommended sequence: **T3 → T1 → T2 → (only then) T4.** T3 first because the
ledger is currently wrong and any reader is being misled today. T4 must not be
started speculatively — most likely S6 dies at T1, and that is the gate working.

## Global FORBIDDEN (apply to every task below unless a task explicitly permits)

- `src/okx_quant/strategies/`, `src/okx_quant/signals/`, `src/okx_quant/risk/`,
  `src/okx_quant/portfolio/`, `src/okx_quant/execution/`
- `src/okx_quant/analytics/dsr.py` — the DSR/PSR math is correct; do not re-edit.
- `config/risk.yaml`, `config/settings.yaml`; any live/demo/shadow/deployment gate.
- `config/strategies.yaml` `enabled:` flags — every strategy stays `enabled:false`.
- `research/strategy_synthesis.md` — Claude-owned; do not edit from a Codex task.
- Existing **cited** result artifacts' numeric payloads (no in-place rewrite).
  Reruns write to a **new** suffixed dir and drop `SUPERSEDED.md` on the old one.

## Global rule

No promotion / live / demo / shadow / readiness claim in any task. Honest
`n_trials` (family-cumulative) everywhere. If a step needs the DB/DSN and it is
unreachable, report it as an explicit **SKIP**, do not fabricate the artifact.

---

# T1 — Refitting WF/CPCV harness + S5/S6 rerun

**Task:** Make the pipeline checkpoint's walk-forward and CPCV select parameters
**inside each train fold** and evaluate the selected parameters **only on the
test fold**, so the reported WF/CPCV/DSR/PSR are genuinely out-of-sample and the
CPCV paths are non-degenerate.

**Strategy/spec source:**
`docs/superpowers/plans/2026-06-25-strategy-research-pipeline-stage1.md`
(Global Constraints: gate is non-negotiable, leak-free, honest n_trials);
Claude review 2026-06-25 (this file's context paragraph).

**Required behavior:**

1. Replace the full-sample-select-then-slice flow. For S6 and S5, precompute
   **once** each grid combo's full causal daily-return series
   (`{combo_key -> daily_returns}`) by calling the existing
   `run_s6_ts_momentum_backtest` / `run_s5_residual_meanrev_backtest`
   (import only — do **not** modify those modules). 48 combos for S6, 72 for S5.
2. The WF/CPCV `returns_for(train, test)` callback must:
   - select the combo whose Sharpe on `train.index` (sliced from the cached
     series) is highest — **selection uses train dates only**;
   - return the selected combo's cached daily returns reindexed to `test.index`
     (`.fillna(0.0)`). This is causal: positions within the test window depend
     only on prices up to each date; only parameter *selection* is fold-local.
3. Factor the per-fold selection into a small **testable** pure function, e.g.
   `select_combo_on(window_index, combo_returns: dict) -> combo_key`, in a new
   `backtesting/pipeline_refit.py` (Codex-owned area). The runner imports it.
4. Keep family-cumulative `n_trials` (48 / 72) fed to CPCV; do **not** read it
   from a hardcoded literal — source it from the scan's `attrs["n_trials"]`
   (fixes the current hardcoded `48`/`72` at
   [:91](../scripts/run_pipeline_batch1_checkpoint.py#L91),[:166](../scripts/run_pipeline_batch1_checkpoint.py#L166)).
5. Replace the hardcoded `"leak_test_passed": True`
   ([:136](../scripts/run_pipeline_batch1_checkpoint.py#L136),[:219](../scripts/run_pipeline_batch1_checkpoint.py#L219))
   with the actual leak-test result, or remove the field. An unconditional
   `True` is a false green flag.
6. Write reruns to **`results/pipeline_batch1_20260625_refit/{s5,s6}/summary.json`**.
   Add `SUPERSEDED.md` to `results/pipeline_batch1_20260625/{s5,s6}/` pointing at
   the refit dir and stating the old numbers used a non-refitting harness.

> Performance ceiling (ponytail): precompute is 48 (S6) / 72 (S5) full backtests;
> per-fold selection is then cache slicing — O(combos) not O(combos×folds). Do
> **not** build a fold-parallel executor unless a real run measurably stalls;
> name the ceiling in a `ponytail:` comment if you cut a corner.

**PERMITTED FILES (only edit these):**
- `scripts/run_pipeline_batch1_checkpoint.py`
- `backtesting/pipeline_refit.py` (new — selection helper)
- `tests/unit/test_pipeline_refit.py` (new)
- `results/pipeline_batch1_20260625_refit/**` (new artifacts) and
  `results/pipeline_batch1_20260625/{s5,s6}/SUPERSEDED.md` (new)
- Docs: `docs/INVARIANTS.md` (add I24), `docs/FAILURE_MODES.md` (add F22),
  `docs/change_manifests/2026-06-25-refitting-wf-cpcv-harness.md` (new, from
  `docs/CHANGE_MANIFEST_TEMPLATE.md`), `docs/DOC_IMPACT_MATRIX.md` (rows),
  `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md`,
  `docs/KNOWN_ISSUES.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`

**FORBIDDEN (on top of Global FORBIDDEN):**
- `backtesting/cpcv.py`, `backtesting/walk_forward.py` — the callback contract
  already supports per-fold refit; do not change the shared engine (it would
  destabilize xs_momentum). T2 owns the cpcv.py change.
- `backtesting/s5_residual_meanrev_backtest.py`,
  `backtesting/s6_ts_momentum_backtest.py` — import only, do not modify.

**SCOPE LIMIT:** Only the validation harness wiring + the two reruns + the leak
flag + the n_trials sourcing. No strategy logic, no sizing, no new grid points,
no S7 work (S7 is the separate current task).

**REQUIRED ON COMPLETION:**
- List changed files.
- Run:
  - `python -m pytest tests/unit/test_pipeline_refit.py tests/unit/test_pipeline_batch1_contracts.py -q`
  - `python scripts/run_pipeline_batch1_checkpoint.py` (needs the DSN; if DB is
    unreachable, report SKIP and do **not** hand-write summaries)
  - `python scripts/docs/check_doc_impact.py`
- Create the Change Manifest; add I24 + F22; update ledger/registry/handoff with
  the **honest** rerun verdict (and correct H-005 status — see T3).
- Commit with `AI-Origin: Codex` trailer when committing is requested.

**ACCEPTANCE CRITERIA:**
- [ ] `returns_for` selects parameters using only `train.index`; a unit test
      builds two disjoint train windows where combo A wins on one and combo B on
      the other, and asserts `select_combo_on` returns the different winners.
- [ ] A unit test on a small synthetic 2-combo case asserts the resulting CPCV
      `path_sharpes` are **not all identical** (dispersion > 0) — the degeneracy
      guard.
- [ ] On the S6 rerun (if DB available), `cpcv.path_sharpes` are not all equal;
      `dsr`/`psr` reflect real cross-path variance. Record the new numbers.
- [ ] `leak_test_passed` reflects an actual check (or is removed); no
      unconditional `True`.
- [ ] `n_trials` fed to CPCV comes from `scan.attrs["n_trials"]`, not a literal.
- [ ] No changes to `cpcv.py`, `walk_forward.py`, strategy modules, configs, or
      gates. New artifacts under `_refit/`; old S5/S6 summaries carry
      `SUPERSEDED.md`.
- [ ] Change Manifest exists; I24 (per-fold selection) + F22 (full-sample
      selection masquerading as OOS / degenerate identical CPCV paths) added;
      doc-impact passes.

**Suggested I24:** "WF/CPCV evidence MUST select parameters within each train
fold and evaluate them only on the held-out test fold. A statistic computed by
slicing a single full-sample, full-sample-selected return series is in-sample and
MUST NOT be reported as `statistical_gate_passed` or OOS Sharpe."

**Suggested F22:** "Pseudo-OOS from full-sample parameter selection — a
validation harness whose per-fold callback ignores the train set re-scores one
fixed return series, yielding identical CPCV paths and a DSR that cannot deflate.
Symptom: all `path_sharpes` equal; `dsr == psr`. Guard: I24 + the dispersion
unit test."

---

# T2 — CPCV raw-path retention + honest n_trials provenance (+ pipeline wiring)

**Task:** Make every CPCV artifact carry the **raw per-path OOS returns** so DSR
is independently recomputable offline, and make `n_trials` an explicit,
provenance-tagged value rather than a silent `len(combos)`. Then extend the same
retention to the pipeline checkpoint summaries (S5/S6/S7).

**Strategy/spec source:** Execute the already-open task
[`tasks/2026-06-24-cpcv-path-return-retention-honest-ntrials-task.md`](2026-06-24-cpcv-path-return-retention-honest-ntrials-task.md)
**as written** (Parts 1 & 2, its permitted files, its acceptance criteria), then
apply the pipeline delta below. Do not re-derive its design here — that file is
the spec.

**Pipeline delta (additive to the open task):**
- After `backtesting/cpcv.py` emits `path_returns` (+ `n_trials_provenance`),
  have `scripts/run_pipeline_batch1_checkpoint.py` copy those fields into each
  `summary.json` (`cpcv.path_returns`, `cpcv.n_trials_provenance`,
  `cpcv.n_trials_is_floor`). The pipeline's `n_trials` is the **family
  cumulative** count → provenance `caller_declared` (not a floor).
- Extend `scripts/recheck_dsr.py` coverage so a pipeline `summary.json` carrying
  raw path returns is **recomputed** (old→new DSR), not just invariant-checked.

**PERMITTED FILES (only edit these):**
- All files permitted by the open task
  (`backtesting/cpcv.py`, `backtesting/xs_momentum_backtest.py`,
  `scripts/recheck_dsr.py`, `tests/unit/test_cpcv.py`,
  `tests/unit/test_xs_momentum_backtest.py`, its doc set).
- Additionally: `scripts/run_pipeline_batch1_checkpoint.py`,
  `tests/unit/test_pipeline_batch1_contracts.py`.

**FORBIDDEN (on top of Global FORBIDDEN):** everything the open task forbids —
notably `src/okx_quant/analytics/dsr.py` and existing artifact payload rewrites.

**SCOPE LIMIT:** Retention field + n_trials-provenance mechanism + pipeline
copy-through. Do **not** change strategy logic, sizing, the leak fix, or
re-derive a "true" trial count (that stays a Claude/user decision — surface the
floor + provenance and stop).

**REQUIRED ON COMPLETION:**
- Run:
  - `python -m pytest tests/unit/test_cpcv.py tests/unit/test_dsr.py tests/unit/test_xs_momentum_backtest.py tests/unit/test_pipeline_batch1_contracts.py -q`
  - `python scripts/recheck_dsr.py` (must run clean against current results)
  - `python scripts/docs/check_doc_impact.py`
- Change Manifest (the open task's) + INVARIANTS path-return-retention entry.
- Commit with `AI-Origin: Codex` trailer when committing is requested.

**ACCEPTANCE CRITERIA:**
- [ ] All acceptance criteria of the open
      `2026-06-24-cpcv-path-return-retention-honest-ntrials-task.md` are met (a
      unit test recomputes DSR from emitted returns within tolerance; recheck
      recomputes when raw returns present; n_trials provenance tagged).
- [ ] Pipeline `summary.json` (S5/S6/S7) carries `cpcv.path_returns` and
      `cpcv.n_trials_provenance == "caller_declared"` with the family-cumulative
      count; a contract test asserts these fields exist.
- [ ] `recheck_dsr.py` recomputes a pipeline summary's DSR from its stored path
      returns and prints old→new.
- [ ] No `dsr.py`/strategy/gate/config changes; no existing cited artifact
      payload rewritten.

**Questions for Claude (answer in handback; do not decide unilaterally):** the
honest `researched_n_trials` for each family once cross-batch retries exist — the
floor + provenance is the mechanism; the number is a research decision.

---

# T3 — Ledger / handoff honesty correction (docs-only)

**Task:** Correct the durable records that currently overstate S6. This is a
pure honesty fix and can run **immediately**, independent of T1/T2.

**Required behavior:**
1. `docs/HYPOTHESIS_LEDGER.md` H-005 (S6) is currently `supported`. Downgrade to
   an accurate status (e.g. `proposed` / `checkpoint-unverified`) with a note:
   "2026-06-25 checkpoint `statistical_gate_passed:true` came from a
   non-refitting WF/CPCV harness (identical CPCV paths, `dsr == psr`); it is
   **not** OOS edge evidence. Re-evaluation pending T1 (refit harness)." Match
   the bar set by H-001 (`supported` = backed by a deterministic test) and H-002
   (`refuted` with explicit binding constraints) — S6 has neither yet.
2. In `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`, and the Stage 3 Change
   Manifest (`docs/change_manifests/2026-06-25-pipeline-batch1-stage3.md`),
   correct the framing that S6 is "blocked **only** because portable validation
   and ct_val gates are false." State plainly that the **statistical gate itself
   is not yet credible** (harness defect), independent of portable/ct_val. Keep
   the existing wording that nothing is promotion/live ready.
3. Optionally tag E-012 in `docs/EXPERIMENT_REGISTRY.md` with the same caveat so
   the experiment row is not read as a clean statistical pass.

**PERMITTED FILES (only edit these):**
- `docs/HYPOTHESIS_LEDGER.md`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`,
  `docs/EXPERIMENT_REGISTRY.md`,
  `docs/change_manifests/2026-06-25-pipeline-batch1-stage3.md`

**FORBIDDEN:** any code, config, result artifact payloads, or gate text. Do not
change the numbers — only the **status label and the interpretation framing**.

**SCOPE LIMIT:** Wording/status only. No new experiments, no reruns.

**REQUIRED ON COMPLETION:**
- Run: `python scripts/docs/check_doc_impact.py` and
  `python scripts/docs/check_doc_metadata.py`.
- Commit with `AI-Origin: Codex` trailer when committing is requested (or assign
  to Claude — docs-only, either owner).

**ACCEPTANCE CRITERIA:**
- [ ] H-005 is no longer `supported`; its note explains the harness defect.
- [ ] CURRENT_STATE, AI_HANDOFF, and the Stage 3 manifest no longer imply the S6
      statistical edge is real-and-only-missing-plumbing.
- [ ] doc-impact + doc-metadata pass; no numeric payloads altered.

---

# T4 — S6 promotion evidence: portable adapter + ct_val + realistic fill

**HARD PRECONDITION — do not start until both are true:**
- T1 rerun shows S6 (on the refitting harness, honest family-cumulative
  n_trials) with **DSR ≥ 0.95 AND PSR ≥ 0.95** and non-degenerate CPCV paths.
- T2 makes that DSR independently recomputable from saved path returns.

If S6 fails the precondition, **do not do T4** — shelve S6 as a spec-correct
research baseline (mirror the H-002 decision) and escalate to Claude/user. This
task is the most likely to never run; that is the gate working.

This is an umbrella of three independent work items. When activated, split each
into its own task file; the blocks below are the acceptance contracts.

## T4a — Portable validation adapter (S6, then S5 if it survives)

**Task:** Implement a reference-engine adapter (vectorbt and/or backtrader) that
**independently recomputes** S6's time-series-momentum target signals, so the
differential-validation portable gate can pass on signal-logic only.

**Required behavior:** Flip the `s6_ts_momentum` contract in
`backtesting/differential_validation.py::REFERENCE_VALIDATION_CONTRACTS` from
`adapter_required` to `implemented` for at least one engine; produce a run where
`engines.<engine>.comparison.signal_logic.status == "PASS"` and
`actionable_mismatch_count == 0`, and `portable_validation_gate.passed == true`.
Scope is **signal-logic only** (per `ai_collaboration.md` Differential
validation gate); PnL/metric mismatches are advisory.

**PERMITTED:** `backtesting/differential_validation.py` (contract status + the
adapter only — **not** the ct_val provenance logic, which ADR-0007 P1 owns until
merge), the adapter module(s) under `backtesting/`, `tests/unit/` coverage, the
generated validation artifact, and the doc set (manifest/ledger/handoff).
**FORBIDDEN:** Global FORBIDDEN + the ct_val provenance functions in
`differential_validation.py` / `replay._attach_ct_val_provenance`.
**ACCEPTANCE:**
- [ ] At least one reference engine independently recomputes S6 target signals
      (not artifact replay) and reports signal_logic PASS / 0 actionable
      mismatch.
- [ ] `portable_validation_gate.passed == true` in the S6 validation artifact;
      contract no longer `adapter_required` for that engine.
- [ ] This is `advisory_only` / not promotion evidence by itself; documented as
      such. No gate text relaxed.

## T4b — ct_val authoritative provenance (S6)

**Task:** Make the S6 run resolve `ct_val` for `BTC-USDT-SWAP` and
`ETH-USDT-SWAP` on Binance from an **authoritative** source so
`ct_val_all_authoritative == true` with the correct venue tag.

**Required behavior:** Per `ai_collaboration.md` ct_val gate, every swap symbol's
`ct_val` must come from `db` (`venue_instrument_specs(binance, symbol)`),
`config_override`, or the applicable `exchange_base_unit`, with
`ct_val_sources[<symbol>].exchange == "binance"`. The S6 summary must carry
`ct_val_all_authoritative: true` and `validation.exchange == "binance"`.
**PERMITTED:** the S6 runner/validation wiring needed to attach + assert
provenance, `venue_instrument_specs` seed/verify scripts, tests, docs. Reuse the
existing 2026-06-23 spec-sync path (`venue_instrument_specs`) — do not hand-code
multipliers. **FORBIDDEN:** Global FORBIDDEN; do not weaken the gate to pass.
**ACCEPTANCE:**
- [ ] S6 artifact: `ct_val_all_authoritative == true`, both swap symbols sourced
      from `db`/`config_override`/`exchange_base_unit`, venue tag `binance`.
- [ ] A test asserts a non-authoritative source (`registry`/`hardcoded_btc_eth`)
      makes the gate FAIL.

## T4c — Realistic execution / replay (S6)

**Task:** Run S6 through the replay engine under a **realistic** (non-idealized)
fill model and preserve the full evidence set, to test whether the edge survives
fees + slippage + missed/partial fills + funding cashflow.

**Required behavior:** A replay run with `idealized_fill == false` /
non-`strategy_fill` profile, preserving fill log, order log, equity curve, fees,
and funding cashflow (reproducible). Report capacity / cost-after-edge honestly;
low fill counts may be execution-model artifacts (check distinct filled order
ids, cancellations, `queue_fill_fraction` vs lot/min size — see the MACD
precedent in CURRENT_STATE).
**PERMITTED:** `backtesting/` replay wiring for S6, tests, generated artifact,
docs. **FORBIDDEN:** Global FORBIDDEN; do not cite any `fill_all_signals` /
`strategy_fill` / `dual_output` run as edge or live-readiness evidence.
**ACCEPTANCE:**
- [ ] A realistic-fill S6 replay artifact exists with fill/order/equity/fees/
      funding logs, reproducible, `idealized_fill == false`.
- [ ] Net-of-realistic-cost result reported with an explicit capacity note; no
      promotion/live claim.

---

## Reporting (all tasks — use the AGENTS.md handback block)

Implementation summary / Diff scope / Files added / Files changed / Assumptions /
Tests run (with SKIP reasons if DB/Node/optional deps missing) / Result
artifacts / Docs updated / Known limitations / Risks / Rollback / Questions for
Claude / Next task / Deployment readiness (always: Not ready).
