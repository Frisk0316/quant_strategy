---
status: current
type: plan
owner: human
created: 2026-06-25
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Strategy Research Pipeline Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal Stage 1 machinery so a single kickoff runs backlog
candidates through 文獻→假設 → 可行性 → 實作+回測, stops at one Claude evidence
review, and emits a shortlist — with honest family-cumulative `n_trials` enforced.

**Architecture:** Reuse `superpowers:subagent-driven-development` as the driver,
the existing `HYPOTHESIS_LEDGER.md` / `EXPERIMENT_REGISTRY.md` as the durable
trial record, and existing `backtesting/{walk_forward,cpcv}.py` +
`differential_validation.py` + ct_val provenance for the gate. The only new code
is one contract change: the candidate scan accepts an explicit
`prior_family_n_trials` and passes the family-cumulative count into CPCV
(replacing the per-run `len(combos)` hard-set that produced the S11 “n_trials=8”
defect). Everything else is process docs and task templates.

**Tech Stack:** Python, pandas/numpy, pytest; markdown governance docs.

**Spec source:** `docs/superpowers/specs/2026-06-25-strategy-research-pipeline-design.md`

## Global Constraints

Copied verbatim from the spec. Every task’s requirements implicitly include this.

- Gate is non-negotiable, never relaxed to make a strategy pass: **DSR ≥ 0.95 AND
  PSR ≥ 0.95**, honest family-cumulative `n_trials`, leak-free, differential
  validation portable gate, ct_val provenance.
- `n_trials` policy: **per hypothesis family, cumulative** = (prior family trials
  across all batches) + (this run’s grid combos). Different families do **not**
  deflate each other.
- **Retry vs new family:** same economic mechanism tweaked/bugfixed = retry (same
  family budget, counts toward K); genuinely different mechanism = new family
  (fresh budget). Relabeling a retry as a new family to dodge K is forbidden.
- **family retry limit K = 2** (original + 2 retries, then shelve + escalate).
- Backtest is **two-pass**: parquet research-tier pre-screen → DB venue-scoped
  CPCV for survivors. Pre-screen is not promotion evidence but its trials still
  count toward the family.
- “Publish” (step 5) = wire passing candidate as `enabled:false` vetted candidate
  + ledger `supported`; **never** auto-enable, **never** touch demo/shadow/live
  gates.
- Durable record = `HYPOTHESIS_LEDGER.md` + `EXPERIMENT_REGISTRY.md`. Per-batch
  JSON scratch + shortlist live in `results/<batch_id>/` and reconcile into the
  ledgers; nothing long-term lives in `tasks/`.
- First batch candidate order = **[S7, S5, S6]**.
- Roles: **Codex implements** trading-core (`backtesting/`, `src/okx_quant/...`);
  **Claude writes** spec/plan/review. Task 1 is Codex’s; Tasks 2–4 are docs.
- **Deferred to Stage 2 (intentional):** machine-readable JSON batch-state file,
  automated evidence-schema validator, background-parallel orchestration,
  literature-search ingestion. Stage 1 checkpoint is a manual Claude review over
  3 candidates, so the driver reads the ledger and passes numbers directly.

> **Scope note:** This plan builds the *machinery*. It does **not** produce a
> passing strategy. Finding edge happens when the machinery is *run* on
> [S7, S5, S6] — a separate action after this plan lands.

---

### Task 1: Family-cumulative `n_trials` in the candidate scan

The honesty fix. `scan_xs_momentum` is the reference scan every pipeline candidate
mirrors. Today it hard-sets `n_trials = len(combos)` (this-run grid only), which is
exactly the understated count that inflated DSR for S11. Add an explicit
`prior_family_n_trials` so the value fed to CPCV is the family-cumulative count.

**Files:**
- Modify: `backtesting/xs_momentum_backtest.py:86-116` (`scan_xs_momentum`)
- Test: `tests/unit/test_xs_momentum_backtest.py`

**Interfaces:**
- Produces: `scan_xs_momentum(close, high, low, vol, funding, membership, params,
  grid, market_close=None, prior_family_n_trials=0) -> pd.DataFrame` where
  `out.attrs["n_trials"] == prior_family_n_trials + len(combos)` and every row’s
  `"n_trials"` column equals that same total.
