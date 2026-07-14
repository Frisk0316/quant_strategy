---
status: archived
type: task
owner: claude
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Task (Claude → Codex): close the three harness/CI governance gaps

Three governance gaps in `docs/KNOWN_ISSUES.md` are **harness/CI implementation**
(Makefile, CI workflow, smoke fixtures, frontend tests) — Codex's lane. The
docs-only governance gaps (lifecycle metadata; AI_HANDOFF→CHANGELOG migration) are
handled separately by Claude. Do these three in priority order. **No trading-core,
gate, or research-logic change.**

## P1 — Run the crypto-alpha-lab suite in verify + CI (correctness gap)

`research/crypto-alpha-lab/` is a separate Python package with its own tests, but
`make verify` and `.github/workflows/ci.yml` only run `pytest tests/unit`. The lab
tests are currently never executed, and collecting them inside the `tests/unit`
invocation fails with `ImportError: crypto_alpha_lab` (documented in KNOWN_ISSUES).

- Add a Makefile target (e.g. `lab-test:`) that runs the lab suite **isolated** from
  `tests/unit`, e.g. `cd research/crypto-alpha-lab && $(PYTEST)` or
  `$(PYTEST) research/crypto-alpha-lab/tests` with the lab as rootdir, so it picks
  up the lab's own `pyproject.toml` and resolves `crypto_alpha_lab`.
- Wire it into `verify` (or a clearly separate CI job/step) as its **own** step, not
  merged into the `tests/unit` pytest call.
- Add a matching step to `ci.yml` (`pip install -e research/crypto-alpha-lab` then
  run its tests, as its own job/step).
- Do **not** edit the lab's source/logic — only the invocation. If a rootdir/import
  fix is unavoidable, prefer pytest config over touching `research/` Python.

## P2 — Frozen no-DB fixture for backtest-smoke

`scripts/smoke/backtest_smoke.py` verifies entrypoints only; KNOWN_ISSUES wants a
tiny frozen no-DB fixture before it counts as replay-execution coverage.

- Add a small frozen fixture (mirror `tests/fixtures/engine_consistency/`) that runs
  one short replay end-to-end with **no DB**, and assert a known result
  (equity/fill count). Keep it fast (seconds).
- Extend `backtest_smoke.py` to execute that fixture; keep the existing
  entrypoint checks.

## P3 — Frontend browser-level chart test (lowest priority, heaviest infra)

KNOWN_ISSUES: progressive multi-symbol chart loading is only covered by
syntax/static + API artifact tests.

- Add a browser-level interaction test for progressive per-symbol chart loading and
  the `runId`-guarded in-flight fetch behavior.
- If a browser-test harness isn't already set up, **stop and report** the infra
  cost rather than adding a heavy new dependency unprompted — this one may be better
  scoped as its own task.

## PERMITTED FILES

- `Makefile`, `.github/workflows/ci.yml`
- `scripts/smoke/backtest_smoke.py`
- `tests/fixtures/**` (new frozen backtest fixture), `tests/**` smoke/frontend tests
- `docs/KNOWN_ISSUES.md` (flip resolved items), `docs/RUNBOOK.md` (if commands change)
- `tasks/2026-06-30-governance-harness-gaps-*.md` (handoffs)

## FORBIDDEN

- `src/okx_quant/strategies/`, `signals/`, `risk/`, `portfolio/`, `execution/`
- `config/risk.yaml`, `config/strategies.yaml`
- `research/crypto-alpha-lab/**` source/logic (invocation/CI wiring only)
- existing `results/**` artifacts
- `docs/AI_HANDOFF.md` history migration (separate Claude single-editor task)

## ACCEPTANCE CRITERIA (binary)

- [ ] `make lab-test` (or equivalent) runs the crypto-alpha-lab suite green, isolated
      from `tests/unit` (no `ImportError: crypto_alpha_lab`).
- [ ] `make verify` and `ci.yml` both execute the parent suite **and** the lab suite
      as separate steps; neither silently skips the lab.
- [ ] `make backtest-smoke` executes a frozen no-DB fixture replay end-to-end and
      asserts a known result, beyond entrypoint validation.
- [ ] P3 done, or explicitly deferred with the infra-cost reason recorded.
- [ ] Resolved KNOWN_ISSUES items updated; `make docs-check` stays 0 warnings.
- [ ] No trading-core, config-gate, research-logic, or result-artifact change.
