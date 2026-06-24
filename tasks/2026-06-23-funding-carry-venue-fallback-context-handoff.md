# Context Handoff: Funding Carry Venue Fallback - 2026-06-23

## Goal (one sentence)
Fix the replay backtest crash caused by Binance venue-scoped `BTC-USDT` spot candle gaps blocking the explicit funding-carry spot-to-perp fallback.

## Current state
- Branch: `codex/xs-momentum-universe-scaffold`.
- Last known good commit / state: not changed; existing dirty tree included unrelated XS momentum files.
- In-progress edits (files): `backtesting/replay.py`, `tests/unit/test_data_loader.py`, `docs/DATA_FLOW.md`, `docs/AI_HANDOFF.md`, `docs/CURRENT_STATE.md`, `docs/change_manifests/2026-06-23-funding-carry-venue-fallback.md`, this handoff, and the paired session handoff.
- What works right now: `tests/unit/test_data_loader.py` passes; same-venue fallback now runs after a primary venue gap.
- What does not work / unfinished: no full real DB replay was run; `scripts/smoke/backtest_smoke.py` still skips full replay because the tiny no-DB fixture is a known gap.

## Decisions made (and why)
- Preserve strict R6.4 venue scoping and handle only the explicit fallback path because the existing `funding_carry` caller already names `fallback_inst_id=perp`.
- Do not catch arbitrary `ValueError` because that would hide unrelated data or validation bugs.

## Open questions / unverified assumptions
- Assumption: using the same-venue perp candle series for funding-carry spot synthetic books remains the intended fallback for missing spot candles.

## Rules in play (preserve verbatim)
- Invariants touched: I19 - a venue-tagged run loads candles only from that venue's provenance-tagged canonical series; source-less parquet or another venue cannot substitute missing bars.
- Domain rules touched: R6.4.
- Do-not-touch: `research/`, strategy assumptions, `src/okx_quant/risk/`, `src/okx_quant/portfolio/`, `src/okx_quant/execution/`, existing result artifacts, deployment gates.

## Context to load next (the reading list)
- Source of truth: `AI_CONTEXT.md`, `docs/DATA_FLOW.md`, `docs/DOMAIN_RULES.md`, ADR-0007, `config/settings.yaml`, `config/strategies.yaml`.
- Owning files / MODULE_BRIEFS: `docs/MODULE_BRIEFS/backtesting-engine.md`, `backtesting/replay.py`, `backtesting/data_loader.py`.
- Context Pack: `docs/CONTEXT_PACKS/harness-scaffolding.md` for harness rules.

## Checks run
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\unit\test_data_loader.py -q -p no:cacheprovider` - 8 passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_metadata.py` - passed with 15 pre-existing warnings.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_feature_map_links.py` - passed.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\docs\check_doc_impact.py` - advisory warning remains for unrelated XS momentum strategy file; this fix's A5 warning cleared.
- `C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe scripts\smoke\backtest_smoke.py` - entrypoints pass; full replay smoke skipped by known fixture gap.

## Approvals
- Human approval needed / obtained: no extra approval required for this scoped bug fix; no gate or strategy assumption changed.

## Next action (single, concrete)
- Rerun the user's original funding-carry replay command against the reachable DB to confirm the CLI no longer fails before fallback.

## Human Learning Notes
Venue-scoped gaps are correct for promotion safety, but existing explicit same-venue fallbacks still need to be allowed at the caller boundary; otherwise a safety guard can accidentally block a documented development fallback.
