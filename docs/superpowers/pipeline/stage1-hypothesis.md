---
status: current
type: template
owner: codex
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Stage 1 Template: Hypothesis From Backlog

Role: research, Claude. No code.

## Input

- One backlog candidate id, such as `S7`.
- The matching `research/strategy_synthesis.md` section.

## Output

Create or update one `HYPOTHESIS_LEDGER.md` entry with:

- `family_id`: stable economic mechanism slug.
- Testable signal, entry, exit, sizing, execution, risk, and universe spec.
- Planned grid and combo count.
- Data needs: series, venue, window, and minimum coverage.
- Validation path: walk-forward settings and CPCV N/k/embargo/purge.
- Pre-registered family `n_trials` budget.

## Pass Criterion

All fields are present and the mechanism is economically distinct enough to be
its own family.

If it is the same mechanism as an existing family, mark it as a retry of that
family. It then consumes that family's `K` budget and its trials accumulate into
that family.

## Do Not

- Do not invent strategy assumptions from chat memory.
- Use only `research/strategy_synthesis.md`, the Stage 1 spec, or explicit user
  instruction as source.

## Autonomous Mode Appendix

Machine idea generators may only create candidate sidecars and ledger drafts.
They must not append to `docs/HYPOTHESIS_LEDGER.md` or advance a candidate
without human review.

Allowed sources:

- B-half taxonomy generation: mechanism taxonomy, experiment registry family
  status/trial metadata, and data-availability labels.
- A-half literature generation: public paper metadata, validated
  `PaperScoring`, validated `AlphaCandidate`, and the parent Stage 1 adapter.

Data firewall:

- Do not include market return series, out-of-sample price data, fold
  boundaries, validation results, or live/shadow/demo state in idea-scoring
  prompts.
- Literature candidates are source `A_literature`; taxonomy candidates are
  source `B_taxonomy`. Mixed batches still write only `idea_batch.json` and
  `hypothesis_ledger_draft.md` until reviewed.
- Family-minting and checkpoint sidecars are advisory research controls, not
  deployment or promotion gates.