- Consumes (downstream): the xs_momentum validation runner reads
  `scan output.attrs["n_trials"]` and passes it as CPCV’s `n_trials` argument.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_xs_momentum_backtest.py` (reuses the existing `_panels()`
fixture and the 16-combo grid from `test_scan_xs_momentum_records_honest_n_trials`):

```python
def test_scan_adds_prior_family_trials_to_n_trials():
    from backtesting.xs_momentum_backtest import scan_xs_momentum

    close, high, low, vol, funding, membership = _panels()
    params = XSMomentumParams(
        universe=list(close.columns),
        rebalance="daily",
        lookback_days=1,
        vol_window_days=2,
        quantile=0.5,
        max_name_weight=1.0,
        vol_target_annual=10.0,
    )
    grid = {
        "lookback_days": [1, 2],
        "skip_days": [0],
        "quantile": [0.25, 0.5],
        "vol_target_annual": [0.1, 0.2],
        "top_n": [2, 3],
    }  # 16 combos

    result = scan_xs_momentum(
        close, high, low, vol, funding, membership, params, grid,
        prior_family_n_trials=10,
    )

    assert result.attrs["n_trials"] == 26
    assert set(result["n_trials"]) == {26}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_xs_momentum_backtest.py::test_scan_adds_prior_family_trials_to_n_trials -v`
Expected: FAIL — `scan_xs_momentum() got an unexpected keyword argument 'prior_family_n_trials'`.

- [ ] **Step 3: Write minimal implementation**

In `backtesting/xs_momentum_backtest.py`, change the signature and the two
`len(combos)` sites:

```python
def scan_xs_momentum(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    funding: pd.DataFrame,
    membership: pd.DataFrame,
    params: XSMomentumParams,
    grid: dict[str, list[Any]],
    market_close: pd.Series | None = None,
    prior_family_n_trials: int = 0,
) -> pd.DataFrame:
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]
    total_n_trials = int(prior_family_n_trials) + len(combos)
    rows = []
    param_fields = set(XSMomentumParams.__dataclass_fields__)
    for combo in combos:
        run_params = replace(params, **{k: v for k, v in combo.items() if k in param_fields})
        result = run_xs_momentum_backtest(
            close, high, low, vol, funding,
            _limit_membership(membership, combo.get("top_n")),
            run_params, market_close=market_close,
        )
        rows.append({**combo, "n_trials": total_n_trials, **result.metrics})
    out = pd.DataFrame(rows)
    out.attrs["n_trials"] = total_n_trials
    return out
```

- [ ] **Step 4: Run tests to verify pass (new + backward-compat)**

Run: `python -m pytest tests/unit/test_xs_momentum_backtest.py -v`
Expected: PASS for both the new test (26) and the existing
`test_scan_xs_momentum_records_honest_n_trials` (still 16, since default is 0).

- [ ] **Step 5: Confirm runner forwards the cumulative count to CPCV**

Locate the runner that calls `cpcv` for xs_momentum (grep for the call site that
produces `results/xs_momentum_validation_*/cpcv.json`; check `backtesting/replay.py`
and any `scripts/` runner). Confirm it passes the scan output’s
`attrs["n_trials"]` as CPCV’s `n_trials`. If it recomputes `n_trials`
independently, change it to use `scan_out.attrs["n_trials"]`. No silent recompute.

- [ ] **Step 6: docs-impact + commit**

Run: `python scripts/docs/check_doc_impact.py`
Then commit:

```bash
git add backtesting/xs_momentum_backtest.py tests/unit/test_xs_momentum_backtest.py
git commit -m "feat(backtest): family-cumulative n_trials in candidate scan

