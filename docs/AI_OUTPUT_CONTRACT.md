---
status: current
type: contract
owner: human
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# AI Output Contract

This contract governs how Claude and Codex produce documentation so a human
reviewer can audit AI-generated work **without reading every `.md` file**. It sits
on top of `AGENTS.md`, `CLAUDE.md`, and `docs/ai_collaboration.md`; where it adds
a rule, that rule is binding for both agents.

The mechanism is the **Human Review Overview** (`docs/human_overviews/`): a
human-facing entry point that summarizes a batch of AI-generated planning /
governance docs. The overview never replaces source docs — see §4.

## 1. When a Human Review Overview is REQUIRED

Create or update an overview whenever an AI change does any of:

- Adds or modifies **2 or more** spec / plan / governance / harness `.md` files.
- Adds a strategy research pipeline (or a new stage of one).
- Adds or modifies a validation gate.
- Adds or modifies a deployment / demo / shadow / live gate.
- Adds or modifies a risk / execution / fill model.
- Adds or modifies an experiment registry, hypothesis ledger, or invariants doc.
- Produces any planning document that needs a human decision.
- Produces any change that would otherwise force the user to hunt for the point
  across multiple `.md` files.

## 2. When an overview is NOT required

- A single typo fix.
- A single small README edit.
- Adding a few words to one test file.
- A low-risk doc patch that changes no decision, no behavior, and no process.

If in doubt and the change touches gates, risk, execution, data provenance, or
the overfit gate (DSR / PSR / CPCV / `n_trials`), write the overview.

## 3. Claude / Codex responsibilities

- **Claude owns** the human-readable review narrative, research framing, risk
  review, and strategy critique.
- **Codex owns** implementation evidence, tests, code changes, and validation
  commands.
- If Claude produces a spec / plan, **Claude writes the overview**.
- If Codex modifies multiple planning / governance docs, **Codex updates the
  overview**.
- If Codex's implementation result diverges from the overview's assumptions,
  Codex must **flag the drift** and request that the overview be updated — it
  must not silently let the overview go stale.

## 4. Overview vs source docs — priority

- **Source docs are the source of truth.**
- The overview is a human entry point only.
- Conflicts between overview and source docs **must be called out** in the
  overview, not hidden.
- The overview **must not silently reinterpret** source docs. If a summary would
  change a source doc's meaning, fix the wording or cite the source doc verbatim.

## 5. Authoring and validation

- Template: `docs/templates/HUMAN_REVIEW_OVERVIEW_TEMPLATE.md`.
- Index: every overview gets a row in `docs/review_index.md`.
- Validate with `python scripts/docs/check_human_overview.py` (frontmatter fields,
  `risk_level` enum, `source_docs` / `human_must_read` path existence, and the ten
  required sections).
- **Future CI note (not wired this change):** `check_human_overview.py` can be
  added to the doc-check workflow alongside `scripts/docs/check_doc_impact.py`. It
  was intentionally left out of CI here to avoid restructuring the existing checks.
