---
status: current
type: review
owner: claude
created: 2026-07-30
last_reviewed: 2026-07-30
expires: none
superseded_by: null
---

# Decision memo: official CME BTC futures data (H-037) — recommend NOT buying

This is the third of three data-unblock plannings requested 2026-07-30. Unlike
the optflow and FRED gaps, the honest planning outcome here is **do not write
an ingestion task yet**. The reasoning is below so the decision is not
re-litigated from scratch later.

## What was verified (scouted 2026-07-30)

- `cme_btc_yfinance` exists and holds **634 rows, 2024-01-02 → 2026-07-10**
  (already stale; not on a schedule). It is `research_only: true` with the note
  "not for promotion/deployment evidence" — a Yahoo OHLCV proxy, no official
  settle, no roll metadata.
- `cme_btc1_continuous` is configured (adapter `nasdaq_data_link`, gated on
  `CME_BTC1_DATASET_CODE` + `NASDAQ_DATA_LINK_API_KEY`, both absent) and holds
  **0 rows**. The config's own note says CHRIS/CME_BTC1 is deliberately unused
  because the legacy continuous-futures dataset is discontinued/stale — web
  research confirms the CHRIS database is deprecated and no longer updated.
- **No free source of multi-year official CME BTC daily settlement history was
  found.** CME's own site publishes current-day settlements only and overwrites
  them daily; historical EOD is sold through CME DataMine (custom pricing).
  Nasdaq Data Link's remaining official CME datasets are premium. Barchart's
  bulk history needs Premier. Databento / Portara / FirstRate are all paid.
- `cme_gap_fill` (`config/strategies.yaml`, `external_features.py:197-260`) is
  `enabled: false` and points at the **empty official** dataset, not the proxy —
  it is correctly inert rather than quietly running on unofficial data.

## Why buying daily data would not fix H-037

H-037's citation (JIMF 2025) is about **intraday** price leadership. Our spec
already conceded that daily-resolution CME data can only test a coarse
session-boundary implication of it, and `backtesting/cme_session_probe.py`
carries that limitation as an explicit `DAILY_LIMITATION` constant.

So a daily-settlement subscription would buy us a weak proxy test of a claim we
could not actually evaluate. Testing the real mechanism needs **paid intraday**
CME data (Databento-class), which is a materially larger spend. Spending the
smaller amount would produce evidence that is not much more informative than
what we already refused to accept from the free proxy.

## Options (user decides; none are urgent)

1. **Leave H-037 blocked (recommended).** Status stays `inconclusive /
   data-blocked` — the mechanism is untested, not refuted. Costs nothing and
   misrepresents nothing. Revisit only if intraday CME data arrives for some
   other reason.
2. **Re-scope H-037 to the coarse daily implication and run it on the free
   yfinance proxy.** Cheap and immediate, but the result could never be
   promotion evidence (R7.1: unofficial/advisory data is not promotion
   evidence), so a PASS would not advance anything and a FAIL would not
   cleanly refute the paper's actual claim. If chosen, the hypothesis text
   must be rewritten first so the weaker claim is what is registered ex ante —
   not reinterpreted after the fact.
3. **Buy daily official data** (Nasdaq Data Link premium or CME DataMine; the
   client code already exists, so ingestion would need only the two env vars).
   Not recommended, per the section above.
4. **Buy intraday CME data** to test the real mechanism. This is the only
   option that genuinely unblocks H-037, and it is the largest spend. Worth
   considering only if intraday cross-venue work becomes a broader priority —
   note that shelved H-010/F-XVENUE-LEADLAG also died partly on venue data, so
   a single intraday purchase could serve more than one hypothesis.

## Recommendation

Option 1. H-037 was flagged as the weakest of the eight candidates when it was
registered, and the data investigation has confirmed that judgement: the cheap
purchase does not test the claim, and the expensive one is not justified by a
single weak candidate. If the user later wants intraday venue data for
several purposes at once, revisit option 4 as a data-strategy decision rather
than an H-037 decision.

## Not blocked by this memo

Nothing else depends on CME data. `cme_gap_fill` stays disabled and correctly
wired to the official dataset; H-037 stays `inconclusive`.