AI-Origin: Codex"
```

---

### Task 2: Trial-accounting convention + invariant + Change Manifest

Operationalize the family-cumulative `n_trials` rule and retry/new-family
distinction as governance, so the manual Stage 1 checkpoint has a written anchor.

**Files:**
- Modify: `docs/EXPERIMENT_REGISTRY.md` (add a “Family trial accounting” section)
- Modify: `docs/HYPOTHESIS_LEDGER.md` (add family-id + cumulative-n_trials columns/notes)
- Modify: `docs/INVARIANTS.md` (add invariant: CPCV `n_trials` ≥ family cumulative)
- Create: `docs/change_manifests/2026-06-25-family-cumulative-n-trials.md`
  (from `docs/CHANGE_MANIFEST_TEMPLATE.md`)
- Modify: `docs/DOC_IMPACT_MATRIX.md` if a row is required for the n_trials rule

- [ ] **Step 1: Write the family trial-accounting convention**

In `docs/EXPERIMENT_REGISTRY.md`, add a section stating: each experiment row
records its `family_id`; a family’s cumulative `n_trials` = sum of (grid combos +
retries) across all rows sharing that `family_id`; CPCV must be fed the family
cumulative, not the per-run grid; retry vs new-family rule (verbatim from Global
Constraints). Add a `family_id` note to the required-fields list.

- [ ] **Step 2: Add the invariant**

In `docs/INVARIANTS.md`, add (next id in sequence, e.g. I23):
“CPCV `n_trials` passed for a candidate MUST be ≥ that family’s cumulative trial
count recorded in `EXPERIMENT_REGISTRY.md`; a per-run grid count alone is a
violation.” Reference the guarding test from Task 1.

- [ ] **Step 3: Write the Change Manifest**

Copy `docs/CHANGE_MANIFEST_TEMPLATE.md` to
`docs/change_manifests/2026-06-25-family-cumulative-n-trials.md` and fill it: rule
changed = how `n_trials` is sourced for the overfit gate; affected =
`backtesting/xs_momentum_backtest.py`, the validation runner, `INVARIANTS.md`;
risk = under-counting inflates DSR; verification = Task 1 tests.

- [ ] **Step 4: Run doc-impact and commit**

Run: `python scripts/docs/check_doc_impact.py`
Expected: PASS (no violations).

```bash
git add docs/EXPERIMENT_REGISTRY.md docs/HYPOTHESIS_LEDGER.md docs/INVARIANTS.md docs/change_manifests/2026-06-25-family-cumulative-n-trials.md docs/DOC_IMPACT_MATRIX.md
git commit -m "docs(validation): family-cumulative n_trials convention + invariant + manifest

AI-Origin: Codex"
```

---

### Task 3: Driver procedure + per-stage subagent templates + shortlist template

The “press once” mechanism. These are the operational documents the driver session
follows; no code.

**Files:**
- Create: `docs/superpowers/pipeline/driver.md` (the kickoff procedure)
- Create: `docs/superpowers/pipeline/stage1-hypothesis.md` (research subagent task template)
- Create: `docs/superpowers/pipeline/stage2-feasibility.md` (feasibility subagent template)
- Create: `docs/superpowers/pipeline/stage3-implement-backtest.md` (Codex subagent template)
- Create: `docs/superpowers/pipeline/shortlist-template.md` (per-batch shortlist format)

- [ ] **Step 1: Write `driver.md`**

Document the kickoff: inputs = `{candidates:[...], K, runtime_cap, data_tier}`;
pre-register the whole batch in the ledgers before running; for each candidate run
Stage 1→3 by dispatching the corresponding subagent template; read each family’s
cumulative `n_trials` from `EXPERIMENT_REGISTRY.md` and pass `prior_family_n_trials`
into the Stage 3 run; STOP at checkpoint① (Claude evidence review using
`docs/REVIEW_QUESTIONS.md` + the gate clauses in `docs/ai_collaboration.md`);
write the shortlist; STOP for the user’s publish decision. Include the stop
conditions (a/b/c) and the retry-vs-new-family rule verbatim.

- [ ] **Step 2: Write the three stage templates**

`stage1-hypothesis.md`: input = backlog candidate id + `strategy_synthesis.md`
section; output = a `HYPOTHESIS_LEDGER` entry (H-xxx) with family_id, testable
signal/entry/exit/sizing/execution/risk spec, planned grid, data needs, validation
path, pre-registered family n_trials budget; pass criterion = all fields present.

`stage2-feasibility.md`: checks (a) data availability in DB/parquet, (b)
correlation-distinctness vs enabled strategies, (c) cheap cost-after-edge smell
test; output PASS→stage3 or FAIL→skip with reason recorded in the ledger.

`stage3-implement-backtest.md`: Codex implements per the stage-1 spec with a
mandatory leak regression test, a `REFERENCE_VALIDATION_CONTRACTS` entry, no
idealized-fill as evidence, ct_val provenance; runs two-pass (parquet pre-screen →
DB CPCV with `prior_family_n_trials`); emits the gate-evidence fields
(candidate_id, family_id, batch_id, grid_size_this_run, family_cumulative_n_trials,
wf_oos_sharpe, cpcv_oos_sharpe, dsr, psr, leak_test_passed,
portable_validation_gate, idealized_fill, ct_val_all_authoritative,
promotion_gate_passed, status) into `results/<batch_id>/<candidate>/summary.json`.

- [ ] **Step 3: Write `shortlist-template.md`**

Per-batch markdown: passing candidates (H-id, family, evidence artifact path,
DSR/PSR/n_trials, Claude verdict note, “next: user publish decision”) + an appendix
of non-passing candidates with reason and cumulative trials.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/pipeline/
git commit -m "docs(pipeline): Stage 1 driver procedure + stage templates + shortlist

AI-Origin: Codex"
```

