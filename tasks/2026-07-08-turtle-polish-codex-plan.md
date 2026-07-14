---
status: archived
type: plan
owner: ai
created: 2026-07-08
last_reviewed: 2026-07-08
expires: 2026-08-08
superseded_by: null
---

# Codex Dispatch: Turtle optional polish (non-blocking)

Claude-written plan. Turtle is already ACCEPTED/usable (2026-07-04); these are
the three items `docs/AI_HANDOFF.md` Next Steps #2 marked "optional, schedule
if the user asks" — the user has now asked. UI/reference-display only, no
strategy/signal/risk/gate change, no Change Manifest required (nothing in
`docs/DOMAIN_RULES.md` scope changes).

```text
Read AGENTS.md first, then execute:

Task: Three independent, non-blocking Turtle UI polish items. Do each as a
separate commit; they touch different code paths and can be done in any order.
Confirmed findings (do not re-derive):

(1) Warmup hint hardcodes 55d.
    `frontend/view-config.js:859-874` builds a `warmupMin` map used to warn
    when the backtest window is too short; the turtle entry
    (`view-config.js:864`, `turtle: 55 * 24 * 60`) hardcodes 55 days
    regardless of the user's actual enter/leave-term params (system 2's
    enter_term_sys2/leave_term_sys2 default to 55/20, but system 1's
    enter_term_sys1/leave_term_sys1 are user-editable 6-30 range per
    `SWEEP_PARAM_SPECS.turtle`, view-config.js:102+). Fix: derive the warmup
    estimate from `max(enter_term_sys1, enter_term_sys2)` (the longest
    Donchian lookback actually in play for the current params) instead of a
    fixed 55.

(2) invest_pct fixed-vs-range unit convention is a heuristic guess.
    `normalizeInvestPct` (`view-config.js:150-153`) guesses fraction-vs-percent
    by magnitude (`n > 1 ? n / 100 : n`), used at `view-config.js:1336,1345` to
    reconcile sweep result rows. Meanwhile the fixed-param slider
    (`view-config.js:1091-1104`) always stores/sends `invest_pct` as a
    fraction (0.0-1.0), and the sweep axis text input
    (`view-config.js:1388-1390`, label "invest_pct percent axis") takes
    percent values (0.1-100) parsed via `parseSweepValues`. The heuristic is
    ambiguous at the boundary (e.g. a genuine invest_pct=1.0 fraction reads as
    100%, indistinguishable from someone typing "1" meaning 1%). Fix: make the
    two paths emit a self-describing value (e.g. sweep rows already carry
    whatever unit the backend echoes back — confirm in
    `src/okx_quant/api/routes_backtest.py` around `invest_pct`/`float_fields`,
    routes_backtest.py:908,936) and replace the magnitude heuristic with an
    explicit unit tag or a single canonical unit end-to-end. Locate the exact
    backend field first; do not change what unit the backend accepts/returns
    for existing non-turtle strategies.

(3) Heatmap has no hover/click detail.
    `HeatmapChart` (`frontend/charts.js:1299-1363`) renders a static SVG grid;
    cells only show an inline text label when large enough
    (`charts.js:1345-1350`), no `title`, `onMouseEnter`/`onMouseMove`, or
    `onClick` handler exists, so small grids (many x/y combos) show no value
    at all and there's no way to inspect an exact cell. Fix: add a hover
    tooltip (reuse whatever tooltip pattern `LineChart`/`TradePriceChart` in
    the same file already use, if any — check before inventing a new one) and
    an onClick that surfaces the exact (x, y, value) for a cell, consistent
    with how `TurtleSweepPanel` (view-config.js:1294+) already selects a row
    from `investRows`.

PERMITTED FILES (only edit these):
- frontend/view-config.js
- frontend/charts.js
- frontend/styles.css (only if a hover/tooltip needs a class, no unrelated
  style changes)
- tests/ or frontend smoke checks if any exist for these files (check first;
  do not invent a new test harness for three small UI fixes)
- docs/AI_HANDOFF.md, docs/CURRENT_STATE.md, config/workstreams.yaml (status
  update only)

FORBIDDEN (do not touch):
- src/okx_quant/{strategies,signals,risk,portfolio,execution}/ ; config/risk.yaml
- Any backend field the fix in (2) discovers is shared with non-turtle
  strategies -- if invest_pct semantics are genuinely shared, stop and report
  instead of changing shared backend behavior.
- docs/HYPOTHESIS_LEDGER.md, docs/EXPERIMENT_REGISTRY.md (not a research change)
- research/ ; any existing results/** artifact

SCOPE LIMIT: fix only the three items above; no adjacent refactoring of
view-config.js or charts.js.

REQUIRED ON COMPLETION:
- git diff --stat; `node --check frontend/view-config.js frontend/charts.js`
  (or the repo's existing frontend-check equivalent per AGENTS.md docs update
  matrix); manual verification notes (screenshot or described browser check)
  since this is UI behavior -- static checks alone don't prove the hover/
  click/warmup-estimate actually works.
- Do not commit unless the user asks.

ACCEPTANCE CRITERIA (binary):
- [ ] Warmup hint scales with the user's actual enter-term params, not a
      fixed 55.
- [ ] invest_pct unit is no longer inferred by a `n > 1` magnitude guess for
      the turtle sweep-result reconciliation path (or the report explains why
      the heuristic is actually safe, with evidence).
- [ ] Heatmap cells expose their (x, y, value) on hover and/or click.
- [ ] Diff contains only permitted files; no strategy/risk/gate/backend
      shared-semantics change.

REPORT: changed files, verification evidence (frontend check + manual/browser
check), assumptions made, anything UNCONFIRMED or skipped.
Also read docs/ai/JUDGMENT_RUBRICS.md §2 and §5 before reporting completion.
```
