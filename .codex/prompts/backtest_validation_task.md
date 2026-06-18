# Backtest Validation Task

Use this prompt only when the task explicitly permits validation or backtest-harness work.

Read first:

- `AI_CONTEXT.md`
- `docs/ai_collaboration.md`
- `docs/backtest_live_parity_plan.md`
- `docs/FEATURE_MAP.md`
- `docs/DATA_FLOW.md`
- Relevant ADRs under `docs/ADR/`

Default boundaries:

- Do not change strategy assumptions from chat memory.
- Do not change live/shadow/demo gates.
- Do not modify existing result artifacts.
- Do not touch differential validation files if another session owns that work.

Required evidence:

- Exact fixture/run ID or reason no fixture exists.
- Validation status and whether it is current, target, or known gap.
- `ct_val` provenance status for SWAP artifacts.
- Whether DB parity was PASS, FAIL, or SKIP; never imply SKIP is PASS.
- Tests or smoke commands run.

Completion warning:

- Never claim live readiness unless every gate in `docs/ai_collaboration.md` passed and the user explicitly approved.
