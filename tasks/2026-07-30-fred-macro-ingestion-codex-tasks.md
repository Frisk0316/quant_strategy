---
status: current
type: task
owner: claude
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Ingest FRED macro series (unblocks H-033, and 2 of 3 inputs for H-036)

Why: E-071/E-072 stopped data-blocked — `external_observations` holds **zero**
FRED rows. H-033 needs `DGS2`; H-036 needs `VIXCLS`, `DTWEXBGS`, and a gold
series.

## Verified facts (scouted 2026-07-30, do not re-derive)

- `src/okx_quant/data/external_clients/fred.py` is a **generic** FRED client
  (arbitrary `series_id`, enforces `publish_lag_days >= 1` against lookahead).
  Only one dataset is configured today: `config/external_data.yaml:242-254`
  (`dgs10`, `api_key_env: FRED_API_KEY`, `publish_lag_days: 1`).
- So the three FRED additions are **config-only, zero new code**.
- Series status: `VIXCLS` active from 1990-01-02 (daily); `DTWEXBGS` active
  from 2006-01-02 (daily, successor to the discontinued `DTWEXB`); `DGS2`
  active from 1976-06-01 (business daily).
- **Gold is not available on FRED.** `GOLDAMGBD228N` / the LBMA AM fixing
  family was **discontinued and removed**; FRED carries no current daily
  gold price series. A substitute is required.
- FRED API keys are **free and instant** (no paid tier); 120 req/min general,
  40 req/min for series observations.
- `FRED_API_KEY` is **absent** from both `.env` and the OS environment, and
  `.env.example` does not list it.

## PRECONDITION (user action — Codex cannot do this)

The user registers a free FRED key at `fredaccount.stlouisfed.org` and adds
`FRED_API_KEY=<key>` to `.env`. **Do not start T2 before the key exists**;
verify with a single read-only API smoke call and stop with a clear message if
it is missing or rejected.

## T1 — Config entries (no code)

Add four `config/external_data.yaml` datasets, mirroring the existing `dgs10`
block's shape:
- `vixcls` → series `VIXCLS`
- `dtwexbgs` → series `DTWEXBGS`
- `dgs2` → series `DGS2`
- `gold_yfinance` → reuse the existing `YFinanceClient` with `ticker: GC=F`
  (COMEX gold futures continuous), `research_only: true`, mirroring the
  `cme_btc_yfinance` block's shape and its "not promotion evidence" note.

Keep `publish_lag_days: 1` on all FRED entries — the anti-lookahead guard is
the reason the client enforces it, and H-033's whole design is event-timing.

Also add `FRED_API_KEY=` to `.env.example` (it is missing today).

**Honesty requirement for the gold entry:** its notes must state plainly that
this is a futures proxy from an unofficial source standing in for a
discontinued FRED series, and that H-036's gold leg therefore rests on
research-only data. Do not silently present it as equivalent to the paper's
input.

Acceptance (binary):
- [ ] Four entries added; no existing entry modified.
- [ ] `python scripts/check_config.py` (or the repo's config validator, the
      one `validate_pipeline.py --check-config-only` invokes) passes.
- [ ] `.env.example` lists `FRED_API_KEY`.

## T2 — Smoke, then ingest

1. Smoke one series (`--dataset dgs2 --start 2026-01-01 --dry-run`, then a real
   short window) and confirm rows land with sane values and `published_at`
   honouring the lag.
2. Full ingest from **2020-01-01** (the common window our candle history
   supports) to now for all four datasets.

Acceptance (binary):
- [ ] Coverage report per dataset: min/max `observed_at`, row count. VIXCLS,
      DTWEXBGS, DGS2 should be business-daily with no unexplained multi-week
      gaps; gaps that are genuine market holidays are fine and must be named
      as such rather than "fixed".
- [ ] `published_at > observed_at` on every FRED row (anti-lookahead).
- [ ] No existing dataset's rows changed.

## T3 — Docs

`config/external_data.yaml` notes (done in T1), `docs/DATA_FLOW.md`,
`docs/FEATURE_MAP.md`, `docs/RUNBOOK.md` (the ingest command + the key
requirement), `docs/AI_HANDOFF.md`, `config/workstreams.yaml`,
`docs/CHANGELOG_AI.md`. Run `python scripts/docs/check_doc_impact.py` and
follow what it flags.

**Out of scope:** any change to the H-033/H-036 probe modules, any Stage-2
re-run, and any judgement about whether the gold proxy is research-acceptable
— that is a Claude/user call recorded separately.

## PERMITTED FILES

`config/external_data.yaml`, `.env.example`, `docs/DATA_FLOW.md`,
`docs/FEATURE_MAP.md`, `docs/RUNBOOK.md`, `docs/AI_HANDOFF.md`,
`config/workstreams.yaml`, `docs/CHANGELOG_AI.md`, and a new
`tests/unit/` test only if one is genuinely needed for the config shape.

## FORBIDDEN

`src/okx_quant/**` (the FRED client needs no change — if you believe it does,
stop and report), `config/risk.yaml`, `config/settings.yaml`, `backtesting/**`,
existing `results/**`, any ledger row, any Stage-2/Stage-3 run, and committing
`.env` or any real key.

REPORT: standard AGENTS.md block plus the per-dataset coverage table.
