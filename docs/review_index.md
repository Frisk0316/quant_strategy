---
status: current
type: index
owner: human
created: 2026-06-25
last_reviewed: 2026-06-25
expires: none
superseded_by: null
---

# Human Review Index

This index lists Human Review Overviews for AI-generated planning, strategy,
governance, and harness changes. Start here when an AI says it produced "a batch
of docs" — the overview tells you what changed, what needs your decision, which
source docs are must-read, and what is still unverified.

The overview is a human entry point, **not** the source of truth. If an overview
conflicts with its source docs, the source docs win. See
[`human_overviews/README.md`](human_overviews/README.md) and
[`AI_OUTPUT_CONTRACT.md`](AI_OUTPUT_CONTRACT.md).

| Date | Topic | Overview | Status | Risk | Decision required | Human decision |
|---|---|---|---|---|---|---|
| 2026-06-25 | Strategy Research Pipeline Stage 1 | [docs/human_overviews/2026-06-25-strategy-research-pipeline-overview.md](human_overviews/2026-06-25-strategy-research-pipeline-overview.md) | draft | medium | yes | pending |
| 2026-06-25 | In-Dashboard User Manual (使用手冊) | [docs/human_overviews/2026-06-25-user-manual-overview.md](human_overviews/2026-06-25-user-manual-overview.md) | draft | low | no | approved |

## Rules

- Every new overview adds a row here.
- `Human decision` starts as `pending`; update to `approved` / `rejected` /
  `superseded` when the user decides.
- When an overview is replaced, set its frontmatter `superseded_by` and mark this
  row `superseded`.
