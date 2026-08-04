---
status: current
type: handoff
owner: claude
created: 2026-08-03
last_reviewed: 2026-08-03
expires: none
superseded_by: null
---

# Handoff: Whole-repo optimization audit — 2026-08-03

Merged Context+Session handoff. Detail: `2026-08-03-project-optimization-codex-plan.md`.

## Goal / Implementation summary
Scan the whole repo + collaboration architecture; diagnose correctness,
efficiency, security, trading-safety, maintainability; deliver a Codex-ready
plan. No production code changed. Two multi-agent rounds (11 areas, 24 agents),
every finding adversarially re-verified, highest-risk items re-read by Claude.

## Diff scope / Docs updated
Added: the plan file, this handoff. Changed (pointers only):
`docs/CURRENT_STATE.md`, `docs/AI_HANDOFF.md`. Deleted: none. The plan lists the
docs each future workstream must update.

## Current state — headline risks (all Claude-verified in source)
- **F1 high, UNGATED** `monitoring/telegram_alert.py:46` — `command_loop` never
  checks `msg["chat"]["id"]`/`from.id` against `_chat_id`, so anyone who can
  message the bot can `/kill` trading or `/reset` the RiskGuard (clears kill +
  soft_stop, restores every size multiplier to 1.0) despite `reset()`'s
  "Requires operator confirmation" docstring. Fix is in `monitoring/` — not a
  protected path.
- **A2 critical** `routes_data.py:437` — `DELETE /api/data/pairs/..` reaches
  `shutil.rmtree` and can wipe `data/` (no `..`/`.` validation).
- **A1 critical** `server.py:46-52,173` — binds `0.0.0.0` by default, auth fails
  open when `API_KEY` unset. Both rounds flagged it independently.
- **B1 high** `run_okx_demo_smoke.py:48` — live-trade-permission OKX key shared
  with demo/live paths (2026-07-31 isolation task unimplemented).
- **C3/C5** `broker.py:87` drops `reduceOnly`; `engine.py:124` fabricates
  `ctVal=0.01` (ETH is 0.1 → 10× sizing error).

Round 2 cleared clean: no real credential in git history (`.env` never tracked),
zero notebooks, tests never touch real network/DB, the frontend's one raw-HTML
sink is unreachable, all 28 HTTP clients set timeouts, no unsafe deserialization.

## Decisions made (and why)
Six workstreams, not micro-tasks. WS-C and F2 are PLAN ONLY and gated — they
touch execution/risk/portfolio, so AGENTS.md requires per-item authorization +
Change Manifest. F1 ranked above WS-A despite being found second: high severity,
small diff, no authorization needed.

## Open questions / Rules in play (preserve verbatim)
WS-C severities assume the live path is reachable with a real key (today
demo/shadow-gated). F1's exposure depends on bot discoverability; the defect is
unconditional. Claude does not edit `strategies/signals/risk/portfolio/
execution/` or `config/risk.yaml`. Business-rule changes need a Change Manifest
+ `check_doc_impact.py --strict`. No live/demo/shadow readiness claim; only
`docs/ai_collaboration.md` gates + explicit user approval can.

## Context to load next / Checks / Approvals / Business-rule? / Experiments
Load: the plan file; `docs/DOC_IMPACT_MATRIX.md` +
`docs/CHANGE_MANIFEST_TEMPLATE.md` before WS-C/F2;
`tasks/2026-07-31-okx-demo-credential-isolation-codex-tasks.md` for B1.
No test/build run (diagnosis + planning only). Docs gates PASS:
`check_doc_metadata.py` (2 pre-existing warnings), `check_feature_map_links.py`
(284 paths), `check_ledger_consistency.py`. No approvals sought or granted; no
business-rule change; no source-of-truth edits; no experiment run.

## Known limitations / risks / Rollback
Findings reflect the working tree at audit time and a concurrent session is
editing docs — re-verify file:line before implementing. Coverage is broad, but
"no finding" is not proof of absence where neither round instrumented (e.g.
runtime behavior under load). Rollback: delete the two added files, revert the
doc appends.

## Next action / Questions for human review
User triages the plan and authorizes the ungated batch (F1 + WS-A + B1); Codex
implements per the §WS-A Codex Task block plus §WS-F F1. Open: (1) authorize
that batch? (2) which WS-C items, in what order (plan recommends
C5→C3→C2→C6→C1→C7→C8)? (3) keep the worklog task's bare `Bash` + auto-push (F6)?

## Human Learning Notes
- Pattern across both rounds: **safety code that exists and reads correct, but
  is never wired to what would make it fire** — CircuitBreaker with no callers,
  drawdown updated only on fills, a kill switch that doesn't flatten, `reset()`
  documenting an operator check no caller performs. Trace who feeds the guard.
- Docstrings and handoffs asserted guarantees the enforcement layer never
  provided (worklog "scope-limited to docs/worklogs/" was prompt prose only).
  Treat a documented constraint as a claim to verify, not a fact.
- `resumeFromRunId` replayed finished agents from cache after session limits.
