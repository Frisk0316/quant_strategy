---
status: current
type: task
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# Stage-2 probe modules for the registered slate (H-030…H-037) — Codex tasks

Contracts (read first; the frozen signals, grids, windows, power inputs, and
distinctness references live there and bind verbatim):
- `docs/superpowers/specs/2026-07-29-literature-slate-h030-h031.md`
- `docs/superpowers/specs/2026-07-29-literature-slate-h032-h037.md`

This is **ADR-0016 phase 3** work: give every counted candidate a registered
deterministic Stage-2 runner. Pattern precedent: `backtesting/moneyness_vol_probe.py`
and `backtesting/funding_settlement_probe.py` (E-064…E-068 shape). Reuse
`min_detectable_sharpe` (`pipeline_power_screen.py`) and
`load_reference_series`/`abs_correlation` (`xvenue_leadlag_probe.py`).
Windows: no `make`.

## Scope of authorization for this task

- **Build** the modules for H-030…H-037 and **run Stage 2** for each.
- **Stage 3 is NOT authorized here.** A four-check PASS stops with the artifact
  written and the outcome registered; each Stage-3 grid needs its own user
  authorization (eight families' first validations would otherwise consume a
  large amount of family trial budget in one unreviewed batch).
- **H-038 / F-S5-RESIDUAL-MEANREV is out of scope entirely** — it would take
  F-S5 to K 2/2, which is terminal for that family, and needs separate explicit
  authorization.

## Global contract (all candidates)

- Four checks per candidate: data / distinctness / cost / power, with the
  frozen first grid cell as the Stage-2 proxy (declared in the artifact).
- **I49 pre-flight before any DB probe access**, whole-batch: for every
  distinctness reference, verify the required common-day overlap is
  structurally attainable. A shortfall is a contract stop reported to Claude,
  never recorded as a distinctness failure.
- Costs 8 bps round trip per traded event, applied at trade time (no F36-style
  signal-day costing).
- Power inputs declared honestly per the spec's per-candidate convention
  (breadth, n_obs, periods_per_year, n_trials=4 prospective). Never annualize
  an event-spaced return series at 365 unless the events are daily.
- Any check FAIL → stop that candidate, write the artifact, register the honest
  outcome, no retune, continue to the next candidate.
- One EXPERIMENT_REGISTRY entry per executed candidate (next free E-numbers,
  sequential) + HYPOTHESIS_LEDGER status/resolution update, artifacts with
  SHA-256 under `results/slate_stage2_20260729/<candidate_dir>/`.

## Slices, in order (each is its own commit)

**S1 — H-030 F-INTRABAR-PERIODICITY (highest priority, ship first).**
`backtesting/intrabar_periodicity_probe.py`. Signed taker imbalance at
quarter-hour boundary minutes from `market_klines.raw_payload.raw[9]/[10]`
(the fields `taker_flow_probe.py` already parses — reuse, do not reimplement).
This is the only candidate whose event count plausibly clears the power floor
that killed H-024…H-029 and H-029/E-068, so its result is the most informative
single output of this task. Its distinctness vs **F-TAKER-FLOW / E-059 is
decisive**: correlation at or above the MINT threshold falsifies the
"boundary timing, not flow level" mechanism claim — record and stop, do not
reshape the signal.

**S2 — options-derived: H-031 F-OPT-EXPIRY-GAMMA, H-035 F-OPT-LARGE-TRADE-INFO.**
`backtesting/options_flow_probe.py` (shared helpers, one probe fn each). Both
consume `optflow_deribit_*` 2024-01+. H-031 needs a flow-derived dealer-gamma
proxy — its approximation weakness (unknown initial position, snapshot-only
`optsurf` has no usable history) must be stated **in the artifact**, not just
in code comments. H-035 conditions on **trade size** (top-decile), which is the
whole mechanism claim; distinctness vs E-044 and E-064 is decisive for it.
Formal windows end at the last day with complete bucket fields (archive lag).

