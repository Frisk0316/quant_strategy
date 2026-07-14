---
status: current
type: report
owner: codex
created: 2026-07-13
last_reviewed: 2026-07-13
expires: 2026-10-13
superseded_by: null
---

# Full Deribit BTC/ETH option-chain history: acquisition options

Retrieved 2026-07-13. This is a purchase comparison only: no account,
credential, quote request, or purchase was created.

| Vendor | Coverage window | Granularity | Delivery | Public price relevant to full history | License fit for this repo |
|---|---|---|---|---|---|
| **Tardis.dev** | Deribit instruments, including options, since **2019-03-30**; normalized `options_chain` is one daily file for all active options. | Tick-level option summaries from Deribit WebSocket feeds: bid/ask, IV, Greeks, underlying, strike, and expiry. | Daily gzip CSV; raw replay API and local replay tooling on Pro/Business. | Options plan: Academic $350, Solo $700, Pro $1,000, Business **$3,000/month**. Only Business with yearly billing advertises all available history; other yearly tiers provide four years. | Best fit. Terms allow internal storage/manipulation and derived data; raw redistribution/resale is restricted. Business supports up to 10 keys and vendor onboarding. |
| **Amberdata** | Full history is available with yearly billing, but the public Deribit product page does not state an exact raw-chain start date; confirm it in the quote. Its published hourly Deribit BTC/ETH SVI history starts **2019-04-01**. | Raw trades/order-book events plus one-minute book snapshots; Level-1 chain streams at 100 ms but the historical endpoint returns the first observation per 1m/1h/1d interval. | REST, WebSocket, AWS S3 bulk add-on, and CSV through API docs. | **Quote required**; no numeric market-data price is published. Full API history requires yearly billing and S3 is an add-on. | Standard license permits commercial internal use but prohibits redistribution, resale, and sublicensing; API keys are single-tenant. Good institutional fit after price/start-date confirmation. |
| **Laevitas** | Historical Deribit contract, snapshot, IV, price, OI, and underlying endpoints exist, but the public docs do not commit to a complete start date. Premium advertises one year; full-history retention must be confirmed. | API-selected granularity with pagination capped at 144 items per page; chain snapshot and per-contract analytics, not a documented bulk tick-chain dump. | REST API on Enterprise; CSV export on Premium; custom high-throughput delivery by quote. | Enterprise **$500/month per seat**; Custom Enterprise is quote-based. | Weak fit for a retained backtest corpus: public terms restrict storing/archiving and derived use unless explicitly authorized. Written license clarification would be required. |

**Recommended / why / monthly cost:** **Tardis.dev Options Business — $3,000/month
(yearly billing)**, because it is the only compared public offer that explicitly
combines all available Deribit history with a normalized, reproducible bulk
`options_chain` format and an internal-storage license. Before purchase, ask for
a one-off Deribit BTC/ETH-only history quote and confirm derived-artifact sharing;
the user makes the purchase decision.

## Official sources

- Tardis Deribit coverage and free samples:
  https://docs.tardis.dev/historical-data-details/deribit
- Tardis options-chain schema and CSV delivery:
  https://docs.tardis.dev/downloadable-csv-files/data-types
- Tardis pricing and full-history tier:
  https://tardis.dev/ and
  https://docs.tardis.dev/faq/billing-and-subscriptions
- Tardis license:
  https://docs.tardis.dev/legal/terms-of-service
- Amberdata Deribit datasets and Level-1 chain:
  https://www.amberdata.io/deribit-market-data and
  https://docs.amberdata.io/http/analytics/derivatives/level-1-quotes
- Amberdata pricing/history/license FAQ:
  https://www.amberdata.io/pricing and
  https://www.amberdata.io/online-market-data-ordering-faq
- Laevitas historical options API, pricing, and terms:
  https://docs.laevitas.ch/options/historical,
  https://www.laevitas.ch/contact/contact, and
  https://www.laevitas.ch/TermsOfService/
