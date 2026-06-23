# D3 Review — XS Momentum + Universe Scaffold (2026-06-23, Claude)

Reviewer: Claude. Scope: Codex implementation of
`docs/superpowers/plans/2026-06-23-xs-momentum-universe.md` against the spec
`docs/superpowers/specs/2026-06-23-xs-momentum-universe-design.md`,
`docs/REVIEW_QUESTIONS.md`, `docs/CRITIQUE_PROTOCOL.md`, and `docs/DOMAIN_RULES.md`.

## Verdict

**Scaffold (Phase A + B + D1) is complete, sound, and honestly documented.
Phase C (the entire validation) was not done, so there is zero edge/return
evidence.** One funding-sign error was found — in the *plan*, not Codex's code —
and has been corrected. All XS code is currently uncommitted on branch
`fix/ohlcv-exchange-provenance`.

## Verification run

| Check | Result |
|---|---|
| `tests/unit/test_xs_momentum.py`, `tests/unit/test_universe_membership.py` | 9/9 PASS |
| `python scripts/docs/check_doc_impact.py` | PASS (27 changed files, no impact-matrix violations) |
| config load + replay registry builds `xs_momentum` | PASS (covered by tests) |
| `universe_membership.parquet` | 30 symbols, 2024-01-01→2026-06-21, ≤16 eligible/day after $10M ADV filter |
| 1m parquet breadth | 28 symbols present |

Not run: full `tests/unit` suite (changes are additive; recommend before PR),
any backtest (Phase C absent), DB-backed venue parity (no DSN seeded for new coins).

## Done & verified
- **A:** `config/universe.yaml` (top30 / ADV $10M / full deny-list); `scripts/build_universe_membership.py` — survivorship logic correct (`active=dv.notna()` so delisted→out; warmup enforced via shifted rolling count; ADV uses `shift(1)` → no same-day lookahead); membership artifact generated.
- **B:** `dollar_neutral_long_short_weights` (net 0, gross-normalized); `vol_normalized_momentum`; `target_weights` (membership filter + neutrality + cap tested); crash scaler; disabled strategy stub; config schema; replay registry wiring. Tests are meaningful.
- **D1:** ADR-0009, Change Manifest, INVARIANTS **I20**, FAILURE_MODES **F19**, and `check_doc_impact.py` rules *strengthened* (added FAILURE_MODES + universe.yaml/DATA_FLOW coverage). ADR + manifest are honest about what remains.

## Not done (the substance)
- **Phase C entirely absent:** no `backtesting/xs_momentum_backtest.py`, no funding accounting, no `scan_xs_momentum`/honest `n_trials`, no walk-forward, no CPCV, no DSR/PSR, no `results/` artifact → **no edge evidence at all.**
- **A2 coverage report** (`results/universe_coverage_*.json`) not produced (data is present though).
- **Canonical-DB seeding** for new universe coins unverified — builder reads parquet directly; current state is research-tier, not promotion-grade (venue-scoped DB reads required for promotion).

## Findings
1. **[Plan error — FIXED]** Plan Task C1 said the short leg *pays* positive funding; `DOMAIN_RULES.md` R3.1 is the opposite (long pays positive, short receives). Codex correctly **deferred C1** rather than implement the wrong sign — good implementer judgment. Plan corrected in commit `5c80cc7`; R3.1 is canonical; **C1 is now unblocked** (short receives positive funding; net book funding sums across both legs).
2. **[Code — fix in Phase C]** `xs_momentum.py` vol-target gross `min(1, vol_target_annual / median_daily_vol)` is not annualized; in crypto the ratio is >1 so `gross` pins to 1.0 → **vol-targeting is effectively a no-op**. Annualize (e.g. ×√365 on the daily vol, or target daily) and prefer portfolio-vol over median-name-vol.
3. **[Code — wired in Phase C]** crash filter is inert unless `market_close` is passed; the Phase C runner must supply the market series. Unit test exercises it directly, so the mechanism is sound.

## Risks / state
- ⚠️ **All XS scaffold is uncommitted** and mixed on `fix/ohlcv-exchange-provenance` (which also carries unrelated commit `52b4f81` OHLCV-source-exchange). Recommend Codex commit the scaffold (own branch + `AI-Origin: Codex` trailer) before it is lost. Claude did **not** commit Codex's trading-core (role boundary).
- `enabled: false`, no validation → **no promotion/live claim permitted** (consistent with ADR-0009).

## Decision / next
1. Codex: commit scaffold; build **Phase C** with corrected funding sign (R3.1), fix vol-target annualization, wire `market_close` into the crash filter, seed canonical DB for promotion-grade runs.
2. After Phase C artifacts exist: Claude re-reviews; **WF/CPCV + DSR/PSR ≥ 0.95** decide whether this alpha stands. Until then it is design + scaffold only.