---

### Task 4: Register the pipeline in state/handoff docs

Make the pipeline discoverable on a cold start and point the strategy backlog at it.

**Files:**
- Modify: `docs/AI_HANDOFF.md` (add a current-state note)
- Modify: `docs/CURRENT_STATE.md` (one-line snapshot entry)
- Modify: `research/strategy_synthesis.md` (note that S5/S6/S7 feed the Stage 1 pipeline; order [S7, S5, S6])

- [ ] **Step 1: Update handoff + current state**

Add: “Strategy Research Pipeline Stage 1 machinery exists (spec
`…2026-06-25-strategy-research-pipeline-design.md`, plan
`…2026-06-25-strategy-research-pipeline-stage1.md`). Manual driver, backlog
source, one Claude checkpoint, family-cumulative n_trials enforced. Not yet run;
first batch = [S7, S5, S6].”

- [ ] **Step 2: Point the backlog at it**

In `research/strategy_synthesis.md`, add a short note near the strategy list that
unimplemented candidates S5/S6/S7 are the Stage 1 pipeline’s first batch in order
[S7, S5, S6].

- [ ] **Step 3: Run doc checks and commit**

Run: `python scripts/docs/check_doc_impact.py`

```bash
git add docs/AI_HANDOFF.md docs/CURRENT_STATE.md research/strategy_synthesis.md
git commit -m "docs: register Strategy Research Pipeline Stage 1

AI-Origin: Codex"
```

---

## Self-Review

**Spec coverage:**
- Locked decisions 1–8 → Global Constraints (all) + Task 3 templates (1,2,3,5,6) +
  Task 1 (4) + Task 2 (4 accounting) + Task 4 (8 registration). ✓
- Section 1 architecture/flow → Task 3 driver.md. ✓
- Section 2 trial-count protocol → Task 1 (code) + Task 2 (convention/invariant). ✓
- Section 3 per-stage contracts → Task 3 stage templates. ✓
- Section 4 checkpoint①/shortlist/publish → Task 3 driver.md + shortlist-template. ✓
- Section 5 reuse/new → reflected; JSON state + evidence validator **deferred to
  Stage 2** per Global Constraints (intentional, not a gap). ✓
- Defaults (K=2, two-pass, candidate order, runtime cap required) → Global
  Constraints + Task 3 driver.md. ✓

**Placeholder scan:** Task 1 has full test + impl code. Doc tasks specify exact
content to write (not “write docs”). No TBD/TODO. ✓

**Type consistency:** `prior_family_n_trials` (int, default 0), `attrs["n_trials"]`,
and the gate-evidence field names are used identically in Tasks 1 and 3. ✓

## Notes for the executor

- Task 1 is the only trading-core code change and belongs to **Codex**. Tasks 2–4
  are governance/process docs.
- This plan deliberately stops at machinery. The first real pipeline **run** on
  [S7, S5, S6] is the next action and is expected to *refute* most candidates —
  that is the gate working, not a failure.
