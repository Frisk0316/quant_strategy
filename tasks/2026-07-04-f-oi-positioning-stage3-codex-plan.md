---
status: archived
type: plan
owner: ai
created: 2026-07-04
last_reviewed: 2026-07-04
expires: 2026-08-04
superseded_by: null
---

# Codex Dispatch: F-OI-POSITIONING OI backfill + Stage-3 (H-012)

Claude-written plan (AI_WORKFLOW roles: Claude plans, Codex implements, user
approves). Spec source (user-signed-off 2026-07-04, including the directed
universe-wide OI backfill):
`docs/superpowers/specs/2026-07-04-f-oi-positioning-hypothesis.md`.
Two sequential tasks; **B is gated on A's probe PASS** (≥ 10 OI-good symbols).

---

## Task A — Universe-wide OI backfill + extended Stage-2 probe

```text
Read AGENTS.md first, then execute:

Task: Backfill Binance Vision 5m OI history for the remaining point-in-time
universe symbols (BTC/ETH already ingested, E-034), then extend and run the
Stage-2 OI probe PIT-aware over the universe, and record the verdict.
Strategy/spec source: docs/superpowers/specs/2026-07-04-f-oi-positioning-hypothesis.md
(Instruments + Hand-off step 0); precedents: E-034 (BTC/ETH OI probe),
E-030 funding probe (PIT/warmup-aware per-symbol coverage pattern).
Required behavior:
(1) Extend scripts/market_data/download_binance_vision_metrics.py so its
    DATASETS symbol→dataset-id mapping covers the PIT-universe symbols
    (data/universe/universe_membership.parquet union), convention
    oi_binance_hist_<base-lowercase>. Mapping/generalization only — no new
    ingestion path, no schema change. Symbols listed mid-window have no
    Vision zips before listing: start each symbol at max(2024-01-01, its
    first PIT-membership day) and tolerate missing daily zips the way the
    existing MissingDailyZip handling does; do not fabricate rows.
(2) Run the backfill for all missing symbols over 2024-01-01 →
    2026-06-17T00:00:00Z end-exclusive.
(3) Extend backtesting/pipeline_stage2_registry.py's OI probe (or add an
    oi-universe entry) to evaluate per-symbol coverage/missing/stale over
    each symbol's PIT-eligible span, mirroring the funding probe's
    warmup-aware pattern, with min_good_symbols=10; keep the existing
    fixed-window BTC/ETH probe behavior and the E-034 artifact untouched.
(4) Emit a new probe artifact under results/, record a new E-row, and update
    H-012's note with the good-symbol list/count.

NETWORK CAVEAT: the OKX backfill attempt failed in-sandbox
(httpx.ConnectError WinError 10013, escalation rejected — see E-035). If
data.binance.vision is likewise unreachable, STOP, report the exact
command(s) for a local/user run, and record the gap — do not invent a
workaround or substitute data.

PERMITTED FILES (only edit these):
- scripts/market_data/download_binance_vision_metrics.py (mapping extension only)
- backtesting/pipeline_stage2_registry.py
- scripts/run_pipeline_stage2_data_probe.py
- tests/unit/ (probe/mapping tests only)
- docs/EXPERIMENT_REGISTRY.md (new E-row); docs/HYPOTHESIS_LEDGER.md (H-012 note)
- results/ (new artifacts only; never modify existing artifacts, incl. E-034's)

FORBIDDEN (do not touch):
- src/okx_quant/{strategies,signals,risk,portfolio,execution}/ ; config/risk.yaml
- research/ ; any existing results/** artifact
- canonical_candles / funding ingestion paths (OI metrics only)

SCOPE LIMIT: fix only what is described; no adjacent refactoring. Long
download runtime is an acceptable partial outcome — report per-symbol
progress + remaining list instead of shortcuts.

REQUIRED ON COMPLETION:
- git diff --stat; pytest tests/unit -k "stage2 or vision or pipeline" -q tail;
  probe summary output; per-symbol row counts.
- Do not commit unless the user asks.

ACCEPTANCE CRITERIA (binary):
- [ ] Every PIT-universe symbol either has ingested OI rows or an explicit
      per-symbol gap reason (no silent omissions).
- [ ] Extended probe ran PIT-aware; artifact lists per-symbol coverage,
      missing_ratio, stale_ratio, and the good-symbol set.
- [ ] Verdict recorded: PASS (≥10 good symbols) or FAIL/blocked — either is
      valid; no strategy claim.
- [ ] New E-row + H-012 note update link the artifact; E-034 artifact untouched.
- [ ] Diff contains only permitted files.

REPORT: changed files, test tail, probe summary, per-symbol gaps, assumptions,
anything UNCONFIRMED or skipped.
Also read docs/ai/JUDGMENT_RUBRICS.md §2 and §5 before reporting completion.
```

---

