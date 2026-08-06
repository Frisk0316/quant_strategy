---
status: current
type: research
owner: claude
created: 2026-08-06
last_reviewed: 2026-08-06
expires: none
superseded_by: null
---

# Data inventory — what is in the DB and what no hypothesis has used

Step 1 of the candidate-quality plan: inventory confirmed data *before* searching
literature, because nine of thirty represented hypotheses never confirmed their
required input (`tasks/2026-08-05-candidate-input-quality-review.md`). This
answers "what could a candidate stand on today", not "what should we build".

Read-only. No experiment ran, no trial or K was consumed, no `results/**` file
changed.

## Method and as-of

- Source: `external_datasets` left-joined to a grouped `external_observations`
  scan, queried 2026-08-06 against the live TimescaleDB (`docker-timescaledb-1`).
- Consumption is cross-referenced against every `docs/superpowers/specs/*.md`,
  by dataset id. A dataset is "consumed" if any registered hypothesis spec names
  it — including hypotheses that were later refuted or shelved.
- Gap and publication-lag figures are measured per dataset, not assumed.
- 78 datasets exist in the registry; one (`oi_binance_hist_shib`) has zero rows.

**Measurement caveat:** the first pass ran during the F78 outage, when three
collectors had been failing since 2026-08-03. Staleness figures below were taken
after that fix landed. Treat any freshness claim as of 2026-08-06 only.

## The binding constraint is the crypto side, not the external series

This correction governs everything below. `cboe_vix` has 9,241 daily rows back
to 1990 and the COT series have 1,051 weekly rows back to 2006, but a crypto
strategy can only use the **overlap with crypto returns**. Canonical candles
cover 2024–2026, and the repository's most recent dated daily return series
(E-095) is 898 observations. So:

- usable daily observations ≈ **898**, not 9,241;
- usable weekly observations ≈ **128**, not 1,051.

Raw `market_klines` holds OKX 1m from 2020 which is not promoted into the
canonical layer (see `docs/KNOWN_ISSUES.md`). Extending the crypto side is a
separate authorized task; until it happens, long external history buys nothing.

## Datasets no registered hypothesis has used

| Dataset | Rows | Range | Max gap | Publication lag |
| --- | ---: | --- | --- | --- |
| `cboe_vix` | 9,241 | 1990-01-02 → 2026-07-31 | 7 d | +1 d, 0 leaky rows |
| `cboe_vix6m` | 4,674 | 2008-01-02 → 2026-07-31 | 5 d | +1 d, 0 leaky rows |
| `cboe_vix3m` | 4,242 | 2009-09-18 → 2026-07-31 | 5 d | +1 d, 0 leaky rows |
| `cboe_vix9d` | 3,916 | 2011-01-04 → 2026-07-31 | 5 d | +1 d, 0 leaky rows |
| `cot_es` | 1,051 | 2006-06-13 → 2026-07-28 | 8 d | +2d20:30 … +4d20:30 |
| `cot_gold` | 1,051 | 2006-06-13 → 2026-07-28 | 8 d | as above |
| `cot_usd_index` | 1,051 | 2006-06-13 → 2026-07-28 | 8 d | as above |
| `cot_ust10y` | 1,051 | 2006-06-13 → 2026-07-28 | 8 d | as above |
| `rv30_deribit_btc_1h` | 68,959 | 2018-09-14 → 2026-07-27 | — | — |
| `rv30_deribit_eth_1h` | 63,871 | 2019-04-14 → 2026-07-27 | — | — |
| `gold_yfinance` | 1,653 | 2020-01-02 → 2026-07-29 | — | research-only proxy |
| `cme_btc_yfinance` | 634 | 2024-01-02 → 2026-07-10 | — | research-only proxy |
| `hv_deribit_btc/eth_1h` | 554 each | 2026-07-10 → 2026-08-02 | — | rolling window only |
| `oi_binance_btc/eth` | 500 each | 2026-07-12 → 2026-08-02 | — | hourly, short |
| `cboe_pcr_total` | 3,253 | 2006-11-01 → **2019-10-04** | 5 d | discontinued archive |

