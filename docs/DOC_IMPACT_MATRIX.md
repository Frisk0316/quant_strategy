---
status: current
type: governance
owner: human
created: 2026-06-12
last_reviewed: 2026-07-12
expires: none
superseded_by: null
---

# Doc Impact Matrix

Maps **changed areas** to the documents and artifacts that must be reviewed or
updated in the same change. This is the human-readable mirror of the rules
enforced by `scripts/docs/check_doc_impact.py` (run via `make docs-impact`).

The script is the executable source of truth for *enforcement*; this table is
the source of truth for *intent*. Keep them in sync: when you add a rule here,
add the matching rule in the script, and vice versa.

Legend:

- **Manifest?** — does a change in this area require a Change Manifest
  (`docs/CHANGE_MANIFEST_TEMPLATE.md`)? Yes for business-rule areas.
- **ADR?** — does changing the *rule* (not just the code) require an ADR?

| # | Changed area (trigger) | Must also review / update | Manifest? | ADR? |
|---|---|---|---|---|
| A1 | `src/okx_quant/strategies/`, `src/okx_quant/signals/` | `research/strategy_synthesis.md`, `docs/DOMAIN_RULES.md`, `docs/FEATURE_MAP.md`, `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, relevant ADR | Yes | If assumptions change |
| A2 | `src/okx_quant/portfolio/`, `src/okx_quant/execution/` | `docs/DOMAIN_RULES.md` (R1–R5), `docs/INVARIANTS.md`, `docs/FAILURE_MODES.md`, relevant ADR | Yes | If accounting/fill policy changes |
| A3 | `src/okx_quant/risk/`, `config/risk.yaml` | `docs/DOMAIN_RULES.md` (R4), `docs/INVARIANTS.md`, `docs/ai_collaboration.md`, relevant ADR | Yes | If limits/semantics change |
| A4 | `config/strategies.yaml`, `config/settings.yaml`, `config/universe.yaml` | `docs/DOMAIN_RULES.md`, `docs/FEATURE_MAP.md`, `docs/DATA_FLOW.md`, `research/strategy_synthesis.md` | Yes | If a mode/gate changes |
| A5 | `backtesting/`, `scripts/run_backtest.py`, `scripts/run_replay_backtest.py` | `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md`, `docs/GOLDEN_CASES.md`, `docs/INVARIANTS.md`, ADR-0002/0005; CPCV result-retention/schema changes must also review `docs/KNOWN_ISSUES.md` and `docs/EXPERIMENT_REGISTRY.md` | Yes | If result schema or gates change |
| A6 | `sql/`, DB schema / migrations | `docs/DATA_FLOW.md`, ADR-0002, `docs/KNOWN_ISSUES.md` | Yes | Yes |
| A7 | `src/okx_quant/api/` | `docs/UI_MAP.md`, `docs/DATA_FLOW.md`, `docs/FEATURE_MAP.md` | No | If schema contract changes |
| A8 | `frontend/` | `docs/UI_MAP.md`, `docs/FEATURE_MAP.md` | No | No |
| A9 | Validation / gates (replay/WF/CPCV, differential/source-provenance validation, research execution controls, pipeline checkpoint, DSR/PSR audit tooling) | `docs/DOMAIN_RULES.md` (R7), `docs/ai_collaboration.md`, ADR-0005, `docs/INVARIANTS.md`; n_trials provenance changes must also review `docs/EXPERIMENT_REGISTRY.md` | Yes | Yes |
| A10 | Core governance contracts/tooling (`AGENTS.md`, `CLAUDE.md`, `AI_CONTEXT.md`, workflow/lifecycle/branch/output/collaboration/impact docs, `check_doc_impact.py`) | `docs/README.md`, `docs/DOC_LIFECYCLE.md`, this matrix | No | If authority order changes |
| A11 | Experiments / research runs | `docs/HYPOTHESIS_LEDGER.md`, `docs/EXPERIMENT_REGISTRY.md` | No | No |

A11 is not represented as a changed-file rule in `check_doc_impact.py`: research
artifacts may be gitignored or external, so a diff-only rule would create false
assurance. Ledger cross-consistency needs a dedicated validator; until that task
lands, A11 remains an explicit review requirement.

## Rules of use

1. A change touching a **Manifest? = Yes** area is a *business-rule change*.
   Create or update a Change Manifest before completion.
2. Check every "Must also review / update" cell for the areas you touched. If a
   listed doc genuinely needs no change, say so explicitly in the Change
   Manifest rather than silently skipping it.
3. `make docs-impact` is advisory by default (warnings, exit 0) and strict under
   `--strict` (violations become errors). CI / merge gating should run strict.
4. This matrix does not replace judgement. A change that affects money or risk
   but is not listed here still requires a manifest — add the missing row.

Related: [[DOMAIN_RULES]] · [[CHANGE_MANIFEST_TEMPLATE]] · [[ADR/README]].