## Task B — Stage-3 build + checkpoint ① (GATED on Task A probe PASS)

```text
Read AGENTS.md first, then execute:

Task: Implement the F-OI-POSITIONING Stage-3 research backtest per the
signed-off Stage-1 spec and run it through checkpoint ①.
Strategy/spec source: docs/superpowers/specs/2026-07-04-f-oi-positioning-hypothesis.md
(authoritative for signal, sizing, grid, guards — do not redesign);
implementation skeleton precedent: backtesting/funding_xs_dispersion_backtest.py
and the E-031 Stage-3 wiring.
Required behavior:
(1) PRE-FLIGHT: run backtesting/pipeline_family_minting.py with the
    constructed OI-fade signal vs the F-FUNDING-XS-DISPERSION reference
    (E-031 artifacts); record family_minting.json. On ASSIGN/SKIP_RECOMMENDED:
    fold into that family's trial/K budget per I27, update H-012, STOP for
    Claude/user review — do not run the grid under a fresh budget.
(2) New research module backtesting/oi_positioning_backtest.py patterned on
    funding_xs_dispersion_backtest.py. OI loading per spec: contract count
    from fields.open_interest_contracts (NEVER value_num — USDT notional is
    mechanically price-correlated), quality_status != 'suspect', daily sample
    = last observation <= daily close ts, no cross-day forward fill.
(3) Signal/construction/sizing/costs exactly per spec (90d z-normalized
    L-day ΔlogOI, fade on z <= -z_min, flat otherwise; inverse-vol,
    max_name_weight=0.10, vol_target_annual=0.175, daily, fee/slip 2/2 bps;
    R3.1 funding cashflow on held positions; ct_val provenance per I16).
(4) Pre-registered grid ONLY: L ∈ {3,7} × z_min ∈ {0.0,0.5} (4 combos),
    fold-refit WF/CPCV via backtesting/pipeline_refit.py, caller-declared
    family n_trials=4, retained CPCV path_returns (I25), no idealized fill
    (I17), mandatory leak test (t+1 shift, xs_momentum fixed pattern),
    REFERENCE_VALIDATION_CONTRACTS entry.
(5) Data-integrity report: per-symbol count of zero-Δ-contract days; if >5%
    of days for a symbol, flag it and exclude that symbol pending review
    (record the exclusion), per spec.
(6) Run scripts/run_pipeline_checkpoint1_check.py; STOP at checkpoint ① per
    the contract. Record new E-row + H-012 update. No promotion/live claim.

PERMITTED FILES (only edit these):
- backtesting/oi_positioning_backtest.py (new)
- Stage-3 registry/runner wiring following the E-031 precedent (locate first;
  list the exact files in your report)
- tests/unit/ (new module + leak/integrity tests)
- docs/EXPERIMENT_REGISTRY.md, docs/HYPOTHESIS_LEDGER.md (H-012)
- results/ (new artifacts only)

FORBIDDEN (do not touch):
- src/okx_quant/{strategies,signals,risk,portfolio,execution}/ ; config/risk.yaml
- xs_momentum_backtest.py, funding_xs_dispersion_backtest.py (read/reuse, no edits)
- research/ ; any existing results/** artifact
- grid values, thresholds, or gates beyond the spec (no chase-the-gate)

SCOPE LIMIT: fix only what is described; no adjacent refactoring.

REQUIRED ON COMPLETION:
- git diff --stat; pytest tail for the new tests + "stage2 or stage3 or
  pipeline" selection; family_minting verdict; checkpoint1_auto.json status;
  WF/CPCV/DSR/PSR numbers; realized breadth (symbol count).
- Do not commit unless the user asks.

ACCEPTANCE CRITERIA (binary):
- [ ] family_minting.json recorded BEFORE grid; ASSIGN handled per I27 (stop).
- [ ] Grid is exactly the 4 pre-registered combos; n_trials=4 reconciles to
      the registry (I23); checkpoint1_auto.json present (I26).
- [ ] Leak test green; path_returns retained; no idealized fill; zero-ΔOI
      integrity report present.
- [ ] E-row + H-012 updated; STOPPED at checkpoint ① with no promotion claim.
- [ ] Diff contains only permitted files.

REPORT: changed files, test tail, minting verdict, checkpoint numbers,
assumptions, anything UNCONFIRMED or skipped.
Also read docs/ai/JUDGMENT_RUBRICS.md §2 and §5 before reporting completion.
```

---

## Sequencing

1. Task A now. If sandbox network blocks Binance Vision, A ends as a
   gap report with exact local-run commands (same handling as E-035).
2. Task B only after A's probe records PASS (≥ 10 OI-good symbols).
3. After checkpoint ① evidence exists → back to Claude/user for review
   (precedent: E-031 → user-ratified verdict). No promotion, adapter, demo,
   shadow, or live work in either task.
