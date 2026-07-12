---
status: archived
type: plan
owner: ai
created: 2026-07-04
last_reviewed: 2026-07-04
expires: 2026-08-04
superseded_by: null
---

# Codex Dispatch: Pipeline Next Candidates (F-OI-POSITIONING, F-XVENUE-LEADLAG)

Claude-written plan (AI_WORKFLOW roles: Claude plans, Codex implements, user
approves scope before Codex starts). Two independent tasks; A can start now,
B is gated on OKX backfill state. Stage-1 specs remain Claude's job after the
probes pass — Codex does NOT write hypothesis specs.

Note: the P9 merge blocker (universe membership timestamp precision) is
already committed as `1c97399` — no Codex action needed there.

---

## Task A — F-OI-POSITIONING Stage-2 data probe (ready now)

```text
Read AGENTS.md first, then execute:

Task: Run a Stage-2 data-availability probe for F-OI-POSITIONING (open-interest
positioning candidate from taxonomy_002) against the ingested Binance Vision
5m OI history, and record the verdict in both ledgers.
Strategy/spec source: docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md
(F-OI-POSITIONING row) + results/idea_batch_20260701_taxonomy_002/idea_batch.json
(it was skipped as data_blocked on 2026-07-01; the OI tables
oi_binance_hist_{btc,eth} now exist with 262,814 rows each, 2024-01-01→now).
Required behavior: extend backtesting/pipeline_stage2_registry.py +
scripts/run_pipeline_stage2_data_probe.py with an F-OI-POSITIONING entry
(precedent: the E-030 funding-dispersion probe entry) measuring coverage,
missing_ratio, stale_ratio for the OI series over the probe window, and emit
the standard probe artifact under results/.

PERMITTED FILES (only edit these):
- scripts/run_pipeline_stage2_data_probe.py
- backtesting/pipeline_stage2_registry.py
- tests/unit/ (new/updated probe-registry test only)
- docs/EXPERIMENT_REGISTRY.md (new E-row)
- docs/HYPOTHESIS_LEDGER.md (new proposed H-row for F-OI-POSITIONING,
  precedent: H-010 placeholder row)
- results/ (new probe artifact only; never modify existing artifacts)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ , src/okx_quant/signals/
- src/okx_quant/risk/ , src/okx_quant/portfolio/ , src/okx_quant/execution/
- config/risk.yaml
- research/
- any existing results/** artifact
- any Stage-1 spec writing (Claude's job)

SCOPE LIMIT: fix only what is described; no adjacent refactoring.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run: pytest tests/unit -k "stage2 or pipeline" -q and paste the output tail;
  then the probe command itself and paste its summary output.
- Update docs per the AGENTS.md docs-update matrix (EXPERIMENT_REGISTRY +
  HYPOTHESIS_LEDGER rows count as the experiment-update requirement).
- Do not commit unless the user asks.

ACCEPTANCE CRITERIA (binary):
- [ ] Probe runs against oi_binance_hist_{btc,eth} and emits an artifact with
      coverage / missing_ratio / stale_ratio for the probe window.
- [ ] Verdict recorded as data-available or data-blocked (either is a valid
      outcome; no strategy claim either way).
- [ ] New E-row in EXPERIMENT_REGISTRY and proposed H-row in HYPOTHESIS_LEDGER,
      both linking the artifact path.
- [ ] Diff contains only permitted files; no existing artifact modified.

REPORT: changed files, test output tail, probe summary, assumptions made,
anything UNCONFIRMED or skipped.

Also read docs/ai/JUDGMENT_RUBRICS.md §2 (definition of done) and §5
(quality floor) before reporting completion.
```

---

## Task B — F-XVENUE-LEADLAG backfill check + Stage-2 reprobe (gated)

```text
Read AGENTS.md first, then execute:

Task: Verify whether the OKX BTC/ETH-USDT-SWAP 1m backfill has completed, and
if the E-029 probe window is now covered, rerun the Stage-2 probe for
F-XVENUE-LEADLAG; otherwise report remaining gap and continue the backfill.
Strategy/spec source: docs/EXPERIMENT_REGISTRY.md E-029 (OKX 0 rows / 0.0
coverage, I19 forbids cross-venue substitution) +
docs/superpowers/specs/2026-06-30-mechanism-taxonomy.md (backfill was started
via keyless scripts/market_data/ingest.py --exchange okx).
Required behavior: (1) measure current OKX venue-scoped 1m coverage for
BTC-USDT-SWAP and ETH-USDT-SWAP over the E-029 probe window; (2) if coverage
is incomplete, resume/continue the existing ingest command — do not write a
new ingestion path; (3) once covered, rerun
scripts/run_pipeline_stage2_data_probe.py for F-XVENUE-LEADLAG and record a
new E-row (E-029 stays as the historical blocked probe; H-010 status updates).

PERMITTED FILES (only edit these):
- docs/EXPERIMENT_REGISTRY.md (new E-row)
- docs/HYPOTHESIS_LEDGER.md (H-010 row update)
- results/ (new probe artifact only)
- scripts/run_pipeline_stage2_data_probe.py (only if the reprobe needs a
  window/venue parameter fix; no behavior redesign)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ , src/okx_quant/signals/ , src/okx_quant/risk/ ,
  src/okx_quant/portfolio/ , src/okx_quant/execution/ , config/risk.yaml
- research/ ; any existing results/** artifact
- scripts/market_data/ingest.py (run it, don't edit it)
- cross-venue substitution of any kind (I19)

SCOPE LIMIT: fix only what is described; no adjacent refactoring. Long
backfill runtime is an acceptable partial outcome — report progress + ETA
instead of inventing a shortcut.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Paste OKX coverage numbers before/after, and probe summary if it ran.
- Update docs per the AGENTS.md docs-update matrix.
- Do not commit unless the user asks.

ACCEPTANCE CRITERIA (binary):
- [ ] OKX 1m coverage for both legs over the E-029 window is measured and
      reported with row counts.
- [ ] Either: reprobe ran with a new E-row + H-010 update, OR: a concrete
      remaining-gap report (symbols, date ranges, ETA) with backfill resumed.
- [ ] No cross-venue fill used anywhere (I19).
- [ ] Diff contains only permitted files.

REPORT: coverage numbers, probe/backfill output tail, assumptions made,
anything UNCONFIRMED or skipped.

Also read docs/ai/JUDGMENT_RUBRICS.md §2 (definition of done) and §5
(quality floor) before reporting completion.
```

---

## Sequencing

1. Task A now (independent, data already ingested).
2. Task B now or in parallel — worst case it only reports backfill gap/ETA.
3. After a probe passes → user brings the result back to Claude for the
   Stage-1 hypothesis spec (precedent:
   `docs/superpowers/specs/2026-07-04-f-funding-xs-dispersion-hypothesis.md`),
   then a Stage-3 checkpoint task gets planned separately with a
   pre-registered grid and family n_trials.