Cboe gap structure is clean: average spacing 1.45 days and **zero gaps over
seven days** across all five series — that is a US trading calendar, not missing
data. COT averages exactly 7.00 days with eleven gaps over seven days in the
20-year series, consistent with holiday weeks.

Both families have `published_at > observed_at` on every row, so an as-of join
is expressible. **But** COT's `published_at` is the standard scheduled Friday
15:30 ET, not a historical holiday-release calendar (`docs/KNOWN_ISSUES.md`), so
holiday-delay weeks must stay fail-closed until that calendar is supplied.

## Datasets already consumed, and how that went

| Dataset family | Consumed by | Outcome |
| --- | --- | --- |
| `optflow_deribit_*`, `optsurf_deribit_*` | H-030, H-031, F-VRP-TIMING, F-OPTFLOW-POSITIONING | cost/power FAIL or data-blocked |
| `dvol_deribit_*_1h` | H-014, F-VRP-TIMING | H-014 `supported`, promotion-blocked |
| `oi_binance_hist_*` | F-OI-POSITIONING, H-012 | shelved |
| `funding_deribit_*` | H-021 | refuted at Stage 3 |
| `fear_greed_btc` | C3 | refuted |
| `liq_okx_*` | H-028, H-029 | data-blocked until ~2027-07 |
| `xvenue_opt_iv_*` | H-039 | Stage 2 blocked until ~270 obs |
| `dgs2`, `dgs10`, `vixcls`, `dtwexbgs`, `cm_*`, `wiki_pageviews_*`, `cot_cme_btc/eth` | H-040…H-046 | closed 2026-08-02; refuted, data-blocked, or power FAIL |

**Negative precedent that matters:** H-033/H-036 took FRED macro inputs
(DGS2, VIXCLS, DTWEXBGS) plus a gold proxy into crypto and were closed by
H-045/H-046 on power. The unconsumed Cboe and COT series are adjacent to that
failed direction. What is genuinely untried is the *term structure* (VIX9D /
VIX / VIX3M / VIX6M slope) and *positioning structure* (COT trader-category
composition), rather than a single macro level. That is a difference, not a
reason to expect a different result.

## Two data defects found

1. `oi_binance_hist_shib` has **zero rows** while the other 29 symbols each hold
   about 258,000. Any universe built from that family silently drops SHIB.
2. `optsurf_deribit_btc` / `_eth` have **3 rows each**. Option-surface history is
   snapshot-only with no forward scheduler; it cannot support a time-series
   hypothesis in its current state.

## No recurring ingest exists for most of this

Only three external families are on a registered Windows task:
`liq_okx_*` (`quant_liq_okx_ingest`), `xvenue_opt_iv_*`
(`quant_xvenue_options_iv`), and `dvol_deribit_*_1h` (topped up by
`quant_h014_shadow_daily`).

Cboe, COT, FRED, Coin Metrics, Wikimedia, Fear&Greed, Binance OI, RV30, HV,
option flow/surface, Deribit funding, and both Yahoo proxies have **no scheduled
incremental ingest at all**. This is the open item in `config/workstreams.yaml`
("Decide the recurring weekly/daily incremental ingest schedule").

Consequence for candidate admission: a candidate resting on an unscheduled
dataset has a valid research path but **no live path**, because nothing keeps
its input current. That belongs in the admission packet's A2 provenance, not
discovered at deployment.

## What this inventory is not

It is A1-grade on row counts, ranges, gaps, and publication lag. It does not yet
carry per-dataset timezone/key confirmation, expected-row denominators, or query
hashes. A candidate admission packet must add those for the specific datasets it
names; see `tasks/2026-08-06-vix-cot-candidate-packets.md` for the first two.

Related: `tasks/2026-08-05-candidate-input-quality-review.md`,
`docs/KNOWN_ISSUES.md`, `docs/DATA_FLOW.md`, `config/workstreams.yaml`.
