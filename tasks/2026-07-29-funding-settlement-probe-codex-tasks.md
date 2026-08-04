---
status: current
type: task
owner: claude
created: 2026-07-29
last_reviewed: 2026-07-29
expires: none
superseded_by: null
---

# H-029 F-FUNDING-SETTLEMENT-DRIFT Stage-2 probe — Codex tasks

Contract (read first): `docs/superpowers/specs/2026-07-29-event-probe-hypotheses.md`
§H-029 — the frozen signal, window, grid, power inputs, and distinctness
references live there and bind verbatim. User authorized Stage 2 + conditional
Stage 3 on 2026-07-29. Pattern precedent: `backtesting/moneyness_vol_probe.py`
(E-064..E-067 shape); H-028 is registration-only — do NOT build or run
anything for it.

## Key implementation notes (beyond the spec)

- Data: `funding_rates` (source='binance', 8h regular, verified 2020-01→
  2026-07-02) + `canonical_candles` 1m binance BTC/ETH (verified through
  2026-07-14). Window end frozen 2026-07-02 — no new ingestion needed or
  permitted in this task.
- Event returns: entry at settlement ts + 1min (next 1m bar open), exit at
  entry + hold, both legs costed at trade time (8 bps round trip total).
  No F36-style signal-day costing.
- Power: `min_detectable_sharpe(breadth=1.5, n_obs=<pooled traded-eligible
  settlement timestamps>, n_trials=4, periods_per_year=1095)`. n_obs counts
  distinct settlement TIMESTAMPS (not ×2 symbols); per-event returns pool the
  two symbols' positions into one event PnL. Declare all inputs in the
  artifact.
- Distinctness on daily-aggregated event PnL, |corr| < 0.30, ≥365 common
  days: E-031/E-063 dated series (`results/idea_batch_20260701_taxonomy_002/f_funding_xs_dispersion/family_minting_candidate.json`
  signal — mandatory) + F-VOL-REGIME-OPT
  (`results/h014_stage3_20260714/combo_daily_returns.csv`) + E-026
  F-FUNDING-CARRY only if a dated series artifact exists (locate under
  results/pipeline_batch2*/c2_funding_carry/; if only an undated summary
  exists, report the I49 gap to Claude and proceed with the other two gates —
  Claude's ruling: E-026's mechanism distinction is documented ex-ante in the
  spec, so its reference is best-effort, unlike the mandatory funding-XS gate).
- I49 pre-flight before DB probe work, as in the moneyness batch.
- Stage 3 only on four-check PASS: frozen 4-cell grid, family-cumulative
  n_trials = 4, retained CPCV path returns, K untouched (original validation).
- Bookkeeping identical to E-064..E-067: one EXPERIMENT_REGISTRY entry (next
  free E-number), ledger status update, artifacts + SHA-256 under
  `results/funding_settlement_probe_20260729/`.

## PERMITTED FILES

- `backtesting/funding_settlement_probe.py` (new; may reuse shared helpers
  from moneyness_vol_probe by import, not copy),
  `backtesting/pipeline_stage2_registry.py` (one CandidateSpec + probe
  wiring), `backtesting/pipeline_stage3_registry.py` (only if Stage 3 runs)
- `tests/unit/test_funding_settlement_probe.py` (new)
- `results/funding_settlement_probe_20260729/**` (new artifacts only)
- `docs/EXPERIMENT_REGISTRY.md`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/AI_HANDOFF.md`, `config/workstreams.yaml`, `docs/CHANGELOG_AI.md`

## FORBIDDEN

- `src/okx_quant/**`, `config/*.yaml` except workstreams, existing
  `results/**` artifacts, `research/**`, any ingestion run
- Any H-028 implementation; any signal/threshold change after seeing results;
  Stage 3 without a four-check PASS

ACCEPTANCE CRITERIA (binary):
- [ ] I49 pre-flight ran before DB probe access; any reference gap reported,
      not recorded as a distinctness fail.
- [ ] Event construction test: fixture funding rows + 1m bars → correct entry
      bar (ts+1min), exit bar, per-event cost application, z-eligibility.
- [ ] Power inputs in the artifact match the frozen convention (breadth 1.5,
      periods_per_year 1095, declared n_obs).
- [ ] One registry entry with SHA-256 + ledger update; K/trials untouched
      unless Stage 3 ran (then family n_trials=4 recorded).
- [ ] `python -m pytest tests/unit/test_funding_settlement_probe.py -v`
      green; ledger consistency passes; diff only in permitted files.

REPORT: standard AGENTS.md block + check-by-check verdict table with headline
numbers (coverage, corrs, annualized net Sharpe vs floor). Questions to
Claude instead of silent deviation.