**S3 — macro/event: H-033 F-MACRO-EVENT-DRIFT, H-036 F-XASSET-MACRO-LEAD.**
`backtesting/macro_state_probe.py`. H-033 needs the FOMC calendar (public,
fixed — commit the dates used as a frozen fixture so the run is reproducible)
and a FRED 2-year-yield surprise proxy. H-036 uses FRED VIX / broad dollar
index / gold. Both are expected to be power-marginal (H-033 has ~48 events,
H-036 is a daily breadth-2 book); a power fail is an honest stop.

**S4 — candle/vol-derived: H-032 F-VOL-OF-VOL, H-034 F-VARIANCE-DECOMP,
H-037 F-CME-LEADERSHIP.** `backtesting/vol_structure_probe.py` for H-032
(VoV = realized vol of DVOL) and H-034 (realized semivariance / jump
decomposition over the PIT universe from 1m candles);
`backtesting/cme_session_probe.py` for H-037. H-032's distinctness vs E-050
and E-067 and H-034's vs E-062 are the decisive gates. H-037 is the weakest
candidate (daily-only CME data tests a coarse implication of an intraday
finding) — say so in its artifact.

**S5 — registration + wrap-up.** CandidateSpec + STAGE2_PROBES entries for all
eight in `pipeline_stage2_registry.py`; unit tests per module (feature
construction from fixtures + the I49 refusal path); ledger/registry updates;
`python scripts/docs/check_doc_impact.py`; AI_HANDOFF/workstreams one-line sync.

## PERMITTED FILES

- `backtesting/intrabar_periodicity_probe.py`, `backtesting/options_flow_probe.py`,
  `backtesting/macro_state_probe.py`, `backtesting/vol_structure_probe.py`,
  `backtesting/cme_session_probe.py` (new), `backtesting/pipeline_stage2_registry.py`
- `tests/unit/test_intrabar_periodicity_probe.py`, `tests/unit/test_options_flow_probe.py`,
  `tests/unit/test_macro_state_probe.py`, `tests/unit/test_vol_structure_probe.py`,
  `tests/unit/test_cme_session_probe.py` (new), `tests/unit/test_pipeline_stage2_registry.py`
- `tests/fixtures/` (new FOMC-date fixture only)
- `results/slate_stage2_20260729/**` (new artifacts only)
- `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`, `docs/FEATURE_MAP.md`,
  `docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`

## FORBIDDEN

- `src/okx_quant/**`, `config/*.yaml` except workstreams, `research/**`,
  existing `results/**` artifacts, any ingestion run
- **Any Stage-3 grid, for any candidate** (separate authorization required)
- Any H-038 / F-S5 work
- Any signal, threshold, window, or grid change after seeing results

ACCEPTANCE CRITERIA (binary):
- [ ] Whole-batch I49 pre-flight ran before DB access; shortfalls reported as
      contract stops, not distinctness failures.
- [ ] Eight artifacts, each with four named checks, declared power inputs, and
      SHA-256; eight registry entries; eight ledger status updates.
- [ ] H-031's gamma-proxy limitation and H-037's daily-resolution limitation
      appear in their artifacts.
- [ ] Zero Stage-3 runs; family trials and K unchanged for all eight families.
- [ ] `python -m pytest tests/unit/test_intrabar_periodicity_probe.py
      tests/unit/test_options_flow_probe.py tests/unit/test_macro_state_probe.py
      tests/unit/test_vol_structure_probe.py tests/unit/test_cme_session_probe.py
      tests/unit/test_pipeline_stage2_registry.py -v` green.
- [ ] Ledger consistency check passes; diff only in permitted files.

REPORT: standard AGENTS.md block + a per-candidate verdict table (check-by-check
PASS/FAIL with headline numbers: coverage, max |corr| and against what,
annualized net Sharpe, power floor). Questions to Claude instead of silent
deviation — especially if a spec's frozen signal cannot be computed from the
data as written.
