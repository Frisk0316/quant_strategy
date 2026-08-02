---
status: archived
type: handoff
owner: codex
created: 2026-07-31
last_reviewed: 2026-07-31
expires: none
superseded_by: tasks/2026-07-31-xvenue-cot-cboe-context-handoff.md
---

# Context Handoff: H-039 cross-venue options IV - 2026-07-31

## Goal (one sentence)

Implement the user-authorized Stage-0 forward collector and governance record
for H-039 without creating proxy history or changing strategy/deployment rules.

## Current state

- Branch: `feature/deribit-moneyness-hypotheses`.
- Last known good state: mocked ingestion tests and all six public live
  normalizations pass; no commit was created.
- In-progress edits: H-039 client, ingest wiring, six dataset configs, snapshot
  command/wrapper, one unit-test module, hypothesis/governance/runbook docs.
- What works right now: OKX, Bybit, and Deribit BTC/ETH public option responses
  normalize to one nearest-listed-30d hourly row; Tardis OKX/Deribit sample
  headers are calibrated; a recovered snapshot raises a post-write alert when
  the prior bucket gap exceeds 1.5 hours.
- What does not work / unfinished: no row has landed in
  `external_observations` because local TimescaleDB/Docker is offline; no
  scheduled task is registered and the forward data window has not started.

## Decisions made (and why)

- Reuse `external_datasets` / `external_observations` because the existing store
  already supports scalar hourly rows and JSON fields/raw payloads.
- Store one row per venue/currency with nearest-listed-30d ATM IV as
  `value_num`, selected skew/spread/OI fields, and four selected raw legs because
  that is the minimal Stage-0 contract frozen in the named H-039 spec.
- Use source snapshot time as `published_at` and its UTC-hour floor as
  `observed_at` because the observation must not appear available before the
  public response.
- Do not register Task Scheduler from Codex because the repository runbook makes
  user registration the activation step.
- Do not create an experiment row because schema calibration and forward data
  acquisition do not consume a trial or K budget.

## Open questions / unverified assumptions

- The adjacent combined collector/COT/CBOE task describes a richer T1 contract
  (full-chain payload plus two-expiry total-variance interpolation), while the
  user-named H-039 spec now freezes nearest-listed tenor plus four selected
  legs. Claude should resolve that contract before scheduler activation if the
  richer replay requirement is still intended.
- H-039 remains `proposed / data-blocked`; earliest honest Stage 2 is after at
  least 270 daily observations.

## Rules in play (preserve verbatim)

- Invariants touched: I57 - The H-039 collector accepts both legacy Bybit option
  symbols ending in `-C`/`-P` and current symbols with an additional settlement
  suffix such as `-C-USDT`; both forms must preserve expiry, strike, and option
  type instead of silently dropping the full venue chain.
- Domain rules touched: R6.2 external feature publication/as-of provenance.
- Do-not-touch: `research/`, existing `results/`, external-store schema and
  `src/okx_quant/data/external_store.py`, strategy/signal/risk/portfolio/
  execution behavior, live/shadow/demo/deployment gates, and the partial
  Deribit option-flow backfill owned by another session.

## Context to load next (the reading list)

- Source of truth:
  `docs/superpowers/specs/2026-07-31-xvenue-options-iv-hypothesis.md`,
  `config/external_data.yaml`, `docs/HYPOTHESIS_LEDGER.md`,
  `docs/EXPERIMENT_REGISTRY.md`, `docs/DOMAIN_RULES.md`.
- Owning files:
  `src/okx_quant/data/external_clients/xvenue_option_surface.py`,
  `scripts/market_data/ingest_external.py`,
  `scripts/market_data/snapshot_xvenue_options.py`,
  `tests/unit/test_xvenue_option_surface.py`, `docs/FEATURE_MAP.md`,
  `docs/DATA_FLOW.md`, `docs/RUNBOOK.md`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md`.

## Checks run

- `python -m pytest tests/unit/test_xvenue_option_surface.py
  tests/unit/test_external_data.py -q` - 13 passed; pytest cache write warning
  only.
- Targeted Ruff - passed.
- `scripts/validate_pipeline.py --check-config-only` - passed.
- Doc metadata - passed with two pre-existing missing-metadata warnings.
- Feature-map links, ledger consistency, advisory doc impact, and
  `git diff --check` - passed.
- Six public live fetches - passed for OKX/Bybit/Deribit BTC/ETH.
- First DB snapshot - blocked before writes with connection refused because
  TimescaleDB/Docker is offline.

## Approvals

- Human approval obtained through the 2026-07-31 user request for H-039 Stage 0.
- Human activation still required for Windows Task Scheduler registration.
- No approval exists for proxy history, Stage 2/3, strategy changes, or
  deployment.

## Next action (single, concrete)

- Start local TimescaleDB, then run
  `python scripts\market_data\snapshot_xvenue_options.py` once and verify all six
  dataset rows before registering the hourly task.

## Human Learning Notes

Bybit's current option symbols may append a settlement token after the option
type (`-C-USDT` / `-P-USDT`); assuming that call/put is always the final token
silently removes the entire live chain. Also, a passing public-API smoke does
not start a research data window: the clock begins only after verified DB
persistence and scheduler activation.
